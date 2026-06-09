from django.urls import path
from apps.careers import api_views

app_name = "api_careers"

urlpatterns = [
    path("sectors/", api_views.CareerSectorListView.as_view(), name="sector-list"),
    path("sectors/<int:pk>/", api_views.CareerSectorDetailView.as_view(), name="sector-detail"),
    path("paths/", api_views.CareerPathListView.as_view(), name="path-list"),
    path("paths/<uuid:pk>/", api_views.CareerPathDetailView.as_view(), name="path-detail"),
]
