"""
accounts/context_processors.py — Inject unread alert count into every template.
"""
from apps.accounts.models import UserRole


def unread_alerts(request):
    """Add unread_alert_count to every template context."""
    count = 0
    if request.user.is_authenticated and request.user.role in (UserRole.COUNSELOR, UserRole.ADMIN):
        try:
            from apps.alerts.models import Alert
            if request.user.role == UserRole.COUNSELOR:
                count = Alert.objects.filter(
                    youth__assigned_counselor=request.user, is_read=False
                ).count()
            else:
                count = Alert.objects.filter(is_read=False).count()
        except Exception:
            count = 0
    return {"unread_alert_count": count}
