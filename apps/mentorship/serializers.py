"""
mentorship/serializers.py — Nested serializers.
"""
from datetime import date, timedelta
from rest_framework import serializers

from apps.accounts.models import UserRole
from apps.mentorship.models import MentorProfile, MentorshipSession
from apps.youth.models import YouthStatus


class MentorProfileSerializer(serializers.ModelSerializer):
    availability_display = serializers.CharField(source="get_availability_display", read_only=True)
    sector_name = serializers.CharField(source="sector.name", read_only=True)
    mentor_name = serializers.SerializerMethodField()

    class Meta:
        model = MentorProfile
        fields = [
            "id", "user", "mentor_name", "sector", "sector_name", "company_name",
            "years_of_experience", "bio", "availability", "availability_display",
            "max_youth_capacity", "current_youth_count", "is_verified",
        ]
        read_only_fields = ["id"]

    def get_mentor_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class MentorshipSessionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    session_type_display = serializers.CharField(source="get_session_type_display", read_only=True)
    youth_name = serializers.SerializerMethodField()
    mentor_name = serializers.SerializerMethodField()

    class Meta:
        model = MentorshipSession
        fields = [
            "id", "youth", "youth_name", "mentor", "mentor_name",
            "session_date", "session_type", "session_type_display",
            "status", "status_display", "notes", "recommendations",
            "counselor_notified", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_youth_name(self, obj):
        return obj.youth.user.get_full_name() or obj.youth.user.username

    def get_mentor_name(self, obj):
        return obj.mentor.get_full_name() or obj.mentor.username

    def validate_session_date(self, value):
        max_future = date.today() + timedelta(days=30)
        if value > max_future:
            raise serializers.ValidationError(
                "La date ne peut pas être à plus de 30 jours dans le futur."
            )
        return value

    def validate(self, data):
        youth = data.get("youth") or (self.instance.youth if self.instance else None)
        if youth and youth.status == YouthStatus.INACTIVE:
            raise serializers.ValidationError(
                {"youth": "Impossible de créer une séance pour un jeune inactif."}
            )
        request = self.context.get("request")
        if request and request.user.role == UserRole.MENTOR:
            if youth and youth.assigned_mentor != request.user:
                raise serializers.ValidationError(
                    {"youth": "Vous ne pouvez créer des séances que pour vos jeunes assignés."}
                )
        return data
