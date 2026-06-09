from django.urls import path
from apps.dashboard import api_views

app_name = "api_dashboard"

urlpatterns = [
    path("kpis/", api_views.dashboard_kpis, name="kpis"),
]
