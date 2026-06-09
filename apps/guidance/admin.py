"""
guidance/admin.py
"""
from django.contrib import admin
from apps.guidance.models import ActionPlan


@admin.register(ActionPlan)
class ActionPlanAdmin(admin.ModelAdmin):
    list_display = [
        "youth", "created_by", "status", "target_sector",
        "start_date", "end_date", "validated_by", "validated_at",
    ]
    list_filter = ["status", "target_sector"]
    search_fields = ["youth__user__username", "created_by__username", "objectives"]
    readonly_fields = ["created_at", "updated_at", "validated_at"]
    ordering = ["-created_at"]
    fieldsets = (
        ("Jeune & Conseiller", {
            "fields": ("youth", "created_by"),
        }),
        ("Objectifs & Cible", {
            "fields": ("objectives", "target_sector", "target_career"),
        }),
        ("Calendrier", {
            "fields": ("start_date", "end_date", "milestones"),
        }),
        ("Validation", {
            "fields": ("status", "validated_by", "validated_at"),
        }),
        ("Métadonnées", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
