"""
conftest.py — Shared pytest fixtures for CareerPathTN test suite.
"""
import pytest
from datetime import date, timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# User fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    u = User.objects.create_user(
        username="test_admin", email="admin@test.tn",
        password="admin123", role="ADMIN",
        first_name="Admin", last_name="Test",
        is_staff=True, is_superuser=True,
    )
    return u


@pytest.fixture
def counselor_user(db):
    return User.objects.create_user(
        username="test_counselor", email="counselor@test.tn",
        password="counsel123", role="COUNSELOR",
        first_name="Sonia", last_name="Ben Ali",
    )


@pytest.fixture
def mentor_user_1(db, sample_sectors):
    from apps.mentorship.models import MentorProfile
    u = User.objects.create_user(
        username="test_mentor1", email="mentor1@test.tn",
        password="mentor123", role="MENTOR",
        first_name="Karim", last_name="Trabelsi",
    )
    MentorProfile.objects.create(
        user=u, sector=sample_sectors[0],
        company_name="TechTN", years_of_experience=5,
        bio="Expert en informatique.", availability="AVAILABLE",
        max_youth_capacity=3, current_youth_count=0, is_verified=True,
    )
    return u


@pytest.fixture
def mentor_user_2(db, sample_sectors):
    from apps.mentorship.models import MentorProfile
    u = User.objects.create_user(
        username="test_mentor2", email="mentor2@test.tn",
        password="mentor234", role="MENTOR",
        first_name="Fatma", last_name="Chaabane",
    )
    MentorProfile.objects.create(
        user=u, sector=sample_sectors[1],
        company_name="HealthTN", years_of_experience=8,
        bio="Professionnelle de santé.", availability="AVAILABLE",
        max_youth_capacity=2, current_youth_count=0, is_verified=True,
    )
    return u


@pytest.fixture
def youth_user_1(db):
    return User.objects.create_user(
        username="test_youth1", email="youth1@test.tn",
        password="youth123", role="YOUTH",
        first_name="Ahmed", last_name="Mansouri",
    )


@pytest.fixture
def youth_user_2(db):
    return User.objects.create_user(
        username="test_youth2", email="youth2@test.tn",
        password="youth234", role="YOUTH",
        first_name="Mariem", last_name="Khelifi",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Career fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_sectors(db):
    from apps.careers.models import CareerSector
    s1, _ = CareerSector.objects.get_or_create(
        name="Informatique",
        defaults={"description": "IT sector", "demand_level": "HIGH", "relevance_weight": 3},
    )
    s2, _ = CareerSector.objects.get_or_create(
        name="Santé",
        defaults={"description": "Health sector", "demand_level": "HIGH", "relevance_weight": 3},
    )
    s3, _ = CareerSector.objects.get_or_create(
        name="Commerce",
        defaults={"description": "Commerce sector", "demand_level": "MEDIUM", "relevance_weight": 2},
    )
    return [s1, s2, s3]


@pytest.fixture
def sample_career_paths(db, sample_sectors):
    from apps.careers.models import CareerPath
    import uuid
    paths = []
    data = [
        (sample_sectors[0], "Développeur Web", 18),
        (sample_sectors[1], "Infirmier(ère)", 36),
        (sample_sectors[2], "Comptable", 24),
    ]
    for sector, title, months in data:
        p, _ = CareerPath.objects.get_or_create(
            title=title,
            defaults={
                "sector": sector, "description": f"Métier: {title}",
                "required_skills": "Compétences diverses",
                "training_duration_months": months, "is_active": True,
            }
        )
        paths.append(p)
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Youth profile fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def youth_profile_1(db, youth_user_1, counselor_user, sample_sectors):
    from apps.youth.models import YouthProfile, YouthStatus
    p = YouthProfile.objects.create(
        user=youth_user_1,
        date_of_birth=date(2006, 5, 15),
        gender="M",
        governorate="TUNIS",
        education_level="BAC",
        assigned_counselor=counselor_user,
        status=YouthStatus.REGISTERED,
    )
    p.interests.set([sample_sectors[0]])
    return p


@pytest.fixture
def youth_profile_2(db, youth_user_2, counselor_user, sample_sectors):
    from apps.youth.models import YouthProfile, YouthStatus
    p = YouthProfile.objects.create(
        user=youth_user_2,
        date_of_birth=date(2004, 8, 20),
        gender="F",
        governorate="SFAX",
        education_level="LICENCE",
        assigned_counselor=counselor_user,
        status=YouthStatus.REGISTERED,
    )
    p.interests.set([sample_sectors[1]])
    return p


@pytest.fixture
def active_youth_with_plan(db, youth_profile_1, counselor_user, mentor_user_1, sample_sectors, sample_career_paths):
    """Youth with PLAN_ACTIVE status, assigned counselor + mentor, validated plan."""
    from apps.youth.models import YouthProfile, YouthStatus
    from apps.guidance.models import ActionPlan, ActionPlanStatus
    from apps.mentorship.models import MentorProfile

    youth_profile_1.status = YouthStatus.PLAN_ACTIVE
    youth_profile_1.assigned_mentor = mentor_user_1
    youth_profile_1.save()

    # Update mentor count
    mp = mentor_user_1.mentor_profile
    mp.current_youth_count = 1
    mp.save()

    ActionPlan.objects.create(
        youth=youth_profile_1,
        created_by=counselor_user,
        status=ActionPlanStatus.ACTIVE,
        objectives="Devenir développeur web.",
        target_sector=sample_sectors[0],
        target_career=sample_career_paths[0],
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=60),
        milestones=[{"title": "Étape 1", "due_date": str(date.today()), "done": False}],
    )
    return youth_profile_1


@pytest.fixture
def inactive_youth(db, youth_user_1, counselor_user, sample_sectors):
    from apps.youth.models import YouthProfile, YouthStatus
    # Need a different user since youth_user_1 might already have a profile
    u = User.objects.create_user(
        username="test_inactive_youth", email="inactive@test.tn",
        password="inactive123", role="YOUTH",
        first_name="Inactive", last_name="Youth",
    )
    p = YouthProfile.objects.create(
        user=u,
        date_of_birth=date(2005, 3, 10),
        gender="M",
        governorate="GABES",
        education_level="LYCEE",
        assigned_counselor=counselor_user,
        status=YouthStatus.INACTIVE,
    )
    p.interests.set([sample_sectors[0]])
    return p


@pytest.fixture
def youth_with_two_missed_sessions(db, youth_profile_1, mentor_user_1, sample_sectors):
    """Youth with 2 consecutive MISSED sessions."""
    from apps.youth.models import YouthStatus
    from apps.mentorship.models import MentorshipSession, SessionStatus, SessionType

    youth_profile_1.assigned_mentor = mentor_user_1
    youth_profile_1.status = YouthStatus.IN_MENTORSHIP
    youth_profile_1.save()

    for i in range(2):
        MentorshipSession.objects.create(
            youth=youth_profile_1,
            mentor=mentor_user_1,
            session_date=date.today() - timedelta(days=7 * (i + 1)),
            session_type=SessionType.FOLLOW_UP,
            status=SessionStatus.MISSED,
        )
    return youth_profile_1


@pytest.fixture
def mentor_at_full_capacity(db, mentor_user_1):
    """Mentor with current_youth_count == max_youth_capacity."""
    mp = mentor_user_1.mentor_profile
    mp.max_youth_capacity = 3
    mp.current_youth_count = 3
    mp.save()
    return mentor_user_1
