"""
guidance/views.py — Scenario 2: ActionPlan create, validate, list, detail.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from apps.accounts.models import AuditLog, UserRole
from apps.accounts.permissions import counselor_required, counselor_or_admin_required
from apps.accounts.utils import get_client_ip
from apps.guidance.forms import ActionPlanForm
from apps.guidance.models import ActionPlan, ActionPlanStatus
from apps.youth.models import YouthProfile


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
# List
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def action_plan_list(request):
    user = request.user
    if user.role == UserRole.YOUTH:
        try:
            plans = ActionPlan.objects.filter(youth=user.youth_profile).select_related(
                "target_sector", "created_by"
            )
        except Exception:
            plans = ActionPlan.objects.none()
    elif user.role == UserRole.COUNSELOR:
        plans = ActionPlan.objects.filter(created_by=user).select_related(
            "youth__user", "target_sector"
        )
    elif user.role == UserRole.ADMIN:
        plans = ActionPlan.objects.select_related("youth__user", "target_sector", "created_by").all()
    else:
        raise PermissionDenied

    status_filter = request.GET.get("status", "")
    if status_filter:
        plans = plans.filter(status=status_filter)

    return render(request, "guidance/plan_list.html", {
        "plans": plans,
        "status_choices": ActionPlanStatus.choices,
        "current_status": status_filter,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Detail
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def action_plan_detail(request, pk):
    plan = get_object_or_404(ActionPlan, pk=pk)
    user = request.user
    if user.role == UserRole.YOUTH:
        if not hasattr(user, "youth_profile") or plan.youth != user.youth_profile:
            raise PermissionDenied
    elif user.role == UserRole.COUNSELOR:
        if plan.created_by != user:
            raise PermissionDenied
    elif user.role == UserRole.MENTOR:
        raise PermissionDenied
    return render(request, "guidance/plan_detail.html", {"plan": plan})


# ─────────────────────────────────────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_required
def action_plan_create(request):
    if request.method == "POST":
        form = ActionPlanForm(request.POST, counselor=request.user)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.created_by = request.user
            plan.status = ActionPlanStatus.DRAFT
            plan.save()
            _audit(request, "CREATE_PLAN", "ActionPlan", plan.pk)
            messages.success(request, "Plan d'action créé (brouillon).")
            return redirect("guidance:plan-detail", pk=plan.pk)
        else:
            _audit(request, "CREATE_PLAN", "ActionPlan", "",
                   result=AuditLog.Result.FAILURE, reason=str(form.errors))
    else:
        # Pre-select youth from query param
        youth_pk = request.GET.get("youth")
        initial = {}
        if youth_pk:
            initial["youth"] = youth_pk
        form = ActionPlanForm(counselor=request.user, initial=initial)

    return render(request, "guidance/plan_form.html", {
        "form": form,
        "form_title": "Nouveau plan d'action",
        "submit_label": "Créer le plan",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Validate — FAILURE 2D
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_required
def action_plan_validate(request, pk):
    """
    Set status=VALIDATED, record validated_by + validated_at.
    FAILURE 2D: youth has no completed assessment → inline error.
    Creates alerts for mentor and youth.
    """
    plan = get_object_or_404(ActionPlan, pk=pk)

    if plan.created_by != request.user:
        _audit(request, "ACCESS_DENIED", "ActionPlan", pk,
               result=AuditLog.Result.FAILURE, reason="Counselor not owner")
        raise PermissionDenied("Ce plan ne vous appartient pas.")

    if plan.status not in (ActionPlanStatus.DRAFT,):
        messages.warning(request, "Ce plan ne peut pas être validé dans son état actuel.")
        return redirect("guidance:plan-detail", pk=pk)

    # FAILURE 2D: assessment required
    youth = plan.youth
    has_assessment = youth.assessments.filter(status="COMPLETED").exists()
    if not has_assessment:
        error_msg = "L'évaluation des intérêts doit être complétée avant d'activer le plan."
        _audit(request, "VALIDATION_FAILED", "ActionPlan", pk,
               result=AuditLog.Result.FAILURE, reason=error_msg)
        messages.error(request, error_msg)
        return redirect("guidance:plan-detail", pk=pk)

    if request.method == "POST":
        plan.status = ActionPlanStatus.VALIDATED
        plan.validated_by = request.user
        plan.validated_at = timezone.now()
        plan.save()

        # Alert for mentor
        if youth.assigned_mentor:
            from apps.alerts.models import AlertType, AlertSeverity
            from apps.alerts.services import trigger_alert
            try:
                mentor_youth = YouthProfile.objects.get(assigned_mentor=youth.assigned_mentor,
                                                         pk=youth.pk)
                trigger_alert(
                    youth=youth,
                    alert_type=AlertType.MENTOR_RECOMMENDATION,
                    severity=AlertSeverity.LOW,
                    message=(
                        f"Nouveau plan d'action validé pour "
                        f"{youth.user.get_full_name() or youth.user.username}."
                    ),
                    triggered_by=request.user.email or request.user.username,
                )
            except Exception:
                pass

        _audit(request, "VALIDATE_PLAN", "ActionPlan", pk)
        messages.success(request, "Plan d'action validé.")
        return redirect("guidance:plan-detail", pk=pk)

    return render(request, "guidance/plan_validate_confirm.html", {"plan": plan})
