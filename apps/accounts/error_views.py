"""
accounts/error_views.py — Custom error handlers.
"""
from django.shortcuts import render


def handler403(request, exception=None):
    return render(request, "errors/403.html", {"exception": exception}, status=403)


def handler404(request, exception=None):
    return render(request, "errors/404.html", {"exception": exception}, status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)
