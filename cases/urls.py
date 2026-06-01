from django.urls import path
from . import views

app_name = 'cases'

urlpatterns = [
    path('', views.case_list, name='case_list'),
    path('<int:pk>/', views.case_detail, name='case_detail'),
    path('<int:pk>/transition/', views.case_transition, name='case_transition'),
    path('<int:pk>/modal/', views.case_modal, name='case_modal'),
    path('thresholds/', views.risk_threshold_list, name='risk_threshold_list'),
    path('export/', views.export_cases_csv, name='export_cases'),
]
