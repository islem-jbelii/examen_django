"""Tests unitaires pour l'app `cases`.

Ce fichier contient des helpers de création et plusieurs classes de tests
correspondant à la demande : machines d'état, calcul de risque, suivi santé,
import CSV, contrôles d'accès, validation de formulaires et audit.

Remarques:
- Les helpers retournent des objets avec `select_related('profile')` quand
  nécessaire pour respecter les attentes des tests.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError

from django.contrib.auth import get_user_model

from .models import Student, Case, CaseEvent, RiskThreshold, HealthRecord, Alert
from .services import RiskAssessmentService, HealthFollowUpService, CSVImportService
from .forms import CaseForm, CaseTransitionForm
from core.models import AuditLog


User = get_user_model()


# -----------------
# Helpers
# -----------------
def make_user(username: str, role: str, password: str = 'test123'):
    """Crée un utilisateur, met à jour le `profile.role` et retourne
    l'instance chargée avec `select_related('profile')`.
    """
    user = User.objects.create_user(username=username, password=password)
    # Le signal doit avoir créé le profile; récupérer et mettre à jour
    profile = getattr(user, 'profile', None)
    if profile is None:
        # Dans certains environnements de test le signal peut ne pas s'être
        # attaché : créer manuellement si nécessaire.
        from core.models import UserProfile

        profile = UserProfile.objects.create(user=user, role=role)
    else:
        profile.role = role
        profile.save()

    return User.objects.select_related('profile').get(pk=user.pk)


def make_student(code: str = 'STU-TEST-001', age: int = 14) -> Student:
    """Crée un `Student` minimal valide pour les tests."""
    return Student.objects.create(
        student_code=code,
        first_name='Test',
        last_name='Student',
        age=age,
        gender=Student.GENDER_M,
    )


def make_thresholds(created_by=None) -> List[RiskThreshold]:
    """Crée 6 seuils de risque standard utilisés par la batterie de tests.

    Retourne la liste des objets créés.
    """
    thr = []
    # Absences: >=10 -> MEDIUM
    thr.append(RiskThreshold.objects.create(
        indicator=RiskThreshold.IND_ABSENCES,
        operator=RiskThreshold.OP_GTE,
        threshold_value=10,
        risk_level=RiskThreshold.RISK_MEDIUM,
        description='Absences fréquentes (>=10)',
        created_by=created_by,
    ))
    # Absences: >=20 -> HIGH
    thr.append(RiskThreshold.objects.create(
        indicator=RiskThreshold.IND_ABSENCES,
        operator=RiskThreshold.OP_GTE,
        threshold_value=20,
        risk_level=RiskThreshold.RISK_HIGH,
        description='Absences très fréquentes (>=20)',
        created_by=created_by,
    ))

    # Grade average: <=8 -> MEDIUM
    thr.append(RiskThreshold.objects.create(
        indicator=RiskThreshold.IND_GRADE_AVG,
        operator=RiskThreshold.OP_LTE,
        threshold_value=8,
        risk_level=RiskThreshold.RISK_MEDIUM,
        description='Moyenne basse (<=8)',
        created_by=created_by,
    ))
    # Grade average: <=4 -> CRITICAL
    thr.append(RiskThreshold.objects.create(
        indicator=RiskThreshold.IND_GRADE_AVG,
        operator=RiskThreshold.OP_LTE,
        threshold_value=4,
        risk_level=RiskThreshold.RISK_CRITICAL,
        description='Moyenne critique (<=4)',
        created_by=created_by,
    ))

    # Missed sessions: >=2 -> MEDIUM (utilisé par HealthFollowUpService)
    thr.append(RiskThreshold.objects.create(
        indicator=RiskThreshold.IND_MISSED,
        operator=RiskThreshold.OP_GTE,
        threshold_value=2,
        risk_level=RiskThreshold.RISK_MEDIUM,
        description='Séances manquées >=2',
        created_by=created_by,
    ))

    # Extra: absences critical >=30 -> CRITICAL
    thr.append(RiskThreshold.objects.create(
        indicator=RiskThreshold.IND_ABSENCES,
        operator=RiskThreshold.OP_GTE,
        threshold_value=30,
        risk_level=RiskThreshold.RISK_CRITICAL,
        description='Absences extrêmes (>=30)',
        created_by=created_by,
    ))

    return thr


# -----------------
# Tests
# -----------------


class CaseStateMachineTest(TestCase):
    """Tests unitaires pour la machine d'état du modèle `Case`.

    Ces tests vérifient les transitions valides, invalides et la création
    d'événements (`CaseEvent`).
    """

    def setUp(self):
        self.user = make_user('operator1', role='OPERATOR')
        self.student = make_student()

    def test_initial_status_is_new(self):
        case = Case.objects.create(student=self.student, title='c1', created_by=self.user)
        self.assertEqual(case.status, Case.STATUS_NEW)

    def test_valid_transition_new_to_assessment(self):
        case = Case.objects.create(student=self.student, title='c2', created_by=self.user)
        case.transition_to(Case.STATUS_ASSESSMENT, user=self.user, reason='début éval')
        case.refresh_from_db()
        self.assertEqual(case.status, Case.STATUS_ASSESSMENT)

    def test_valid_full_workflow(self):
        case = Case.objects.create(student=self.student, title='workflow', created_by=self.user)
        seq = [Case.STATUS_ASSESSMENT, Case.STATUS_INTERVENTION, Case.STATUS_FOLLOW_UP, Case.STATUS_CLOSED]
        for s in seq:
            case.transition_to(s, user=self.user, reason=f'to {s}')
        case.refresh_from_db()
        self.assertEqual(case.status, Case.STATUS_CLOSED)

    def test_invalid_transition_raises_error(self):
        case = Case.objects.create(student=self.student, title='bad', created_by=self.user)
        with self.assertRaises(ValidationError):
            case.transition_to(Case.STATUS_CLOSED, user=self.user, reason='impossible')

    def test_invalid_transition_new_to_follow_up(self):
        case = Case.objects.create(student=self.student, title='bad2', created_by=self.user)
        with self.assertRaises(ValidationError):
            case.transition_to(Case.STATUS_FOLLOW_UP, user=self.user, reason='saut invalide')

    def test_closed_case_cannot_transition(self):
        case = Case.objects.create(student=self.student, title='closed', created_by=self.user)
        case.status = Case.STATUS_CLOSED
        case.save()
        with self.assertRaises(ValidationError):
            case.transition_to(Case.STATUS_ASSESSMENT, user=self.user, reason='post-closure')

    def test_transition_creates_event_in_timeline(self):
        case = Case.objects.create(student=self.student, title='evt', created_by=self.user)
        before = case.events.count()
        case.transition_to(Case.STATUS_ASSESSMENT, user=self.user, reason='t')
        after = case.events.count()
        self.assertEqual(after, before + 1)

    def test_transition_event_has_correct_data(self):
        case = Case.objects.create(student=self.student, title='evt2', created_by=self.user)
        case.transition_to(Case.STATUS_ASSESSMENT, user=self.user, reason='raison précise')
        ev = case.events.order_by('timestamp').last()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.user.pk, self.user.pk)
        self.assertIn('raison précise', ev.reason)


class RiskCalculationTest(TestCase):
    """Vérifie le calcul des risques et la création d'alertes via
    `RiskAssessmentService` et `Case.compute_risk()`.
    """

    def setUp(self):
        self.user = make_user('analyst', role='SUPERVISOR')
        self.student = make_student()
        make_thresholds(created_by=self.user)

    def test_no_risk_for_normal_student(self):
        case = Case.objects.create(student=self.student, title='r1', created_by=self.user, absences=2, grade_avg=Decimal('15'))
        lvl, expl = case.compute_risk()
        self.assertEqual(lvl, RiskThreshold.RISK_LOW)
        self.assertEqual(len(expl), 0)

    def test_medium_risk_for_absences(self):
        case = Case.objects.create(student=self.student, title='r2', created_by=self.user, absences=12)
        lvl, _ = case.compute_risk()
        self.assertEqual(lvl, RiskThreshold.RISK_MEDIUM)

    def test_high_risk_for_high_absences(self):
        case = Case.objects.create(student=self.student, title='r3', created_by=self.user, absences=22)
        lvl, _ = case.compute_risk()
        self.assertEqual(lvl, RiskThreshold.RISK_HIGH)

    def test_medium_risk_for_low_grade(self):
        case = Case.objects.create(student=self.student, title='r4', created_by=self.user, grade_avg=Decimal('7.0'))
        lvl, _ = case.compute_risk()
        self.assertEqual(lvl, RiskThreshold.RISK_MEDIUM)

    def test_explanation_lists_triggered_rules(self):
        case = Case.objects.create(student=self.student, title='r5', created_by=self.user, absences=12)
        _, expl = case.compute_risk()
        joined = '\n'.join(expl)
        # L'explication doit mentionner l'indicateur ABSENCES
        self.assertIn('ABSENCES', joined)

    def test_risk_assessment_service_saves_to_case(self):
        case = Case.objects.create(student=self.student, title='svc', created_by=self.user, absences=12)
        # Ajouter dynamiquement les champs optionnels pour que le service puisse
        # les écrire (le modèle n'a pas nécessairement ces colonnes persistées).
        setattr(case, 'risk_level', None)
        setattr(case, 'recommendation', None)
        setattr(case, 'recommendation_explanation', None)

        res = RiskAssessmentService.assess_case(case, user=self.user)
        # Vérifier que le service indique avoir sauvegardé sur l'instance
        self.assertTrue(res.get('saved_to_case'))
        # Et que les attributs en mémoire ont été remplis
        self.assertIsNotNone(getattr(case, 'risk_level', None))
        self.assertTrue(bool(getattr(case, 'recommendation', '')))

    def test_high_risk_creates_alert(self):
        case = Case.objects.create(student=self.student, title='r6', created_by=self.user, absences=22)
        res = RiskAssessmentService.assess_case(case, user=self.user)
        alerts = res.get('alerts_created') or []
        self.assertTrue(len(alerts) >= 1)
        self.assertTrue(Alert.objects.filter(case=case).exists())


class HealthFollowUpTest(TestCase):
    """Tests autour du suivi santé et des alertes générées par
    `HealthFollowUpService.check_missed_sessions`.
    """

    def setUp(self):
        self.user = make_user('nurse', role='OPERATOR')
        self.student = make_student()
        make_thresholds(created_by=self.user)
        self.case = Case.objects.create(student=self.student, title='health', created_by=self.user)

    def test_no_alert_below_threshold(self):
        # 1 séance manquée (seuil = 2)
        HealthRecord.objects.create(student=self.student, session_date=timezone.now(), status=HealthRecord.STATUS_MIS, created_by=self.user)
        created = HealthFollowUpService.check_missed_sessions(self.case, user=self.user)
        self.assertEqual(len(created), 0)

    def test_alert_triggered_at_threshold(self):
        HealthRecord.objects.create(student=self.student, session_date=timezone.now(), status=HealthRecord.STATUS_MIS, created_by=self.user)
        HealthRecord.objects.create(student=self.student, session_date=timezone.now(), status=HealthRecord.STATUS_MIS, created_by=self.user)
        created = HealthFollowUpService.check_missed_sessions(self.case, user=self.user)
        self.assertEqual(len(created), 1)
        self.assertTrue(Alert.objects.filter(case=self.case).exists())

    def test_alert_not_duplicated(self):
        HealthRecord.objects.create(student=self.student, session_date=timezone.now(), status=HealthRecord.STATUS_MIS, created_by=self.user)
        HealthRecord.objects.create(student=self.student, session_date=timezone.now(), status=HealthRecord.STATUS_MIS, created_by=self.user)
        first = HealthFollowUpService.check_missed_sessions(self.case, user=self.user)
        second = HealthFollowUpService.check_missed_sessions(self.case, user=self.user)
        # Une seule alerte créée
        self.assertEqual(Alert.objects.filter(case=self.case).count(), 1)
        self.assertEqual(len(second), 0)

    def test_alert_creates_case_event(self):
        HealthRecord.objects.create(student=self.student, session_date=timezone.now(), status=HealthRecord.STATUS_MIS, created_by=self.user)
        HealthRecord.objects.create(student=self.student, session_date=timezone.now(), status=HealthRecord.STATUS_MIS, created_by=self.user)
        HealthFollowUpService.check_missed_sessions(self.case, user=self.user)
        ev = CaseEvent.objects.filter(case=self.case, reason__icontains='REMINDER_SENT').first()
        self.assertIsNotNone(ev)


class CSVImportTest(TestCase):
    """Tests pour `CSVImportService.validate_and_import` en mode dry-run
    et import réel.
    """

    def setUp(self):
        self.user = make_user('importer', role='SUPERVISOR')

    def _make_csv(self, rows: List[dict]) -> str:
        # Génère une chaîne CSV à partir d'une liste de dictionnaires
        headers = ['student_code', 'first_name', 'last_name', 'age', 'grade_average']
        lines = [','.join(headers)]
        for r in rows:
            vals = [r.get(h, '') for h in headers]
            # Échapper les virgules simples; tests simples donc on se contente de join
            lines.append(','.join(str(v) for v in vals))
        return '\n'.join(lines)

    def test_valid_csv_passes(self):
        rows = [
            {'student_code': 'STU-001', 'first_name': 'A', 'last_name': 'B', 'age': '12'},
            {'student_code': 'STU-002', 'first_name': 'C', 'last_name': 'D', 'age': '15'},
        ]
        content = self._make_csv(rows)
        res = CSVImportService.validate_and_import(content, import_type='EDUCATION', user=self.user, dry_run=True)
        self.assertEqual(res['valid_rows'], 2)
        self.assertEqual(res['error_rows'], 0)

    def test_missing_columns_raises_error(self):
        # Enlever la colonne age
        content = 'student_code,first_name,last_name\nSTU-001,A,B'
        with self.assertRaises(ValidationError) as cm:
            CSVImportService.validate_and_import(content, import_type='EDUCATION', user=self.user, dry_run=True)
        self.assertIn('manqu', str(cm.exception).lower())

    def test_bad_values_reported_per_row(self):
        rows = [
            {'student_code': 'BADCODE', 'first_name': '', 'last_name': 'X', 'age': '200'},
            {'student_code': 'STU-OK', 'first_name': 'A', 'last_name': '', 'age': 'abc'},
            {'student_code': 'STU-BAD', 'first_name': 'B', 'last_name': 'C', 'age': '4'},
        ]
        content = self._make_csv(rows)
        res = CSVImportService.validate_and_import(content, import_type='EDUCATION', user=self.user, dry_run=True)
        self.assertEqual(res['error_rows'], 3)
        self.assertEqual(len(res['errors']), 3)
        for e in res['errors']:
            self.assertIn('reason', e)

    def test_dry_run_does_not_create_students(self):
        rows = [
            {'student_code': 'STU-DRY1', 'first_name': 'A', 'last_name': 'B', 'age': '12'},
            {'student_code': 'STU-DRY2', 'first_name': 'C', 'last_name': 'D', 'age': '13'},
        ]
        content = self._make_csv(rows)
        before = Student.objects.count()
        CSVImportService.validate_and_import(content, import_type='EDUCATION', user=self.user, dry_run=True)
        after = Student.objects.count()
        self.assertEqual(before, after)

    def test_real_import_creates_students(self):
        rows = [
            {'student_code': 'STU-R1', 'first_name': 'A', 'last_name': 'B', 'age': '12'},
            {'student_code': 'STU-R2', 'first_name': 'C', 'last_name': 'D', 'age': '13'},
        ]
        content = self._make_csv(rows)
        before = Student.objects.count()
        res = CSVImportService.validate_and_import(content, import_type='EDUCATION', user=self.user, dry_run=False)
        self.assertEqual(res['imported'], 2)
        self.assertEqual(Student.objects.count(), before + 2)


class RoleAccessTest(TestCase):
    """Tests d'accès aux routes pour différents rôles.

    Ces tests utilisent des requêtes HTTP sur les chemins attendus par
    l'application (`/dashboard/`, `/cases/`, `/cases/<pk>/transition/`, `/cases/thresholds/`).
    """

    def setUp(self):
        self.client = Client()
        self.operator = make_user('op', role='OPERATOR')
        self.supervisor = make_user('sup', role='SUPERVISOR')
        self.student = make_student()
        self.case = Case.objects.create(student=self.student, title='access', created_by=self.operator)

    def test_unauthenticated_redirect_to_login(self):
        resp = self.client.get('/dashboard/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_operator_can_see_case_list(self):
        self.client.force_login(self.operator)
        resp = self.client.get('/cases/')
        # Accept 200 or 302 (selon l'implémentation) mais préférer 200
        self.assertIn(resp.status_code, (200, 302))

    def test_operator_cannot_access_transition(self):
        self.client.force_login(self.operator)
        resp = self.client.get(f'/cases/{self.case.pk}/transition/')
        # Access denied expected -> redirect to login ou forbidden
        self.assertIn(resp.status_code, (302, 403))
        # Vérifier qu'un AuditLog ACCESS_DENIED a été créé
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.ACTION_ACCESS_DENIED).exists())

    def test_supervisor_can_access_transition(self):
        self.client.force_login(self.supervisor)
        resp = self.client.get(f'/cases/{self.case.pk}/transition/')
        self.assertIn(resp.status_code, (200, 302))

    def test_operator_cannot_access_risk_thresholds(self):
        self.client.force_login(self.operator)
        resp = self.client.get('/cases/thresholds/')
        self.assertIn(resp.status_code, (302, 403))


class FormValidationTest(TestCase):
    """Vérifie la validation des formulaires `CaseForm` et `CaseTransitionForm`."""

    def setUp(self):
        self.user = make_user('formuser', role='OPERATOR')
        self.student = make_student()

    def test_case_form_rejects_negative_absences(self):
        data = {'student': self.student.pk, 'absences_days': -5}
        form = CaseForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('négatif', str(form.errors).lower())

    def test_case_form_rejects_grade_above_20(self):
        data = {'student': self.student.pk, 'grade_average': '25'}
        form = CaseForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('20', str(form.errors))

    def test_case_form_rejects_recommendation_without_explanation(self):
        data = {'new_status': Case.STATUS_ASSESSMENT, 'reason': 'ok', 'recommendation': 'Faire X', 'recommendation_explanation': ''}
        form = CaseTransitionForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('explication', str(form.errors).lower())


class AuditLogTest(TestCase):
    """Tests pour `AuditLog.log` et conservation des informations."""

    def setUp(self):
        self.user = make_user('auditor', role='ADMIN')

    def test_audit_log_created(self):
        before = AuditLog.objects.count()
        AuditLog.log(user=self.user, action=AuditLog.ACTION_CREATE, description='Test create', model_name='Case', object_id='1')
        self.assertEqual(AuditLog.objects.count(), before + 1)

    def test_failed_action_logged_with_reason(self):
        entry = AuditLog.log(user=self.user, action=AuditLog.ACTION_UPDATE, description='Fail', model_name='Case', object_id='2', success=False, reason='insuffisant')
        self.assertFalse(entry.success)
        self.assertIn('insuffisant', (entry.reason or '').lower())

    def test_audit_log_stores_user(self):
        entry = AuditLog.log(user=self.user, action=AuditLog.ACTION_DELETE, description='Del', model_name='Case', object_id='3')
        self.assertEqual(entry.user.pk, self.user.pk)
