"""
accounts/api_urls.py — DRF API URLs
"""
from django.urls import path
from apps.accounts import api_views

app_name = "api_accounts"

urlpatterns = [
    path("me/", api_views.CurrentUserView.as_view(), name="me"),
    path("audit-logs/", api_views.AuditLogListView.as_view(), name="audit-logs"),
]
