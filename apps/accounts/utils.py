"""
accounts/utils.py — Shared utility helpers
"""


def get_client_ip(request):
    """Extract the real client IP from request headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
