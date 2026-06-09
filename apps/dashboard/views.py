"""
dashboard/views.py — Role dashboards + monitoring dashboard with Chart.js KPIs.
"""
import csv
import io
import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.accounts.models import AuditLog, UserRole
from apps.accounts.permissions import (
    admin_required, counselor_required,
    mentor_required, youth_required, counselor_or_admin_required,
)
from apps.alerts.models import Alert, AlertSeverity
from apps.careers.models import CareerSector
from apps.guidance.models import ActionPlan, ActionPlanStatus
from apps.mentorship.models import MentorProfile, MentorshipSession, SessionStatus
from apps.youth.models import YouthProfile, YouthStatus


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _base_youth_qs(user):
    if user.role == UserRole.COUNSELOR:
        return YouthProfile.objects.filter(assigned_counselor=user)
    return YouthProfile.objects.all()


def _sessions_by_week(user, weeks=8):
    """Return list of {week, completed, missed} for last N weeks."""
    result = []
    today = date.today()
    for i in range(weeks - 1, -1, -1):
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        qs = MentorshipSession.objects.filter(session_date__range=(week_start, week_end))
        if user.role == UserRole.COUNSELOR:
            qs = qs.filter(youth__assigned_counselor=user)
        result.append({
            "week": week_start.strftime("%Y-W%V"),
            "completed": qs.filter(status=SessionStatus.COMPLETED).count(),
            "missed": qs.filter(status=SessionStatus.MISSED).count(),
        })
    return result


def _top_sectors(user, n=5):
    """Return top N sectors by youth interest count."""
    qs = _base_youth_qs(user)
    sectors = (
        CareerSector.objects
        .filter(interested_youth__in=qs)
        .annotate(youth_count=Count("interested_youth"))
        .order_by("-youth_count")[:n]
    )
    return [{"sector": s.name, "count": s.youth_count} for s in sectors]


def _youth_by_governorate(user, n=10):
    qs = _base_youth_qs(user)
    rows = (
        qs.values("governorate")
        .annotate(count=Count("id"))
        .order_by("-count")[:n]
    )
    return list(rows)


def _readiness_distribution(user):
    qs = _base_youth_qs(user)
    low = qs.filter(readiness_score__lte=30).count()
    mid = qs.filter(readiness_score__gt=30, readiness_score__lte=60).count()
    high = qs.filter(readiness_score__gt=60).count()
    return {"0-30": low, "31-60": mid, "61-100": high}


