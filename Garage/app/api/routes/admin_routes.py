"""Admin API routes -- dashboard, ranking, user management."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.admin_utils import configured_admin_emails, is_admin_email, is_admin_username

router = APIRouter(prefix="/api/admin", tags=["admin"])

import os

_user_repo = None
_player_repo = None
_leaderboard_repo = None
_challenge_repo = None
_pending_repo = None


def init_admin_routes(user_repo, player_repo, leaderboard_repo, challenge_repo, pending_repo=None):
    global _user_repo, _player_repo, _leaderboard_repo, _challenge_repo, _pending_repo
    _user_repo = user_repo
    _player_repo = player_repo
    _leaderboard_repo = leaderboard_repo
    _challenge_repo = challenge_repo
    _pending_repo = pending_repo


# Admin e-mail helpers are now shared via admin_utils to avoid drift.
_configured_admin_emails = configured_admin_emails
_is_admin_email = is_admin_email


def _assert_admin(current_user: dict):
    """Raise 403 if the authenticated user is not the admin.

    Primary check: role=admin claim in JWT (set at login via ADMIN_USERNAME).
    Fallback: username claim matches ADMIN_USERNAME env var.
    """
    if not current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied.")

    # Primary: role claim embedded in JWT
    if current_user.get("role") == "admin":
        return

    # Fallback: username in token matches ADMIN_USERNAME
    if is_admin_username(current_user.get("username")):
        return

    raise HTTPException(status_code=403, detail="Access denied. Admin only.")


# ---------------------------------------------------------------------------
# Dashboard overview
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def api_admin_dashboard(current_user: dict = Depends(get_current_user)):
    """Return aggregate dashboard data for the admin panel."""
    _assert_admin(current_user)

    users = _user_repo.get_all() if hasattr(_user_repo, "get_all") else []
    sessions = _player_repo.get_all() if hasattr(_player_repo, "get_all") else []
    challenges = _challenge_repo.get_all() if hasattr(_challenge_repo, "get_all") else []

    total_users = len(users)
    total_sessions = len(sessions)
    total_challenges = len(challenges)

    # Count completed games (status == "completed" or stage == "Distinguished")
    completed_count = 0
    active_count = 0
    game_over_count = 0
    for s in sessions:
        status = s.status.value if hasattr(s.status, "value") else s.status
        stage = s.stage.value if hasattr(s.stage, "value") else s.stage
        if status == "completed" or stage == "Distinguished":
            completed_count += 1
        elif status == "game_over":
            game_over_count += 1
        else:
            active_count += 1

    # Online now: sessions with activity in the last 5 minutes
    online_now = 0
    if hasattr(_player_repo, "get_active_sessions"):
        try:
            online_now = len(_player_repo.get_active_sessions(minutes=5))
        except Exception:  # pragma: no cover
            online_now = 0

    # Pending registrations count (awaiting email verification)
    pending_count = 0
    if _pending_repo is not None and hasattr(_pending_repo, "count_active"):
        try:
            pending_count = _pending_repo.count_active()
        except Exception:
            pass

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_challenges": total_challenges,
        "completed_games": completed_count,
        "active_games": active_count,
        "game_over_sessions": game_over_count,
        "online_now": online_now,
        "pending_count": pending_count,
    }


# ---------------------------------------------------------------------------
# Online now (active in the last 5 minutes)
# ---------------------------------------------------------------------------

@router.get("/online")
def api_admin_online(current_user: dict = Depends(get_current_user)):
    """Return sessions with activity in the last 5 minutes (online right now)."""
    _assert_admin(current_user)

    if not hasattr(_player_repo, "get_active_sessions"):
        return []

    active = _player_repo.get_active_sessions(minutes=5)
    users = _user_repo.get_all() if hasattr(_user_repo, "get_all") else []
    user_map = {u.id: u for u in users}

    result = []
    for s in active:
        user = user_map.get(s.get("user_id"))

        # Skip orphaned sessions: user_id set but user no longer exists (was deleted)
        if s.get("user_id") and user is None:
            continue

        now = datetime.now(timezone.utc)
        last_active = None
        seconds_ago = None
        try:
            last_active = datetime.fromisoformat(s["last_active_at"])
            # Make timezone-aware if naive
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            seconds_ago = int((now - last_active).total_seconds())
        except (TypeError, ValueError, KeyError):  # pragma: no cover
            pass

        STAGE_PT = {
            "Intern": "Estagiario", "Junior": "Junior", "Mid": "Pleno",
            "Senior": "Senior", "Staff": "Staff", "Principal": "Principal",
            "Distinguished": "CEO",
        }
        current_errors = s.get("current_errors", 0)
        result.append({
            "session_id": s.get("session_id"),
            "player_name": s.get("player_name"),
            "user_name": user.full_name if user else "---",
            "user_email": user.email if user else "---",
            "stage": s.get("stage"),
            "stage_pt": STAGE_PT.get(s.get("stage", ""), s.get("stage", "")),
            "score": s.get("score", 0),
            "language": s.get("language", "---"),
            "completed_challenges": s.get("completed_challenges", 0),
            "current_errors": current_errors,
            "errors_remaining": max(0, 2 - current_errors),
            "game_over_count": s.get("game_over_count", 0),
            "last_active_at": s.get("last_active_at"),
            "seconds_ago": seconds_ago,
        })

    return result


# ---------------------------------------------------------------------------
# All users
# ---------------------------------------------------------------------------

@router.get("/users")
def api_admin_users(current_user: dict = Depends(get_current_user)):
    """Return list of all registered users with their session summaries."""
    _assert_admin(current_user)

    users = _user_repo.get_all() if hasattr(_user_repo, "get_all") else []
    all_sessions = _player_repo.get_all_dict() if hasattr(_player_repo, "get_all_dict") else []

    result = []
    for user in users:
        ud = user.to_public_dict()
        ud["created_at"] = user.to_dict().get("created_at", "")
        # Find all sessions for this user
        user_sessions = [s for s in all_sessions if s.get("user_id") == user.id]
        ud["total_sessions"] = len(user_sessions)
        ud["total_score"] = sum(s.get("score", 0) for s in user_sessions)
        ud["total_attempts"] = sum(s.get("total_attempts", 0) for s in user_sessions)
        ud["total_completed_challenges"] = sum(
            len(s.get("completed_challenges", [])) for s in user_sessions
        )
        # Best session
        best = max(user_sessions, key=lambda x: x.get("score", 0)) if user_sessions else None
        ud["best_stage"] = best.get("stage", "---") if best else "---"
        ud["best_score"] = best.get("score", 0) if best else 0
        # Completed runs count
        ud["completed_runs"] = sum(
            1 for s in user_sessions
            if s.get("status") == "completed" or s.get("stage") == "Distinguished"
        )
        # Subscription data
        if hasattr(_user_repo, "get_subscription_status"):
            try:
                sub = _user_repo.get_subscription_status(user.id)
                ud["subscription_status"] = sub.get("status")
                ud["subscription_plan"] = sub.get("plan")
                ud["subscription_expires_at"] = sub.get("expires_at")
            except Exception:
                ud["subscription_status"] = None
                ud["subscription_plan"] = None
                ud["subscription_expires_at"] = None
        result.append(ud)

    return result


# ---------------------------------------------------------------------------
# All sessions (detailed)
# ---------------------------------------------------------------------------

@router.get("/sessions")
def api_admin_sessions(current_user: dict = Depends(get_current_user)):
    """Return all game sessions with detailed info."""
    _assert_admin(current_user)

    all_sessions = _player_repo.get_all_dict() if hasattr(_player_repo, "get_all_dict") else []
    users = _user_repo.get_all() if hasattr(_user_repo, "get_all") else []
    user_map = {u.id: u for u in users}

    result = []
    for s in all_sessions:
        user = user_map.get(s.get("user_id"))
        entry = {
            "session_id": s.get("id"),
            "player_name": s.get("name"),
            "user_name": user.full_name if user else "---",
            "user_email": user.email if user else "---",
            "stage": s.get("stage"),
            "score": s.get("score", 0),
            "status": s.get("status"),
            "completed_challenges": len(s.get("completed_challenges", [])),
            "total_attempts": s.get("total_attempts", 0),
            "game_over_count": s.get("game_over_count", 0),
            "language": s.get("language", "---"),
            "created_at": s.get("created_at", ""),
        }
        # Calculate duration from first to last attempt
        attempts = s.get("attempts", [])
        if attempts:
            timestamps = [a.get("timestamp", "") for a in attempts if a.get("timestamp")]
            if len(timestamps) >= 2:
                try:
                    first = datetime.fromisoformat(min(timestamps))
                    last = datetime.fromisoformat(max(timestamps))
                    entry["duration_seconds"] = int((last - first).total_seconds())
                except (ValueError, TypeError):  # pragma: no cover
                    entry["duration_seconds"] = 0
            else:  # pragma: no cover
                entry["duration_seconds"] = 0
        else:  # pragma: no cover
            entry["duration_seconds"] = 0
        result.append(entry)

    return result


# ---------------------------------------------------------------------------
# Ranking (time-based, all completions)
# ---------------------------------------------------------------------------

@router.get("/ranking")
def api_admin_ranking(current_user: dict = Depends(get_current_user)):
    """
    Global ranking of all game completions.
    Sorted by: fastest completion time (ascending).
    If never completed, sorted by highest stage reached, then score.
    """
    _assert_admin(current_user)

    all_sessions = _player_repo.get_all_dict() if hasattr(_player_repo, "get_all_dict") else []
    users = _user_repo.get_all() if hasattr(_user_repo, "get_all") else []
    user_map = {u.id: u for u in users}

    STAGE_ORDER = {
        "Intern": 0, "Junior": 1, "Mid": 2, "Senior": 3,
        "Staff": 4, "Principal": 5, "Distinguished": 6,
    }

    entries = []
    for s in all_sessions:
        user = user_map.get(s.get("user_id"))
        # Skip orphaned sessions (no linked registered user)
        if user is None:
            continue
        is_completed = s.get("status") == "completed" or s.get("stage") == "Distinguished"

        # Duration from first to last attempt
        duration_sec = 0
        attempts = s.get("attempts", [])
        if attempts:
            timestamps = [a.get("timestamp", "") for a in attempts if a.get("timestamp")]
            if len(timestamps) >= 2:
                try:
                    first = datetime.fromisoformat(min(timestamps))
                    last = datetime.fromisoformat(max(timestamps))
                    duration_sec = int((last - first).total_seconds())
                except (ValueError, TypeError):  # pragma: no cover
                    pass

        entries.append({
            "rank": 0,
            "player_name": s.get("name"),
            "user_id": user.id if user else None,
            "user_name": user.full_name if user else "---",
            "user_email": user.email if user else "---",
            "stage": s.get("stage"),
            "stage_index": STAGE_ORDER.get(s.get("stage"), 0),
            "score": s.get("score", 0),
            "completed": is_completed,
            "duration_seconds": duration_sec,
            "total_attempts": s.get("total_attempts", 0),
            "game_over_count": s.get("game_over_count", 0),
            "created_at": s.get("created_at", ""),
        })

    # Deduplicate: keep only the best session per user.
    # Key: user_id when available, otherwise player_name (anonymous/unlinked sessions).
    # "Best" priority: 1) completed beats incomplete  2) highest score  3) fastest duration
    best_per_user: dict = {}
    for e in entries:
        key = e.get("user_email") if e.get("user_email") != "---" else ("anon::" + (e.get("player_name") or "?"))
        prev = best_per_user.get(key)
        if prev is None:
            best_per_user[key] = e
        else:
            # completed always beats incomplete
            if e["completed"] and not prev["completed"]:
                best_per_user[key] = e  # pragma: no cover
            elif not e["completed"] and prev["completed"]:  # pragma: no cover
                pass  # keep prev
            else:  # pragma: no cover
                # same completion status: higher score wins; tie-break: faster duration
                if e["score"] > prev["score"]:
                    best_per_user[key] = e
                elif e["score"] == prev["score"]:
                    e_dur = e["duration_seconds"] if e["duration_seconds"] > 0 else 999999999
                    p_dur = prev["duration_seconds"] if prev["duration_seconds"] > 0 else 999999999
                    if e_dur < p_dur:
                        best_per_user[key] = e

    entries = list(best_per_user.values())

    # Sort: completed first (by duration asc), then incomplete (by stage desc, score desc)
    completed = [e for e in entries if e["completed"]]
    incomplete = [e for e in entries if not e["completed"]]

    completed.sort(key=lambda x: (x["duration_seconds"] if x["duration_seconds"] > 0 else 999999999))
    incomplete.sort(key=lambda x: (-x["stage_index"], -x["score"]))

    ranked = completed + incomplete
    for i, e in enumerate(ranked):
        e["rank"] = i + 1

    return ranked


# ---------------------------------------------------------------------------
# User detail (all DB data for a single user)
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}")
def api_admin_user_detail(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return all database data for a specific user: profile + all sessions."""
    _assert_admin(current_user)

    users = _user_repo.get_all() if hasattr(_user_repo, "get_all") else []
    user = next((u for u in users if str(u.id) == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")

    user_dict = user.to_dict() if hasattr(user, "to_dict") else {}
    # Remove sensitive credentials before sending to client
    user_dict.pop("password_hash", None)
    user_dict.pop("salt", None)

    all_sessions = _player_repo.get_all_dict() if hasattr(_player_repo, "get_all_dict") else []
    user_sessions = [s for s in all_sessions if str(s.get("user_id")) == user_id]

    # Enrich each session with readable duration
    for s in user_sessions:
        attempts = s.get("attempts", [])
        duration_sec = 0
        if attempts:
            timestamps = [a.get("timestamp", "") for a in attempts if a.get("timestamp")]
            if len(timestamps) >= 2:
                try:
                    first = datetime.fromisoformat(min(timestamps))
                    last = datetime.fromisoformat(max(timestamps))
                    duration_sec = int((last - first).total_seconds())
                except (ValueError, TypeError):
                    pass
        s["duration_seconds"] = duration_sec

    return {
        "user": user_dict,
        "sessions": user_sessions,
        "stats": {
            "total_sessions": len(user_sessions),
            "total_score": sum(s.get("score", 0) for s in user_sessions),
            "total_attempts": sum(s.get("total_attempts", 0) for s in user_sessions),
            "total_completed_challenges": sum(
                len(s.get("completed_challenges", [])) for s in user_sessions
            ),
            "total_game_overs": sum(s.get("game_over_count", 0) for s in user_sessions),
            "best_score": max((s.get("score", 0) for s in user_sessions), default=0),
            "completed_runs": sum(
                1 for s in user_sessions
                if s.get("status") == "completed" or s.get("stage") == "Distinguished"
            ),
        },
    }


# ---------------------------------------------------------------------------
# Delete orphaned sessions (sessions with no linked user)
# ---------------------------------------------------------------------------

@router.delete("/sessions/orphaned")
def api_admin_delete_orphaned_sessions(current_user: dict = Depends(get_current_user)):
    """Delete all game sessions that have no linked registered user."""
    _assert_admin(current_user)

    all_sessions = _player_repo.get_all_dict() if hasattr(_player_repo, "get_all_dict") else []
    users = _user_repo.get_all() if hasattr(_user_repo, "get_all") else []
    valid_user_ids = {str(u.id) for u in users}

    orphaned_ids = [
        s["id"] for s in all_sessions
        if str(s.get("user_id", "")) not in valid_user_ids
    ]

    if not orphaned_ids:
        return {"deleted": 0, "message": "Nenhuma sessao orfã encontrada."}

    if not hasattr(_player_repo, "delete_session"):
        raise HTTPException(status_code=501, detail="Delete de sessao não suportado neste modo.")

    deleted = 0
    for sid in orphaned_ids:
        try:
            if _player_repo.delete_session(sid):
                deleted += 1
        except Exception:
            pass

    try:
        from app.infrastructure.audit import log_event as audit_log
        audit_log("admin_delete_orphaned_sessions", current_user["sub"], {"count": deleted, "ids": orphaned_ids})
    except Exception:
        pass

    return {"deleted": deleted, "message": f"{deleted} sessao(oes) orfã(s) removida(s)."}


# ---------------------------------------------------------------------------
# Delete user
# ---------------------------------------------------------------------------

@router.delete("/users/{user_id}")
def api_admin_delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Permanently delete a user and all their data from the database."""
    _assert_admin(current_user)

    # Prevent self-deletion
    if current_user.get("sub") == user_id:
        raise HTTPException(status_code=400, detail="Voce nao pode deletar sua propria conta.")

    if not hasattr(_user_repo, "delete_user"):
        raise HTTPException(status_code=501, detail="Delete nao suportado neste modo.")

    deleted = _user_repo.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")

    try:
        from app.infrastructure.audit import log_event as audit_log
        audit_log("admin_delete_user", current_user["sub"], {"deleted_user_id": user_id})
    except Exception:
        pass

    return {"success": True, "message": "Usuario deletado com sucesso."}


# ---------------------------------------------------------------------------
# Grant subscription (test / manual activation by admin)
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel


class GrantSubscriptionRequest(_BaseModel):
    plan: str = "monthly"  # "monthly" | "annual"
    days: int | None = None  # override duration; None = use plan default


@router.post("/users/{user_id}/grant-subscription")
def api_admin_grant_subscription(
    user_id: str,
    body: GrantSubscriptionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Manually activate a subscription for a user.

    Used for testing the DEMO paywall flow without a real Asaas payment,
    and for admin courtesy activations (e.g. early-access, sponsorships).
    """
    _assert_admin(current_user)

    if not _user_repo:
        raise HTTPException(status_code=503, detail="User repository not available.")

    if body.plan not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="plan deve ser 'monthly' ou 'annual'.")

    # Calculate expiry
    from datetime import timedelta
    plan_days = {"monthly": 30, "annual": 365}
    days = body.days if body.days and body.days > 0 else plan_days[body.plan]
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    if not hasattr(_user_repo, "activate_subscription"):
        raise HTTPException(status_code=501, detail="activate_subscription nao suportado neste backend.")

    try:
        _user_repo.activate_subscription(user_id=user_id, plan=body.plan, expires_at=expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao ativar assinatura: {exc}")

    # Send welcome email (fire-and-forget — thread separada para nao bloquear a resposta)
    try:
        target_user = _user_repo.find_by_id(user_id) if hasattr(_user_repo, "find_by_id") else None
        if target_user:
            from app.infrastructure.auth.email_sender import send_subscription_welcome_email
            import threading
            threading.Thread(
                target=send_subscription_welcome_email,
                kwargs={
                    "to_email": target_user.email,
                    "full_name": getattr(target_user, "full_name", None) or getattr(target_user, "username", "Dev"),
                    "plan": body.plan,
                    "expires_at": expires_at.strftime("%d/%m/%Y"),
                },
                daemon=True,
            ).start()
    except Exception as exc:
        log.warning("Welcome email failed (non-fatal): %s", exc)

    try:
        from app.infrastructure.audit import log_event as audit_log
        audit_log("admin_grant_subscription", current_user["sub"], {
            "target_user_id": user_id,
            "plan": body.plan,
            "days": days,
            "expires_at": expires_at.isoformat(),
        })
    except Exception:
        pass

    return {
        "success": True,
        "user_id": user_id,
        "plan": body.plan,
        "days": days,
        "expires_at": expires_at.isoformat(),
        "message": f"Assinatura '{body.plan}' ativada por {days} dias.",
    }


# ---------------------------------------------------------------------------
# Revoke subscription (admin manual deactivation)
# ---------------------------------------------------------------------------

@router.post("/users/{user_id}/revoke-subscription")
def api_admin_revoke_subscription(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Immediately cancel a user's active subscription."""
    _assert_admin(current_user)

    if not _user_repo:
        raise HTTPException(status_code=503, detail="User repository not available.")

    if not hasattr(_user_repo, "revoke_subscription"):
        raise HTTPException(status_code=501, detail="revoke_subscription nao suportado neste backend.")

    try:
        _user_repo.revoke_subscription(user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao revogar assinatura: {exc}")

    try:
        from app.infrastructure.audit import log_event as audit_log
        audit_log("admin_revoke_subscription", current_user["sub"], {
            "target_user_id": user_id,
        })
    except Exception:
        pass

    return {
        "success": True,
        "user_id": user_id,
        "message": "Assinatura revogada com sucesso.",
    }


# ---------------------------------------------------------------------------
# Test helper — create an already-verified user (bypasses email OTP flow)
# Intended ONLY for integration tests and local dev — requires admin JWT.
# ---------------------------------------------------------------------------

class CreateVerifiedUserRequest(_BaseModel):
    full_name: str
    username: str
    email: str
    whatsapp: str = "11999999999"
    profession: str = "autonomo"
    password: str


@router.post("/test/create-verified-user", status_code=201)
def api_admin_create_verified_user(
    body: CreateVerifiedUserRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a fully-verified user account directly, bypassing email OTP.

    Only accessible with an admin JWT. Designed for integration test scripts
    that need a real user account without going through the email flow.
    Returns the user's ID and an access token ready to use.
    """
    _assert_admin(current_user)

    if not _user_repo:
        raise HTTPException(status_code=503, detail="User repository unavailable.")

    # Conflict checks
    if _user_repo.exists_username(body.username):
        raise HTTPException(status_code=409, detail="Username já existe.")
    if _user_repo.exists_email(body.email):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado.")

    # Build verified User domain object
    from app.infrastructure.auth.password import hash_password
    from app.infrastructure.auth.jwt_handler import create_access_token
    from app.infrastructure.auth.admin_utils import is_admin_username
    from app.domain.user import User

    # bcrypt hash + placeholder salt (bcrypt embeds its own salt in the hash)
    salt = User.generate_salt()
    pwd_hash = hash_password(body.password)
    user = User(
        full_name=body.full_name,
        username=body.username,
        email=body.email,
        whatsapp=body.whatsapp,
        profession=body.profession,
        password_hash=pwd_hash,
        salt=salt,
        email_verified=True,
    )
    _user_repo.save(user)

    role = "admin" if is_admin_username(user.username) else None
    token = create_access_token(user.id, user.username, role=role)

    try:
        from app.infrastructure.audit import log_event as audit_log
        audit_log("admin_create_verified_user", current_user["sub"], {
            "new_user_id": user.id,
            "username": user.username,
        })
    except Exception:
        pass

    return {
        "success": True,
        "user_id": user.id,
        "username": user.username,
        "access_token": token,
        "token_type": "bearer",
        "message": f"Usuário '{user.username}' criado e verificado com sucesso.",
    }


# ---------------------------------------------------------------------------
# Impersonate — generate JWT for any user (test/support use only)
# ---------------------------------------------------------------------------

@router.post("/users/{user_id}/impersonate")
def api_admin_impersonate(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return a short-lived JWT for any user_id, without needing their password.

    Use case: integration tests, customer support, simulation scripts.
    Requires admin JWT. Audited.
    """
    _assert_admin(current_user)

    if not _user_repo:
        raise HTTPException(status_code=503, detail="User repository unavailable.")

    target = _user_repo.find_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Usuário {user_id} não encontrado.")

    from app.infrastructure.auth.jwt_handler import create_access_token
    from app.infrastructure.auth.admin_utils import is_admin_username

    role = "admin" if is_admin_username(target.username) else None
    token = create_access_token(target.id, target.username, role=role)

    try:
        from app.infrastructure.audit import log_event as audit_log
        audit_log("admin_impersonate", current_user["sub"], {
            "target_user_id": user_id,
            "target_username": target.username,
        })
    except Exception:
        pass

    return {
        "success": True,
        "user_id": target.id,
        "username": target.username,
        "access_token": token,
        "token_type": "bearer",
    }


# ---------------------------------------------------------------------------
# Pending registrations — busca de cadastros incompletos
# ---------------------------------------------------------------------------

@router.get("/pending")
def api_admin_pending(
    q: str = "",
    include_expired: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Return pending registrations awaiting email OTP verification.

    ?q=      — optional text filter (name / username / email, case-insensitive)
    ?include_expired=false — show only still-valid records (default: all)
    """
    _assert_admin(current_user)
    if _pending_repo is None:
        return []
    return _pending_repo.search(q=q.strip(), include_expired=include_expired)


@router.delete("/pending/{pending_id}")
def api_admin_delete_pending(
    pending_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a single pending registration record (admin only)."""
    _assert_admin(current_user)
    if _pending_repo is None:
        raise HTTPException(status_code=404, detail="Pending repo indisponivel.")
    deleted = _pending_repo.delete_by_id(pending_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro pendente nao encontrado.")
    try:
        from app.infrastructure.audit import log_event as audit_log
        audit_log("admin_delete_pending", current_user["sub"], {"pending_id": pending_id})
    except Exception:
        pass
    return {"success": True, "message": "Registro pendente removido."}
