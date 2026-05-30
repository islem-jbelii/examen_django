import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','youth_platform.settings')
import django
django.setup()
import json
from django.utils import timezone
from rest_framework.test import APIClient
from cases.tests import make_user, make_student
from cases.models import Case

user = make_user('hr_user2', role='SUPERVISOR')
client = APIClient()
client.force_authenticate(user)
student = make_student('STU-HR-DEBUG')
case = Case.objects.create(student=student, title='HRDEBUG', created_by=user)
payload = {'session_date': timezone.now().isoformat(), 'status': 'ATTENDED', 'notes': 'ok'}
resp = client.post(f'/api/cases/{case.pk}/health_records/', payload, format='json')
print('status', resp.status_code)
print(json.dumps(resp.data, indent=2, ensure_ascii=False))
