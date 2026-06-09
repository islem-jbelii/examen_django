"""
Integration tests — Scenario 2: Mentorship follow-up and guidance coordination.
"""
import pytest
from datetime import date, timedelta
from django.test import Client


@pytest.mark.django_db
class TestScenario2:

    def _client_as(self, user):
        c = Client()
        c.force_login(user)
        return c

    # ─────────────────────────────────────────────────────────────────────
    # Full mentorship workflow
    # ─────────────────────────────────────────────────────────────────────

    def test_full_mentorship_workflow(
        self, counselor_user, mentor_user_1, youth_profile_1, sample_sectors
    ):
        from apps.youth.models import YouthProfile, YouthStatus
        from apps.mentorship.models import MentorshipSession, SessionStatus, SessionType
        from apps.alerts.models import Alert, AlertType

        # 1. Counselor assigns mentor
        c_counselor = self._client_as(counselor_user)
        mp = mentor_user_1.mentor_profile
        resp = c_counselor.post(
            f"/mentorship/assign/{youth_profile_1.pk}/",
            {"mentor_id": str(mp.pk)},
            follow=True,
        )
        assert resp.status_code == 200
        youth_profile_1.refresh_from_db()
        assert youth_profile_1.assigned_mentor == mentor_user_1

        # 2. Mentor creates session
        c_mentor = self._client_as(mentor_user_1)
        session_date = date.today() - timedelta(days=3)
        resp = c_mentor.post("/mentorship/sessions/create/", {
            "youth": youth_profile_1.pk,
            "session_date": session_date.strftime("%Y-%m-%d"),
            "session_type": SessionType.DISCOVERY,
            "notes": "Première séance.",
            "recommendations": "",
        }, follow=True)
        assert resp.status_code == 200

        session = MentorshipSession.objects.filter(youth=youth_profile_1).first()
        assert session is not None

        # 3. Mark session as COMPLETED with recommendation
        score_before = youth_profile_1.readiness_score or 0
        resp = c_mentor.post(f"/mentorship/sessions/{session.pk}/edit/", {
            "status": SessionStatus.COMPLETED,
            "notes": "Séance productive.",
            "recommendations": "Continuer la formation Python.",
        }, follow=True)
        assert resp.status_code == 200

        session.refresh_from_db()
        assert session.status == SessionStatus.COMPLETED
        assert session.counselor_notified is True

        # 4. Readiness score updated
        youth_profile_1.refresh_from_db()
        assert (youth_profile_1.readiness_score or 0) >= score_before

        # 5. Alert created for counselor
        assert Alert.objects.filter(
            youth=youth_profile_1,
            alert_type=AlertType.MENTOR_RECOMMENDATION,
        ).exists()

    # ─────────────────────────────────────────────────────────────────────
    # FAILURE 2A — Mentor cannot access unassigned youth
    # ─────────────────────────────────────────────────────────────────────

    def test_mentor_cannot_access_unassigned_youth(self, mentor_user_1, youth_profile_1):
        from apps.accounts.models import AuditLog

        # youth_profile_1 has no assigned mentor
        assert youth_profile_1.assigned_mentor is None

        c = self._client_as(mentor_user_1)
        audit_before = AuditLog.objects.filter(action="ACCESS_DENIED").count()

        resp = c.get(
            f"/mentorship/sessions/create/?youth_id={youth_profile_1.pk}",
            follow=True,
        )
        assert resp.status_code == 403
        assert AuditLog.objects.filter(action="ACCESS_DENIED").count() > audit_before

    # ─────────────────────────────────────────────────────────────────────
    # FAILURE 2B — Session blocked for inactive youth
    # ─────────────────────────────────────────────────────────────────────

    def test_session_blocked_for_inactive_youth(self, mentor_user_1, inactive_youth):
        from apps.mentorship.models import MentorshipSession, SessionType

        inactive_youth.assigned_mentor = mentor_user_1
        inactive_youth.save()

        c = self._client_as(mentor_user_1)
        count_before = MentorshipSession.objects.count()

        resp = c.post("/mentorship/sessions/create/", {
            "youth": inactive_youth.pk,
            "session_date": date.today().strftime("%Y-%m-%d"),
            "session_type": SessionType.DISCOVERY,
            "notes": "",
            "recommendations": "",
        }, follow=True)
        assert resp.status_code == 200
        # No session created
        assert MentorshipSession.objects.count() == count_before

    # ─────────────────────────────────────────────────────────────────────
    # FAILURE 2C — Mentor capacity overflow blocked
    # ─────────────────────────────────────────────────────────────────────

    def test_mentor_capacity_overflow_blocked(
        self, counselor_user, mentor_at_full_capacity, youth_profile_1
    ):
        from apps.accounts.models import AuditLog

        c = self._client_as(counselor_user)
        mp = mentor_at_full_capacity.mentor_profile
        audit_before = AuditLog.objects.filter(action="VALIDATION_FAILED").count()

        resp = c.post(
            f"/mentorship/assign/{youth_profile_1.pk}/",
            {"mentor_id": str(mp.pk)},
            follow=True,
        )
        assert resp.status_code == 200

        # Youth still has no mentor
        youth_profile_1.refresh_from_db()
        assert youth_profile_1.assigned_mentor is None

        assert AuditLog.objects.filter(action="VALIDATION_FAILED").count() > audit_before

    # ─────────────────────────────────────────────────────────────────────
    # Two missed sessions trigger HIGH alert
    # ─────────────────────────────────────────────────────────────────────

    def test_two_missed_sessions_trigger_high_alert(self, youth_with_two_missed_sessions):
        from apps.alerts.models import Alert, AlertType, AlertSeverity
        from apps.alerts.services import check_missed_sessions_alert

        check_missed_sessions_alert(youth_with_two_missed_sessions.pk)

        alert = Alert.objects.filter(
            youth=youth_with_two_missed_sessions,
            alert_type=AlertType.MISSED_SESSIONS,
        ).first()
        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH

    # ─────────────────────────────────────────────────────────────────────
    # No duplicate alert for same youth
    # ─────────────────────────────────────────────────────────────────────

    def test_no_duplicate_alert_for_same_youth(self, youth_with_two_missed_sessions):
        from apps.alerts.models import Alert, AlertType
        from apps.alerts.services import check_missed_sessions_alert

        check_missed_sessions_alert(youth_with_two_missed_sessions.pk)
        check_missed_sessions_alert(youth_with_two_missed_sessions.pk)
        check_missed_sessions_alert(youth_with_two_missed_sessions.pk)

        count = Alert.objects.filter(
            youth=youth_with_two_missed_sessions,
            alert_type=AlertType.MISSED_SESSIONS,
            is_read=False,
        ).count()
        assert count == 1
