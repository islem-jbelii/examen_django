"""
youth/views.py — Scenario 1: Youth intake, assessment, bulk import.
"""
import csv
import io
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

from apps.accounts.models import AuditLog, UserRole
from apps.accounts.permissions import (
    counselor_required, counselor_or_admin_required, youth_required,
)
from apps.accounts.utils import get_client_ip
from apps.careers.models import CareerSector
from apps.youth.assessment_questions import QUESTIONS, get_recommended_sectors
from apps.youth.forms import YouthProfileForm, YouthProfileUpdateForm, BulkImportForm
from apps.youth.models import (
    YouthProfile, YouthStatus, EducationLevel, Governorate,
    InterestAssessment, AssessmentStatus,
)
from apps.youth.services import compute_readiness_score


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _audit(request, action, target_model, target_id, result=AuditLog.Result.SUCCESS, reason=""):
    AuditLog.objects.create(
        user=request.user,
        action=action,
        target_model=target_model,
        target_id=str(target_id),
        result=result,
        reason=reason,
        ip_address=get_client_ip(request),
    )


def _score_color(score):
    if score is None:
        return "secondary"
    if score >= 70:
        return "success"
    if score >= 40:
        return "warning"
    return "danger"


# ─────────────────────────────────────────────────────────────────────────────
# 1. YouthProfileCreateView
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_required
def youth_create(request):
    """COUNSELOR only — create a new youth profile."""
    if request.method == "POST":
        form = YouthProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.assigned_counselor = request.user
            profile.status = YouthStatus.REGISTERED
            profile.save()
            form.save_m2m()
            score, _ = compute_readiness_score(profile)
            YouthProfile.objects.filter(pk=profile.pk).update(readiness_score=score)
            _audit(request, "CREATE_PROFILE", "YouthProfile", profile.pk)
            messages.success(request, f"Profil de {profile} créé avec succès.")
            return redirect("youth:profile-detail", pk=profile.pk)
        else:
            _audit(
                request, "CREATE_PROFILE", "YouthProfile", "",
                result=AuditLog.Result.FAILURE,
                reason=str(form.errors),
            )
    else:
        form = YouthProfileForm()

    return render(request, "youth/form.html", {
        "form": form,
        "form_title": "Nouveau profil jeune",
        "submit_label": "Créer le profil",
    })


