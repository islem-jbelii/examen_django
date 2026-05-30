"""Sérialiseurs DRF pour l'app `cases`.

Chaque sérialiseur est documenté et sépare la logique de validation/présentation
pour l'API REST.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from django.utils import timezone
from rest_framework import serializers

from .models import Student, Case, CaseEvent, Alert, HealthRecord, RiskThreshold


class StudentSerializer(serializers.ModelSerializer):
    """Sérialiseur pour `Student` incluant des champs calculés.

    Ajoute : `full_name` et `region_display`.
    Fournit des validateurs pour `student_code` et `age`.
    """

    full_name = serializers.SerializerMethodField()
    region_display = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = '__all__'
        read_only_fields = ['created_at', 'created_by']

    def get_full_name(self, obj: Student) -> str:
        return obj.get_full_name()

    def get_region_display(self, obj: Student) -> str:
        return obj.get_region_display() if hasattr(obj, 'get_region_display') else obj.region

    def validate_student_code(self, value: str) -> str:
        if not (isinstance(value, str) and value.upper().startswith('STU-')):
            raise serializers.ValidationError('Le code étudiant doit commencer par "STU-".')
        return value

    def validate_age(self, value: int) -> int:
        try:
            age = int(value)
        except Exception:
            raise serializers.ValidationError('L\'âge doit être un entier valide.')
        if not (5 <= age <= 25):
            raise serializers.ValidationError('L\'âge doit être compris entre 5 et 25 ans.')
        return age


class CaseEventSerializer(serializers.ModelSerializer):
    """Lecture seule des événements d'un dossier.

    Ajoute `actor_name` (nom de l'acteur) et `event_type_display` qui décrit
    la transition effectuée.
    """

    actor_name = serializers.SerializerMethodField()
    event_type_display = serializers.SerializerMethodField()

    class Meta:
        model = CaseEvent
        fields = ['id', 'case', 'user', 'actor_name', 'from_status', 'to_status', 'reason', 'timestamp', 'event_type_display']
        read_only_fields = fields

    def get_actor_name(self, obj: CaseEvent) -> str:
        return obj.user.username if obj.user else 'Système'

    def get_event_type_display(self, obj: CaseEvent) -> str:
        return f"{obj.from_status or 'N/A'} → {obj.to_status} ({obj.reason or ''})"


class AlertSerializer(serializers.ModelSerializer):
    """Sérialiseur pour `Alert` avec labels lisibles."""

    alert_type_display = serializers.SerializerMethodField()
    severity_display = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = '__all__'

    def get_alert_type_display(self, obj: Alert) -> str:
        return obj.get_level_display() if hasattr(obj, 'get_level_display') else obj.level

    def get_severity_display(self, obj: Alert) -> str:
        return obj.get_level_display() if hasattr(obj, 'get_level_display') else obj.level


class HealthRecordSerializer(serializers.ModelSerializer):
    """Sérialiseur pour `HealthRecord` avec validation sur la date."""

    class Meta:
        model = HealthRecord
        fields = '__all__'
        read_only_fields = ['student', 'created_by']

    def validate_session_date(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("La date de la séance ne peut pas être dans le futur.")
        return value


class CaseSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour `Case`.

    - `student` est imbriqué en lecture via `StudentSerializer`.
    - `student_id` est utilisé en écriture.
    - `events`, `alerts`, `health_records` sont imbriqués en lecture seule.
    - expose `available_transitions`.
    """

    student = StudentSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all(), write_only=True, source='student')
    events = CaseEventSerializer(many=True, read_only=True)
    alerts = AlertSerializer(many=True, read_only=True)
    health_records = HealthRecordSerializer(many=True, read_only=True)
    available_transitions = serializers.SerializerMethodField()
    # Accept a friendly write alias used by the API/tests
    grade_average = serializers.DecimalField(max_digits=5, decimal_places=2, write_only=True, required=False, source='grade_avg')

    class Meta:
        model = Case
        fields = '__all__'

    def get_available_transitions(self, obj: Case) -> list:
        return Case.VALID_TRANSITIONS.get(obj.status, [])

    def validate_grade_avg(self, value):
        try:
            dec = Decimal(value)
        except Exception:
            raise serializers.ValidationError('La moyenne doit être un nombre valide.')
        if not (Decimal('0') <= dec <= Decimal('20')):
            raise serializers.ValidationError('La moyenne doit être comprise entre 0 et 20.')
        return dec

    def validate_grade_average(self, value):
        # Alias used when clients send 'grade_average' in payload
        return self.validate_grade_avg(value)

    def validate_absences(self, value):
        try:
            ival = int(value)
        except Exception:
            raise serializers.ValidationError('Le nombre d\'absences doit être un entier.')
        if ival < 0:
            raise serializers.ValidationError('Le nombre d\'absences ne peut pas être négatif.')
        return ival


class CaseListSerializer(serializers.Serializer):
    """Sérialiseur allégé pour l'affichage en liste des dossiers."""

    id = serializers.IntegerField(read_only=True)
    student_code = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    status = serializers.CharField()
    risk_level = serializers.CharField(allow_blank=True, allow_null=True)
    active_alerts_count = serializers.SerializerMethodField()

    def get_student_code(self, obj: Case) -> str:
        return obj.student.student_code

    def get_student_name(self, obj: Case) -> str:
        return obj.student.get_full_name()

    def get_active_alerts_count(self, obj: Case) -> int:
        return obj.alerts.filter(active=True).count()


class CaseTransitionSerializer(serializers.Serializer):
    """Sérialiseur pour effectuer une transition de dossier via l'API."""

    new_status = serializers.ChoiceField(choices=Case.STATUS_CHOICES)
    reason = serializers.CharField(min_length=5)
    recommendation = serializers.CharField(required=False, allow_blank=True)
    recommendation_explanation = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        rec = attrs.get('recommendation')
        expl = attrs.get('recommendation_explanation')
        if rec and not expl:
            raise serializers.ValidationError('Si une recommandation est fournie, une explication est requise.')
        return attrs


class RiskThresholdSerializer(serializers.ModelSerializer):
    """Sérialiseur pour `RiskThreshold` avec affichages lisibles."""

    indicator_display = serializers.SerializerMethodField()
    operator_display = serializers.SerializerMethodField()
    risk_level_display = serializers.SerializerMethodField()

    class Meta:
        model = RiskThreshold
        fields = '__all__'

    def get_indicator_display(self, obj: RiskThreshold) -> str:
        return obj.get_indicator_display() if hasattr(obj, 'get_indicator_display') else obj.indicator

    def get_operator_display(self, obj: RiskThreshold) -> str:
        return obj.get_operator_display() if hasattr(obj, 'get_operator_display') else obj.operator

    def get_risk_level_display(self, obj: RiskThreshold) -> str:
        return obj.get_risk_level_display() if hasattr(obj, 'get_risk_level_display') else obj.risk_level


class DashboardStatsSerializer(serializers.Serializer):
    """Sérialiseur simple pour exposer statistiques du tableau de bord."""

    total_cases = serializers.IntegerField()
    total_students = serializers.IntegerField()
    cases_by_status = serializers.DictField(child=serializers.IntegerField())
    cases_by_risk = serializers.DictField(child=serializers.IntegerField())
    active_alerts_count = serializers.IntegerField()
    critical_alerts_count = serializers.IntegerField()
    completion_rate = serializers.FloatField()
