from django.urls import path
from apps.youth import api_views

app_name = "api_youth"

urlpatterns = [
    path("profiles/", api_views.YouthProfileListView.as_view(), name="profile-list"),
    path("profiles/<uuid:pk>/", api_views.YouthProfileDetailView.as_view(), name="profile-detail"),
    path("assessments/", api_views.InterestAssessmentListView.as_view(), name="assessment-list"),
    path("assessments/<uuid:pk>/", api_views.InterestAssessmentDetailView.as_view(), name="assessment-detail"),
]
