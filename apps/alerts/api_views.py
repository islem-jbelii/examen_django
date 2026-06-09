"""
alerts/api_views.py
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import UserRole
from apps.accounts.permissions import IsCounselorOrAdmin
from apps.alerts.models import Alert
from apps.alerts.serializers import AlertSerializer
from apps.alerts.services import run_all_checks
from apps.youth.models import YouthProfile


class AlertListView(ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [IsCounselorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = Alert.objects.filter(is_read=False)
        if user.role == UserRole.COUNSELOR:
            return qs.filter(youth__assigned_counselor=user)
        return qs


@api_view(["POST"])
@permission_classes([IsCounselorOrAdmin])
def alert_mark_read(request, pk):
    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return Response({"error": "NOT_FOUND", "message": "Alerte introuvable.", "field": None}, status=404)
    user = request.user
    if user.role == UserRole.COUNSELOR and alert.youth.assigned_counselor != user:
        raise PermissionDenied({"error": "PERMISSION_DENIED", "message": "Accès refusé.", "field": None})
    alert.is_read = True
    alert.save(update_fields=["is_read"])
    return Response({"status": "ok"})


@api_view(["POST"])
@permission_classes([IsCounselorOrAdmin])
def run_alert_checks(request, youth_pk):
    try:
        youth = YouthProfile.objects.get(pk=youth_pk)
    except YouthProfile.DoesNotExist:
        return Response({"error": "NOT_FOUND", "message": "Profil introuvable.", "field": None}, status=404)
    run_all_checks(youth)
    return Response({"status": "Vérifications effectuées."})
