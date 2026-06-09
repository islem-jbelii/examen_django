"""
dashboard/api_views.py — KPI JSON endpoint.
"""
from datetime import date, timedelta

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.accounts.permissions import IsCounselorOrAdmin
from apps.alerts.models import Alert, AlertSeverity
from apps.careers.models import CareerSector
from apps.guidance.models import ActionPlan, ActionPlanStatus
from apps.mentorship.models import MentorProfile, MentorshipSession, SessionStatus
from apps.youth.models import YouthProfile, YouthStatus
from django.db.models import Count


@api_view(["GET"])
@permission_classes([IsCounselorOrAdmin])
def dashboard_kpis(request):
    user = request.user
    today = date.today()
    month_start = today.replace(day=1)
    week7 = today + timedelta(days=7)

    if user.role == UserRole.COUNSELOR:
        youth_qs = YouthProfile.objects.filter(assigned_counselor=user)
        alert_qs = Alert.objects.filter(youth__assigned_counselor=user, is_read=False)
        session_qs = MentorshipSession.objects.filter(youth__assigned_counselor=user)
        plan_qs = ActionPlan.objects.filter(created_by=user, status=ActionPlanStatus.ACTIVE)
    else:
        youth_qs = YouthProfile.objects.all()
        alert_qs = Alert.objects.filter(is_read=False)
        session_qs = MentorshipSession.objects.all()
        plan_qs = ActionPlan.objects.filter(status=ActionPlanStatus.ACTIVE)

    # Youth by status
    youth_by_status = {
        value: youth_qs.filter(status=value).count()
        for value, _ in YouthStatus.choices
    }

    # Sessions by week (last 8)
    sessions_by_week = []
    for i in range(7, -1, -1):
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        qs = session_qs.filter(session_date__range=(week_start, week_end))
        sessions_by_week.append({
            "week": week_start.strftime("%Y-W%V"),
            "completed": qs.filter(status=SessionStatus.COMPLETED).count(),
            "missed": qs.filter(status=SessionStatus.MISSED).count(),
        })

    # Top sectors
    top_sectors = list(
        CareerSector.objects
        .filter(interested_youth__in=youth_qs)
        .annotate(count=Count("interested_youth"))
        .order_by("-count")
        .values("name", "count")[:5]
    )
    top_sectors = [{"sector": s["name"], "count": s["count"]} for s in top_sectors]

    return Response({
        "active_youth": youth_qs.exclude(
            status__in=[YouthStatus.COMPLETED, YouthStatus.INACTIVE]
        ).count(),
        "high_alerts": alert_qs.filter(severity=AlertSeverity.HIGH).count(),
        "missed_sessions_this_month": session_qs.filter(
            status=SessionStatus.MISSED, session_date__gte=month_start
        ).count(),
        "expiring_plans": plan_qs.filter(end_date__lte=week7, end_date__gte=today).count(),
        "available_mentors": MentorProfile.objects.filter(availability="AVAILABLE").count(),
        "completed_this_month": youth_qs.filter(
            status=YouthStatus.COMPLETED, updated_at__date__gte=month_start
        ).count(),
        "youth_by_status": youth_by_status,
        "sessions_by_week": sessions_by_week,
        "top_sectors": top_sectors,
    })
