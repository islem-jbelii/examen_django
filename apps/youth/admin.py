"""
youth/admin.py
"""
from django.contrib import admin
from apps.youth.models import YouthProfile, InterestAssessment


@admin.register(YouthProfile)
class YouthProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user", "age", "governorate", "education_level",
        "status", "readiness_score", "assigned_counselor", "assigned_mentor",
    ]
    list_filter = ["status", "governorate", "education_level", "gender"]
    search_fields = ["user__username", "user__email", "user__first_name", "user__last_name"]
    filter_horizontal = ["interests"]
    readonly_fields = ["readiness_score", "created_at", "updated_at"]
    ordering = ["-created_at"]
    fieldsets = (
        ("Informations personnelles", {
            "fields": ("user", "date_of_birth", "gender", "governorate"),
        }),
        ("Éducation", {
            "fields": ("education_level", "current_school_or_institution"),
        }),
        ("Orientation", {
            "fields": ("interests", "assigned_counselor", "assigned_mentor"),
        }),
        ("Statut & Score", {
            "fields": ("status", "readiness_score", "notes"),
        }),
        ("Métadonnées", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(InterestAssessment)
class InterestAssessmentAdmin(admin.ModelAdmin):
    list_display = ["youth", "conducted_by", "assessment_date", "status", "created_at"]
    list_filter = ["status", "assessment_date"]
    search_fields = ["youth__user__username", "conducted_by__username"]
    filter_horizontal = ["recommended_sectors"]
    readonly_fields = ["created_at", "updated_at"]
