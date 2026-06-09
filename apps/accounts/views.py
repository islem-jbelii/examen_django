"""
accounts/views.py — Login, logout, role-aware redirect
"""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from apps.accounts.forms import LoginForm
from apps.accounts.models import AuditLog, UserRole
from apps.accounts.utils import get_client_ip


def login_view(request):
    """
    Login page with role-aware redirect after successful authentication.
    """
    if request.user.is_authenticated:
        return _role_redirect(request.user)

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Audit log
            AuditLog.objects.create(
                user=user,
                action="LOGIN",
                target_model="User",
                target_id=str(user.pk),
                result=AuditLog.Result.SUCCESS,
                ip_address=get_client_ip(request),
            )
            messages.success(request, f"Bienvenue, {user.get_full_name() or user.username} !")
            return _role_redirect(user)
        else:
            # Log failed attempt
            AuditLog.objects.create(
                user=None,
                action="LOGIN",
                target_model="User",
                target_id=request.POST.get("username", ""),
                result=AuditLog.Result.FAILURE,
                reason="Identifiants invalides",
                ip_address=get_client_ip(request),
            )
            messages.error(request, "Identifiants invalides. Veuillez réessayer.")
    else:
        form = LoginForm(request)

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    """Logout and redirect to login page."""
    AuditLog.objects.create(
        user=request.user,
        action="LOGOUT",
        target_model="User",
        target_id=str(request.user.pk),
        result=AuditLog.Result.SUCCESS,
        ip_address=get_client_ip(request),
    )
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    """Display current user's profile summary."""
    return render(request, "accounts/profile.html", {"user": request.user})


def _role_redirect(user):
    """Return an HttpResponseRedirect based on the user's role."""
    role_urls = {
        UserRole.ADMIN: "/dashboard/admin/",
        UserRole.COUNSELOR: "/dashboard/counselor/",
        UserRole.MENTOR: "/dashboard/mentor/",
        UserRole.YOUTH: "/dashboard/youth/",
    }
    url = role_urls.get(user.role, "/dashboard/")
    return redirect(url)
