"""Unit tests for domain invariant guards."""
import pytest
from app.domain.enums import CareerStage
from app.domain.invariant import (
    validate_stage_access,
    validate_not_game_over,
    validate_challenge_not_completed,
)


class TestValidateStageAccess:
    def test_equal_stage_passes(self):
        # Should not raise
        validate_stage_access(CareerStage.JUNIOR, CareerStage.JUNIOR)

    def test_higher_player_stage_passes(self):
        validate_stage_access(CareerStage.SENIOR, CareerStage.INTERN)

    def test_lower_player_stage_raises(self):
        with pytest.raises(PermissionError, match="Senior required"):
            validate_stage_access(CareerStage.INTERN, CareerStage.SENIOR)

    def test_error_message_contains_required(self):
        with pytest.raises(PermissionError, match="Principal"):
            validate_stage_access(CareerStage.MID, CareerStage.PRINCIPAL)


class TestValidateNotGameOver:
    def test_in_progress_passes(self):
        validate_not_game_over("in_progress")

    def test_completed_passes(self):
        validate_not_game_over("completed")

    def test_game_over_raises(self):
        with pytest.raises(RuntimeError, match="Game Over"):
            validate_not_game_over("game_over")


class TestValidateChallengeNotCompleted:
    def test_not_in_list_passes(self):
        validate_challenge_not_completed(["a", "b"], "c")

    def test_empty_list_passes(self):
        validate_challenge_not_completed([], "any_id")

    def test_already_completed_raises(self):
        with pytest.raises(ValueError, match="already completed"):
            validate_challenge_not_completed(["intern_01"], "intern_01")
