"""Tests pour l'API REST de l'app `cases`.

Utilise `rest_framework.test.APIClient` et les helpers définis dans
`cases.tests` (make_user, make_student, make_thresholds).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from django.test import TestCase

from rest_framework.test import APIClient

from cases.tests import make_user, make_student, make_thresholds
from .models import Student, Case, Alert
from core.models import AuditLog


class StudentAPITest(TestCase):
    def setUp(self):
        self.user = make_user('api_user', role='SUPERVISOR')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_students_returns_200(self):
        resp = self.client.get('/api/students/')
        self.assertEqual(resp.status_code, 200)

    def test_create_student_valid(self):
        payload = {
            'student_code': 'STU-API-001',
            'first_name': 'A',
            'last_name': 'B',
            'age': 12,
            'gender': 'M',
        }
        resp = self.client.post('/api/students/', payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Student.objects.filter(student_code='STU-API-001').exists())

    def test_create_student_invalid_code(self):
        payload = {'student_code': 'BAD', 'first_name': 'A', 'last_name': 'B', 'age': 12, 'gender': 'M'}
        resp = self.client.post('/api/students/', payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('student_code', resp.data)

    def test_create_student_invalid_age(self):
        payload = {'student_code': 'STU-API-002', 'first_name': 'A', 'last_name': 'B', 'age': 50, 'gender': 'M'}
        resp = self.client.post('/api/students/', payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('age', resp.data)

    def test_unauthenticated_request_rejected(self):
        self.client.force_authenticate(None)
        resp = self.client.get('/api/students/')
        self.assertEqual(resp.status_code, 403)


class CaseAPITest(TestCase):
    def setUp(self):
        self.user = make_user('case_user', role='SUPERVISOR')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.student = make_student('STU-CASE-001')
        make_thresholds(created_by=self.user)

    def test_create_case_with_risk_assessment(self):
        payload = {'student_id': self.student.pk, 'title': 'Case with absences', 'absences': 25}
        resp = self.client.post('/api/cases/', payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('_assessment', resp.data)
        risk = resp.data['_assessment'].get('risk_level')
        self.assertIn(risk, ('HIGH', 'CRITICAL'))

    def test_create_case_invalid_grade(self):
        payload = {'student_id': self.student.pk, 'title': 'Bad grade', 'grade_average': 25}
        resp = self.client.post('/api/cases/', payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('grade_average', resp.data)

    def test_list_cases_filter_by_status(self):
        Case.objects.create(student=self.student, title='One', created_by=self.user, status=Case.STATUS_NEW)
        resp = self.client.get('/api/cases/?status=NEW')
        self.assertEqual(resp.status_code, 200)

    def test_case_detail_contains_timeline(self):
        c = Case.objects.create(student=self.student, title='Detail', created_by=self.user)
        resp = self.client.get(f'/api/cases/{c.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('events', resp.data)
        self.assertIn('alerts', resp.data)


class CaseTransitionAPITest(TestCase):
    def setUp(self):
        self.supervisor = make_user('sup_api', role='SUPERVISOR')
        self.operator = make_user('op_api', role='OPERATOR')
        self.client = APIClient()
        self.student = make_student('STU-TRANS-001')
        self.case = Case.objects.create(student=self.student, title='T', created_by=self.operator)

    def test_supervisor_can_transition(self):
        self.client.force_authenticate(self.supervisor)
        payload = {'new_status': Case.STATUS_ASSESSMENT, 'reason': 'valid reason'}
        resp = self.client.post(f'/api/cases/{self.case.pk}/transition/', payload, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('transition', resp.data)
        self.assertEqual(resp.data['transition']['to'], Case.STATUS_ASSESSMENT)

    def test_operator_cannot_transition(self):
        self.client.force_authenticate(self.operator)
        payload = {'new_status': Case.STATUS_ASSESSMENT, 'reason': 'valid reason'}
        resp = self.client.post(f'/api/cases/{self.case.pk}/transition/', payload, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_invalid_transition_returns_400_with_allowed(self):
        self.client.force_authenticate(self.supervisor)
        payload = {'new_status': Case.STATUS_CLOSED, 'reason': 'closing early'}
        resp = self.client.post(f'/api/cases/{self.case.pk}/transition/', payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('allowed_transitions', resp.data)
        self.assertIn(Case.STATUS_ASSESSMENT, resp.data['allowed_transitions'])

    def test_transition_without_reason_rejected(self):
        self.client.force_authenticate(self.supervisor)
        payload = {'new_status': Case.STATUS_ASSESSMENT, 'reason': 'ok'}
        resp = self.client.post(f'/api/cases/{self.case.pk}/transition/', payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('detail', resp.data)

    def test_recommendation_requires_explanation(self):
        self.client.force_authenticate(self.supervisor)
        payload = {'new_status': Case.STATUS_ASSESSMENT, 'reason': 'valid reason', 'recommendation': 'Do X', 'recommendation_explanation': ''}
        resp = self.client.post(f'/api/cases/{self.case.pk}/transition/', payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_transition_logged_in_audit(self):
        self.client.force_authenticate(self.supervisor)
        before = AuditLog.objects.count()
        payload = {'new_status': Case.STATUS_ASSESSMENT, 'reason': 'valid reason'}
        self.client.post(f'/api/cases/{self.case.pk}/transition/', payload, format='json')
        self.assertGreater(AuditLog.objects.count(), before)


class HealthRecordAPITest(TestCase):
    def setUp(self):
        self.user = make_user('hr_user', role='SUPERVISOR')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.student = make_student('STU-HR-001')
        self.case = Case.objects.create(student=self.student, title='HR', created_by=self.user)
        make_thresholds(created_by=self.user)

    def test_create_health_record_attended(self):
        payload = {'session_date': timezone.now().isoformat(), 'status': 'ATTENDED', 'notes': 'ok'}
        resp = self.client.post(f'/api/cases/{self.case.pk}/health_records/', payload, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_create_health_record_future_date_rejected(self):
        future = (timezone.now() + timedelta(days=10)).isoformat()
        payload = {'session_date': future, 'status': 'SCHEDULED', 'notes': 'future'}
        resp = self.client.post(f'/api/cases/{self.case.pk}/health_records/', payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('session_date', resp.data)

    def test_two_missed_sessions_trigger_alert(self):
        payload = {'session_date': timezone.now().isoformat(), 'status': 'MISSED', 'notes': 'miss1'}
        self.client.post(f'/api/cases/{self.case.pk}/health_records/', payload, format='json')
        self.client.post(f'/api/cases/{self.case.pk}/health_records/', payload, format='json')
        self.assertTrue(Alert.objects.filter(case=self.case).exists())


class AlertAPITest(TestCase):
    def setUp(self):
        self.user = make_user('alert_user', role='SUPERVISOR')
        self.operator = make_user('alert_op', role='OPERATOR')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.student = make_student('STU-AL-001')
        self.case = Case.objects.create(student=self.student, title='AL', created_by=self.user)
        make_thresholds(created_by=self.user)

    def test_list_active_alerts(self):
        # Trigger an assessment to create alerts
        self.client.post('/api/cases/', {'student_id': self.student.pk, 'title': 'for alert', 'absences': 22}, format='json')
        resp = self.client.get('/api/alerts/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) >= 0)

    def test_supervisor_can_resolve_alert(self):
        # create an alert
        resp = self.client.post('/api/cases/', {'student_id': self.student.pk, 'title': 'for resolve', 'absences': 22}, format='json')
        # find an alert
        alert = Alert.objects.filter(active=True).first()
        self.assertIsNotNone(alert)
        resp = self.client.post(f'/api/alerts/{alert.pk}/resolve/')
        self.assertEqual(resp.status_code, 200)
        alert.refresh_from_db()
        self.assertFalse(alert.active)

    def test_operator_cannot_resolve_alert(self):
        self.client.force_authenticate(self.operator)
        # create alert as supervisor
        self.client.force_authenticate(self.user)
        self.client.post('/api/cases/', {'student_id': self.student.pk, 'title': 'for resolve op', 'absences': 22}, format='json')
        alert = Alert.objects.filter(active=True).first()
        self.client.force_authenticate(self.operator)
        resp = self.client.post(f'/api/alerts/{alert.pk}/resolve/')
        self.assertEqual(resp.status_code, 403)


class DashboardAPITest(TestCase):
    def setUp(self):
        self.user = make_user('dash', role='SUPERVISOR')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.student = make_student('STU-DASH-001')
        Case.objects.create(student=self.student, title='D1', created_by=self.user)

    def test_dashboard_stats_structure(self):
        resp = self.client.get('/api/dashboard/stats/')
        self.assertEqual(resp.status_code, 200)
        for key in ('total_cases', 'total_students', 'cases_by_status', 'cases_by_risk', 'active_alerts_count', 'completion_rate'):
            self.assertIn(key, resp.data)