def _build_kpis(user):
    today = date.today()
    month_start = today.replace(day=1)
    week7 = today + timedelta(days=7)

    youth_qs = _base_youth_qs(user)
    alert_qs = Alert.objects.filter(is_read=False)
    if user.role == UserRole.COUNSELOR:
        alert_qs = alert_qs.filter(youth__assigned_counselor=user)

    session_qs = MentorshipSession.objects.all()
    if user.role == UserRole.COUNSELOR:
        session_qs = session_qs.filter(youth__assigned_counselor=user)

    plan_qs = ActionPlan.objects.filter(status=ActionPlanStatus.ACTIVE)
    if user.role == UserRole.COUNSELOR:
        plan_qs = plan_qs.filter(created_by=user)

    return {
        "active_youth": youth_qs.exclude(
            status__in=[YouthStatus.COMPLETED, YouthStatus.INACTIVE]
        ).count(),
        "high_alerts": alert_qs.filter(severity=AlertSeverity.HIGH).count(),
        "missed_sessions_month": session_qs.filter(
            status=SessionStatus.MISSED,
            session_date__gte=month_start,
        ).count(),
        "expiring_plans": plan_qs.filter(end_date__lte=week7, end_date__gte=today).count(),
        "available_mentors": MentorProfile.objects.filter(availability="AVAILABLE").count(),
        "completed_month": youth_qs.filter(
            status=YouthStatus.COMPLETED,
            updated_at__date__gte=month_start,
        ).count(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Monitoring Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_or_admin_required
def monitoring_dashboard(request):
    user = request.user
    today = date.today()

    # Filters
    gov_filter = request.GET.get("governorate", "")
    sector_filter = request.GET.get("sector", "")
    edu_filter = request.GET.get("education_level", "")

    youth_qs = _base_youth_qs(user)
    if gov_filter:
        youth_qs = youth_qs.filter(governorate=gov_filter)
    if sector_filter:
        youth_qs = youth_qs.filter(interests__id=sector_filter)
    if edu_filter:
        youth_qs = youth_qs.filter(education_level=edu_filter)

    # KPIs
    kpis = _build_kpis(user)

    # Chart data
    youth_by_status = {
        label: youth_qs.filter(status=value).count()
        for value, label in YouthStatus.choices
    }

    sessions_by_week = _sessions_by_week(user)
    top_sectors = _top_sectors(user)
    youth_by_gov = _youth_by_governorate(user)
    readiness_dist = _readiness_distribution(user)

    # Alerts panel
    alert_qs = Alert.objects.filter(is_read=False).select_related("youth__user")
    if user.role == UserRole.COUNSELOR:
        alert_qs = alert_qs.filter(youth__assigned_counselor=user)
    recent_alerts = alert_qs.order_by(
        "-severity", "-created_at"
    )[:10]

    # Recent audit log
    audit_qs = AuditLog.objects.select_related("user").order_by("-timestamp")[:15]

    # Mentor overview
    mentors = MentorProfile.objects.select_related("user", "sector").all()
    month_start = today.replace(day=1)
    mentor_data = []
    for mp in mentors:
        sessions_month = MentorshipSession.objects.filter(
            mentor=mp.user, session_date__gte=month_start
        ).count()
        mentor_data.append({
            "profile": mp,
            "sessions_month": sessions_month,
        })

    # Governorate choices for filter
    from apps.youth.models import Governorate, EducationLevel
    sectors = CareerSector.objects.all()

    context = {
        "kpis": kpis,
        # Chart.js data (JSON)
        "chart_status_labels": json.dumps(list(youth_by_status.keys())),
        "chart_status_data": json.dumps(list(youth_by_status.values())),
        "chart_sector_labels": json.dumps([s["sector"] for s in top_sectors]),
        "chart_sector_data": json.dumps([s["count"] for s in top_sectors]),
        "chart_weeks_labels": json.dumps([w["week"] for w in sessions_by_week]),
        "chart_weeks_completed": json.dumps([w["completed"] for w in sessions_by_week]),
        "chart_weeks_missed": json.dumps([w["missed"] for w in sessions_by_week]),
        "chart_gov_labels": json.dumps([r["governorate"] for r in youth_by_gov]),
        "chart_gov_data": json.dumps([r["count"] for r in youth_by_gov]),
        "chart_readiness_labels": json.dumps(list(readiness_dist.keys())),
        "chart_readiness_data": json.dumps(list(readiness_dist.values())),
        # Panels
        "recent_alerts": recent_alerts,
        "audit_logs": audit_qs,
        "mentor_data": mentor_data,
        # Filters
        "sectors": sectors,
        "governorate_choices": Governorate.choices,
        "education_choices": EducationLevel.choices,
        "current_gov": gov_filter,
        "current_sector": sector_filter,
        "current_edu": edu_filter,
    }
    return render(request, "dashboard/monitoring.html", context)


# ─────────────────────────────────────────────────────────────────────────────
# CSV Export
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_or_admin_required
def export_youth_csv(request):
    user = request.user
    qs = _base_youth_qs(user).select_related(
        "user", "assigned_counselor", "assigned_mentor"
    ).prefetch_related("interests")

    # Apply same filters as dashboard
    gov = request.GET.get("governorate", "")
    sector = request.GET.get("sector", "")
    edu = request.GET.get("education_level", "")
    if gov:
        qs = qs.filter(governorate=gov)
    if sector:
        qs = qs.filter(interests__id=sector)
    if edu:
        qs = qs.filter(education_level=edu)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="youth_export.csv"'
    response.write("\ufeff")  # BOM for Excel

    writer = csv.writer(response)
    writer.writerow([
        "Nom", "Prénom", "Email", "Date de naissance", "Âge", "Genre",
        "Gouvernorat", "Niveau d'éducation", "Statut", "Score de préparation",
        "Secteurs d'intérêt", "Conseiller", "Mentor", "Date d'inscription",
    ])
    for p in qs:
        writer.writerow([
            p.user.last_name,
            p.user.first_name,
            p.user.email,
            p.date_of_birth.strftime("%d/%m/%Y") if p.date_of_birth else "",
            p.age or "",
            p.get_gender_display(),
            p.get_governorate_display(),
            p.get_education_level_display(),
            p.get_status_display(),
            p.readiness_score or 0,
            ", ".join(s.name for s in p.interests.all()),
            p.assigned_counselor.get_full_name() if p.assigned_counselor else "",
            p.assigned_mentor.get_full_name() if p.assigned_mentor else "",
            p.created_at.strftime("%d/%m/%Y"),
        ])
    return response


# ─────────────────────────────────────────────────────────────────────────────
# PDF Export
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@counselor_or_admin_required
def export_pdf(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    user = request.user
    today = date.today()
    month_start = today.replace(day=1)

    youth_qs = _base_youth_qs(user)
    kpis = _build_kpis(user)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"],
                                 fontSize=18, spaceAfter=6)
    h2_style = ParagraphStyle("h2", parent=styles["Heading2"],
                              fontSize=13, spaceAfter=4, spaceBefore=12)
    normal = styles["Normal"]

    story = []

    # Title
    story.append(Paragraph("CareerPathTN — Rapport de suivi", title_style))
    story.append(Paragraph(f"Généré le {today.strftime('%d/%m/%Y')} par {user.get_full_name() or user.username}", normal))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e63946")))
    story.append(Spacer(1, 0.4*cm))

    # KPI summary
    story.append(Paragraph("Indicateurs clés", h2_style))
    kpi_data = [
        ["Indicateur", "Valeur"],
        ["Jeunes actifs", str(kpis["active_youth"])],
        ["Alertes HIGH non lues", str(kpis["high_alerts"])],
        ["Séances manquées ce mois", str(kpis["missed_sessions_month"])],
        ["Plans expirant dans 7 jours", str(kpis["expiring_plans"])],
        ["Mentors disponibles", str(kpis["available_mentors"])],
        ["Parcours complétés ce mois", str(kpis["completed_month"])],
    ]
    kpi_table = Table(kpi_data, colWidths=[10*cm, 4*cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1f2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4*cm))

    # Youth by status
    story.append(Paragraph("Répartition des jeunes par statut", h2_style))
    status_data = [["Statut", "Nombre"]]
    for value, label in YouthStatus.choices:
        count = youth_qs.filter(status=value).count()
        status_data.append([label, str(count)])
    st = Table(status_data, colWidths=[10*cm, 4*cm])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(st)
    story.append(Spacer(1, 0.4*cm))

    # Top sectors
    story.append(Paragraph("Top secteurs demandés", h2_style))
    top = _top_sectors(user)
    sec_data = [["Secteur", "Nombre de jeunes"]] + [[s["sector"], str(s["count"])] for s in top]
    sec_table = Table(sec_data, colWidths=[10*cm, 4*cm])
    sec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#198754")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sec_table)
    story.append(Spacer(1, 0.4*cm))

    # Alert summary
    story.append(Paragraph("Résumé des alertes", h2_style))
    alert_qs = Alert.objects.all()
    if user.role == UserRole.COUNSELOR:
        alert_qs = alert_qs.filter(youth__assigned_counselor=user)
    alert_data = [["Type", "Sévérité", "Non lues"]]
    from apps.alerts.models import AlertType
    for val, label in AlertType.choices:
        unread = alert_qs.filter(alert_type=val, is_read=False).count()
        sev = alert_qs.filter(alert_type=val).values_list("severity", flat=True).first() or ""
        alert_data.append([label, sev, str(unread)])
    at = Table(alert_data, colWidths=[8*cm, 3*cm, 3*cm])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dc3545")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(at)
    story.append(Spacer(1, 0.4*cm))

    # Mentor activity
    story.append(Paragraph("Activité des mentors", h2_style))
    mentor_rows = [["Mentor", "Secteur", "Jeunes", "Séances ce mois", "Dispo"]]
    for mp in MentorProfile.objects.select_related("user", "sector").all():
        sm = MentorshipSession.objects.filter(
            mentor=mp.user, session_date__gte=month_start
        ).count()
        mentor_rows.append([
            mp.user.get_full_name() or mp.user.username,
            str(mp.sector) if mp.sector else "",
            f"{mp.current_youth_count}/{mp.max_youth_capacity}",
            str(sm),
            mp.get_availability_display(),
        ])
    mt = Table(mentor_rows, colWidths=[5*cm, 3*cm, 2*cm, 3*cm, 3*cm])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6f42c1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(mt)

    doc.build(story)
    buf.seek(0)
    response = HttpResponse(buf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="rapport_careerpathtn_{today}.pdf"'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Role dashboards (unchanged logic, updated templates)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def dashboard_redirect(request):
    role_urls = {
        UserRole.ADMIN: "dashboard:admin",
        UserRole.COUNSELOR: "dashboard:counselor",
        UserRole.MENTOR: "dashboard:mentor",
        UserRole.YOUTH: "dashboard:youth",
    }
    url_name = role_urls.get(request.user.role)
    if url_name:
        return redirect(url_name)
    raise PermissionDenied


@login_required
@admin_required
def admin_dashboard(request):
    context = {
        "total_youth": YouthProfile.objects.count(),
        "active_plans": ActionPlan.objects.filter(status=ActionPlanStatus.ACTIVE).count(),
        "completed_sessions": MentorshipSession.objects.filter(status=SessionStatus.COMPLETED).count(),
        "unread_alerts": Alert.objects.filter(is_read=False).count(),
        "youth_by_status": [
            (label, YouthProfile.objects.filter(status=value).count())
            for value, label in YouthStatus.choices
        ],
        "recent_alerts": Alert.objects.select_related("youth__user").order_by("-created_at")[:10],
    }
    return render(request, "dashboard/admin_dashboard.html", context)


@login_required
@counselor_required
def counselor_dashboard(request):
    user = request.user
    assigned_youth = YouthProfile.objects.filter(
        assigned_counselor=user
    ).select_related("user", "assigned_mentor").order_by("-readiness_score")
    context = {
        "assigned_youth": assigned_youth[:10],
        "total_assigned": assigned_youth.count(),
        "pending_plans": ActionPlan.objects.filter(created_by=user, status=ActionPlanStatus.DRAFT).count(),
        "active_plans": ActionPlan.objects.filter(created_by=user, status=ActionPlanStatus.ACTIVE).count(),
        "unread_alerts": Alert.objects.filter(youth__assigned_counselor=user, is_read=False).count(),
        "recent_alerts": Alert.objects.filter(youth__assigned_counselor=user).order_by("-created_at")[:5],
    }
    return render(request, "dashboard/counselor_dashboard.html", context)


@login_required
@mentor_required
def mentor_dashboard(request):
    user = request.user
    sessions = MentorshipSession.objects.filter(mentor=user).select_related("youth__user")
    context = {
        "upcoming_sessions": sessions.filter(status=SessionStatus.SCHEDULED).count(),
        "completed_sessions": sessions.filter(status=SessionStatus.COMPLETED).count(),
        "missed_sessions": sessions.filter(status=SessionStatus.MISSED).count(),
        "recent_sessions": sessions.order_by("-session_date")[:5],
        "assigned_youth": YouthProfile.objects.filter(assigned_mentor=user).select_related("user"),
    }
    return render(request, "dashboard/mentor_dashboard.html", context)


@login_required
@youth_required
def youth_dashboard(request):
    user = request.user
    try:
        profile = user.youth_profile
        from apps.youth.services import compute_readiness_score
        score, breakdown = compute_readiness_score(profile)
        plans = profile.action_plans.filter(
            status__in=[ActionPlanStatus.ACTIVE, ActionPlanStatus.VALIDATED]
        ).select_related("target_sector")
        sessions = profile.mentorship_sessions.order_by("-session_date")[:5]
    except Exception:
        profile = None
        score = 0
        breakdown = {}
        plans = []
        sessions = []
    return render(request, "dashboard/youth_dashboard.html", {
        "profile": profile,
        "readiness_score": score,
        "score_breakdown": breakdown,
        "plans": plans,
        "recent_sessions": sessions,
    })
