"""
careers/serializers.py
"""
from rest_framework import serializers
from apps.careers.models import CareerSector, CareerPath


class CareerSectorSerializer(serializers.ModelSerializer):
    demand_level_display = serializers.CharField(source="get_demand_level_display", read_only=True)

    class Meta:
        model = CareerSector
        fields = [
            "id", "name", "description", "demand_level", "demand_level_display",
            "average_salary_range", "required_education_level", "relevance_weight",
        ]


class CareerPathSerializer(serializers.ModelSerializer):
    sector_name = serializers.CharField(source="sector.name", read_only=True)

    class Meta:
        model = CareerPath
        fields = [
            "id", "sector", "sector_name", "title", "description",
            "required_skills", "training_duration_months", "is_active",
        ]
