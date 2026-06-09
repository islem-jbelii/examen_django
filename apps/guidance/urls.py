from django.urls import path
from apps.guidance import views

app_name = "guidance"

urlpatterns = [
    path("plans/", views.action_plan_list, name="plan-list"),
    path("plans/create/", views.action_plan_create, name="plan-create"),
    path("plans/<uuid:pk>/", views.action_plan_detail, name="plan-detail"),
    path("plans/<uuid:pk>/validate/", views.action_plan_validate, name="plan-validate"),
]
