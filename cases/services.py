"""Services métier pour l'app `cases`.

Ce module sépare la logique métier des vues afin de faciliter les tests
unitaires et la réutilisation.
"""
from __future__ import annotations

import csv
import io
import logging
from decimal import Decimal
from typing import Dict, List, Any

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    Case,
    CaseEvent,
    Alert,
    RiskThreshold,
    HealthRecord,
    Student,
)
from core.models import AuditLog

logger = logging.getLogger(__name__)


class RiskAssessmentService:
    """Service responsable de l'évaluation du risque pour un dossier.

    Méthode principale:
    - `assess_case(case, user)` : évalue le risque via `case.compute_risk()`,
      crée des alertes si nécessaire, crée un `CaseEvent` et écrit dans `AuditLog`.
    """

    @staticmethod
    def assess_case(case: Case, user) -> Dict[str, Any]:
        """Évalue le risque d'un `case` et agit en conséquence.

        Retourne un dict: {risk_level, explanation, alerts_created}.
        """
        risk_level, explanations = case.compute_risk()

        # Sauvegarde dans le modèle Case si les champs existent, sinon en CaseEvent
        saved_to_case = False
        try:
            if hasattr(case, 'risk_level'):
                case.risk_level = risk_level
            if hasattr(case, 'recommendation_explanation'):
                case.recommendation_explanation = '\n'.join(explanations)
            if hasattr(case, 'recommendation'):
                # recommendation simple basée sur risk_level
                rec_map = {
                    'LOW': 'Surveiller',
                    'MEDIUM': 'Intervention recommandée',
                    'HIGH': 'Intervention urgente',
                    'CRITICAL': 'Prise en charge immédiate',
                }
                case.recommendation = rec_map.get(risk_level, 'Aucune')
            case.save()
            saved_to_case = True
        except Exception:
            saved_to_case = False

        alerts_created: List[Alert] = []

        # On ré-évalue les règles pour obtenir les objets RiskThreshold déclenchés
        triggered_thresholds = []
        for thr in RiskThreshold.objects.filter(is_active=True):
            val = case.get_indicator_value(thr.indicator)
            try:
                if thr.evaluate(val):
                    triggered_thresholds.append(thr)
            except Exception:
                continue

        # Créer des alertes si le risque est >= MEDIUM
        severity_order = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        if severity_order.index(risk_level) >= severity_order.index(RiskThreshold.RISK_MEDIUM):
            with transaction.atomic():
                for thr in triggered_thresholds:
                    # éviter doublons d'alerte active pour la même règle
                    exists = Alert.objects.filter(case=case, active=True, triggered_by_rule=thr).exists()
                    if not exists:
                        alert = Alert.objects.create(
                            case=case,
                            student=case.student,
                            level=Alert.LEVEL_WARNING,
                            message=f"Règle déclenchée: {thr.indicator} {thr.operator} {thr.threshold_value} -> {thr.risk_level}",
                            triggered_by_rule=thr,
                        )
                        alerts_created.append(alert)

                # Créer un CaseEvent indiquant qu'une alerte a été déclenchée
                CaseEvent.objects.create(
                    case=case,
                    user=user,
                    from_status=case.status,
                    to_status=case.status,
                    reason=f"ALERT_TRIGGERED: {', '.join([str(t.pk) for t in triggered_thresholds])}",
                )

        # Écrire dans l'AuditLog
        AuditLog.log(
            user=user,
            action=AuditLog.ACTION_ALERT,
            description=f"Évaluation du risque pour le dossier {case.pk}: {risk_level}",
            model_name='Case',
            object_id=str(case.pk),
            success=True,
            reason='; '.join(explanations) if explanations else None,
        )

        return {
            'risk_level': risk_level,
            'explanation': explanations,
            'alerts_created': alerts_created,
            'saved_to_case': saved_to_case,
        }


