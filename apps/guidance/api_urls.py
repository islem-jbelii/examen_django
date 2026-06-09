from django.urls import path
from apps.guidance import api_views

app_name = "api_guidance"

urlpatterns = [
    path("plans/", api_views.ActionPlanListView.as_view(), name="plan-list"),
    path("plans/<uuid:pk>/", api_views.ActionPlanDetailView.as_view(), name="plan-detail"),
]
