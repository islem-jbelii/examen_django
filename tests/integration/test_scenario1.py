"""
Integration tests — Scenario 1: Youth intake and career assessment.
"""
import io
import pytest
from datetime import date, timedelta
from django.test import Client


@pytest.mark.django_db
class TestScenario1:

    def _client_as(self, user):
        c = Client()
        c.force_login(user)
        return c

    # ─────────────────────────────────────────────────────────────────────
    # Full intake workflow
    # ─────────────────────────────────────────────────────────────────────

    def test_full_intake_workflow(
        self, counselor_user, youth_user_1, sample_sectors, sample_career_paths
    ):
        from apps.youth.models import YouthProfile, YouthStatus, AssessmentStatus
        from apps.guidance.models import ActionPlan, ActionPlanStatus
        from apps.accounts.models import AuditLog

        c = self._client_as(counselor_user)

        # 1. Create youth profile
        dob = date.today().replace(year=date.today().year - 18)
        resp = c.post("/youth/create/", {
            "user": youth_user_1.pk,
            "date_of_birth": dob.strftime("%Y-%m-%d"),
            "gender": "M",
            "governorate": "TUNIS",
            "education_level": "BAC",
            "interests": [sample_sectors[0].pk],
        }, follow=True)
        assert resp.status_code == 200

        profile = YouthProfile.objects.get(user=youth_user_1)
        assert profile.status == YouthStatus.REGISTERED
        assert profile.readiness_score is not None
        assert AuditLog.objects.filter(action="CREATE_PROFILE", result="SUCCESS").exists()

        # 2. Conduct assessment
        responses = {f"q{i}": "4" for i in range(1, 11)}
        resp = c.post(f"/youth/{profile.pk}/assessment/", responses, follow=True)
        assert resp.status_code == 200

        profile.refresh_from_db()
        assert profile.status == YouthStatus.ASSESSED
        assert profile.assessments.filter(status=AssessmentStatus.COMPLETED).exists()

        # 3. Create and validate action plan
        start = date.today()
        end = start + timedelta(days=90)
        resp = c.post("/guidance/plans/create/", {
            "youth": profile.pk,
            "objectives": "Devenir développeur web.",
            "target_sector": sample_sectors[0].pk,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "milestones_json": "[]",
        }, follow=True)
        assert resp.status_code == 200

        plan = ActionPlan.objects.filter(youth=profile).first()
        assert plan is not None

        resp = c.post(f"/guidance/plans/{plan.pk}/validate/", follow=True)
        assert resp.status_code == 200
        plan.refresh_from_db()
        assert plan.status == ActionPlanStatus.VALIDATED

        # 4. Transition to PLAN_ACTIVE
        resp = c.post(f"/youth/{profile.pk}/edit/", {"transition": "to_plan_active"}, follow=True)
        assert resp.status_code == 200
        profile.refresh_from_db()
        assert profile.status == YouthStatus.PLAN_ACTIVE

    # ─────────────────────────────────────────────────────────────────────
    # Bulk import — valid CSV
    # ─────────────────────────────────────────────────────────────────────

    def test_bulk_import_valid_csv(self, counselor_user, sample_sectors):
        from apps.youth.models import YouthProfile

        c = self._client_as(counselor_user)
        count_before = YouthProfile.objects.count()

        csv_content = (
            "first_name,last_name,date_of_birth,gender,governorate,education_level,interests\n"
            f"Amine,Jebali,2006-03-15,M,TUNIS,BAC,{sample_sectors[0].name}\n"
            f"Rania,Hamdi,2005-07-22,F,SFAX,LICENCE,{sample_sectors[1].name}\n"
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "valid.csv"

        resp = c.post("/youth/import/", {"csv_file": csv_file}, follow=True)
        assert resp.status_code == 200

        count_after = YouthProfile.objects.count()
        assert count_after == count_before + 2

    # ─────────────────────────────────────────────────────────────────────
    # Bulk import — malformed CSV
    # ─────────────────────────────────────────────────────────────────────

    def test_bulk_import_malformed_csv(self, counselor_user, sample_sectors):
        from apps.youth.models import YouthProfile
        from apps.accounts.models import AuditLog

        c = self._client_as(counselor_user)
        count_before = YouthProfile.objects.count()
        audit_before = AuditLog.objects.filter(action="BULK_IMPORT_ROW_FAILED").count()

        csv_content = (
            "first_name,last_name,date_of_birth,gender,governorate,education_level,interests\n"
            "Bad,Date,not-a-date,M,TUNIS,BAC,Informatique\n"          # invalid date
            "Bad,Gov,2006-01-01,M,INVALID_GOV,BAC,Informatique\n"     # invalid governorate
            "Too,Young,2015-01-01,F,TUNIS,BAC,Informatique\n"         # age < 15
            "Bad,Edu,2006-01-01,M,TUNIS,INVALID_EDU,Informatique\n"   # invalid education
            "Bad,Sector,2006-01-01,M,TUNIS,BAC,SECTEUR_INCONNU\n"     # unknown sector
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "malformed.csv"

        resp = c.post("/youth/import/", {"csv_file": csv_file}, follow=True)
        assert resp.status_code == 200

        # No new profiles created
        assert YouthProfile.objects.count() == count_before

        # AuditLog entries for each failed row
        audit_after = AuditLog.objects.filter(action="BULK_IMPORT_ROW_FAILED").count()
        assert audit_after > audit_before

    # ─────────────────────────────────────────────────────────────────────
    # FAILURE 1B — Unauthorized status transition by mentor
    # ─────────────────────────────────────────────────────────────────────

    def test_unauthorized_status_transition_by_mentor(self, mentor_user_1, youth_profile_1):
        from apps.accounts.models import AuditLog

        c = self._client_as(mentor_user_1)
        audit_before = AuditLog.objects.filter(action="ACCESS_DENIED").count()

        resp = c.get(f"/youth/{youth_profile_1.pk}/edit/")
        assert resp.status_code == 403

        assert AuditLog.objects.filter(action="ACCESS_DENIED").count() > audit_before

    # ─────────────────────────────────────────────────────────────────────
    # FAILURE 1B — Plan activation blocked without validated plan
    # ─────────────────────────────────────────────────────────────────────

    def test_plan_activation_blocked_without_validated_plan(
        self, counselor_user, youth_profile_1, sample_sectors
    ):
        from apps.youth.models import YouthStatus
        from apps.accounts.models import AuditLog

        youth_profile_1.status = YouthStatus.ASSESSED
        youth_profile_1.save()

        c = self._client_as(counselor_user)
        audit_before = AuditLog.objects.filter(action="VALIDATION_FAILED").count()

        resp = c.post(
            f"/youth/{youth_profile_1.pk}/edit/",
            {"transition": "to_plan_active"},
            follow=True,
        )
        assert resp.status_code == 200

        youth_profile_1.refresh_from_db()
        assert youth_profile_1.status == YouthStatus.ASSESSED  # unchanged

        assert AuditLog.objects.filter(action="VALIDATION_FAILED").count() > audit_before
