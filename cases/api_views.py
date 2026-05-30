"""API views DRF pour l'app `cases`.

Contient les permissions personnalisées et les vues API demandées.
Chaque action importante est enregistrée dans `AuditLog`.
"""
from __future__ import annotations

from typing import Any, Dict

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, views, status
from rest_framework.decorators import api_view
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from core.models import AuditLog
from .models import Student, Case, CaseEvent, Alert, HealthRecord, RiskThreshold
from .serializers import (
    StudentSerializer,
    CaseSerializer,
    CaseListSerializer,
    CaseEventSerializer,
    AlertSerializer,
    HealthRecordSerializer,
    RiskThresholdSerializer,
    CaseTransitionSerializer,
    DashboardStatsSerializer,
)
from .services import RiskAssessmentService, HealthFollowUpService


class IsAuthenticatedWithProfile(BasePermission):
    """Vérifie que l'utilisateur est authentifié et possède un `profile`."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and hasattr(user, 'profile'))


class IsSupervisorOrAdmin(IsAuthenticatedWithProfile):
    """Autorise uniquement les SUPERVISOR et ADMIN."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        role = getattr(request.user.profile, 'role', None)
        return role in {request.user.profile.ROLE_SUPERVISOR if hasattr(request.user.profile, 'ROLE_SUPERVISOR') else 'SUPERVISOR',
                        request.user.profile.ROLE_ADMIN if hasattr(request.user.profile, 'ROLE_ADMIN') else 'ADMIN'}


class StudentListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création d'étudiants. Filtres: `region`, `search`."""

    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticatedWithProfile]

    def get_queryset(self):
        qs = super().get_queryset()
        region = self.request.GET.get('region')
        search = self.request.GET.get('search')
        if region:
            qs = qs.filter(region=region)
        if search:
            qs = qs.filter(first_name__icontains=search) | qs.filter(last_name__icontains=search) | qs.filter(student_code__icontains=search)
        return qs

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        AuditLog.log(user=self.request.user, action=AuditLog.ACTION_CREATE, description=f"Student créé: {obj.pk}", model_name='Student', object_id=str(obj.pk), success=True)


class StudentDetailAPIView(generics.RetrieveUpdateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticatedWithProfile]


class CaseListCreateAPIView(generics.ListCreateAPIView):
    """Liste et création de dossiers. GET -> CaseListSerializer; POST -> CaseSerializer."""

    queryset = Case.objects.select_related('student').all()
    permission_classes = [IsAuthenticatedWithProfile]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CaseListSerializer
        return CaseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_q = self.request.GET.get('status')
        risk = self.request.GET.get('risk_level')
        case_type = self.request.GET.get('case_type')
        student_code = self.request.GET.get('student_code')
        if status_q:
            qs = qs.filter(status=status_q)
        if risk and any(f.name == 'risk_level' for f in Case._meta.get_fields()):
            qs = qs.filter(risk_level=risk)
        if case_type and any(f.name == 'case_type' for f in Case._meta.get_fields()):
            qs = qs.filter(case_type=case_type)
        if student_code:
            qs = qs.filter(student__student_code=student_code)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance

        # Évaluer le risque après création
        assessment = RiskAssessmentService.assess_case(instance, request.user)

        headers = self.get_success_headers(serializer.data)
        data = serializer.data
        data['_assessment'] = {
            'risk_level': assessment.get('risk_level'),
            'explanation': assessment.get('explanation'),
        }
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        AuditLog.log(user=self.request.user, action=AuditLog.ACTION_CREATE, description=f"Case créé", model_name='Case', object_id=str(serializer.instance.pk), success=True)


