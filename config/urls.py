"""
CareerPathTN — Root URL configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/accounts/login/", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("youth/", include("apps.youth.urls", namespace="youth")),
    path("careers/", include("apps.careers.urls", namespace="careers")),
    path("mentorship/", include("apps.mentorship.urls", namespace="mentorship")),
    path("guidance/", include("apps.guidance.urls", namespace="guidance")),
    path("alerts/", include("apps.alerts.urls", namespace="alerts")),
    path("dashboard/", include("apps.dashboard.urls", namespace="dashboard")),
    # API routes
    path("api/accounts/", include("apps.accounts.api_urls", namespace="api_accounts")),
    path("api/youth/", include("apps.youth.api_urls", namespace="api_youth")),
    path("api/careers/", include("apps.careers.api_urls", namespace="api_careers")),
    path("api/mentorship/", include("apps.mentorship.api_urls", namespace="api_mentorship")),
    path("api/guidance/", include("apps.guidance.api_urls", namespace="api_guidance")),
    path("api/alerts/", include("apps.alerts.api_urls", namespace="api_alerts")),
    path("api/dashboard/", include("apps.dashboard.api_urls", namespace="api_dashboard")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers
handler403 = "apps.accounts.error_views.handler403"
handler404 = "apps.accounts.error_views.handler404"
handler500 = "apps.accounts.error_views.handler500"
