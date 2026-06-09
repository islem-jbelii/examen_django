"""
Management command: check_alerts
Run: python manage.py check_alerts

Executes all three idempotent alert checks:
  1. check_plan_expiring_alert  — plans expiring within 7 days
  2. check_inactivity_alert     — youth with no activity in 30 days
  3. check_missed_sessions_alert — per-youth consecutive missed sessions
"""
from django.core.management.base import BaseCommand

from apps.alerts.services import (
    check_plan_expiring_alert,
    check_inactivity_alert,
    check_missed_sessions_alert,
)
from apps.youth.models import YouthProfile


class Command(BaseCommand):
    help = "Run all alert engine checks (idempotent)"

    def handle(self, *args, **options):
        self.stdout.write("Running alert checks...")

        # 1. Plan expiring
        self.stdout.write("  [1/3] Checking expiring plans...")
        check_plan_expiring_alert()
        self.stdout.write(self.style.SUCCESS("       Done."))

        # 2. Inactivity
        self.stdout.write("  [2/3] Checking inactivity...")
        check_inactivity_alert()
        self.stdout.write(self.style.SUCCESS("       Done."))

        # 3. Missed sessions (per youth)
        self.stdout.write("  [3/3] Checking missed sessions...")
        count = 0
        for youth in YouthProfile.objects.all():
            check_missed_sessions_alert(youth.pk)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"       Checked {count} youth profiles."))

        self.stdout.write(self.style.SUCCESS("\nAll alert checks completed."))
