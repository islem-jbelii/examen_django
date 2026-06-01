from django.urls import path
from . import views

app_name = 'cases'

urlpatterns = [
    path('', views.case_list, name='case_list'),
    path('<int:pk>/modal/', views.case_modal, name='case_modal'),
    path('<int:pk>/transition/', views.case_transition, name='case_transition'),
    path('thresholds/', views.risk_threshold_list, name='risk_threshold_list'),
]