class HealthFollowUpService:
    """Service gérant le suivi santé et les rappels basés sur les séances manquées.

    Méthode principale:
    - `check_missed_sessions(case, user)` : vérifie les séances manquées et crée
      des alertes et événements si nécessaire.
    """

    @staticmethod
    def check_missed_sessions(case: Case, user) -> List[Alert]:
        """Compte les `HealthRecord` manqués pour le `case` et crée des alertes.

        Retourne la liste des `Alert` créées (peut être vide).
        """
        # Compter les séances MISSED pour l'étudiant lié au dossier
        missed_count = HealthRecord.objects.filter(student=case.student, status=HealthRecord.STATUS_MIS).count()

        # Récupérer le seuil MISSED_SESSIONS ; si plusieurs, prendre le plus strict (le plus bas)
        thresh_qs = RiskThreshold.objects.filter(is_active=True, indicator=RiskThreshold.IND_MISSED).order_by('threshold_value')
        if thresh_qs.exists():
            threshold = int(thresh_qs.first().threshold_value)
            rule = thresh_qs.first()
        else:
            threshold = 2
            rule = None

        created_alerts: List[Alert] = []
        if missed_count >= threshold:
            # vérifier existence d'une alerte active déjà liée à cette règle (ou message similaire)
            exists = False
            if rule:
                exists = Alert.objects.filter(case=case, active=True, triggered_by_rule=rule).exists()
            else:
                exists = Alert.objects.filter(case=case, active=True, message__icontains='séances manquées').exists()

            if not exists:
                with transaction.atomic():
                    message = f"{missed_count} séances manquées (seuil={threshold})."
                    alert = Alert.objects.create(
                        case=case,
                        student=case.student,
                        level=Alert.LEVEL_WARNING,
                        message=message,
                        triggered_by_rule=rule,
                    )
                    created_alerts.append(alert)

                    # Créer un CaseEvent de type REMINDER_SENT stockant le compteur
                    CaseEvent.objects.create(
                        case=case,
                        user=user,
                        from_status=case.status,
                        to_status=case.status,
                        reason=f"REMINDER_SENT: missed_count={missed_count}",
                    )

                    AuditLog.log(
                        user=user,
                        action=AuditLog.ACTION_ALERT,
                        description=f"Alerte séances manquées pour le dossier {case.pk}: {message}",
                        model_name='Case',
                        object_id=str(case.pk),
                        success=True,
                    )

        return created_alerts


class CSVImportService:
    """Service d'import CSV pour créer des `Student` à partir d'un CSV.

    Usage:
        CSVImportService.validate_and_import(file_content, import_type, user, dry_run=True)

    Le paramètre `file_content` est une chaîne (texte) contenant le CSV.
    """

    REQUIRED_COLUMNS = {'student_code', 'first_name', 'last_name', 'age'}

    @classmethod
    def validate_and_import(cls, file_content: str, import_type: str, user, dry_run: bool = True) -> Dict[str, Any]:
        """Valide et (optionnellement) importe les lignes CSV.

        Retourne un rapport dict contenant : {valid_rows, error_rows, errors, imported, total}
        """
        f = io.StringIO(file_content)
        reader = csv.DictReader(f)
        headers = {h.strip() for h in reader.fieldnames or []}

        missing = cls.REQUIRED_COLUMNS - headers
        if missing:
            raise ValidationError(f"Colonnes requises manquantes: {', '.join(sorted(missing))}")

        valid_rows = 0
        error_rows = 0
        errors: List[Dict[str, Any]] = []
        imported = 0
        total = 0

        for idx, row in enumerate(reader, start=1):
            total += 1
            row_errors: List[str] = []
            student_code = (row.get('student_code') or '').strip()
            first_name = (row.get('first_name') or '').strip()
            last_name = (row.get('last_name') or '').strip()
            age_raw = (row.get('age') or '').strip()
            grade_avg_raw = (row.get('grade_average') or '').strip()

            # Validations
            if not student_code.startswith('STU-'):
                row_errors.append('student_code doit commencer par STU-')
            try:
                age = int(age_raw)
                if not (5 <= age <= 25):
                    row_errors.append('age doit être entre 5 et 25')
            except Exception:
                row_errors.append('age invalide')

            if not first_name:
                row_errors.append('first_name manquant')
            if not last_name:
                row_errors.append('last_name manquant')

            if grade_avg_raw:
                try:
                    grade_avg = Decimal(grade_avg_raw)
                    if not (Decimal('0') <= grade_avg <= Decimal('20')):
                        row_errors.append('grade_average doit être entre 0 et 20')
                except Exception:
                    row_errors.append('grade_average invalide')

            if row_errors:
                error_rows += 1
                errors.append({'row': idx, 'reason': '; '.join(row_errors)})
                continue

            valid_rows += 1

            if not dry_run:
                # Créer ou récupérer l'étudiant
                defaults = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'age': age,
                }
                if grade_avg_raw:
                    try:
                        defaults['grade_avg'] = Decimal(grade_avg_raw)
                    except Exception:
                        pass

                obj, created = Student.objects.get_or_create(student_code=student_code, defaults=defaults)
                if created:
                    imported += 1

        # Log d'import si exécution réelle
        if not dry_run:
            AuditLog.log(
                user=user,
                action=AuditLog.ACTION_IMPORT,
                description=f"Import CSV type={import_type}: total={total}, imported={imported}, errors={len(errors)}",
                model_name='Student',
                object_id=None,
                success=(len(errors) == 0),
            )

        return {
            'valid_rows': valid_rows,
            'error_rows': error_rows,
            'errors': errors,
            'imported': imported,
            'total': total,
        }
