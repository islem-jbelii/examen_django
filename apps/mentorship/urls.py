from django.urls import path
from apps.mentorship import views

app_name = "mentorship"

urlpatterns = [
    path("mentors/", views.mentor_list, name="mentor-list"),
    path("sessions/", views.session_list, name="session-list"),
    path("sessions/create/", views.session_create, name="session-create"),
    path("sessions/<uuid:pk>/", views.session_detail, name="session-detail"),
    path("sessions/<uuid:pk>/edit/", views.session_update, name="session-update"),
    path("assign/<uuid:youth_pk>/", views.mentor_assign, name="mentor-assign"),
]
