from django.urls import path
from apps.mentorship import api_views

app_name = "api_mentorship"

urlpatterns = [
    path("mentors/", api_views.MentorProfileListView.as_view(), name="mentor-list"),
    path("mentors/<uuid:pk>/", api_views.MentorProfileDetailView.as_view(), name="mentor-detail"),
    path("sessions/", api_views.MentorshipSessionListView.as_view(), name="session-list"),
    path("sessions/<uuid:pk>/", api_views.MentorshipSessionDetailView.as_view(), name="session-detail"),
]
