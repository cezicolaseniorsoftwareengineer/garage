"""Game API routes -- start, submit, challenges, leaderboard, metrics."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.application.start_game import start_game
from app.application.submit_answer import submit_answer
from app.application.progress_stage import recover_from_game_over, get_progress
from app.domain.enums import CareerStage
from app.infrastructure.auth.dependencies import get_current_user, get_optional_user


router = APIRouter(prefix="/api", tags=["game"])


class StartGameRequest(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=50)
    gender: str = Field(..., pattern="^(male|female)$")
    ethnicity: str = Field(..., pattern="^(black|white|asian)$")
    avatar_index: int = Field(..., ge=0, le=5)
    language: str


class SubmitAnswerRequest(BaseModel):
    session_id: str
    challenge_id: str
    selected_index: int = Field(..., ge=0)


class RecoverRequest(BaseModel):
    session_id: str


_player_repo = None
_challenge_repo = None
_leaderboard_repo = None
_metrics = None
_events = None


def init_routes(player_repo, challenge_repo, leaderboard_repo,
                metrics_service=None, event_service=None):
    global _player_repo, _challenge_repo, _leaderboard_repo, _metrics, _events
    _player_repo = player_repo
    _challenge_repo = challenge_repo
    _leaderboard_repo = leaderboard_repo
    _metrics = metrics_service
    _events = event_service


# ---------------------------------------------------------------------------
# Helper: ownership check
# ---------------------------------------------------------------------------

def _assert_owner(player, current_user: dict):
    """Raise 403 if the authenticated user does not own the session."""
    if player.user_id and current_user and player.user_id != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied.")


# ---------------------------------------------------------------------------
# Game lifecycle
# ---------------------------------------------------------------------------

@router.post("/start")
def api_start_game(req: StartGameRequest, current_user: dict = Depends(get_current_user)):
    """Create a new game session linked to the authenticated user."""
    user_id = current_user["sub"]
    try:
        player = start_game(
            player_name=req.player_name,
            gender=req.gender,
            ethnicity=req.ethnicity,
            avatar_index=req.avatar_index,
            language=req.language,
            user_id=user_id,
        )
        _player_repo.save(player)

        if _metrics:
            _metrics.on_game_started(user_id, req.language)
        if _events:
            _events.log("game_started", user_id=user_id,
                        session_id=str(player.id),
                        payload={"language": req.language})

        return {
            "session_id": str(player.id),
            "player": player.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}")
def api_get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get current game session state (owner only)."""
    player = _player_repo.get(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_owner(player, current_user)
    return player.to_dict()


@router.get("/challenges")
def api_get_challenges(stage: Optional[str] = None):
    """Get available challenges, optionally filtered by stage. Public."""
    if stage:
        try:
            career_stage = CareerStage(stage)
            challenges = _challenge_repo.get_by_stage(career_stage)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid stage: {stage}")
    else:
        challenges = _challenge_repo.get_all()
    return [c.to_dict_for_player() for c in challenges]


@router.get("/challenges/{challenge_id}")
def api_get_challenge(challenge_id: str):
    """Get a specific challenge (without correct answer). Public."""
    challenge = _challenge_repo.get_by_id(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge.to_dict_for_player()


@router.post("/submit")
def api_submit_answer(req: SubmitAnswerRequest, current_user: dict = Depends(get_current_user)):
    """Submit an answer to a challenge (owner only)."""
    player = _player_repo.get(req.session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_owner(player, current_user)

    challenge = _challenge_repo.get_by_id(req.challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    try:
        result = submit_answer(
            player=player,
            challenge=challenge,
            selected_index=req.selected_index,
        )
        _player_repo.save(player)

        user_id = current_user["sub"]
        is_correct = result.get("outcome") == "correct"
        points = result.get("points_awarded", 0)

        if _metrics:
            _metrics.on_answer_submitted(user_id, is_correct, points)
            if result.get("outcome") == "game_over":
                _metrics.on_game_over(user_id)
            if result.get("promotion"):
                _metrics.on_stage_promoted(
                    user_id, result.get("new_stage", ""), player.score,
                )

        if _events:
            _events.log(
                "answer_submitted", user_id=user_id,
                session_id=req.session_id,
                payload={
                    "challenge_id": req.challenge_id,
                    "outcome": result.get("outcome"),
                    "points": points,
                },
            )

        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/recover")
def api_recover(req: RecoverRequest, current_user: dict = Depends(get_current_user)):
    """Recover from Game Over state (owner only)."""
    player = _player_repo.get(req.session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_owner(player, current_user)

    result = recover_from_game_over(player)
    _player_repo.save(player)

    if _events:
        _events.log("game_recovered", user_id=current_user["sub"],
                     session_id=req.session_id)

    return result


@router.get("/progress/{session_id}")
def api_get_progress(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get player progression details (owner only)."""
    player = _player_repo.get(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_owner(player, current_user)
    return get_progress(player)


@router.get("/leaderboard")
def api_get_leaderboard(limit: int = 10):
    """Get top scores. Public."""
    return _leaderboard_repo.get_top(limit)


# ---------------------------------------------------------------------------
# User metrics and sessions
# ---------------------------------------------------------------------------

@router.get("/me/metrics")
def api_get_metrics(current_user: dict = Depends(get_current_user)):
    """Return aggregate gameplay statistics for the authenticated user."""
    if not _metrics:
        return {}
    metrics = _metrics.get_metrics(current_user["sub"])
    return metrics or {}


@router.get("/me/sessions")
def api_get_user_sessions(current_user: dict = Depends(get_current_user)):
    """List all game sessions belonging to the authenticated user."""
    if hasattr(_player_repo, "find_by_user_id"):
        return _player_repo.find_by_user_id(current_user["sub"])
    return []


@router.get("/map")
def api_get_map():
    """Get Silicon Valley map regions and their metadata."""
    from app.domain.scoring import MapConfig
    return {
        "regions": MapConfig.REGION_STAGE_MAP,
        "bosses": MapConfig.BOSS_ARCHETYPES,
        "mentors": MapConfig.MENTOR_ARCHETYPES,
    }
