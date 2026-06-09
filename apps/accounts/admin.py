"""
accounts/admin.py
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import User, AuditLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "role", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering = ["username"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Rôle CareerPathTN", {"fields": ("role",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Rôle CareerPathTN", {"fields": ("role",)}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "target_model", "target_id", "result", "ip_address"]
    list_filter = ["action", "result", "target_model"]
    search_fields = ["user__username", "action", "target_id", "reason"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
