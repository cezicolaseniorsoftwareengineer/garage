"""Unit tests for progress_stage use case."""
import pytest
from app.application.progress_stage import recover_from_game_over, get_progress
from app.domain.enums import GameEnding
from app.domain.player import Player
from tests.conftest import make_player


class TestRecoverFromGameOver:
    def test_returns_in_progress_status(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        result = recover_from_game_over(p)
        assert result["status"] == "in_progress"

    def test_returns_correct_stage(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        result = recover_from_game_over(p)
        assert result["stage"] == "Intern"

    def test_message_in_result(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        result = recover_from_game_over(p)
        assert "message" in result

    def test_player_becomes_in_progress(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        recover_from_game_over(p)
        assert p.status == GameEnding.IN_PROGRESS


class TestGetProgress:
    def test_all_keys_present(self):
        p = make_player()
        result = get_progress(p)
        expected_keys = {
            "stage", "stage_index", "total_stages", "score",
            "completed_challenges", "total_attempts", "current_errors",
            "max_errors", "game_over_count", "status",
        }
        assert expected_keys <= set(result.keys())

    def test_max_errors_attribute_exists(self):
        """Regression test: MAX_ERRORS_PER_CHALLENGE was a typo (now fixed to MAX_ERRORS_PER_STAGE)."""
        assert hasattr(Player, "MAX_ERRORS_PER_STAGE"), "Player.MAX_ERRORS_PER_STAGE must exist"
        p = make_player()
        result = get_progress(p)
        assert result["max_errors"] == Player.MAX_ERRORS_PER_STAGE

    def test_stage_index_intern_is_zero(self):
        p = make_player()
        result = get_progress(p)
        assert result["stage_index"] == 0

    def test_total_stages_is_seven(self):
        p = make_player()
        assert get_progress(p)["total_stages"] == 7
