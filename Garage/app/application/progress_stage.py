"""Use case: game over recovery and stage progression."""
from app.domain.player import Player


def recover_from_game_over(player: Player) -> dict:
    """
    Allows player to restart from current stage after game over.
    History is preserved. Learning is never erased.
    """
    player.recover_from_game_over()
    return {
        "status": player.status.value,
        "stage": player.stage.value,
        "score": player.score,
        "message": "Recovered. Returning to start of current stage.",
    }


def get_progress(player: Player) -> dict:
    """Returns current player progression state."""
    return {
        "stage": player.stage.value,
        "stage_index": player.stage.stage_index(),
        "total_stages": 7,
        "score": player.score,
        "completed_challenges": len(player.completed_challenges),
        "total_attempts": len(player.attempts),
        "current_errors": player.current_errors,
        "max_errors": Player.MAX_ERRORS_PER_CHALLENGE,
        "game_over_count": player.game_over_count,
        "status": player.status.value,
    }
