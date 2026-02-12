"""Validation guards for domain state transitions."""
from app.domain.enums import CareerStage


def validate_stage_access(player_stage: CareerStage, required_stage: CareerStage) -> None:
    """Raises if player does not have sufficient career stage."""
    if required_stage.stage_index() > player_stage.stage_index():
        raise PermissionError(
            f"Stage {required_stage.value} required. Current: {player_stage.value}."
        )


def validate_not_game_over(status: str) -> None:
    """Raises if player is in Game Over state."""
    if status == "game_over":
        raise RuntimeError("Player is in Game Over state. Must recover first.")


def validate_challenge_not_completed(completed: list, challenge_id: str) -> None:
    """Raises if challenge was already completed."""
    if challenge_id in completed:
        raise ValueError(f"Challenge {challenge_id} already completed.")
