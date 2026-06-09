"""
alerts/admin.py
"""
from django.contrib import admin
from apps.alerts.models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["youth", "alert_type", "severity", "triggered_by", "is_read", "created_at"]
    list_filter = ["alert_type", "severity", "is_read"]
    search_fields = ["youth__user__username", "message", "triggered_by"]
    readonly_fields = ["created_at"]
    list_editable = ["is_read"]
    ordering = ["-created_at"]
