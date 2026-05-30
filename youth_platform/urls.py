from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView, LogoutView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('cases/', include('cases.urls')),
    path('api/', include('cases.api_urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('login/', LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
