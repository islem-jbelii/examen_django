from django.urls import path
from apps.careers import views

app_name = "careers"

urlpatterns = [
    path("", views.sector_list, name="sector-list"),
    path("<int:pk>/", views.sector_detail, name="sector-detail"),
    path("path/<uuid:pk>/", views.career_path_detail, name="career-path-detail"),
]
