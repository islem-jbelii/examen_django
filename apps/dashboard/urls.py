from django.urls import path
from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_redirect, name="redirect"),
    path("admin/", views.admin_dashboard, name="admin"),
    path("counselor/", views.counselor_dashboard, name="counselor"),
    path("mentor/", views.mentor_dashboard, name="mentor"),
    path("youth/", views.youth_dashboard, name="youth"),
    path("monitoring/", views.monitoring_dashboard, name="monitoring"),
    path("export/csv/", views.export_youth_csv, name="export-csv"),
    path("export/pdf/", views.export_pdf, name="export-pdf"),
]
