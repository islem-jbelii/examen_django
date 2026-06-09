"""
accounts/permissions.py — DRF permission classes + view decorators
"""
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


# ---------------------------------------------------------------------------
# DRF Permission Classes
# ---------------------------------------------------------------------------

class IsYouth(BasePermission):
    """Allow access only to users with YOUTH role."""
    message = "Accès réservé aux jeunes."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.YOUTH
        )


class IsCounselor(BasePermission):
    """Allow access only to users with COUNSELOR role."""
    message = "Accès réservé aux conseillers d'orientation."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.COUNSELOR
        )


class IsMentor(BasePermission):
    """Allow access only to users with MENTOR role."""
    message = "Accès réservé aux mentors."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.MENTOR
        )


class IsAdmin(BasePermission):
    """Allow access only to users with ADMIN role."""
    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.ADMIN
        )


class IsCounselorOrAdmin(BasePermission):
    """Allow access to COUNSELOR or ADMIN."""
    message = "Accès réservé aux conseillers et administrateurs."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.COUNSELOR, UserRole.ADMIN)
        )


class IsMentorOrCounselorOrAdmin(BasePermission):
    """Allow access to MENTOR, COUNSELOR, or ADMIN."""
    message = "Accès non autorisé."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.MENTOR, UserRole.COUNSELOR, UserRole.ADMIN)
        )


# ---------------------------------------------------------------------------
# View Decorators (for Django template views)
# ---------------------------------------------------------------------------

def role_required(*roles):
    """
    Decorator that restricts a view to users with one of the given roles.
    Redirects unauthenticated users to login; raises PermissionDenied for
    authenticated users with wrong role.

    Usage:
        @login_required
        @role_required(UserRole.COUNSELOR, UserRole.ADMIN)
        def my_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if request.user.role not in roles:
                raise PermissionDenied(
                    f"Votre rôle ({request.user.get_role_display()}) "
                    "ne vous permet pas d'accéder à cette page."
                )
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def youth_required(view_func):
    return role_required(UserRole.YOUTH)(view_func)


def counselor_required(view_func):
    return role_required(UserRole.COUNSELOR)(view_func)


def mentor_required(view_func):
    return role_required(UserRole.MENTOR)(view_func)


def admin_required(view_func):
    return role_required(UserRole.ADMIN)(view_func)


def counselor_or_admin_required(view_func):
    return role_required(UserRole.COUNSELOR, UserRole.ADMIN)(view_func)


def staff_required(view_func):
    """Counselor, Mentor, or Admin."""
    return role_required(UserRole.COUNSELOR, UserRole.MENTOR, UserRole.ADMIN)(view_func)
