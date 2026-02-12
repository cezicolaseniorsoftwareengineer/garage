"""Use case: validate and record a player's answer."""
from app.domain.player import Player
from app.domain.challenge import Challenge
from app.domain.scoring import ScoringRules
from app.domain.invariant import (
    validate_stage_access,
    validate_not_game_over,
    validate_challenge_not_completed,
)


def submit_answer(
    player: Player,
    challenge: Challenge,
    selected_index: int,
) -> dict:
    """
    Process a player's answer submission.
    All validation happens in the domain.
    Returns outcome dict with result details.
    """
    # Domain invariant checks
    validate_not_game_over(player.status.value)
    validate_stage_access(player.stage, challenge.required_stage)
    validate_challenge_not_completed(player.completed_challenges, challenge.id)

    # Validate selected index
    if selected_index < 0 or selected_index >= len(challenge.options):
        raise ValueError(f"Invalid option index: {selected_index}")

    # Determine correctness
    is_correct = selected_index == challenge.correct_index
    selected_option = challenge.options[selected_index]

    # Calculate points using domain scoring rules
    points = ScoringRules.calculate_points(
        is_correct=is_correct,
        previous_errors_on_challenge=player.current_errors,
        category=challenge.category.value,
    )

    # Record attempt in player aggregate
    result = player.record_attempt(
        challenge_id=challenge.id,
        selected_index=selected_index,
        is_correct=is_correct,
        points=points if points > 0 else 0,
    )

    # Add explanation to result
    result["explanation"] = selected_option.explanation

    # Check for promotion after correct answer
    if is_correct:
        promotion = player.check_promotion()
        if promotion:
            result["promotion"] = True
            result["new_stage"] = promotion["new_stage"]
            result["promotion_message"] = promotion["message"]

    return result
