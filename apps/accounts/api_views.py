"""
accounts/api_views.py — DRF API views
"""
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import AuditLog
from apps.accounts.permissions import IsAdmin
from apps.accounts.serializers import UserSerializer, AuditLogSerializer


class CurrentUserView(RetrieveAPIView):
    """Return the currently authenticated user's data."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AuditLogListView(ListAPIView):
    """List audit logs — Admin only."""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    queryset = AuditLog.objects.select_related("user").all()
