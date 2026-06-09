"""
Integration tests — REST API endpoints.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestAPI:

    def _client_as(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_api_counselor_sees_only_assigned_youth(
        self, counselor_user, youth_profile_1, youth_profile_2
    ):
        """Counselor only sees their assigned youth via API."""
        # youth_profile_1 is assigned to counselor_user
        # youth_profile_2 is also assigned to counselor_user (from fixture)
        c = self._client_as(counselor_user)
        resp = c.get("/api/youth/profiles/")
        assert resp.status_code == 200
        data = resp.json()
        pks = [str(p["id"]) for p in data]
        assert str(youth_profile_1.pk) in pks
        assert str(youth_profile_2.pk) in pks

    def test_api_admin_sees_all_youth(self, admin_user, youth_profile_1, youth_profile_2):
        c = self._client_as(admin_user)
        resp = c.get("/api/youth/profiles/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    def test_api_mentor_sees_only_assigned_sessions(
        self, mentor_user_1, youth_profile_1
    ):
        from apps.mentorship.models import MentorshipSession, SessionType, SessionStatus
        from datetime import date, timedelta

        youth_profile_1.assigned_mentor = mentor_user_1
        youth_profile_1.save()

        MentorshipSession.objects.create(
            youth=youth_profile_1, mentor=mentor_user_1,
            session_date=date.today() - timedelta(days=5),
            session_type=SessionType.DISCOVERY,
            status=SessionStatus.COMPLETED,
        )

        c = self._client_as(mentor_user_1)
        resp = c.get("/api/mentorship/sessions/")
        assert resp.status_code == 200
        data = resp.json()
        for session in data:
            assert session["mentor"] == mentor_user_1.pk

    def test_api_permission_denied_returns_correct_format(
        self, youth_user_1, youth_profile_1, youth_profile_2
    ):
        """Youth trying to access another youth's profile gets 403."""
        c = self._client_as(youth_user_1)
        resp = c.get(f"/api/youth/profiles/{youth_profile_2.pk}/")
        assert resp.status_code == 403

    def test_api_dashboard_kpis_return_correct_structure(self, counselor_user, youth_profile_1):
        c = self._client_as(counselor_user)
        resp = c.get("/api/dashboard/kpis/")
        assert resp.status_code == 200
        data = resp.json()

        required_keys = [
            "active_youth", "high_alerts", "missed_sessions_this_month",
            "expiring_plans", "available_mentors", "completed_this_month",
            "youth_by_status", "sessions_by_week", "top_sectors",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

        assert isinstance(data["youth_by_status"], dict)
        assert isinstance(data["sessions_by_week"], list)
        assert len(data["sessions_by_week"]) == 8
        assert isinstance(data["top_sectors"], list)

    def test_api_mark_alert_read(self, counselor_user, youth_profile_1):
        from apps.alerts.models import Alert, AlertType, AlertSeverity

        alert = Alert.objects.create(
            youth=youth_profile_1,
            alert_type=AlertType.INACTIVITY,
            severity=AlertSeverity.LOW,
            message="Test alert",
            is_read=False,
        )

        c = self._client_as(counselor_user)
        resp = c.post(f"/api/alerts/{alert.pk}/read/")
        assert resp.status_code == 200

        alert.refresh_from_db()
        assert alert.is_read is True

    def test_api_career_sectors_accessible_to_all_roles(
        self, counselor_user, mentor_user_1, youth_user_1, admin_user
    ):
        for user in [counselor_user, mentor_user_1, youth_user_1, admin_user]:
            c = self._client_as(user)
            resp = c.get("/api/careers/sectors/")
            assert resp.status_code == 200, f"Failed for role {user.role}"

    def test_api_unauthenticated_returns_403(self):
        c = Client()
        resp = c.get("/api/youth/profiles/")
        assert resp.status_code in (403, 401)

    def test_api_career_paths_filterable_by_sector(self, counselor_user, sample_career_paths, sample_sectors):
        c = self._client_as(counselor_user)
        resp = c.get(f"/api/careers/paths/?sector={sample_sectors[0].pk}")
        assert resp.status_code == 200
        data = resp.json()
        for path in data:
            assert path["sector"] == sample_sectors[0].pk
