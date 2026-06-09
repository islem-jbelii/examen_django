"""
mentorship/admin.py
"""
from django.contrib import admin
from apps.mentorship.models import MentorProfile, MentorshipSession


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user", "sector", "company_name", "years_of_experience",
        "availability", "current_youth_count", "max_youth_capacity", "is_verified",
    ]
    list_filter = ["sector", "availability", "is_verified"]
    search_fields = ["user__username", "user__email", "company_name"]
    list_editable = ["is_verified", "availability"]


@admin.register(MentorshipSession)
class MentorshipSessionAdmin(admin.ModelAdmin):
    list_display = [
        "youth", "mentor", "session_date", "session_type",
        "status", "counselor_notified", "created_at",
    ]
    list_filter = ["status", "session_type", "counselor_notified"]
    search_fields = ["youth__user__username", "mentor__username"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-session_date"]
