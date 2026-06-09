from django.urls import path
from apps.alerts import views

app_name = "alerts"

urlpatterns = [
    path("", views.alert_list, name="alert-list"),
    path("<uuid:pk>/mark-read/", views.alert_mark_read, name="mark-read"),
    path("mark-all-read/", views.alert_mark_all_read, name="mark-all-read"),
]
