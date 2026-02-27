"""Unit tests for submit_answer use case."""
import pytest
from app.application.submit_answer import submit_answer
from app.domain.enums import CareerStage, GameEnding, ChallengeCategory
from tests.conftest import make_player, make_challenge


class TestSubmitAnswerCorrect:
    def test_correct_answer_returns_correct_outcome(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        result = submit_answer(p, ch, selected_index=0)
        assert result["outcome"] == "correct"

    def test_correct_answer_explanation_included(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        result = submit_answer(p, ch, 0)
        assert "explanation" in result

    def test_correct_answer_awards_points(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        before = p.score
        submit_answer(p, ch, 0)
        assert p.score > before

    def test_correct_marks_challenge_completed(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        submit_answer(p, ch, 0)
        assert p.has_completed("intern_01")


class TestSubmitAnswerWrong:
    def test_wrong_answer_returns_wrong_outcome(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        result = submit_answer(p, ch, 1)
        assert result["outcome"] == "wrong"

    def test_wrong_answer_explanation_included(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        result = submit_answer(p, ch, 1)
        assert "explanation" in result

    def test_wrong_increments_error_count(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        submit_answer(p, ch, 1)
        assert p.current_errors == 1


class TestSubmitAnswerGameOver:
    def test_two_wrongs_trigger_game_over(self):
        p = make_player()
        ch1 = make_challenge("intern_01", correct_index=0)
        ch2 = make_challenge("intern_02", correct_index=0)
        submit_answer(p, ch1, 1)  # wrong
        result = submit_answer(p, ch2, 1)  # wrong again
        assert result["outcome"] == "game_over"
        assert p.status == GameEnding.GAME_OVER


class TestSubmitAnswerArchitecturePenalty:
    def test_wrong_architecture_result_still_wrong_outcome(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0, category=ChallengeCategory.ARCHITECTURE)
        result = submit_answer(p, ch, 1)
        assert result["outcome"] == "wrong"
        # Architecture penalty: points_awarded is 0 (penalty applied inside player)
        # Score shouldn't change
        assert p.score == 0


class TestSubmitAnswerValidation:
    def test_invalid_index_raises_value_error(self):
        p = make_player()
        ch = make_challenge("intern_01", n_options=4)
        with pytest.raises(ValueError, match="Invalid option"):
            submit_answer(p, ch, 99)

    def test_negative_index_raises_value_error(self):
        p = make_player()
        ch = make_challenge("intern_01", n_options=4)
        with pytest.raises(ValueError, match="Invalid option"):
            submit_answer(p, ch, -1)

    def test_game_over_state_raises(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        ch = make_challenge("intern_01")
        with pytest.raises(RuntimeError, match="Game Over"):
            submit_answer(p, ch, 0)

    def test_insufficient_stage_raises_permission_error(self):
        p = make_player(stage=CareerStage.INTERN)
        ch = make_challenge("senior_01", required_stage=CareerStage.SENIOR)
        with pytest.raises(PermissionError, match="Senior"):
            submit_answer(p, ch, 0)

    def test_already_completed_raises_value_error(self):
        p = make_player()
        ch = make_challenge("intern_01", correct_index=0)
        submit_answer(p, ch, 0)  # complete it
        with pytest.raises(ValueError, match="already completed"):
            submit_answer(p, ch, 0)  # try again


class TestSubmitAnswerPromotion:
    def test_three_corrects_promote_player(self):
        p = make_player(stage=CareerStage.INTERN)
        results = []
        for i in range(3):
            ch = make_challenge(f"intern_0{i+1}_x", required_stage=CareerStage.INTERN),
            results.append(submit_answer(p, ch[0], 0))
        assert p.stage == CareerStage.JUNIOR
        # Last result should indicate promotion
        assert results[-1].get("promotion") is True
