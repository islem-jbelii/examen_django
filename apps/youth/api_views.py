"""
youth/api_views.py — REST API views with role-scoped access.
"""
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import UserRole
from apps.accounts.permissions import IsCounselorOrAdmin
from apps.youth.models import YouthProfile, InterestAssessment
from apps.youth.serializers import YouthProfileSerializer, InterestAssessmentSerializer


class YouthProfileListView(ListCreateAPIView):
    serializer_class = YouthProfileSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCounselorOrAdmin()]
        return [IsCounselorOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.COUNSELOR:
            return YouthProfile.objects.filter(assigned_counselor=user).select_related("user")
        return YouthProfile.objects.select_related("user").all()


class YouthProfileDetailView(RetrieveUpdateAPIView):
    serializer_class = YouthProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return YouthProfile.objects.select_related("user").all()

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        if user.role == UserRole.YOUTH:
            if not hasattr(user, "youth_profile") or user.youth_profile.pk != obj.pk:
                raise PermissionDenied({
                    "error": "PERMISSION_DENIED",
                    "message": "Vous ne pouvez consulter que votre propre profil.",
                    "field": None,
                })
        elif user.role == UserRole.COUNSELOR:
            if obj.assigned_counselor != user:
                raise PermissionDenied({
                    "error": "PERMISSION_DENIED",
                    "message": "Ce jeune ne vous est pas assigné.",
                    "field": None,
                })
        elif user.role == UserRole.MENTOR:
            if obj.assigned_mentor != user:
                raise PermissionDenied({
                    "error": "PERMISSION_DENIED",
                    "message": "Ce jeune ne vous est pas assigné.",
                    "field": None,
                })
        return obj


class InterestAssessmentListView(ListCreateAPIView):
    serializer_class = InterestAssessmentSerializer
    permission_classes = [IsCounselorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.COUNSELOR:
            return InterestAssessment.objects.filter(conducted_by=user)
        return InterestAssessment.objects.all()


class InterestAssessmentDetailView(RetrieveUpdateAPIView):
    serializer_class = InterestAssessmentSerializer
    permission_classes = [IsCounselorOrAdmin]
    queryset = InterestAssessment.objects.all()
