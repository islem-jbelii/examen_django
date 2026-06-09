from django.urls import path
from apps.youth import views

app_name = "youth"

urlpatterns = [
    path("", views.youth_list, name="youth-list"),
    path("create/", views.youth_create, name="youth-create"),
    path("my-profile/", views.my_profile, name="my-profile"),
    path("import/", views.youth_bulk_import, name="bulk-import"),
    path("import/result/", views.import_result, name="import-result"),
    path("<uuid:pk>/", views.youth_profile_detail, name="profile-detail"),
    path("<uuid:pk>/edit/", views.youth_update, name="youth-update"),
    path("<uuid:pk>/assessment/", views.interest_assessment, name="assessment"),
    path("<uuid:pk>/assessment/<uuid:assessment_pk>/result/", views.assessment_result, name="assessment-result"),
]
