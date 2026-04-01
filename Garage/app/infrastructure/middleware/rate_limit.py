"""Global IP-based sliding-window rate limiter middleware.

Limits:
  /api/auth/*           15 req / 60 s per IP  (credential stuffing protection)
  /api/payments/webhook  excluded              (Asaas retries from fixed IPs)
  everything else       300 req / 60 s per IP  (burst protection)

Thread-safe: a single lock guards the shared buckets dict.
Works across uvicorn's sync thread pool and async event loop.
"""
import collections
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_GLOBAL_LIMIT  = 300
_AUTH_LIMIT    = 15
_WINDOW_S      = 60

_AUTH_PREFIX    = "/api/auth/"
_WEBHOOK_PREFIX = "/api/payments/webhook"

_buckets: dict[str, collections.deque] = {}
_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    """Extract real client IP; honour X-Forwarded-For set by Render's proxy."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # Leftmost address is the originating client (Render configuration).
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    return (request.client.host if request.client else "unknown")


def _is_allowed(ip: str, limit: int) -> bool:
    """Sliding-window check. Returns True if the request is within the limit."""
    key = f"{ip}:{limit}"
    now = time.monotonic()
    with _lock:
        dq = _buckets.setdefault(key, collections.deque())
        # Evict timestamps older than the window
        while dq and now - dq[0] > _WINDOW_S:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


class IpRateLimitMiddleware(BaseHTTPMiddleware):
    """Outermost middleware — rate-limits by client IP before any other handler."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Webhook must never be blocked — Asaas expects 200 or it retries
        if path.startswith(_WEBHOOK_PREFIX):
            return await call_next(request)

        ip = _client_ip(request)
        limit = _AUTH_LIMIT if path.startswith(_AUTH_PREFIX) else _GLOBAL_LIMIT

        if not _is_allowed(ip, limit):
            return Response(
                content='{"detail":"Muitas requisicoes. Tente novamente em instantes."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(_WINDOW_S)},
            )

        return await call_next(request)
