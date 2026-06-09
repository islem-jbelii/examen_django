"""
guidance/serializers.py — Nested ActionPlan serializer.
"""
from rest_framework import serializers
from apps.guidance.models import ActionPlan


class ActionPlanSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    youth_name = serializers.SerializerMethodField()
    target_career_title = serializers.SerializerMethodField()
    target_sector_name = serializers.CharField(source="target_sector.name", read_only=True)

    class Meta:
        model = ActionPlan
        fields = [
            "id", "youth", "youth_name", "created_by", "validated_by", "validated_at",
            "status", "status_display", "objectives",
            "target_sector", "target_sector_name",
            "target_career", "target_career_title",
            "start_date", "end_date", "milestones",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "validated_at", "created_at", "updated_at"]

    def get_youth_name(self, obj):
        return obj.youth.user.get_full_name() or obj.youth.user.username

    def get_target_career_title(self, obj):
        return obj.target_career.title if obj.target_career else None

    def validate(self, data):
        start = data.get("start_date") or (self.instance.start_date if self.instance else None)
        end = data.get("end_date") or (self.instance.end_date if self.instance else None)
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "La date de fin doit être postérieure à la date de début."}
            )
        return data
