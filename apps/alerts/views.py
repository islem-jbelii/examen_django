"""
alerts/views.py
"""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

from apps.accounts.models import UserRole
from apps.alerts.models import Alert, AlertType, AlertSeverity


@login_required
def alert_list(request):
    user = request.user
    if user.role == UserRole.COUNSELOR:
        alerts = Alert.objects.filter(
            youth__assigned_counselor=user
        ).select_related("youth__user")
    elif user.role == UserRole.ADMIN:
        alerts = Alert.objects.select_related("youth__user").all()
    else:
        raise PermissionDenied

    # Filters
    type_filter = request.GET.get("alert_type", "")
    severity_filter = request.GET.get("severity", "")
    read_filter = request.GET.get("is_read", "")

    if type_filter:
        alerts = alerts.filter(alert_type=type_filter)
    if severity_filter:
        alerts = alerts.filter(severity=severity_filter)
    if read_filter == "0":
        alerts = alerts.filter(is_read=False)
    elif read_filter == "1":
        alerts = alerts.filter(is_read=True)

    alerts = alerts.order_by("-created_at")
    paginator = Paginator(alerts, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "alerts/list.html", {
        "page_obj": page,
        "alerts": page.object_list,
        "type_choices": AlertType.choices,
        "severity_choices": AlertSeverity.choices,
        "current_type": type_filter,
        "current_severity": severity_filter,
        "current_read": read_filter,
        "unread_total": Alert.objects.filter(
            **({} if user.role == UserRole.ADMIN else {"youth__assigned_counselor": user}),
            is_read=False
        ).count(),
    })


@login_required
def alert_mark_read(request, pk):
    user = request.user
    alert = get_object_or_404(Alert, pk=pk)

    if user.role == UserRole.COUNSELOR and alert.youth.assigned_counselor != user:
        raise PermissionDenied
    elif user.role not in (UserRole.COUNSELOR, UserRole.ADMIN):
        raise PermissionDenied

    alert.is_read = True
    alert.save(update_fields=["is_read"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})
    return redirect("alerts:alert-list")


@login_required
def alert_mark_all_read(request):
    user = request.user
    if user.role == UserRole.COUNSELOR:
        Alert.objects.filter(youth__assigned_counselor=user, is_read=False).update(is_read=True)
    elif user.role == UserRole.ADMIN:
        Alert.objects.filter(is_read=False).update(is_read=True)
    else:
        raise PermissionDenied
    return redirect("alerts:alert-list")
