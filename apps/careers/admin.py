"""
careers/admin.py
"""
from django.contrib import admin
from apps.careers.models import CareerSector, CareerPath


@admin.register(CareerSector)
class CareerSectorAdmin(admin.ModelAdmin):
    list_display = ["name", "demand_level", "relevance_weight", "average_salary_range", "required_education_level"]
    list_filter = ["demand_level", "relevance_weight"]
    search_fields = ["name", "description"]
    ordering = ["name"]


@admin.register(CareerPath)
class CareerPathAdmin(admin.ModelAdmin):
    list_display = ["title", "sector", "training_duration_months", "is_active"]
    list_filter = ["sector", "is_active"]
    search_fields = ["title", "description", "required_skills"]
    ordering = ["sector__name", "title"]
    list_editable = ["is_active"]
