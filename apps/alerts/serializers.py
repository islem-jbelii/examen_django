"""
alerts/serializers.py
"""
from rest_framework import serializers
from apps.alerts.models import Alert


class AlertSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source="get_alert_type_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    youth_name = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id", "youth", "youth_name", "alert_type", "alert_type_display",
            "severity", "severity_display", "message",
            "triggered_by", "is_read", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_youth_name(self, obj):
        return obj.youth.user.get_full_name() or obj.youth.user.username
