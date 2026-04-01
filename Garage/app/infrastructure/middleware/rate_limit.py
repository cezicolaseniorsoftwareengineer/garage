"""Global IP-based sliding-window rate limiter middleware.

Limits (logical, per-user total):
  /api/auth/*           15 req / 60 s per IP  (credential stuffing protection)
  /api/payments/webhook  excluded              (Asaas retries from fixed IPs)
  everything else       300 req / 60 s per IP  (burst protection)

Multi-worker note:
  uvicorn --workers N spawns N independent OS processes, each with its own
  memory space.  To keep the effective per-IP limit correct, each process
  enforces GLOBAL_LIMIT // WORKER_COUNT and AUTH_LIMIT // WORKER_COUNT.
  Round-robin load distribution at the OS level means each worker sees
  approximately 1/N of a given IP's traffic, so the aggregate stays on target.
  WEB_CONCURRENCY is the standard uvicorn env var; default assumed: 2.

Thread-safe: a single lock guards the shared buckets dict per process.
"""
import collections
import math
import os
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Total logical limits (across all workers combined)
_GLOBAL_LIMIT_TOTAL = 300
_AUTH_LIMIT_TOTAL   = 15
_WINDOW_S           = 60

# Divide by worker count so that per-process enforcement equals logical total
_WORKER_COUNT  = max(1, int(os.getenv("WEB_CONCURRENCY", "2")))
_GLOBAL_LIMIT  = max(1, math.ceil(_GLOBAL_LIMIT_TOTAL / _WORKER_COUNT))
_AUTH_LIMIT    = max(1, math.ceil(_AUTH_LIMIT_TOTAL   / _WORKER_COUNT))

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
