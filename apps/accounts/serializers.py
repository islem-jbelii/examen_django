"""
accounts/serializers.py
"""
from rest_framework import serializers
from apps.accounts.models import User, AuditLog


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "role", "role_display", "is_active", "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]


class AuditLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True, default="system")

    class Meta:
        model = AuditLog
        fields = [
            "id", "user", "user_username", "action", "target_model",
            "target_id", "result", "reason", "ip_address", "timestamp",
        ]
        read_only_fields = fields
