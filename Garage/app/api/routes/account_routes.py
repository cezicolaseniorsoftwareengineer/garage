"""Account routes — user area: subscription status + game usage stats.

Endpoints:
  GET  /api/account/me      → user profile + subscription info
  GET  /api/account/usage   → game usage statistics
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from app.infrastructure.auth.dependencies import get_current_user

log = logging.getLogger("garage.account")

router = APIRouter(prefix="/api/account", tags=["account"])

_user_repo = None
_session_factory = None


def init_account_routes(user_repo, session_factory=None):
    global _user_repo, _session_factory
    _user_repo = user_repo
    _session_factory = session_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAN_LABELS = {
    "monthly":      "Plano Mensal · R$ 97/mês",
    "annual":       "Plano Anual · R$ 997/ano",
    "institutional": "Plano Institucional",
}

_STATUS_LABELS = {
    "active":      "Ativo",
    "expired":     "Expirado",
    "cancelled":   "Cancelado",
    "none":        "Sem assinatura",
}


def _subscription_block(user_id: str) -> dict:
    """Build subscription summary dict for a user_id."""
    sub = {"status": "none", "plan": None, "expires_at": None}
    if hasattr(_user_repo, "get_subscription_status"):
        sub = _user_repo.get_subscription_status(user_id)

    days_remaining = None
    if sub.get("expires_at"):
        try:
            exp = datetime.fromisoformat(sub["expires_at"])
            delta = exp - datetime.now(timezone.utc)
            days_remaining = max(0, delta.days)
        except Exception:
            pass

    plan = sub.get("plan")
    return {
        "status": sub["status"],
        "status_label": _STATUS_LABELS.get(sub["status"], sub["status"]),
        "plan": plan,
        "plan_label": _PLAN_LABELS.get(plan or "", "Sem plano ativo"),
        "expires_at": sub.get("expires_at"),
        "days_remaining": days_remaining,
    }


# ---------------------------------------------------------------------------
# GET /api/account/me
# ---------------------------------------------------------------------------

@router.get("/me")
def account_me(current_user: dict = Depends(get_current_user)):
    """Return the authenticated user's profile + subscription info."""
    user_id = current_user["sub"]

    if not hasattr(_user_repo, "find_by_id"):
        raise HTTPException(status_code=503, detail="User repo unavailable")

    user = _user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": user.to_public_dict(),
        "subscription": _subscription_block(user_id),
    }


# ---------------------------------------------------------------------------
# GET /api/account/usage
# ---------------------------------------------------------------------------

@router.get("/usage")
def account_usage(current_user: dict = Depends(get_current_user)):
    """Return game usage statistics for the authenticated user."""
    user_id = current_user["sub"]

    _empty = {
        "sessions_count": 0,
        "total_challenges_completed": 0,
        "total_score": 0,
        "companies_completed": [],
        "books_collected": [],
        "current_stage": "Estagiario",
        "current_region": None,
        "last_played_at": None,
    }

    if _session_factory is None:
        return _empty

    try:
        from app.infrastructure.database.models import GameSessionModel
        with _session_factory() as session:
            sessions = (
                session.query(GameSessionModel)
                .filter(GameSessionModel.user_id == user_id)
                .order_by(GameSessionModel.updated_at.desc())
                .all()
            )

        if not sessions:
            return _empty

        latest = sessions[0]
        total_challenges = sum(len(s.completed_challenges or []) for s in sessions)
        total_score = sum(s.score or 0 for s in sessions)

        all_regions: set = set()
        all_books: set = set()
        for s in sessions:
            all_regions.update(s.completed_regions or [])
            all_books.update(s.collected_books or [])

        return {
            "sessions_count": len(sessions),
            "total_challenges_completed": total_challenges,
            "total_score": total_score,
            "companies_completed": sorted(list(all_regions)),
            "books_collected": sorted(list(all_books)),
            "current_stage": latest.stage or "Estagiario",
            "current_region": latest.current_region,
            "last_played_at": latest.updated_at.isoformat() if latest.updated_at else None,
        }

    except Exception as exc:
        log.exception("Failed to fetch usage stats for user %s: %s", user_id, exc)
        return {**_empty, "error": str(exc)}
