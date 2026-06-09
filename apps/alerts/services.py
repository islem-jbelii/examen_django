"""
alerts/services.py — Alert engine with idempotent checks.
"""
from datetime import date, timedelta

from apps.alerts.models import Alert, AlertType, AlertSeverity


def trigger_alert(youth, alert_type, message, severity=AlertSeverity.MEDIUM, triggered_by="system"):
    """Create an alert for a youth profile."""
    return Alert.objects.create(
        youth=youth,
        alert_type=alert_type,
        severity=severity,
        message=message,
        triggered_by=triggered_by,
    )


def _has_unread_alert(youth, alert_type):
    """Return True if an unread alert of this type already exists for this youth."""
    return Alert.objects.filter(
        youth=youth, alert_type=alert_type, is_read=False
    ).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — check_missed_sessions_alert
# ─────────────────────────────────────────────────────────────────────────────

def check_missed_sessions_alert(youth_id):
    """
    Check the last 5 sessions for this youth.
    If 2 or more consecutive sessions are MISSED → create HIGH alert.
    Idempotent: skip if unread alert already exists.
    """
    from apps.youth.models import YouthProfile
    try:
        youth = YouthProfile.objects.get(pk=youth_id)
    except YouthProfile.DoesNotExist:
        return

    if _has_unread_alert(youth, AlertType.MISSED_SESSIONS):
        return  # Already alerted

    last_5 = list(
        youth.mentorship_sessions.order_by("-session_date").values_list("status", flat=True)[:5]
    )

    # Count consecutive MISSED from the most recent
    consecutive_missed = 0
    for status in last_5:
        if status == "MISSED":
            consecutive_missed += 1
        else:
            break

    if consecutive_missed >= 2:
        trigger_alert(
            youth=youth,
            alert_type=AlertType.MISSED_SESSIONS,
            severity=AlertSeverity.HIGH,
            message=(
                f"2 séances de mentorat consécutives manquées pour "
                f"{youth.user.get_full_name() or youth.user.username}."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# check_plan_expiring_alert — idempotent, run via management command
# ─────────────────────────────────────────────────────────────────────────────

def check_plan_expiring_alert():
    """
    Find all ACTIVE ActionPlans expiring within 7 days.
    Create PLAN_EXPIRING alert for each — idempotent.
    """
    from apps.guidance.models import ActionPlan, ActionPlanStatus
    threshold = date.today() + timedelta(days=7)
    expiring = ActionPlan.objects.filter(
        status=ActionPlanStatus.ACTIVE,
        end_date__lte=threshold,
        end_date__gte=date.today(),
    ).select_related("youth")

    for plan in expiring:
        youth = plan.youth
        if _has_unread_alert(youth, AlertType.PLAN_EXPIRING):
            continue
        trigger_alert(
            youth=youth,
            alert_type=AlertType.PLAN_EXPIRING,
            severity=AlertSeverity.MEDIUM,
            message=(
                f"Le plan d'action de "
                f"{youth.user.get_full_name() or youth.user.username} "
                f"expire le {plan.end_date.strftime('%d/%m/%Y')}."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# check_inactivity_alert — run via management command
# ─────────────────────────────────────────────────────────────────────────────

def check_inactivity_alert():
    """
    Find youth with no session or audit activity in the last 30 days
    and status not in [COMPLETED, INACTIVE].
    Create INACTIVITY alert — idempotent.
    """
    from apps.youth.models import YouthProfile, YouthStatus
    cutoff = date.today() - timedelta(days=30)

    active_youth = YouthProfile.objects.exclude(
        status__in=[YouthStatus.COMPLETED, YouthStatus.INACTIVE]
    ).prefetch_related("mentorship_sessions")

    for youth in active_youth:
        if _has_unread_alert(youth, AlertType.INACTIVITY):
            continue

        # Check last session
        last_session = youth.mentorship_sessions.order_by("-session_date").first()
        has_recent_session = last_session and last_session.session_date >= cutoff

        # Check last audit activity
        from apps.accounts.models import AuditLog
        has_recent_audit = AuditLog.objects.filter(
            target_model="YouthProfile",
            target_id=str(youth.pk),
            timestamp__date__gte=cutoff,
        ).exists()

        if not has_recent_session and not has_recent_audit:
            trigger_alert(
                youth=youth,
                alert_type=AlertType.INACTIVITY,
                severity=AlertSeverity.LOW,
                message=(
                    f"{youth.user.get_full_name() or youth.user.username} "
                    f"n'a eu aucune activité depuis plus de 30 jours."
                ),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy helpers (kept for backward compat)
# ─────────────────────────────────────────────────────────────────────────────

def check_missed_sessions(youth):
    check_missed_sessions_alert(youth.pk)


def check_plan_expiring(youth):
    if _has_unread_alert(youth, AlertType.PLAN_EXPIRING):
        return
    soon = date.today() + timedelta(days=14)
    expiring_plans = youth.action_plans.filter(status="ACTIVE", end_date__lte=soon)
    for plan in expiring_plans:
        trigger_alert(
            youth=youth,
            alert_type=AlertType.PLAN_EXPIRING,
            severity=AlertSeverity.MEDIUM,
            message=f"Le plan d'action de {youth} expire le {plan.end_date}.",
        )


def check_assessment_required(youth):
    if _has_unread_alert(youth, AlertType.ASSESSMENT_REQUIRED):
        return
    has_assessment = youth.assessments.filter(status="COMPLETED").exists()
    if not has_assessment:
        trigger_alert(
            youth=youth,
            alert_type=AlertType.ASSESSMENT_REQUIRED,
            severity=AlertSeverity.MEDIUM,
            message=f"{youth} n'a pas encore complété son évaluation d'intérêts.",
        )


def check_inactivity(youth):
    from apps.youth.models import YouthStatus
    if _has_unread_alert(youth, AlertType.INACTIVITY):
        return
    if youth.status == YouthStatus.INACTIVE:
        trigger_alert(
            youth=youth,
            alert_type=AlertType.INACTIVITY,
            severity=AlertSeverity.HIGH,
            message=f"{youth} est marqué comme inactif.",
        )


def run_all_checks(youth):
    check_missed_sessions(youth)
    check_plan_expiring(youth)
    check_assessment_required(youth)
    check_inactivity(youth)
