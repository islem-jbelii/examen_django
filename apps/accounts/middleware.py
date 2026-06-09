import logging
import threading
import uuid
import time

_request_local = threading.local()

def _set_request_attrs(request_id: str, user_repr: str | None):
    _request_local.request_id = request_id
    _request_local.user = user_repr

def _clear_request_attrs():
    for attr in ("request_id", "user"):
        try:
            delattr(_request_local, attr)
        except Exception:
            pass

def get_request_id():
    return getattr(_request_local, "request_id", "-")

def get_user():
    u = getattr(_request_local, "user", None)
    if u is None:
        return "-"
    return u


class RequestIdFilter(logging.Filter):
    """Logging filter that injects `request_id` and `user` into the record."""

    def filter(self, record):
        record.request_id = get_request_id()
        record.user = get_user()
        return True


class RequestLoggingMiddleware:
    """Middleware that assigns a request_id and logs request summary.

    - Generates a uuid4 request_id and stores it in `request.request_id`.
    - Exposes request_id and user on a thread-local for logging via `RequestIdFilter`.
    - Logs method, path, user, status_code, duration_ms and request_id as structured key=val.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("apps.accounts")

    def __call__(self, request):
        start = time.time()
        request_id = uuid.uuid4().hex
        user_repr = None
        try:
            if hasattr(request, "user") and request.user is not None and request.user.is_authenticated:
                # keep a short repr (username or id)
                try:
                    user_repr = str(request.user.get_username())
                except Exception:
                    user_repr = str(getattr(request.user, "id", "user"))
            else:
                user_repr = "anonymous"
        except Exception:
            user_repr = "-"

        request.request_id = request_id
        _set_request_attrs(request_id, user_repr)

        try:
            response = self.get_response(request)
            status = getattr(response, "status_code", 0)
            return response
        except Exception as exc:  # pragma: no cover - bubble after logging
            status = 500
            raise
        finally:
            duration_ms = int((time.time() - start) * 1000)
            # structured key=val log
            try:
                self.logger.info(
                    "method=%s path=%s user=%s status_code=%s duration_ms=%s",
                    request.method,
                    request.get_full_path(),
                    user_repr,
                    status,
                    duration_ms,
                )
            except Exception:
                pass
            _clear_request_attrs()