class CaseDetailAPIView(generics.RetrieveUpdateAPIView):
    queryset = Case.objects.all()
    serializer_class = CaseSerializer
    permission_classes = [IsAuthenticatedWithProfile]

    def get_queryset(self):
        return super().get_queryset().prefetch_related('events', 'alerts', 'student__health_records')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        AuditLog.log(user=request.user, action=AuditLog.ACTION_ACCESS_DENIED if False else AuditLog.ACTION_ACCESS_DENIED if False else AuditLog.ACTION_ALERT, description=f"Consultation dossier {instance.pk}", model_name='Case', object_id=str(instance.pk), success=True)
        # Above: minimal audit; success True
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CaseTransitionAPIView(views.APIView):
    permission_classes = [IsSupervisorOrAdmin]

    def post(self, request, pk):
        case = get_object_or_404(Case, pk=pk)
        serializer = CaseTransitionSerializer(data=request.data)
        if not serializer.is_valid():
            AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Transition invalide payload pour {case.pk}", model_name='Case', object_id=str(case.pk), success=False, reason=str(serializer.errors))
            return Response({'detail': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['new_status']
        reason = serializer.validated_data['reason']
        try:
            case.transition_to(new_status, user=request.user, reason=reason)
            AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Transition effectuée {case.pk}: {new_status}", model_name='Case', object_id=str(case.pk), success=True)
            return Response({'case': CaseSerializer(case).data, 'transition': {'from': case.status, 'to': new_status}, 'message': 'Transition effectuée.'})
        except DjangoValidationError as e:
            allowed = Case.VALID_TRANSITIONS.get(case.status, [])
            AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Échec transition {case.pk}", model_name='Case', object_id=str(case.pk), success=False, reason=str(e))
            return Response({'error': str(e), 'current_status': case.status, 'allowed_transitions': allowed}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Erreur transition {case.pk}", model_name='Case', object_id=str(case.pk), success=False, reason=str(e))
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CaseAssessAPIView(views.APIView):
    permission_classes = [IsAuthenticatedWithProfile]

    def post(self, request, pk):
        case = get_object_or_404(Case, pk=pk)
        result = RiskAssessmentService.assess_case(case, request.user)
        AuditLog.log(user=request.user, action=AuditLog.ACTION_ALERT, description=f"Évaluation risque API pour {case.pk}", model_name='Case', object_id=str(case.pk), success=True)
        # inclure recommendation si présent
        recommendation = getattr(case, 'recommendation', None)
        return Response({**result, 'recommendation': recommendation})


class HealthRecordCreateAPIView(generics.CreateAPIView):
    serializer_class = HealthRecordSerializer
    permission_classes = [IsAuthenticatedWithProfile]

    def perform_create(self, serializer):
        case_pk = self.kwargs.get('case_pk')
        case = get_object_or_404(Case, pk=case_pk)
        instance = serializer.save(student=case.student, created_by=self.request.user)
        AuditLog.log(user=self.request.user, action=AuditLog.ACTION_CREATE, description=f"HealthRecord créé {instance.pk}", model_name='HealthRecord', object_id=str(instance.pk), success=True)
        if instance.status == HealthRecord.STATUS_MIS:
            HealthFollowUpService.check_missed_sessions(case, self.request.user)


class AlertListAPIView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticatedWithProfile]

    def get_queryset(self):
        qs = Alert.objects.all()
        active_only = self.request.GET.get('active_only', 'true').lower() != 'false'
        severity = self.request.GET.get('severity')
        if active_only:
            qs = qs.filter(active=True)
        if severity:
            qs = qs.filter(level=severity)
        return qs


class AlertResolveAPIView(views.APIView):
    permission_classes = [IsSupervisorOrAdmin]

    def post(self, request, pk):
        alert = get_object_or_404(Alert, pk=pk)
        # vérifier état
        already_resolved = False
        if hasattr(alert, 'is_resolved'):
            already_resolved = bool(alert.is_resolved)
        else:
            already_resolved = not bool(alert.active)

        if already_resolved:
            AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Tentative résolution alerte déjà résolue {alert.pk}", model_name='Alert', object_id=str(alert.pk), success=False)
            return Response({'detail': 'Alerte déjà résolue.'}, status=status.HTTP_400_BAD_REQUEST)

        # Marquer résolu
        if hasattr(alert, 'is_resolved'):
            alert.is_resolved = True
        alert.active = False
        if hasattr(alert, 'resolved_by'):
            alert.resolved_by = request.user
        if hasattr(alert, 'resolved_at'):
            alert.resolved_at = timezone.now()
        alert.save()

        if alert.case:
            CaseEvent.objects.create(case=alert.case, user=request.user, from_status=alert.case.status, to_status=alert.case.status, reason=f"Alerte résolue API: {alert.pk}")

        AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Alerte résolue: {alert.pk}", model_name='Alert', object_id=str(alert.pk), success=True)
        return Response({'detail': 'Alerte résolue.'})


class RiskThresholdListCreateAPIView(generics.ListCreateAPIView):
    queryset = RiskThreshold.objects.all()
    serializer_class = RiskThresholdSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticatedWithProfile()]
        return [IsSupervisorOrAdmin()]

    def perform_create(self, serializer):
        thr = serializer.save(created_by=self.request.user)
        AuditLog.log(user=self.request.user, action=AuditLog.ACTION_CREATE, description=f"RiskThreshold créé: {thr.pk}", model_name='RiskThreshold', object_id=str(thr.pk), success=True)


@api_view(['GET'])
def dashboard_stats(request):
    """Retourne des KPIs pour le tableau de bord."""
    total_cases = Case.objects.count()
    total_students = Student.objects.count()
    cases_by_status_qs = Case.objects.values('status').annotate(count=Count('id'))
    cases_by_status = {item['status']: item['count'] for item in cases_by_status_qs}
    if any(f.name == 'risk_level' for f in Case._meta.get_fields()):
        cases_by_risk_qs = Case.objects.values('risk_level').annotate(count=Count('id'))
        cases_by_risk = {item['risk_level'] or 'UNKNOWN': item['count'] for item in cases_by_risk_qs}
    else:
        cases_by_risk = {}

    active_alerts = Alert.objects.filter(active=True).count()
    critical_alerts = Alert.objects.filter(active=True, level=Alert.LEVEL_CRITICAL).count()
    completion_rate = (Case.objects.filter(status=Case.STATUS_CLOSED).count() / total_cases) if total_cases else 0.0

    data = {
        'total_cases': total_cases,
        'total_students': total_students,
        'cases_by_status': cases_by_status,
        'cases_by_risk': cases_by_risk,
        'active_alerts_count': active_alerts,
        'critical_alerts_count': critical_alerts,
        'completion_rate': float(completion_rate),
    }

    AuditLog.log(user=request.user if request.user.is_authenticated else None, action=AuditLog.ACTION_ACCESS_DENIED if False else AuditLog.ACTION_ACCESS_DENIED if False else AuditLog.ACTION_ALERT, description='Récupération dashboard stats', model_name='Dashboard', object_id=None, success=True)
    serializer = DashboardStatsSerializer(data)
    return Response(serializer.data)
