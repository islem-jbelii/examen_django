from django.urls import path
from apps.alerts import api_views

app_name = "api_alerts"

urlpatterns = [
    path("", api_views.AlertListView.as_view(), name="alert-list"),
    path("<uuid:pk>/read/", api_views.alert_mark_read, name="mark-read"),
    path("check/<uuid:youth_pk>/", api_views.run_alert_checks, name="run-checks"),
]
