"""Admin API routes -- dashboard, ranking, user management."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from app.infrastructure.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

import os

_user_repo = None
_player_repo = None
_leaderboard_repo = None
_challenge_repo = None


def init_admin_routes(user_repo, player_repo, leaderboard_repo, challenge_repo):
    global _user_repo, _player_repo, _leaderboard_repo, _challenge_repo
    _user_repo = user_repo
    _player_repo = player_repo
    _leaderboard_repo = leaderboard_repo
    _challenge_repo = challenge_repo


def _configured_admin_emails() -> set[str]:
    """Return normalized admin emails from env vars."""
    emails: set[str] = set()

    primary = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if primary:
        emails.add(primary)

    aliases = os.environ.get("ADMIN_EMAILS", "").strip()
    if aliases:
        for item in aliases.split(","):
            value = item.strip().lower()
            if value:
                emails.add(value)

    return emails


def _is_admin_email(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() in _configured_admin_emails()


def _assert_admin(current_user: dict):
    """Raise 403 if the authenticated user is not the admin."""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    # First, check role claim on token
    if current_user.get("role") == "admin":
        return

    # Fallback: legacy email-based admin check
    user = None
    if hasattr(_user_repo, "find_by_id"):
        user = _user_repo.find_by_id(user_id)
    if not user or not _is_admin_email(getattr(user, "email", None)):
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
        except Exception:
            online_now = 0

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_challenges": total_challenges,
        "completed_games": completed_count,
        "active_games": active_count,
        "game_over_sessions": game_over_count,
        "online_now": online_now,
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
        now = datetime.now(timezone.utc)
        last_active = None
        seconds_ago = None
        try:
            last_active = datetime.fromisoformat(s["last_active_at"])
            # Make timezone-aware if naive
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            seconds_ago = int((now - last_active).total_seconds())
        except (TypeError, ValueError, KeyError):
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
                except (ValueError, TypeError):
                    entry["duration_seconds"] = 0
            else:
                entry["duration_seconds"] = 0
        else:
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
                except (ValueError, TypeError):
                    pass

        entries.append({
            "rank": 0,
            "player_name": s.get("name"),
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
                best_per_user[key] = e
            elif not e["completed"] and prev["completed"]:
                pass  # keep prev
            else:
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
