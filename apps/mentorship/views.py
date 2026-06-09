"""
mentorship/views.py — Scenario 2: Session management, mentor assignment.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect

from apps.accounts.models import AuditLog, UserRole
from apps.accounts.permissions import (
    counselor_required, mentor_required, counselor_or_admin_required,
)
from apps.accounts.utils import get_client_ip
from apps.mentorship.forms import MentorshipSessionForm, SessionStatusUpdateForm
from apps.mentorship.models import MentorProfile, MentorshipSession, SessionStatus
from apps.youth.models import YouthProfile, YouthStatus
from apps.youth.services import compute_readiness_score


def _audit(request, action, target_model, target_id,
           result=AuditLog.Result.SUCCESS, reason=""):
    AuditLog.objects.create(
        user=request.user,
        action=action,
        target_model=target_model,
        target_id=str(target_id),
        result=result,
        reason=reason,
        ip_address=get_client_ip(request),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. MentorshipSessionCreateView — MENTOR only
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@mentor_required
def session_create(request):
    """
    MENTOR only. Dropdown shows only assigned youth.
    FAILURE 2A: youth_id in URL not assigned → 403 + AuditLog.
    FAILURE 2B: youth INACTIVE → form error + AuditLog.
    """
    # Pre-select youth from query param (URL manipulation check)
    preselect_youth_id = request.GET.get("youth_id") or request.POST.get("youth")
    if preselect_youth_id:
        try:
            preselect_youth = YouthProfile.objects.get(pk=preselect_youth_id)
            if preselect_youth.assigned_mentor != request.user:
                _audit(
                    request, "ACCESS_DENIED", "YouthProfile", preselect_youth_id,
                    result=AuditLog.Result.FAILURE,
                    reason="Mentor not assigned",
                )
                raise PermissionDenied("Vous n'êtes pas assigné à ce jeune.")
        except YouthProfile.DoesNotExist:
            pass

    if request.method == "POST":
        form = MentorshipSessionForm(request.POST, mentor_user=request.user)
        if form.is_valid():
            youth = form.cleaned_data["youth"]

            # Double-check assignment (FAILURE 2A via POST manipulation)
            if youth.assigned_mentor != request.user:
                _audit(
                    request, "ACCESS_DENIED", "YouthProfile", youth.pk,
                    result=AuditLog.Result.FAILURE,
                    reason="Mentor not assigned",
                )
                raise PermissionDenied(
                    "Vous ne pouvez créer des séances que pour les jeunes qui vous sont assignés."
                )

            # FAILURE 2B: inactive youth
            if youth.status == YouthStatus.INACTIVE:
                _audit(
                    request, "CREATE_SESSION", "MentorshipSession", youth.pk,
                    result=AuditLog.Result.FAILURE,
                    reason="Youth is INACTIVE",
                )
                form.add_error(None, "Impossible de créer une séance pour un jeune inactif.")
            else:
                session = form.save(commit=False)
                session.mentor = request.user
                session.status = SessionStatus.SCHEDULED
                session.save()
                _audit(request, "CREATE_SESSION", "MentorshipSession", session.pk)
                messages.success(request, "Séance planifiée avec succès.")
                return redirect("mentorship:session-list")
    else:
        form = MentorshipSessionForm(mentor_user=request.user)

    return render(request, "mentorship/session_form.html", {
        "form": form,
        "form_title": "Planifier une séance",
        "submit_label": "Créer la séance",
    })


# ─────────────────────────────────────────────────────────────────────────────
# 2. MentorshipSessionListView
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def session_list(request):
    """
    MENTOR: own sessions.
    COUNSELOR: sessions for assigned youth, filterable.
    YOUTH: own sessions (read-only).
    ADMIN: all.
    """
    user = request.user
    if user.role == UserRole.MENTOR:
        qs = MentorshipSession.objects.filter(mentor=user)
    elif user.role == UserRole.COUNSELOR:
        qs = MentorshipSession.objects.filter(youth__assigned_counselor=user)
    elif user.role == UserRole.ADMIN:
        qs = MentorshipSession.objects.all()
    elif user.role == UserRole.YOUTH:
        try:
            qs = MentorshipSession.objects.filter(youth=user.youth_profile)
        except Exception:
            qs = MentorshipSession.objects.none()
    else:
        raise PermissionDenied

    qs = qs.select_related("youth__user", "mentor").order_by("-session_date")

    # Filters (counselor/admin)
    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("session_type", "")
    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(session_type=type_filter)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    from apps.mentorship.models import SessionType
    return render(request, "mentorship/session_list.html", {
        "page_obj": page,
        "sessions": page.object_list,
        "status_choices": SessionStatus.choices,
        "type_choices": SessionType.choices,
        "current_status": status_filter,
        "current_type": type_filter,
        "is_youth": user.role == UserRole.YOUTH,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 3. MentorshipSessionUpdateView
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def session_update(request, pk):
    """
    MENTOR: own sessions only.
    COUNSELOR: sessions for assigned youth.
    On COMPLETED: recompute readiness_score.
    On MISSED: trigger alert check.
    On COMPLETED with recommendations: set counselor_notified, create alert.
    """
    session = get_object_or_404(MentorshipSession, pk=pk)
    user = request.user

    if user.role == UserRole.MENTOR:
        if session.mentor != user:
            _audit(request, "ACCESS_DENIED", "MentorshipSession", pk,
                   result=AuditLog.Result.FAILURE, reason="Mentor not owner")
            raise PermissionDenied("Cette séance ne vous appartient pas.")
    elif user.role == UserRole.COUNSELOR:
        if session.youth.assigned_counselor != user:
            _audit(request, "ACCESS_DENIED", "MentorshipSession", pk,
                   result=AuditLog.Result.FAILURE, reason="Counselor not assigned")
            raise PermissionDenied("Ce jeune ne vous est pas assigné.")
    elif user.role not in (UserRole.ADMIN,):
        raise PermissionDenied

    old_status = session.status

    if request.method == "POST":
        form = SessionStatusUpdateForm(request.POST, instance=session)
        if form.is_valid():
            updated = form.save()
            new_status = updated.status

            # On COMPLETED: recompute score
            if new_status == SessionStatus.COMPLETED and old_status != SessionStatus.COMPLETED:
                score, _ = compute_readiness_score(updated.youth)
                YouthProfile.objects.filter(pk=updated.youth.pk).update(readiness_score=score)

                # If recommendations present: notify counselor
                if updated.recommendations.strip():
                    updated.counselor_notified = True
                    updated.save(update_fields=["counselor_notified"])
                    from apps.alerts.models import AlertType, AlertSeverity
                    from apps.alerts.services import trigger_alert
                    trigger_alert(
                        youth=updated.youth,
                        alert_type=AlertType.MENTOR_RECOMMENDATION,
                        severity=AlertSeverity.MEDIUM,
                        message=(
                            f"Recommandation du mentor {user.get_full_name() or user.username} "
                            f"pour {updated.youth.user.get_full_name() or updated.youth.user.username} : "
                            f"{updated.recommendations[:200]}"
                        ),
                        triggered_by=user.email or user.username,
                    )

            # On MISSED: trigger alert check
            if new_status == SessionStatus.MISSED and old_status != SessionStatus.MISSED:
                from apps.alerts.services import check_missed_sessions_alert
                check_missed_sessions_alert(updated.youth.pk)

            _audit(request, "UPDATE_SESSION", "MentorshipSession", pk,
                   reason=f"{old_status} → {new_status}")
            messages.success(request, "Séance mise à jour.")
            return redirect("mentorship:session-list")
    else:
        form = SessionStatusUpdateForm(instance=session)

    return render(request, "mentorship/session_form.html", {
        "form": form,
        "session": session,
        "form_title": f"Modifier la séance — {session.get_session_type_display()}",
        "submit_label": "Enregistrer",
        "is_update": True,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. MentorAssignView — COUNSELOR only, FAILURE 2C
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_required
def mentor_assign(request, youth_pk):
    """
    COUNSELOR assigns a mentor to a youth.
    FAILURE 2C: mentor at max capacity → error.
    """
    profile = get_object_or_404(YouthProfile, pk=youth_pk)

    if profile.assigned_counselor != request.user:
        _audit(request, "ACCESS_DENIED", "YouthProfile", youth_pk,
               result=AuditLog.Result.FAILURE, reason="Counselor not assigned")
        raise PermissionDenied("Ce jeune ne vous est pas assigné.")

    # Available mentors: verified, not at capacity
    mentors = MentorProfile.objects.select_related("user", "sector").filter(is_verified=True)

    assign_error = None

    if request.method == "POST":
        mentor_id = request.POST.get("mentor_id")
        if not mentor_id:
            assign_error = "Veuillez sélectionner un mentor."
        else:
            try:
                mentor_profile = MentorProfile.objects.get(pk=mentor_id)
            except MentorProfile.DoesNotExist:
                assign_error = "Mentor introuvable."
            else:
                # FAILURE 2C: capacity check
                if mentor_profile.current_youth_count >= mentor_profile.max_youth_capacity:
                    assign_error = (
                        f"Ce mentor a atteint sa capacité maximale "
                        f"({mentor_profile.current_youth_count}/{mentor_profile.max_youth_capacity})."
                    )
                    _audit(
                        request, "VALIDATION_FAILED", "MentorProfile", mentor_id,
                        result=AuditLog.Result.FAILURE,
                        reason=assign_error,
                    )
                else:
                    # Decrement old mentor count if any
                    if profile.assigned_mentor:
                        try:
                            old_mp = profile.assigned_mentor.mentor_profile
                            if old_mp.current_youth_count > 0:
                                old_mp.current_youth_count -= 1
                                old_mp.save(update_fields=["current_youth_count"])
                        except Exception:
                            pass

                    # Assign
                    profile.assigned_mentor = mentor_profile.user
                    profile.save(update_fields=["assigned_mentor"])
                    mentor_profile.current_youth_count += 1
                    mentor_profile.save(update_fields=["current_youth_count"])

                    _audit(request, "ASSIGN_MENTOR", "YouthProfile", youth_pk,
                           reason=f"Mentor: {mentor_profile.user.username}")
                    messages.success(
                        request,
                        f"Mentor {mentor_profile.user.get_full_name() or mentor_profile.user.username} "
                        f"assigné à {profile}."
                    )
                    return redirect("youth:profile-detail", pk=youth_pk)

    return render(request, "mentorship/mentor_assign.html", {
        "profile": profile,
        "mentors": mentors,
        "assign_error": assign_error,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 5. Mentor list (for assignment search)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_or_admin_required
def mentor_list(request):
    sector_filter = request.GET.get("sector", "")
    mentors = MentorProfile.objects.select_related("user", "sector").filter(is_verified=True)
    if sector_filter:
        mentors = mentors.filter(sector_id=sector_filter)

    from apps.careers.models import CareerSector
    sectors = CareerSector.objects.all()
    return render(request, "mentorship/mentor_list.html", {
        "mentors": mentors,
        "sectors": sectors,
        "current_sector": sector_filter,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 6. Session detail
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def session_detail(request, pk):
    session = get_object_or_404(MentorshipSession, pk=pk)
    user = request.user
    if user.role == UserRole.MENTOR and session.mentor != user:
        raise PermissionDenied
    elif user.role == UserRole.COUNSELOR and session.youth.assigned_counselor != user:
        raise PermissionDenied
    elif user.role == UserRole.YOUTH:
        try:
            if session.youth != user.youth_profile:
                raise PermissionDenied
        except Exception:
            raise PermissionDenied
    return render(request, "mentorship/session_detail.html", {"session": session})
