"""
Management command: generate_sample_data
Loads realistic synthetic data from CSV files in the data/ directory.

Run:
    python manage.py generate_sample_data
    python manage.py generate_sample_data --clear

CSV files loaded (in order):
    data/users.csv
    data/mentor_profiles.csv
    data/youth_profiles.csv
    data/assessments.csv
    data/action_plans.csv
    data/mentorship_sessions.csv
    data/alerts.csv
"""
import csv
import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()
DATA_DIR = Path(__file__).resolve().parents[4] / "data"


def _read_csv(filename):
    """Read a CSV file from the data/ directory and return list of dicts."""
    path = DATA_DIR / filename
    if not path.exists():
        raise CommandError(f"CSV file not found: {path}")
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "Load synthetic sample data from CSV files in data/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete existing synthetic data (username starts with synth_) before loading",
        )

    def handle(self, *args, **options):
        from apps.accounts.models import UserRole
        from apps.youth.models import (
            YouthProfile, YouthStatus, InterestAssessment, AssessmentStatus,
        )
        from apps.careers.models import CareerSector
        from apps.mentorship.models import MentorProfile, MentorshipSession
        from apps.guidance.models import ActionPlan, ActionPlanStatus
        from apps.alerts.models import Alert, AlertType, AlertSeverity

        if options["clear"]:
            self.stdout.write("  Clearing existing synthetic data...")
            YouthProfile.objects.filter(user__username__startswith="synth_").delete()
            User.objects.filter(username__startswith="synth_").delete()
            self.stdout.write(self.style.WARNING("  Cleared."))

        # ── 1. Users ──────────────────────────────────────────────────────
        self.stdout.write("Loading users.csv...")
        users_created = 0
        for row in _read_csv("users.csv"):
            u, created = User.objects.get_or_create(
                username=row["username"],
                defaults={
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "email": row["email"],
                    "role": row["role"],
                    "is_active": row["is_active"].strip().lower() == "true",
                },
            )
            if created:
                u.set_password(row["password"])
                u.save()
                users_created += 1
        self.stdout.write(self.style.SUCCESS(f"  {users_created} users created."))

        # ── 2. Mentor profiles ────────────────────────────────────────────
        self.stdout.write("Loading mentor_profiles.csv...")
        mentors_created = 0
        for row in _read_csv("mentor_profiles.csv"):
            try:
                user = User.objects.get(username=row["username"])
                sector = CareerSector.objects.get(name=row["sector_name"])
            except (User.DoesNotExist, CareerSector.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f"  Skipping mentor {row['username']}: {e}"))
                continue
            _, created = MentorProfile.objects.get_or_create(
                user=user,
                defaults={
                    "sector": sector,
                    "company_name": row["company_name"],
                    "years_of_experience": int(row["years_of_experience"]),
                    "bio": row["bio"],
                    "availability": row["availability"],
                    "max_youth_capacity": int(row["max_youth_capacity"]),
                    "current_youth_count": int(row["current_youth_count"]),
                    "is_verified": row["is_verified"].strip().lower() == "true",
                },
            )
            if created:
                mentors_created += 1
        self.stdout.write(self.style.SUCCESS(f"  {mentors_created} mentor profiles created."))

        # ── 3. Youth profiles ─────────────────────────────────────────────
        self.stdout.write("Loading youth_profiles.csv...")
        youth_created = 0
        for row in _read_csv("youth_profiles.csv"):
            try:
                user = User.objects.get(username=row["username"])
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  Skipping youth {row['username']}: user not found"))
                continue

            counselor = None
            if row.get("assigned_counselor"):
                counselor = User.objects.filter(username=row["assigned_counselor"]).first()

            mentor = None
            if row.get("assigned_mentor"):
                mentor = User.objects.filter(username=row["assigned_mentor"]).first()

            profile, created = YouthProfile.objects.get_or_create(
                user=user,
                defaults={
                    "date_of_birth": date.fromisoformat(row["date_of_birth"]),
                    "gender": row["gender"],
                    "governorate": row["governorate"],
                    "education_level": row["education_level"],
                    "current_school_or_institution": row.get("current_school_or_institution", ""),
                    "assigned_counselor": counselor,
                    "assigned_mentor": mentor,
                    "status": row["status"],
                    "notes": row.get("notes", ""),
                },
            )
            if created:
                # Set interests
                interest_names = [n.strip() for n in row.get("interests", "").split("|") if n.strip()]
                sectors = CareerSector.objects.filter(name__in=interest_names)
                profile.interests.set(sectors)
                youth_created += 1
        self.stdout.write(self.style.SUCCESS(f"  {youth_created} youth profiles created."))

        # ── 4. Assessments ────────────────────────────────────────────────
        self.stdout.write("Loading assessments.csv...")
        assessments_created = 0
        for row in _read_csv("assessments.csv"):
            try:
                youth = YouthProfile.objects.get(user__username=row["youth_username"])
                counselor = User.objects.get(username=row["conducted_by_username"])
            except (YouthProfile.DoesNotExist, User.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f"  Skipping assessment: {e}"))
                continue

            if youth.assessments.exists():
                continue

            # Build responses dict from q1..q10 columns
            responses = {f"q{i}": row[f"q{i}"] for i in range(1, 11) if row.get(f"q{i}")}

            # Score breakdown
            score_breakdown = {}
            for sector_name, q_key in [
                ("Informatique", "q1"), ("Santé", "q2"), ("Agriculture", "q3"),
                ("Commerce", "q4"), ("Artisanat", "q5"), ("Tourisme", "q6"),
                ("Ingénierie", "q7"), ("Éducation", "q8"),
            ]:
                if q_key in responses:
                    score_breakdown[sector_name] = int(responses[q_key])

            assessment = InterestAssessment.objects.create(
                youth=youth,
                conducted_by=counselor,
                assessment_date=date.fromisoformat(row["assessment_date"]),
                responses=responses,
                score_breakdown=score_breakdown,
                status=row["status"],
            )

            # Recommended sectors
            rec_names = [n.strip() for n in row.get("recommended_sectors", "").split("|") if n.strip()]
            rec_sectors = CareerSector.objects.filter(name__in=rec_names)
            assessment.recommended_sectors.set(rec_sectors)
            assessments_created += 1

        self.stdout.write(self.style.SUCCESS(f"  {assessments_created} assessments created."))

        # ── 5. Action plans ───────────────────────────────────────────────
        self.stdout.write("Loading action_plans.csv...")
        plans_created = 0
        for row in _read_csv("action_plans.csv"):
            try:
                youth = YouthProfile.objects.get(user__username=row["youth_username"])
                counselor = User.objects.get(username=row["created_by_username"])
                sector = CareerSector.objects.get(name=row["target_sector"])
            except (YouthProfile.DoesNotExist, User.DoesNotExist, CareerSector.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f"  Skipping plan: {e}"))
                continue

            if youth.action_plans.exists():
                continue

            milestones = []
            raw_milestones = row.get("milestones", "[]").strip()
            if raw_milestones:
                try:
                    milestones = json.loads(raw_milestones)
                except json.JSONDecodeError:
                    milestones = []

            ActionPlan.objects.create(
                youth=youth,
                created_by=counselor,
                status=row["status"],
                objectives=row["objectives"],
                target_sector=sector,
                start_date=date.fromisoformat(row["start_date"]),
                end_date=date.fromisoformat(row["end_date"]),
                milestones=milestones,
            )
            plans_created += 1

        self.stdout.write(self.style.SUCCESS(f"  {plans_created} action plans created."))

        # ── 6. Mentorship sessions ────────────────────────────────────────
        self.stdout.write("Loading mentorship_sessions.csv...")
        sessions_created = 0
        for row in _read_csv("mentorship_sessions.csv"):
            try:
                youth = YouthProfile.objects.get(user__username=row["youth_username"])
                mentor = User.objects.get(username=row["mentor_username"])
            except (YouthProfile.DoesNotExist, User.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f"  Skipping session: {e}"))
                continue

            MentorshipSession.objects.create(
                youth=youth,
                mentor=mentor,
                session_date=date.fromisoformat(row["session_date"]),
                session_type=row["session_type"],
                status=row["status"],
                notes=row.get("notes", ""),
                recommendations=row.get("recommendations", ""),
                counselor_notified=row.get("counselor_notified", "False").strip().lower() == "true",
            )
            sessions_created += 1

        self.stdout.write(self.style.SUCCESS(f"  {sessions_created} sessions created."))

        # ── 7. Alerts ─────────────────────────────────────────────────────
        self.stdout.write("Loading alerts.csv...")
        alerts_created = 0
        for row in _read_csv("alerts.csv"):
            try:
                youth = YouthProfile.objects.get(user__username=row["youth_username"])
            except YouthProfile.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  Skipping alert: youth {row['youth_username']} not found"))
                continue

            Alert.objects.create(
                youth=youth,
                alert_type=row["alert_type"],
                severity=row["severity"],
                message=row["message"],
                triggered_by=row.get("triggered_by", "system"),
                is_read=row.get("is_read", "False").strip().lower() == "true",
            )
            alerts_created += 1

        self.stdout.write(self.style.SUCCESS(f"  {alerts_created} alerts created."))

        # ── Summary ───────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Sample data loaded from CSV files.\n"
            f"  Users:    {users_created}\n"
            f"  Mentors:  {mentors_created}\n"
            f"  Youth:    {youth_created}\n"
            f"  Assessments: {assessments_created}\n"
            f"  Plans:    {plans_created}\n"
            f"  Sessions: {sessions_created}\n"
            f"  Alerts:   {alerts_created}"
        ))
