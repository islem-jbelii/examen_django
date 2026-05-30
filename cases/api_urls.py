from django.urls import path
from . import api_views

urlpatterns = [
    path('students/', api_views.StudentListCreateAPIView.as_view(), name='api_students'),
    path('students/<int:pk>/', api_views.StudentDetailAPIView.as_view(), name='api_student_detail'),

    path('cases/', api_views.CaseListCreateAPIView.as_view(), name='api_cases'),
    path('cases/<int:pk>/', api_views.CaseDetailAPIView.as_view(), name='api_case_detail'),
    path('cases/<int:pk>/transition/', api_views.CaseTransitionAPIView.as_view(), name='api_case_transition'),
    path('cases/<int:pk>/assess/', api_views.CaseAssessAPIView.as_view(), name='api_case_assess'),
    path('cases/<int:case_pk>/health_records/', api_views.HealthRecordCreateAPIView.as_view(), name='api_case_health_records'),

    path('alerts/', api_views.AlertListAPIView.as_view(), name='api_alerts'),
    path('alerts/<int:pk>/resolve/', api_views.AlertResolveAPIView.as_view(), name='api_alert_resolve'),

    path('thresholds/', api_views.RiskThresholdListCreateAPIView.as_view(), name='api_thresholds'),
    path('dashboard/stats/', api_views.dashboard_stats, name='api_dashboard_stats'),
]
