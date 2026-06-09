"""
youth/serializers.py — Full nested serializers.
"""
from datetime import date
from rest_framework import serializers

from apps.accounts.models import UserRole
from apps.youth.models import YouthProfile, InterestAssessment
from apps.youth.services import compute_readiness_score


class YouthProfileSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    governorate_display = serializers.CharField(source="get_governorate_display", read_only=True)
    education_display = serializers.CharField(source="get_education_level_display", read_only=True)
    counselor_email = serializers.SerializerMethodField()
    mentor_name = serializers.SerializerMethodField()
    sector_names = serializers.SerializerMethodField()
    readiness_score_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = YouthProfile
        fields = [
            "id", "user", "date_of_birth", "age", "gender", "governorate",
            "governorate_display", "education_level", "education_display",
            "current_school_or_institution", "interests", "sector_names",
            "assigned_counselor", "counselor_email",
            "assigned_mentor", "mentor_name",
            "status", "status_display", "readiness_score",
            "readiness_score_breakdown", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "readiness_score", "created_at", "updated_at"]

    def get_counselor_email(self, obj):
        return obj.assigned_counselor.email if obj.assigned_counselor else None

    def get_mentor_name(self, obj):
        return obj.assigned_mentor.get_full_name() if obj.assigned_mentor else None

    def get_sector_names(self, obj):
        return [s.name for s in obj.interests.all()]

    def get_readiness_score_breakdown(self, obj):
        _, breakdown = compute_readiness_score(obj)
        return breakdown

    def validate_date_of_birth(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if not (15 <= age <= 25):
            raise serializers.ValidationError(
                f"L'âge doit être entre 15 et 25 ans (âge : {age} ans)."
            )
        return value

    def validate_interests(self, value):
        if not value:
            raise serializers.ValidationError("Au moins un secteur d'intérêt requis.")
        return value


class InterestAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterestAssessment
        fields = [
            "id", "youth", "conducted_by", "assessment_date", "responses",
            "recommended_sectors", "score_breakdown", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