# ─────────────────────────────────────────────────────────────────────────────
# 2. YouthListView
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_or_admin_required
def youth_list(request):
    """
    COUNSELOR: assigned youth only.
    ADMIN: all youth.
    Filters: status, governorate, sector, education_level.
    Sorted by readiness_score desc by default.
    """
    user = request.user
    if user.role == UserRole.COUNSELOR:
        qs = YouthProfile.objects.filter(assigned_counselor=user)
    else:
        qs = YouthProfile.objects.all()

    qs = qs.select_related("user", "assigned_mentor").prefetch_related("interests")

    # Filters
    status_filter = request.GET.get("status", "")
    gov_filter = request.GET.get("governorate", "")
    sector_filter = request.GET.get("sector", "")
    edu_filter = request.GET.get("education_level", "")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if gov_filter:
        qs = qs.filter(governorate=gov_filter)
    if sector_filter:
        qs = qs.filter(interests__id=sector_filter)
    if edu_filter:
        qs = qs.filter(education_level=edu_filter)

    # Sort
    sort = request.GET.get("sort", "-readiness_score")
    allowed_sorts = ["readiness_score", "-readiness_score", "user__last_name", "-created_at"]
    if sort not in allowed_sorts:
        sort = "-readiness_score"
    qs = qs.order_by(sort)

    sectors = CareerSector.objects.all()

    # Pagination
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "youth/list.html", {
        "profiles": page_obj,
        "page_obj": page_obj,
        "sectors": sectors,
        "status_choices": YouthStatus.choices,
        "governorate_choices": Governorate.choices,
        "education_choices": EducationLevel.choices,
        "current_filters": {
            "status": status_filter,
            "governorate": gov_filter,
            "sector": sector_filter,
            "education_level": edu_filter,
            "sort": sort,
        },
        "score_color": _score_color,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 3. YouthDetailView
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def youth_profile_detail(request, pk):
    """
    Tabbed detail view: Profil | Évaluation | Plan d'action | Séances | Alertes | Journal
    Access control: YOUTH=own only, COUNSELOR=assigned only, MENTOR=assigned only, ADMIN=all.
    """
    profile = get_object_or_404(YouthProfile, pk=pk)
    user = request.user

    if user.role == UserRole.YOUTH:
        if not hasattr(user, "youth_profile") or user.youth_profile.pk != profile.pk:
            _audit(request, "ACCESS_DENIED", "YouthProfile", pk,
                   result=AuditLog.Result.FAILURE, reason="Youth accessing other profile")
            raise PermissionDenied("Vous ne pouvez consulter que votre propre profil.")
    elif user.role == UserRole.COUNSELOR:
        if profile.assigned_counselor != user:
            _audit(request, "ACCESS_DENIED", "YouthProfile", pk,
                   result=AuditLog.Result.FAILURE, reason="Counselor not assigned")
            raise PermissionDenied("Ce jeune ne vous est pas assigné.")
    elif user.role == UserRole.MENTOR:
        if profile.assigned_mentor != user:
            _audit(request, "ACCESS_DENIED", "YouthProfile", pk,
                   result=AuditLog.Result.FAILURE, reason="Mentor not assigned")
            raise PermissionDenied("Ce jeune ne vous est pas assigné.")

    _audit(request, "VIEW_PROFILE", "YouthProfile", pk)

    score, breakdown = compute_readiness_score(profile)
    assessments = profile.assessments.prefetch_related("recommended_sectors").order_by("-assessment_date")
    plans = profile.action_plans.select_related("target_sector", "target_career", "created_by").order_by("-created_at")
    sessions = profile.mentorship_sessions.select_related("mentor").order_by("-session_date")
    alerts = profile.alerts.order_by("-created_at")
    audit_logs = AuditLog.objects.filter(
        target_model="YouthProfile", target_id=str(pk)
    ).select_related("user").order_by("-timestamp")[:50]

    active_tab = request.GET.get("tab", "profile")

    return render(request, "youth/detail.html", {
        "profile": profile,
        "score": score,
        "score_breakdown": breakdown,
        "score_color": _score_color(score),
        "assessments": assessments,
        "plans": plans,
        "sessions": sessions,
        "alerts": alerts,
        "audit_logs": audit_logs,
        "active_tab": active_tab,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. YouthUpdateView with status transitions
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def youth_update(request, pk):
    """
    COUNSELOR only — edit profile + status transition buttons.
    MENTOR/YOUTH → 403 + AuditLog.
    """
    profile = get_object_or_404(YouthProfile, pk=pk)
    user = request.user

    # FAILURE 1B: unauthorized role
    if user.role in (UserRole.MENTOR, UserRole.YOUTH):
        _audit(request, "ACCESS_DENIED", "YouthProfile", pk,
               result=AuditLog.Result.FAILURE,
               reason=f"Role {user.role} attempted YouthUpdateView")
        raise PermissionDenied("Vous n'avez pas la permission de modifier ce profil.")

    if user.role == UserRole.COUNSELOR and profile.assigned_counselor != user:
        _audit(request, "ACCESS_DENIED", "YouthProfile", pk,
               result=AuditLog.Result.FAILURE, reason="Counselor not assigned")
        raise PermissionDenied("Ce jeune ne vous est pas assigné.")

    transition_error = None

    # ── Handle status transition POST ──
    if request.method == "POST" and "transition" in request.POST:
        transition = request.POST["transition"]
        current = profile.status

        if transition == "to_assessed":
            has_assessment = profile.assessments.filter(status=AssessmentStatus.COMPLETED).exists()
            if not has_assessment:
                transition_error = "L'évaluation des intérêts doit être complétée avant de passer au statut Évalué."
                _audit(request, "VALIDATION_FAILED", "YouthProfile", pk,
                       result=AuditLog.Result.FAILURE, reason=transition_error)
            else:
                profile.status = YouthStatus.ASSESSED
                profile.save()
                _audit(request, "STATUS_TRANSITION", "YouthProfile", pk,
                       reason=f"{current} → ASSESSED")
                messages.success(request, "Statut mis à jour : Évalué.")
                return redirect("youth:profile-detail", pk=pk)

        elif transition == "to_plan_active":
            has_validated_plan = profile.action_plans.filter(status="VALIDATED").exists()
            if not has_validated_plan:
                transition_error = "Un plan d'action validé est requis avant d'activer le statut Plan actif."
                _audit(request, "VALIDATION_FAILED", "YouthProfile", pk,
                       result=AuditLog.Result.FAILURE, reason=transition_error)
            else:
                profile.status = YouthStatus.PLAN_ACTIVE
                profile.save()
                _audit(request, "STATUS_TRANSITION", "YouthProfile", pk,
                       reason=f"{current} → PLAN_ACTIVE")
                messages.success(request, "Statut mis à jour : Plan actif.")
                return redirect("youth:profile-detail", pk=pk)

        elif transition == "to_mentorship":
            if not profile.assigned_mentor:
                transition_error = "Aucun mentor assigné à ce jeune."
                _audit(request, "VALIDATION_FAILED", "YouthProfile", pk,
                       result=AuditLog.Result.FAILURE, reason=transition_error)
            else:
                profile.status = YouthStatus.IN_MENTORSHIP
                profile.save()
                _audit(request, "STATUS_TRANSITION", "YouthProfile", pk,
                       reason=f"{current} → IN_MENTORSHIP")
                messages.success(request, "Statut mis à jour : En mentorat.")
                return redirect("youth:profile-detail", pk=pk)

        elif transition == "to_completed":
            profile.status = YouthStatus.COMPLETED
            profile.save()
            _audit(request, "STATUS_TRANSITION", "YouthProfile", pk,
                   reason=f"{current} → COMPLETED")
            messages.success(request, "Parcours clôturé.")
            return redirect("youth:profile-detail", pk=pk)

        elif transition == "to_inactive":
            profile.status = YouthStatus.INACTIVE
            profile.save()
            _audit(request, "STATUS_TRANSITION", "YouthProfile", pk,
                   reason=f"{current} → INACTIVE")
            messages.warning(request, "Jeune marqué comme inactif.")
            return redirect("youth:profile-detail", pk=pk)

    # ── Handle profile form POST ──
    if request.method == "POST" and "transition" not in request.POST:
        form = YouthProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            score, _ = compute_readiness_score(profile)
            YouthProfile.objects.filter(pk=profile.pk).update(readiness_score=score)
            _audit(request, "UPDATE_PROFILE", "YouthProfile", pk)
            messages.success(request, "Profil mis à jour.")
            return redirect("youth:profile-detail", pk=pk)
        else:
            _audit(request, "UPDATE_PROFILE", "YouthProfile", pk,
                   result=AuditLog.Result.FAILURE, reason=str(form.errors))
    else:
        form = YouthProfileUpdateForm(instance=profile)

    # Determine which transition buttons to show
    transitions = _get_available_transitions(profile)

    return render(request, "youth/form.html", {
        "form": form,
        "profile": profile,
        "form_title": f"Modifier le profil — {profile}",
        "submit_label": "Enregistrer les modifications",
        "transitions": transitions,
        "transition_error": transition_error,
        "is_update": True,
    })


def _get_available_transitions(profile):
    """Return list of (transition_key, label, btn_class) for current status."""
    s = profile.status
    transitions = []
    if s == YouthStatus.REGISTERED:
        transitions.append(("to_assessed", "Lancer l'évaluation", "btn-primary"))
    if s == YouthStatus.ASSESSED:
        transitions.append(("to_plan_active", "Activer le plan d'action", "btn-success"))
    if s == YouthStatus.PLAN_ACTIVE:
        transitions.append(("to_mentorship", "Démarrer le mentorat", "btn-info"))
    if s == YouthStatus.IN_MENTORSHIP:
        transitions.append(("to_completed", "Clôturer le parcours", "btn-purple"))
    if s != YouthStatus.INACTIVE and s != YouthStatus.COMPLETED:
        transitions.append(("to_inactive", "Marquer inactif", "btn-danger"))
    return transitions


# ─────────────────────────────────────────────────────────────────────────────
# 5. InterestAssessmentView — multi-step form
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_required
def interest_assessment(request, pk):
    """
    COUNSELOR only — conduct a 10-question interest assessment for a youth.
    """
    profile = get_object_or_404(YouthProfile, pk=pk)

    if profile.assigned_counselor != request.user:
        _audit(request, "ACCESS_DENIED", "YouthProfile", pk,
               result=AuditLog.Result.FAILURE, reason="Counselor not assigned")
        raise PermissionDenied("Ce jeune ne vous est pas assigné.")

    if request.method == "POST":
        responses = {}
        errors = []
        for q in QUESTIONS:
            val = request.POST.get(q["id"])
            if not val:
                errors.append(f"Question {q['id']} sans réponse.")
            else:
                responses[q["id"]] = val

        if errors:
            messages.error(request, "Veuillez répondre à toutes les questions.")
            return render(request, "youth/assessment_form.html", {
                "profile": profile,
                "questions": QUESTIONS,
                "responses": responses,
            })

        # Compute recommended sectors
        recommended_names = get_recommended_sectors(responses)
        from apps.youth.assessment_questions import compute_sector_scores
        score_breakdown = compute_sector_scores(responses)

        # Save assessment
        assessment = InterestAssessment.objects.create(
            youth=profile,
            conducted_by=request.user,
            assessment_date=date.today(),
            responses=responses,
            score_breakdown=score_breakdown,
            status=AssessmentStatus.COMPLETED,
        )
        # Link recommended sectors
        recommended_sectors = CareerSector.objects.filter(name__in=recommended_names)
        assessment.recommended_sectors.set(recommended_sectors)

        # Update youth interests if not already set
        if not profile.interests.exists():
            profile.interests.set(recommended_sectors)

        # Update youth status to ASSESSED
        if profile.status == YouthStatus.REGISTERED:
            profile.status = YouthStatus.ASSESSED
            profile.save()

        _audit(request, "CONDUCT_ASSESSMENT", "InterestAssessment", assessment.pk)
        messages.success(request, "Évaluation complétée avec succès.")
        return redirect("youth:assessment-result", pk=pk, assessment_pk=assessment.pk)

    return render(request, "youth/assessment_form.html", {
        "profile": profile,
        "questions": QUESTIONS,
        "responses": {},
    })


@login_required
def assessment_result(request, pk, assessment_pk):
    """Show assessment results with recommended sectors."""
    profile = get_object_or_404(YouthProfile, pk=pk)
    assessment = get_object_or_404(InterestAssessment, pk=assessment_pk, youth=profile)
    user = request.user

    if user.role == UserRole.COUNSELOR and profile.assigned_counselor != user:
        raise PermissionDenied
    if user.role == UserRole.YOUTH:
        if not hasattr(user, "youth_profile") or user.youth_profile.pk != profile.pk:
            raise PermissionDenied

    return render(request, "youth/assessment_result.html", {
        "profile": profile,
        "assessment": assessment,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 6. YouthBulkImportView — FAILURE 1A
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {
    "first_name", "last_name", "date_of_birth",
    "gender", "governorate", "education_level", "interests",
}

VALID_GENDERS = {"M", "F"}
VALID_GOVERNORATES = {v for v, _ in Governorate.choices}
VALID_EDUCATION = {v for v, _ in EducationLevel.choices}


@login_required
@counselor_required
def youth_bulk_import(request):
    """
    COUNSELOR only — bulk import youth profiles from CSV.
    Validates each row; skips invalid rows with detailed error report.
    """
    form = BulkImportForm()

    if request.method == "POST":
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            decoded = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))

            # Check required columns
            if reader.fieldnames is None:
                messages.error(request, "Fichier CSV vide ou invalide.")
                return render(request, "youth/bulk_import.html", {"form": form})

            actual_cols = {c.strip().lower() for c in reader.fieldnames}
            missing = REQUIRED_COLUMNS - actual_cols
            if missing:
                messages.error(
                    request,
                    f"Colonnes manquantes : {', '.join(sorted(missing))}. "
                    "Le fichier entier a été rejeté."
                )
                return render(request, "youth/bulk_import.html", {"form": form})

            # Process rows
            imported = 0
            error_rows = []
            all_sectors = {s.name: s for s in CareerSector.objects.all()}

            for row_num, row in enumerate(reader, start=2):
                row = {k.strip().lower(): v.strip() for k, v in row.items()}
                row_errors = []

                # Validate date_of_birth
                dob = None
                try:
                    dob = date.fromisoformat(row.get("date_of_birth", ""))
                    today = date.today()
                    age = (
                        today.year - dob.year
                        - ((today.month, today.day) < (dob.month, dob.day))
                    )
                    if not (15 <= age <= 25):
                        row_errors.append(f"Âge invalide ({age} ans, doit être 15-25)")
                except ValueError:
                    row_errors.append(f"Format de date invalide : '{row.get('date_of_birth')}'")

                # Validate gender
                gender = row.get("gender", "").upper()
                if gender not in VALID_GENDERS:
                    row_errors.append(f"Genre invalide : '{row.get('gender')}' (attendu M ou F)")

                # Validate governorate
                governorate = row.get("governorate", "").upper()
                if governorate not in VALID_GOVERNORATES:
                    row_errors.append(f"Gouvernorat inconnu : '{row.get('governorate')}'")

                # Validate education_level
                education = row.get("education_level", "").upper()
                if education not in VALID_EDUCATION:
                    row_errors.append(f"Niveau d'éducation invalide : '{row.get('education_level')}'")

                # Validate interests
                interest_names = [n.strip() for n in row.get("interests", "").split(",") if n.strip()]
                valid_sectors = []
                for name in interest_names:
                    if name in all_sectors:
                        valid_sectors.append(all_sectors[name])
                    else:
                        row_errors.append(f"Secteur inconnu : '{name}'")

                if row_errors:
                    error_rows.append({
                        "row": row_num,
                        "data": f"{row.get('first_name', '')} {row.get('last_name', '')}",
                        "errors": "; ".join(row_errors),
                    })
                    AuditLog.objects.create(
                        user=request.user,
                        action="BULK_IMPORT_ROW_FAILED",
                        target_model="YouthProfile",
                        target_id=f"row_{row_num}",
                        result=AuditLog.Result.FAILURE,
                        reason=f"Row {row_num}: {'; '.join(row_errors)}",
                        ip_address=get_client_ip(request),
                    )
                    continue

                # Create user + profile
                from django.contrib.auth import get_user_model
                User = get_user_model()
                username_base = f"{row['first_name'].lower()}.{row['last_name'].lower()}"
                username = username_base
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{username_base}{counter}"
                    counter += 1

                user_obj = User.objects.create_user(
                    username=username,
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    role=UserRole.YOUTH,
                    password=f"tmp_{username}_change_me",
                )
                profile = YouthProfile.objects.create(
                    user=user_obj,
                    date_of_birth=dob,
                    gender=gender,
                    governorate=governorate,
                    education_level=education,
                    assigned_counselor=request.user,
                    status=YouthStatus.REGISTERED,
                )
                profile.interests.set(valid_sectors)
                imported += 1

            # Build error CSV for download
            error_csv = None
            if error_rows:
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=["row", "data", "errors"])
                writer.writeheader()
                writer.writerows(error_rows)
                error_csv = buf.getvalue()

            request.session["import_result"] = {
                "imported": imported,
                "error_count": len(error_rows),
                "error_csv": error_csv,
            }
            return redirect("youth:import-result")

    return render(request, "youth/bulk_import.html", {"form": form})


@login_required
@counselor_required
def import_result(request):
    """Show import result summary and offer error CSV download."""
    result = request.session.pop("import_result", None)
    if not result:
        return redirect("youth:bulk-import")

    if request.GET.get("download") == "errors" and result.get("error_csv"):
        response = HttpResponse(result["error_csv"], content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="import_errors.csv"'
        return response

    return render(request, "youth/import_result.html", {"result": result})


# ─────────────────────────────────────────────────────────────────────────────
# 7. My profile (YOUTH)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@youth_required
def my_profile(request):
    """Youth user views their own profile."""
    try:
        profile = request.user.youth_profile
    except YouthProfile.DoesNotExist:
        return render(request, "youth/no_profile.html")
    score, breakdown = compute_readiness_score(profile)
    return redirect("youth:profile-detail", pk=profile.pk)
