"""
guidance/api_views.py
"""
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import UserRole, AuditLog
from apps.accounts.permissions import IsCounselorOrAdmin
from apps.accounts.utils import get_client_ip
from apps.guidance.models import ActionPlan, ActionPlanStatus
from apps.guidance.serializers import ActionPlanSerializer


class ActionPlanListView(ListCreateAPIView):
    serializer_class = ActionPlanSerializer
    permission_classes = [IsCounselorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.COUNSELOR:
            return ActionPlan.objects.filter(created_by=user)
        return ActionPlan.objects.all()

    def perform_create(self, serializer):
        plan = serializer.save(created_by=self.request.user)
        AuditLog.objects.create(
            user=self.request.user, action="CREATE_PLAN",
            target_model="ActionPlan", target_id=str(plan.pk),
            result=AuditLog.Result.SUCCESS,
            ip_address=get_client_ip(self.request),
        )


class ActionPlanDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ActionPlanSerializer
    permission_classes = [IsCounselorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.COUNSELOR:
            return ActionPlan.objects.filter(created_by=user)
        return ActionPlan.objects.all()

    def perform_update(self, serializer):
        plan = serializer.save()
        if plan.status == ActionPlanStatus.VALIDATED and not plan.validated_at:
            ActionPlan.objects.filter(pk=plan.pk).update(
                validated_by=self.request.user,
                validated_at=timezone.now(),
            )
        AuditLog.objects.create(
            user=self.request.user,
            action="VALIDATE_PLAN" if plan.status == ActionPlanStatus.VALIDATED else "UPDATE_PLAN",
            target_model="ActionPlan", target_id=str(plan.pk),
            result=AuditLog.Result.SUCCESS,
            ip_address=get_client_ip(self.request),
        )
