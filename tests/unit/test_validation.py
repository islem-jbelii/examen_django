"""
Unit tests for model and form validation rules.
"""
import pytest
from datetime import date, timedelta
from django.core.exceptions import ValidationError


@pytest.mark.django_db
class TestValidation:

    def test_youth_age_must_be_between_15_and_25(self, youth_user_1, counselor_user, sample_sectors):
        from apps.youth.models import YouthProfile

        # Too young (10 years old)
        p = YouthProfile(
            user=youth_user_1,
            date_of_birth=date.today() - timedelta(days=365 * 10),
            gender="M", governorate="TUNIS", education_level="COLLEGE",
            assigned_counselor=counselor_user,
        )
        with pytest.raises(ValidationError) as exc:
            p.clean()
        assert "date_of_birth" in exc.value.message_dict

    def test_youth_age_valid_at_boundary(self, youth_user_1, counselor_user, sample_sectors):
        from apps.youth.models import YouthProfile

        # Exactly 15 years old — should pass
        dob = date.today().replace(year=date.today().year - 15)
        p = YouthProfile(
            user=youth_user_1,
            date_of_birth=dob,
            gender="M", governorate="TUNIS", education_level="LYCEE",
            assigned_counselor=counselor_user,
        )
        p.clean()  # Should not raise

    def test_youth_requires_at_least_one_sector_interest(self):
        from apps.youth.forms import YouthProfileUpdateForm
        form = YouthProfileUpdateForm(data={
            "date_of_birth": "2006-01-01",
            "gender": "M",
            "governorate": "TUNIS",
            "education_level": "BAC",
            "interests": [],
        })
        assert not form.is_valid()
        assert "interests" in form.errors

    def test_session_blocked_for_inactive_youth(self, inactive_youth, mentor_user_1):
        from apps.mentorship.models import MentorshipSession, SessionType

        session = MentorshipSession(
            youth=inactive_youth,
            mentor=mentor_user_1,
            session_date=date.today(),
            session_type=SessionType.DISCOVERY,
        )
        with pytest.raises(ValidationError) as exc:
            session.clean()
        assert "youth" in exc.value.message_dict

    def test_plan_end_date_must_be_after_start_date(self, youth_profile_1, counselor_user, sample_sectors):
        from apps.guidance.models import ActionPlan

        plan = ActionPlan(
            youth=youth_profile_1,
            created_by=counselor_user,
            objectives="Test",
            target_sector=sample_sectors[0],
            start_date=date.today() + timedelta(days=10),
            end_date=date.today(),  # Before start_date
        )
        with pytest.raises(ValidationError) as exc:
            plan.clean()
        assert "end_date" in exc.value.message_dict

    def test_mentor_capacity_cannot_be_exceeded(self, mentor_at_full_capacity):
        from apps.mentorship.models import MentorProfile
        mp = mentor_at_full_capacity.mentor_profile
        mp.current_youth_count = mp.max_youth_capacity + 1
        with pytest.raises(ValidationError):
            mp.clean()

    def test_assessment_required_before_plan_activation(self, youth_profile_1, counselor_user, sample_sectors):
        """Counselor tries ASSESSED→PLAN_ACTIVE without validated plan — should fail."""
        from apps.youth.models import YouthStatus
        from apps.guidance.models import ActionPlan, ActionPlanStatus

        youth_profile_1.status = YouthStatus.ASSESSED
        youth_profile_1.save()

        # No validated plan exists
        has_validated = ActionPlan.objects.filter(
            youth=youth_profile_1, status=ActionPlanStatus.VALIDATED
        ).exists()
        assert not has_validated
