"""Vues pour l'app `cases`.

Contient:
- le décorateur `require_role(min_role)` pour contrôler l'accès par rôle
- vues CRUD et actions métier demandées dans la spécification.
"""
from __future__ import annotations

import csv
import io
from functools import wraps
from typing import Callable, Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from core.models import AuditLog
from .models import Case, Alert, CaseEvent, RiskThreshold, HealthRecord, Student
from .forms import (
    CaseForm,
    CaseTransitionForm,
    HealthRecordForm,
    RiskThresholdForm,
    CSVImportForm,
)
from .services import RiskAssessmentService, HealthFollowUpService, CSVImportService


ROLE_ORDER = {
    'OPERATOR': 0,
    'SUPERVISOR': 1,
    'ADMIN': 2,
}


def require_role(min_role: str) -> Callable:
    """Décorateur vérifiant que l'utilisateur a au moins `min_role`.

    Si l'accès est refusé, on loggue l'événement, on affiche un message
    d'erreur et on redirige vers `/dashboard/`.
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            profile = getattr(user, 'profile', None)
            actual_role = getattr(profile, 'role', None) if profile else None

            required_rank = ROLE_ORDER.get(min_role, 999)
            actual_rank = ROLE_ORDER.get(actual_role, -1)

            if actual_rank < required_rank:
                reason = f"Accès refusé: rôle requis={min_role}, rôle actuel={actual_role}"
                AuditLog.log(user=user if user.is_authenticated else None,
                             action=AuditLog.ACTION_ACCESS_DENIED,
                             description=f"Tentative d'accès à {request.path}",
                             model_name=view_func.__name__,
                             object_id=None,
                             success=False,
                             reason=reason)
                messages.error(request, 'Accès refusé: privilèges insuffisants.')
                return redirect('/dashboard/')

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


@login_required
def case_list(request):
    qs = Case.objects.select_related('student').all()

    status = request.GET.get('status')
    risk_level = request.GET.get('risk_level')
    case_type = request.GET.get('case_type')
    search = request.GET.get('search')

    # Filtres simples
    if status:
        qs = qs.filter(status=status)

    # Certains champs peuvent ne pas exister sur le modèle ; on vérifie
    case_fields = {f.name for f in Case._meta.get_fields()}
    if 'risk_level' in case_fields and risk_level:
        qs = qs.filter(risk_level=risk_level)
    if 'case_type' in case_fields and case_type:
        qs = qs.filter(case_type=case_type)

    if search:
        qs = qs.filter(
            student__first_name__icontains=search,
        ) | qs.filter(student__student_code__icontains=search)

    status_choices = Case.STATUS_CHOICES
    # risk choices à présenter: on récupère depuis RiskThreshold si disponible
    risk_choices = getattr(RiskThreshold, 'RISK_CHOICES', [])
    type_choices = []
    if 'case_type' in case_fields:
        type_choices = Case.objects.values_list('case_type', flat=True).distinct()

    current_filters = {'status': status, 'risk_level': risk_level, 'case_type': case_type, 'search': search}

    context = {
        'cases': qs,
        'status_choices': status_choices,
        'risk_choices': risk_choices,
        'type_choices': type_choices,
        'current_filters': current_filters,
    }
    return render(request, 'cases/case_list.html', context)


@login_required
def case_detail(request, pk):
    case = get_object_or_404(Case, pk=pk)
    events = case.events.all()
    alerts = case.alerts.filter(active=True)
    health_records = case.student.health_records.all()

    available_transitions = Case.VALID_TRANSITIONS.get(case.status, [])

    context = {
        'case': case,
        'events': events,
        'alerts': alerts,
        'health_records': health_records,
        'available_transitions': available_transitions,
    }
    return render(request, 'cases/case_detail.html', context)


@login_required
def case_modal(request, pk):
    """Return an HTML partial for a case suitable for loading into the dashboard modal."""
    case = get_object_or_404(Case, pk=pk)
    events = case.events.all()[:6]
    alerts = case.alerts.filter(active=True)[:6]
    health_records = case.student.health_records.all()[:6]
    context = {
        'case': case,
        'events': events,
        'alerts': alerts,
        'health_records': health_records,
    }
    return render(request, 'cases/partials/case_modal.html', context)


@login_required
def case_create(request):
    if request.method == 'POST':
        form = CaseForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            case.created_by = request.user
            case.save()
            CaseEvent.objects.create(
                case=case,
                user=request.user,
                from_status=None,
                to_status=case.status,
                reason='Dossier créé',
            )

            AuditLog.log(user=request.user, action=AuditLog.ACTION_CREATE, description=f"Dossier {case.pk} créé", model_name='Case', object_id=str(case.pk), success=True)

            # Évaluer le risque
            result = RiskAssessmentService.assess_case(case, request.user)
            messages.success(request, f"Dossier créé. Niveau de risque: {result.get('risk_level')}")
            return redirect('case_detail', pk=case.pk)
        else:
            messages.error(request, 'Le formulaire contient des erreurs.')
    else:
        form = CaseForm()

    return render(request, 'cases/case_form.html', {'form': form})


@login_required
@require_role('SUPERVISOR')
def case_transition(request, pk):
    case = get_object_or_404(Case, pk=pk)

    if request.method == 'POST':
        form = CaseTransitionForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['new_status']
            reason = form.cleaned_data['reason']
            recommendation = form.cleaned_data.get('recommendation')
            recommendation_explanation = form.cleaned_data.get('recommendation_explanation')
            try:
                case.transition_to(new_status, user=request.user, reason=reason)

                # Sauvegarder recommandation si fournie
                if recommendation:
                    if hasattr(case, 'recommendation'):
                        case.recommendation = recommendation
                    if hasattr(case, 'recommendation_explanation'):
                        case.recommendation_explanation = recommendation_explanation
                    case.save()

                AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Transition {case.pk}: {new_status}", model_name='Case', object_id=str(case.pk), success=True)
                messages.success(request, 'Transition effectuée avec succès.')
                return redirect('case_detail', pk=case.pk)
            except Exception as e:
                # ValidationError attendu pour transition invalide
                AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Échec transition {case.pk}", model_name='Case', object_id=str(case.pk), success=False, reason=str(e))
                messages.error(request, f"Erreur de transition : {e}")
    else:
        form = CaseTransitionForm()

    return render(request, 'cases/case_transition.html', {'form': form, 'case': case})


@login_required
def health_record_create(request, case_pk):
    case = get_object_or_404(Case, pk=case_pk)
    if request.method == 'POST':
        form = HealthRecordForm(request.POST)
        if form.is_valid():
            hr = form.save(commit=False)
            hr.student = case.student
            hr.created_by = request.user
            hr.save()

            CaseEvent.objects.create(case=case, user=request.user, from_status=case.status, to_status=case.status, reason=f"Séance ajoutée: {hr.status}")

            AuditLog.log(user=request.user, action=AuditLog.ACTION_CREATE, description=f"HealthRecord créé pour dossier {case.pk}", model_name='HealthRecord', object_id=str(hr.pk), success=True)

            if hr.status == HealthRecord.STATUS_MIS:
                alerts = HealthFollowUpService.check_missed_sessions(case, request.user)
                if alerts:
                    messages.warning(request, f"{len(alerts)} alerte(s) créées suite aux séances manquées.")
            messages.success(request, 'Séance enregistrée.')
            return redirect('case_detail', pk=case.pk)
        else:
            messages.error(request, 'Le formulaire contient des erreurs.')
    else:
        form = HealthRecordForm()

    return render(request, 'cases/health_record_form.html', {'form': form, 'case': case})


@login_required
@require_role('SUPERVISOR')
def risk_threshold_list(request):
    if request.method == 'POST':
        form = RiskThresholdForm(request.POST)
        if form.is_valid():
            thr = form.save(commit=False)
            thr.created_by = request.user
            thr.save()
            AuditLog.log(user=request.user, action=AuditLog.ACTION_CREATE, description=f"Seuil créé: {thr.pk}", model_name='RiskThreshold', object_id=str(thr.pk), success=True)
            messages.success(request, 'Seuil créé.')
            return redirect('risk_threshold_list')
        else:
            messages.error(request, 'Le formulaire contient des erreurs.')
    else:
        form = RiskThresholdForm()

    thresholds = RiskThreshold.objects.all()
    return render(request, 'cases/risk_threshold_list.html', {'thresholds': thresholds, 'form': form})


@login_required
@require_role('SUPERVISOR')
def alert_resolve(request, alert_pk):
    if request.method != 'POST':
        messages.error(request, 'Méthode non autorisée.')
        return redirect('/dashboard/')

    alert = get_object_or_404(Alert, pk=alert_pk)
    # Marquer comme résolu; le modèle utilise `active` pour l'état
    alert.active = False
    if hasattr(alert, 'is_resolved'):
        alert.is_resolved = True
    if hasattr(alert, 'resolved_by'):
        alert.resolved_by = request.user
    if hasattr(alert, 'resolved_at'):
        alert.resolved_at = timezone.now()
    alert.save()

    CaseEvent.objects.create(case=alert.case, user=request.user, from_status=alert.case.status, to_status=alert.case.status, reason=f"Alerte résolue: {alert.pk}")
    AuditLog.log(user=request.user, action=AuditLog.ACTION_UPDATE, description=f"Alerte résolue: {alert.pk}", model_name='Alert', object_id=str(alert.pk), success=True)
    messages.success(request, 'Alerte marquée comme résolue.')
    return redirect('case_detail', pk=alert.case.pk if alert.case else 'dashboard')


@login_required
def csv_import(request):
    report = None
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data['csv_file']
            import_type = form.cleaned_data['import_type']
            dry_run = form.cleaned_data.get('dry_run', True)
            try:
                content = f.read().decode('utf-8')
            except Exception:
                content = f.read().decode('latin-1')

            try:
                report = CSVImportService.validate_and_import(content, import_type, request.user, dry_run=dry_run)
                messages.success(request, f"Import terminé (dry_run={dry_run}).")
            except ValidationError as e:
                messages.error(request, f"Erreur d'import: {e}")
        else:
            messages.error(request, 'Le formulaire contient des erreurs.')
    else:
        form = CSVImportForm()

    return render(request, 'cases/csv_import.html', {'form': form, 'report': report})


@login_required
def export_cases_csv(request):
    qs = Case.objects.select_related('student').all()
    status = request.GET.get('status')
    risk = request.GET.get('risk')
    if status:
        qs = qs.filter(status=status)
    if risk and 'risk_level' in {f.name for f in Case._meta.get_fields()}:
        qs = qs.filter(risk_level=risk)

    # Préparer la réponse CSV avec BOM UTF-8 pour compatibilité Excel
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['student_code', 'first_name', 'last_name', 'status', 'risk_level', 'absences', 'grade_avg'])
    for c in qs:
        writer.writerow([
            c.student.student_code,
            c.student.first_name,
            c.student.last_name,
            c.status,
            getattr(c, 'risk_level', ''),
            getattr(c, 'absences', 0),
            getattr(c, 'grade_avg', ''),
        ])

    AuditLog.log(user=request.user, action=AuditLog.ACTION_EXPORT, description=f"Export CSV dossiers: total={qs.count()}", model_name='Case', object_id=None, success=True)
    return response
