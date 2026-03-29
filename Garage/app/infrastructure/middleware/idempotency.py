import json
from datetime import datetime, timedelta, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import text

from app.infrastructure.database.connection import dynamic_session_factory

# In-memory fallback store when the DB is not initialised or unavailable.
# Structure: { idempotency_key: {"status": int, "body": obj, "expires_at": datetime} }
_in_memory_store = {}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware that implements server-side idempotency using a DB table.

    Behavior:
    - If request has header `Idempotency-Key` and a stored response exists,
      return the stored response immediately.
    - Otherwise store a placeholder (id, method, path), run the handler,
      then persist the response body and status for future deduplication.

    This is intentionally conservative and best-effort: when DB is not
    available, requests are forwarded normally (no blocking fallback).
    """

    async def dispatch(self, request: Request, call_next):
        key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        # Only apply idempotency for mutating methods
        if not key or request.method.upper() not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        method = request.method
        path = request.url.path

        # First attempt DB lookup; on failure consult in-memory fallback store.
        try:
            with dynamic_session_factory() as session:
                sel = text(
                    "SELECT status_code, response_body FROM idempotency_keys "
                    "WHERE id = :id AND (expires_at IS NULL OR expires_at > NOW())"
                )
                row = session.execute(sel, {"id": key}).fetchone()
                if row and row[0] is not None and row[1] is not None:
                    content = json.dumps(row[1]).encode("utf-8")
                    return Response(content=content, status_code=row[0], media_type="application/json")

                ins = text(
                    "INSERT INTO idempotency_keys (id, method, path, created_at) "
                    "VALUES (:id, :method, :path, NOW()) ON CONFLICT (id) DO NOTHING"
                )
                session.execute(ins, {"id": key, "method": method, "path": path})
                session.commit()
        except Exception:
            # DB unavailable — consult in-memory store
            entry = _in_memory_store.get(key)
            if entry and entry.get("expires_at") and entry["expires_at"] > datetime.now(timezone.utc):
                content = json.dumps(entry["body"]).encode("utf-8")
                return Response(content=content, status_code=entry["status"], media_type="application/json")
            # else proceed to execute handler and populate in-memory fallback below

        # Execute handler and capture response body
        response = await call_next(request)

        # Read response body bytes (supports both Response.body and body_iterator)
        body_bytes = b""
        try:
            if getattr(response, "body", None) is not None:
                body_bytes = response.body
            else:
                # body_iterator may be async generator
                async for chunk in response.body_iterator:
                    body_bytes += chunk
        except Exception:
            # If we fail to read body, fall back to sending original response
            return response

        # Persist response into DB for future deduplication
        try:
            parsed = None
            try:
                parsed = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                # Not JSON — store as text
                parsed = {"_raw": body_bytes.decode("utf-8", errors="replace")}

            with dynamic_session_factory() as session:
                upd = text(
                    "UPDATE idempotency_keys SET status_code = :status, response_body = :body, expires_at = (NOW() + interval '24 hours') "
                    "WHERE id = :id"
                )
                session.execute(upd, {"status": response.status_code, "body": json.dumps(parsed), "id": key})
                session.commit()
        except Exception:
            # DB write failed — store in in-memory fallback with 24h expiry
            try:
                _in_memory_store[key] = {
                    "status": response.status_code,
                    "body": parsed,
                    "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
                }
            except Exception:
                pass

        # Recreate response preserving status and media type
        headers = dict(response.headers)
        return Response(content=body_bytes, status_code=response.status_code, headers=headers, media_type=response.media_type)
