"""Landing page analytics routes.

Public endpoints (no auth — called by the landing page):
  POST /api/analytics/landing          → record an event

Admin endpoints (JWT required):
  GET  /api/analytics/landing/summary  → aggregate metrics for admin panel
  GET  /api/analytics/landing/events   → recent raw events (last 100)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.admin_utils import is_admin_username

log = logging.getLogger("garage.analytics")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_repo = None  # PgLandingAnalyticsRepository — injected by init_analytics_routes


def init_analytics_routes(repo) -> None:
    global _repo
    _repo = repo


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LandingEventIn(BaseModel):
    visitor_id: str = Field(..., min_length=8, max_length=64)
    event_type: str = Field(
        ..., pattern="^(page_view|click|checkout_click|scroll_depth|section_view)$"
    )
    element: Optional[str] = Field(None, max_length=100)
    section: Optional[str] = Field(None, max_length=50)
    scroll_pct: Optional[int] = Field(None, ge=0, le=100)
    plan: Optional[str] = Field(None, pattern="^(monthly|annual)$")
    referrer: Optional[str] = Field(None, max_length=500)
    user_agent: Optional[str] = Field(None, max_length=200)


# ---------------------------------------------------------------------------
# POST /api/analytics/landing   (public — CORS open for landing page domain)
# ---------------------------------------------------------------------------

@router.post("/landing", status_code=201)
async def record_event(body: LandingEventIn, request: Request):
    """Receive a tracking event from the landing page.

    No authentication required — called by anonymous visitors.
    Rate-limiting should be applied at the reverse proxy level.
    """
    if _repo is None:
        # No-op when running without PostgreSQL (JSON fallback dev mode)
        return {"ok": True, "note": "analytics_disabled"}

    # Best-effort IP from X-Forwarded-For (Render/Cloudflare sets this)
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else str(request.client.host) if request.client else None

    try:
        _repo.record(
            visitor_id=body.visitor_id,
            event_type=body.event_type,
            element=body.element,
            section=body.section,
            scroll_pct=body.scroll_pct,
            plan=body.plan,
            referrer=body.referrer,
            user_agent=body.user_agent,
            ip_address=ip,
        )
    except Exception as exc:
        log.error("analytics record failed: %s", exc)
        # Never let tracking errors break the user flow
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /api/analytics/landing/summary   (admin only)
# ---------------------------------------------------------------------------

@router.get("/landing/summary")
def landing_summary(current_user: dict = Depends(get_current_user)):
    _assert_admin(current_user)
    if _repo is None:
        return {"error": "analytics_disabled", "note": "PostgreSQL required"}
    try:
        return _repo.summary()
    except Exception as exc:
        log.exception("analytics summary failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /api/analytics/landing/events    (admin only)
# ---------------------------------------------------------------------------

@router.get("/landing/events")
def landing_events(current_user: dict = Depends(get_current_user)):
    _assert_admin(current_user)
    if _repo is None:
        return []
    try:
        return _repo.recent_events(limit=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_admin(current_user: dict) -> None:
    if current_user.get("role") == "admin":
        return
    if is_admin_username(current_user.get("username")):
        return
    raise HTTPException(status_code=403, detail="Access denied. Admin only.")
