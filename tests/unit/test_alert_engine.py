"""
Unit tests for the alert engine services.
"""
import pytest
from datetime import date, timedelta


@pytest.mark.django_db
class TestAlertEngine:

    def test_alert_created_after_two_consecutive_missed_sessions(self, youth_with_two_missed_sessions):
        from apps.alerts.models import Alert, AlertType, AlertSeverity
        from apps.alerts.services import check_missed_sessions_alert

        check_missed_sessions_alert(youth_with_two_missed_sessions.pk)

        alert = Alert.objects.filter(
            youth=youth_with_two_missed_sessions,
            alert_type=AlertType.MISSED_SESSIONS,
        ).first()
        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH

    def test_no_duplicate_alert_created(self, youth_with_two_missed_sessions):
        from apps.alerts.models import Alert, AlertType
        from apps.alerts.services import check_missed_sessions_alert

        check_missed_sessions_alert(youth_with_two_missed_sessions.pk)
        check_missed_sessions_alert(youth_with_two_missed_sessions.pk)

        count = Alert.objects.filter(
            youth=youth_with_two_missed_sessions,
            alert_type=AlertType.MISSED_SESSIONS,
            is_read=False,
        ).count()
        assert count == 1

    def test_alert_not_created_for_one_missed_session(self, youth_profile_1, mentor_user_1):
        from apps.mentorship.models import MentorshipSession, SessionStatus, SessionType
        from apps.alerts.models import Alert, AlertType
        from apps.alerts.services import check_missed_sessions_alert

        youth_profile_1.assigned_mentor = mentor_user_1
        youth_profile_1.save()

        MentorshipSession.objects.create(
            youth=youth_profile_1, mentor=mentor_user_1,
            session_date=date.today() - timedelta(days=7),
            session_type=SessionType.DISCOVERY,
            status=SessionStatus.MISSED,
        )

        check_missed_sessions_alert(youth_profile_1.pk)

        assert not Alert.objects.filter(
            youth=youth_profile_1, alert_type=AlertType.MISSED_SESSIONS
        ).exists()

    def test_plan_expiring_alert_created_within_7_days(self, active_youth_with_plan):
        from apps.guidance.models import ActionPlan, ActionPlanStatus
        from apps.alerts.models import Alert, AlertType
        from apps.alerts.services import check_plan_expiring_alert

        # Set plan to expire in 3 days
        plan = active_youth_with_plan.action_plans.filter(status=ActionPlanStatus.ACTIVE).first()
        plan.end_date = date.today() + timedelta(days=3)
        plan.save()

        check_plan_expiring_alert()

        assert Alert.objects.filter(
            youth=active_youth_with_plan,
            alert_type=AlertType.PLAN_EXPIRING,
        ).exists()

    def test_inactivity_alert_created_after_30_days(self, youth_profile_1):
        from apps.alerts.models import Alert, AlertType
        from apps.alerts.services import check_inactivity_alert

        # No sessions, no recent audit — should trigger
        check_inactivity_alert()

        assert Alert.objects.filter(
            youth=youth_profile_1,
            alert_type=AlertType.INACTIVITY,
        ).exists()

    def test_mentor_recommendation_alert_on_completed_session(
        self, youth_profile_1, mentor_user_1, counselor_user
    ):
        from apps.mentorship.models import MentorshipSession, SessionStatus, SessionType
        from apps.alerts.models import Alert, AlertType
        from apps.alerts.services import trigger_alert

        youth_profile_1.assigned_mentor = mentor_user_1
        youth_profile_1.save()

        trigger_alert(
            youth=youth_profile_1,
            alert_type=AlertType.MENTOR_RECOMMENDATION,
            message="Recommandation test.",
            triggered_by=mentor_user_1.email,
        )

        assert Alert.objects.filter(
            youth=youth_profile_1,
            alert_type=AlertType.MENTOR_RECOMMENDATION,
        ).exists()
