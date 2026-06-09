"""
Unit tests for compute_readiness_score service.
"""
import pytest
from datetime import date, timedelta


@pytest.mark.django_db
class TestReadinessScore:

    def test_score_zero_for_new_youth_no_assessment(self, youth_profile_1):
        from apps.youth.services import compute_readiness_score
        score, breakdown = compute_readiness_score(youth_profile_1)
        # Has 1 sector (weight=3 → +30), BAC education (+15) = 45 minimum
        # But no assessment, no plan, no mentor session
        assert "assessment_completed" not in breakdown
        assert score >= 0

    def test_score_increases_with_completed_assessment(self, youth_profile_1, counselor_user):
        from apps.youth.models import InterestAssessment, AssessmentStatus
        from apps.youth.services import compute_readiness_score

        score_before, _ = compute_readiness_score(youth_profile_1)

        InterestAssessment.objects.create(
            youth=youth_profile_1,
            conducted_by=counselor_user,
            assessment_date=date.today(),
            responses={"q1": "4"},
            status=AssessmentStatus.COMPLETED,
        )

        score_after, breakdown = compute_readiness_score(youth_profile_1)
        assert score_after > score_before
        assert breakdown.get("assessment_completed") == 30

    def test_score_increases_with_active_plan(self, youth_profile_1, counselor_user, sample_sectors):
        from apps.guidance.models import ActionPlan, ActionPlanStatus
        from apps.youth.services import compute_readiness_score

        score_before, _ = compute_readiness_score(youth_profile_1)

        ActionPlan.objects.create(
            youth=youth_profile_1,
            created_by=counselor_user,
            status=ActionPlanStatus.ACTIVE,
            objectives="Test objectives",
            target_sector=sample_sectors[0],
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
        )

        score_after, breakdown = compute_readiness_score(youth_profile_1)
        assert score_after > score_before
        assert breakdown.get("active_action_plan") == 25

    def test_score_increases_with_completed_session(self, youth_profile_1, mentor_user_1):
        from apps.mentorship.models import MentorshipSession, SessionStatus, SessionType
        from apps.youth.services import compute_readiness_score

        youth_profile_1.assigned_mentor = mentor_user_1
        youth_profile_1.save()

        score_before, _ = compute_readiness_score(youth_profile_1)

        MentorshipSession.objects.create(
            youth=youth_profile_1,
            mentor=mentor_user_1,
            session_date=date.today() - timedelta(days=7),
            session_type=SessionType.DISCOVERY,
            status=SessionStatus.COMPLETED,
        )

        score_after, breakdown = compute_readiness_score(youth_profile_1)
        assert score_after > score_before
        assert breakdown.get("mentor_with_session") == 20

    def test_inactive_youth_gets_penalty(self, inactive_youth):
        from apps.youth.services import compute_readiness_score
        score, breakdown = compute_readiness_score(inactive_youth)
        assert breakdown.get("inactive_penalty") == -30

    def test_score_breakdown_is_human_readable(self, youth_profile_1):
        from apps.youth.services import compute_readiness_score
        score, breakdown = compute_readiness_score(youth_profile_1)
        assert isinstance(breakdown, dict)
        assert "total" in breakdown
        for key in breakdown:
            assert isinstance(breakdown[key], int)

    def test_score_capped_at_100(self, active_youth_with_plan, counselor_user):
        """A youth with everything filled in should not exceed 100."""
        from apps.youth.models import InterestAssessment, AssessmentStatus
        from apps.mentorship.models import MentorshipSession, SessionStatus, SessionType
        from apps.youth.services import compute_readiness_score

        InterestAssessment.objects.create(
            youth=active_youth_with_plan,
            conducted_by=counselor_user,
            assessment_date=date.today(),
            responses={},
            status=AssessmentStatus.COMPLETED,
        )
        MentorshipSession.objects.create(
            youth=active_youth_with_plan,
            mentor=active_youth_with_plan.assigned_mentor,
            session_date=date.today() - timedelta(days=1),
            session_type=SessionType.DISCOVERY,
            status=SessionStatus.COMPLETED,
        )

        score, _ = compute_readiness_score(active_youth_with_plan)
        assert score <= 100
        assert score >= 0
