"""
youth/services.py — Business logic for youth profiles

compute_readiness_score(youth) → int (0-100)
"""
from apps.youth.models import AssessmentStatus, YouthStatus, EducationLevel


def compute_readiness_score(youth) -> int:
    """
    Compute a readiness score for a YouthProfile instance.

    Scoring breakdown:
    ─────────────────────────────────────────────────────────
    +30  Assessment completed
    +25  Action plan is ACTIVE
    +N   Each interest sector: sector.relevance_weight × 10
    +15  Education level is BAC or above
    +20  Mentor assigned AND at least 1 COMPLETED session
    -30  Status is INACTIVE
    ─────────────────────────────────────────────────────────
    Result is clamped to [0, 100].
    """
    score = 0
    breakdown = {}

    # 1. Assessment completed
    has_completed_assessment = youth.assessments.filter(
        status=AssessmentStatus.COMPLETED
    ).exists()
    if has_completed_assessment:
        score += 30
        breakdown["assessment_completed"] = 30

    # 2. Active action plan
    has_active_plan = youth.action_plans.filter(status="ACTIVE").exists()
    if has_active_plan:
        score += 25
        breakdown["active_action_plan"] = 25

    # 3. Interest sectors
    sector_score = 0
    for sector in youth.interests.all():
        sector_score += sector.relevance_weight * 10
    if sector_score:
        score += sector_score
        breakdown["interest_sectors"] = sector_score

    # 4. Education level BAC or above
    high_education = {
        EducationLevel.BAC,
        EducationLevel.BAC_PLUS_2,
        EducationLevel.LICENCE,
        EducationLevel.MASTER,
    }
    if youth.education_level in high_education:
        score += 15
        breakdown["education_level"] = 15

    # 5. Mentor assigned + at least 1 completed session
    if youth.assigned_mentor:
        completed_sessions = youth.mentorship_sessions.filter(status="COMPLETED").count()
        if completed_sessions >= 1:
            score += 20
            breakdown["mentor_with_session"] = 20

    # 6. Inactive penalty
    if youth.status == YouthStatus.INACTIVE:
        score -= 30
        breakdown["inactive_penalty"] = -30

    # Clamp
    final_score = max(0, min(100, score))
    breakdown["total"] = final_score
    return final_score, breakdown
