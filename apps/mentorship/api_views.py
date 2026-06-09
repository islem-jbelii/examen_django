"""
mentorship/api_views.py
"""
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import UserRole, AuditLog
from apps.accounts.permissions import IsMentorOrCounselorOrAdmin, IsAdmin
from apps.accounts.utils import get_client_ip
from apps.mentorship.models import MentorProfile, MentorshipSession
from apps.mentorship.serializers import MentorProfileSerializer, MentorshipSessionSerializer


class MentorProfileListView(ListCreateAPIView):
    serializer_class = MentorProfileSerializer
    permission_classes = [IsAuthenticated]
    queryset = MentorProfile.objects.select_related("user", "sector").all()


class MentorProfileDetailView(RetrieveUpdateAPIView):
    serializer_class = MentorProfileSerializer
    queryset = MentorProfile.objects.all()
    permission_classes = [IsAuthenticated]


class MentorshipSessionListView(ListCreateAPIView):
    serializer_class = MentorshipSessionSerializer
    permission_classes = [IsMentorOrCounselorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.MENTOR:
            return MentorshipSession.objects.filter(mentor=user)
        elif user.role == UserRole.COUNSELOR:
            return MentorshipSession.objects.filter(youth__assigned_counselor=user)
        return MentorshipSession.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        youth = serializer.validated_data.get("youth")
        if user.role == UserRole.MENTOR and youth.assigned_mentor != user:
            AuditLog.objects.create(
                user=user, action="ACCESS_DENIED",
                target_model="YouthProfile", target_id=str(youth.pk),
                result=AuditLog.Result.FAILURE,
                reason="Mentor not assigned",
                ip_address=get_client_ip(self.request),
            )
            raise PermissionDenied({
                "error": "PERMISSION_DENIED",
                "message": "Vous n'êtes pas assigné à ce jeune.",
                "field": "youth",
            })
        session = serializer.save()
        AuditLog.objects.create(
            user=user, action="CREATE_SESSION",
            target_model="MentorshipSession", target_id=str(session.pk),
            result=AuditLog.Result.SUCCESS,
            ip_address=get_client_ip(self.request),
        )


class MentorshipSessionDetailView(RetrieveUpdateAPIView):
    serializer_class = MentorshipSessionSerializer
    permission_classes = [IsMentorOrCounselorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.MENTOR:
            return MentorshipSession.objects.filter(mentor=user)
        elif user.role == UserRole.COUNSELOR:
            return MentorshipSession.objects.filter(youth__assigned_counselor=user)
        return MentorshipSession.objects.all()
