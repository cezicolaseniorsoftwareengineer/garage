"""Game API routes -- start, submit, challenges, leaderboard."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.application.start_game import start_game
from app.application.submit_answer import submit_answer
from app.application.progress_stage import recover_from_game_over, get_progress
from app.domain.enums import CareerStage


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


def init_routes(player_repo, challenge_repo, leaderboard_repo):
    global _player_repo, _challenge_repo, _leaderboard_repo
    _player_repo = player_repo
    _challenge_repo = challenge_repo
    _leaderboard_repo = leaderboard_repo


@router.post("/start")
def api_start_game(req: StartGameRequest):
    """Create a new game session."""
    try:
        player = start_game(
            player_name=req.player_name,
            gender=req.gender,
            ethnicity=req.ethnicity,
            avatar_index=req.avatar_index,
            language=req.language,
        )
        _player_repo.save(player)
        return {
            "session_id": str(player.id),
            "player": player.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}")
def api_get_session(session_id: str):
    """Get current game session state."""
    player = _player_repo.get(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    return player.to_dict()


@router.get("/challenges")
def api_get_challenges(stage: Optional[str] = None):
    """Get available challenges, optionally filtered by stage."""
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
    """Get a specific challenge (without correct answer)."""
    challenge = _challenge_repo.get_by_id(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge.to_dict_for_player()


@router.post("/submit")
def api_submit_answer(req: SubmitAnswerRequest):
    """Submit an answer to a challenge."""
    player = _player_repo.get(req.session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")

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
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/recover")
def api_recover(req: RecoverRequest):
    """Recover from Game Over state."""
    player = _player_repo.get(req.session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")

    result = recover_from_game_over(player)
    _player_repo.save(player)
    return result


@router.get("/progress/{session_id}")
def api_get_progress(session_id: str):
    """Get player progression details."""
    player = _player_repo.get(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    return get_progress(player)


@router.get("/leaderboard")
def api_get_leaderboard(limit: int = 10):
    """Get top scores."""
    return _leaderboard_repo.get_top(limit)


@router.get("/map")
def api_get_map():
    """Get Silicon Valley map regions and their metadata."""
    from app.domain.scoring import MapConfig
    return {
        "regions": MapConfig.REGION_STAGE_MAP,
        "bosses": MapConfig.BOSS_ARCHETYPES,
        "mentors": MapConfig.MENTOR_ARCHETYPES,
    }
