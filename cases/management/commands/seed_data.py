from __future__ import annotations

import random
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from cases.models import Student, Case, RiskThreshold, HealthRecord, Alert
from cases.services import RiskAssessmentService, HealthFollowUpService
from core.models import UserProfile


User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data: users, thresholds, students, cases and health scenarios.'

    def handle(self, *args, **options):
        self.stdout.write('Démarrage du seed_data...')

        # 1) Utilisateurs
        users_spec = [
            ('admin', 'admin123', True, True, 'ADMIN'),
            ('supervisor', 'sup123', False, False, 'SUPERVISOR'),
            ('operator', 'op123', False, False, 'OPERATOR'),
        ]

        created_users = {}
        for username, pwd, is_super, is_staff, role in users_spec:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(pwd)
                user.is_superuser = is_super
                user.is_staff = is_staff
                user.save()
                msg = 'créé'
            else:
                # ensure flags are consistent
                user.is_superuser = is_super or user.is_superuser
                user.is_staff = is_staff or user.is_staff
                user.save()
                msg = 'existe déjà'

            profile = getattr(user, 'profile', None)
            if profile is None:
                UserProfile.objects.get_or_create(user=user, defaults={'role': role})
            else:
                profile.role = role
                profile.save()

            self.stdout.write(f'Utilisateur {username}: {msg} (role={role})')
            created_users[role] = user

        admin = created_users.get('ADMIN')
        supervisor = created_users.get('SUPERVISOR')
        operator = created_users.get('OPERATOR')

        # 2) Seuils de risque: supprimer anciens
        RiskThreshold.objects.all().delete()
        self.stdout.write('Anciennes règles supprimées.')

        thresholds = [
            # absences
            (RiskThreshold.IND_ABSENCES, RiskThreshold.OP_GTE, Decimal(10), RiskThreshold.RISK_MEDIUM, 'Absences >=10'),
            (RiskThreshold.IND_ABSENCES, RiskThreshold.OP_GTE, Decimal(20), RiskThreshold.RISK_HIGH, 'Absences >=20'),
            (RiskThreshold.IND_ABSENCES, RiskThreshold.OP_GTE, Decimal(30), RiskThreshold.RISK_CRITICAL, 'Absences >=30'),
            # grades
            (RiskThreshold.IND_GRADE_AVG, RiskThreshold.OP_LTE, Decimal(8), RiskThreshold.RISK_MEDIUM, 'Moyenne <=8'),
            (RiskThreshold.IND_GRADE_AVG, RiskThreshold.OP_LTE, Decimal(5), RiskThreshold.RISK_HIGH, 'Moyenne <=5'),
            # missed sessions
            (RiskThreshold.IND_MISSED, RiskThreshold.OP_GTE, Decimal(2), RiskThreshold.RISK_HIGH, 'Séances manquées >=2'),
        ]

        for ind, op, val, lvl, desc in thresholds:
            RiskThreshold.objects.create(
                indicator=ind,
                operator=op,
                threshold_value=val,
                risk_level=lvl,
                description=desc,
                created_by=admin,
            )
            self.stdout.write(f'Rule created: {ind} {op} {val} -> {lvl}')

        # 3) 15 élèves synthétiques
        random.seed(0)
        first_names = ['Amira', 'Houssem', 'Sarra', 'Youssef', 'Khalil', 'Amina', 'Mourad', 'Nadia', 'Zied', 'Leila', 'Mehdi', 'Rim', 'Firas', 'Lina', 'Oussama']
        last_names = ['Ben Ali', 'Trabelsi', 'Khlifi', 'Sassi', 'Ben Youssef', 'Gharbi', 'Jaballi', 'Ayari', 'Mansour', 'Zribi']
        regions = [Student.REGION_TUNIS, Student.REGION_SFAX, Student.REGION_SOUSSE, Student.REGION_MONASTIR, Student.REGION_BIZERTE, Student.REGION_GABES]
        schools = ['Lycée Carthage', 'Collège Habib', 'Lycée La Marsa', 'Collège Hammam', 'Ecole Technique Sfax']

        students = []
        for i in range(15):
            code = f'STU-SEED-{i+1:03d}'
            fname = first_names[i % len(first_names)]
            lname = last_names[i % len(last_names)]
            age = random.randint(12, 17)
            region = regions[i % len(regions)]
            school = schools[i % len(schools)]
            absences = random.randint(0, 35)
            grade = round(random.uniform(3.5, 19.0), 1)

            student, created = Student.objects.get_or_create(student_code=code, defaults={
                'first_name': fname,
                'last_name': lname,
                'age': age,
                'gender': Student.GENDER_M if i % 2 == 0 else Student.GENDER_F,
                'region': region,
                'school_name': school,
            })
            students.append({'obj': student, 'absences': absences, 'grade': Decimal(str(grade))})
            status = 'créé' if created else 'existe déjà'
            self.stdout.write(f"Étudiant {code}: {status} - absences={absences} grade={grade}")

        # 4) 10 dossiers EDUCATION (Scénario 1)
        self.stdout.write('\nCréation des dossiers EDUCATION...')
        for idx, s in enumerate(students[:10]):
            stud = s['obj']
            absences = s['absences']
            grade = s['grade']
            with transaction.atomic():
                case, created = Case.objects.get_or_create(student=stud, title=f'EDU {stud.student_code}', defaults={'created_by': supervisor})
                # mettre à jour indicateurs
                case.absences = absences
                case.grade_avg = grade
                case.save()

                assessment = RiskAssessmentService.assess_case(case, supervisor)

                # transitions: ASSESSMENT if absences>20 or grade<8; INTERVENTION if absences>25
                try:
                    if absences > 20 or (grade is not None and grade < Decimal('8')):
                        case.transition_to(Case.STATUS_ASSESSMENT, user=supervisor, reason='Auto-évaluation seed')
                    if absences > 25:
                        # ensure second step only after ASSESSMENT
                        if case.status != Case.STATUS_ASSESSMENT:
                            case.transition_to(Case.STATUS_ASSESSMENT, user=supervisor, reason='Auto-évaluation seed')
                        case.transition_to(Case.STATUS_INTERVENTION, user=supervisor, reason='Auto-évaluation seed')
                except Exception as e:
                    self.stdout.write(f'Warning transition pour {case.pk}: {e}')

                level = assessment.get('risk_level')
                self.stdout.write(f'Dossier #{case.pk} {stud.student_code} risque:{level}')

        # 5) 5 dossiers HEALTH (Scénario 2)
        self.stdout.write('\nCréation des dossiers HEALTH...')
        for s in students[10:15]:
            stud = s['obj']
            with transaction.atomic():
                case, created = Case.objects.get_or_create(student=stud, title=f'HEA {stud.student_code}', defaults={'created_by': supervisor})
                # perform transitions NEW -> ASSESSMENT -> INTERVENTION -> FOLLOW_UP
                try:
                    case.transition_to(Case.STATUS_ASSESSMENT, user=supervisor, reason='Seed flow')
                    case.transition_to(Case.STATUS_INTERVENTION, user=supervisor, reason='Seed flow')
                    case.transition_to(Case.STATUS_FOLLOW_UP, user=supervisor, reason='Seed flow')
                except Exception as e:
                    self.stdout.write(f'Warning health transition for case {case.pk}: {e}')

                # add 4 health sessions (2 MISSED, 2 ATTENDED)
                now = timezone.now()
                HealthRecord.objects.create(student=stud, session_date=now - timedelta(days=14), status=HealthRecord.STATUS_MIS, created_by=operator)
                HealthRecord.objects.create(student=stud, session_date=now - timedelta(days=7), status=HealthRecord.STATUS_MIS, created_by=operator)
                HealthRecord.objects.create(student=stud, session_date=now - timedelta(days=3), status=HealthRecord.STATUS_ATT, created_by=operator)
                HealthRecord.objects.create(student=stud, session_date=now - timedelta(days=1), status=HealthRecord.STATUS_ATT, created_by=operator)

                HealthFollowUpService.check_missed_sessions(case, supervisor)
                self.stdout.write(f'Dossier santé #{case.pk} {stud.student_code}')

        # Récapitulatif
        total_cases = Case.objects.count()
        total_alerts = Alert.objects.count()
        users_count = User.objects.count()
        self.stdout.write('\n=== RÉCAPITULATIF ===')
        self.stdout.write(f'Total dossiers: {total_cases}')
        self.stdout.write(f'Total alertes: {total_alerts}')
        self.stdout.write(f'Utilisateurs: {users_count} (admin={User.objects.filter(is_superuser=True).count()})')
        self.stdout.write('Seed terminé.')
