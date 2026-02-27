"""
Comprehensive unit tests for Player aggregate root.

Covers:
- Creation and property access
- can_attempt invariants
- record_attempt: correct / wrong / game-over trigger
- _trigger_game_over: prefix filter safety (underscore boundary)
- check_promotion
- recover_from_game_over
- mark_completed
- World state: update_world_state (sentinel), collect_book, complete_region
- to_dict serialization
"""
import pytest
from app.domain.enums import CareerStage, BackendLanguage, GameEnding
from app.domain.player import Player, _UNSET
from tests.conftest import make_character, make_player, make_challenge


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
class TestPlayerCreation:
    def test_default_stage_is_intern(self):
        p = make_player()
        assert p.stage == CareerStage.INTERN

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            Player(name="", character=make_character(), language=BackendLanguage.JAVA)

    def test_whitespace_only_name_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            Player(name="   ", character=make_character(), language=BackendLanguage.JAVA)

    def test_name_is_stripped(self):
        p = Player(name="  Alice  ", character=make_character(), language=BackendLanguage.JAVA)
        assert p.name == "Alice"

    def test_initial_score_zero(self):
        p = make_player()
        assert p.score == 0

    def test_initial_errors_zero(self):
        p = make_player()
        assert p.current_errors == 0

    def test_initial_status_in_progress(self):
        p = make_player()
        assert p.status == GameEnding.IN_PROGRESS

    def test_user_id_stored(self):
        p = make_player(user_id="uuid-abc")
        assert p.user_id == "uuid-abc"

    def test_world_defaults(self):
        p = make_player()
        assert p.collected_books == []
        assert p.completed_regions == []
        assert p.current_region is None
        assert p.player_world_x == 100


# ---------------------------------------------------------------------------
# can_attempt
# ---------------------------------------------------------------------------
class TestCanAttempt:
    def test_can_attempt_own_stage(self):
        p = make_player()
        ch = make_challenge("intern_01", required_stage=CareerStage.INTERN)
        assert p.can_attempt(ch.id, ch.required_stage) is True

    def test_cannot_attempt_higher_stage(self):
        p = make_player()
        ch = make_challenge("senior_01", required_stage=CareerStage.SENIOR)
        assert p.can_attempt(ch.id, ch.required_stage) is False

    def test_cannot_attempt_already_completed(self):
        p = make_player()
        p._completed_challenges = ["intern_01"]
        ch = make_challenge("intern_01", required_stage=CareerStage.INTERN)
        assert p.can_attempt(ch.id, ch.required_stage) is False

    def test_cannot_attempt_in_game_over(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        ch = make_challenge("intern_01", required_stage=CareerStage.INTERN)
        assert p.can_attempt(ch.id, ch.required_stage) is False

    def test_higher_stage_player_can_attempt_lower_challenge(self):
        p = make_player(stage=CareerStage.SENIOR)
        ch = make_challenge("intern_01", required_stage=CareerStage.INTERN)
        assert p.can_attempt(ch.id, ch.required_stage) is True


# ---------------------------------------------------------------------------
# record_attempt
# ---------------------------------------------------------------------------
class TestRecordAttempt:
    def test_correct_answer_increases_score(self):
        p = make_player()
        result = p.record_attempt("intern_01", 0, True, 100)
        assert result["outcome"] == "correct"
        assert p.score == 100

    def test_correct_adds_to_completed(self):
        p = make_player()
        p.record_attempt("intern_01", 0, True, 100)
        assert "intern_01" in p.completed_challenges

    def test_correct_no_duplicate_in_completed(self):
        p = make_player()
        p.record_attempt("intern_01", 0, True, 100)
        p.record_attempt("intern_01", 0, True, 100)  # second call
        assert p.completed_challenges.count("intern_01") == 1

    def test_wrong_increments_errors(self):
        p = make_player()
        result = p.record_attempt("intern_01", 1, False, 0)
        assert result["outcome"] == "wrong"
        assert p.current_errors == 1

    def test_two_wrongs_triggers_game_over(self):
        p = make_player()
        p.record_attempt("intern_01", 1, False, 0)
        result = p.record_attempt("intern_02", 1, False, 0)
        assert result["outcome"] == "game_over"
        assert p.status == GameEnding.GAME_OVER
        assert p.game_over_count == 1

    def test_errors_remaining_decrements(self):
        p = make_player()
        result = p.record_attempt("intern_01", 1, False, 0)
        assert result["errors_remaining"] == 1

    def test_cannot_record_during_game_over(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        with pytest.raises(RuntimeError, match="Game Over"):
            p.record_attempt("intern_01", 0, True, 100)

    def test_attempts_list_grows(self):
        p = make_player()
        p.record_attempt("intern_01", 0, True, 100)
        p.record_attempt("intern_02", 1, False, 0)
        assert len(p.attempts) == 2

    def test_attempts_property_returns_copy(self):
        p = make_player()
        a1 = p.attempts
        a1.append("hack")  # mutate copy
        assert p.attempts == []  # original unchanged


# ---------------------------------------------------------------------------
# _trigger_game_over — prefix filter robustness
# ---------------------------------------------------------------------------
class TestTriggerGameOverFilter:
    """Verify the underscore-boundary fix: 'intern_' not just 'intern'."""

    def test_clears_only_intern_challenges(self):
        p = make_player(stage=CareerStage.INTERN)
        p._completed_challenges = [
            "intern_01_xerox",
            "intern_02_xerox",
            "junior_01_microsoft",  # must survive
        ]
        # Trigger game over
        p._current_errors = Player.MAX_ERRORS_PER_STAGE - 1
        p.record_attempt("intern_03", 1, False, 0)  # 2nd wrong
        # Junior challenges must survive
        assert "junior_01_microsoft" in p.completed_challenges
        # Intern challenges must be removed
        assert "intern_01_xerox" not in p.completed_challenges

    def test_does_not_remove_different_stage_with_similar_prefix(self):
        """
        If a stage is e.g. 'Mid' and there was a challenge 'mid_01',
        it should not accidentally match 'mid_something_else' from
        a different namespace. The underscore enforces a strict boundary.
        """
        p = make_player(stage=CareerStage.INTERN)
        # Hypothetical challenge whose id starts with 'intern' but no underscore
        # — should still be caught only if id starts with 'intern_'
        p._completed_challenges = ["intern_01", "internship_bonus"]
        p._current_errors = Player.MAX_ERRORS_PER_STAGE - 1
        p.record_attempt("intern_02", 1, False, 0)
        # 'internship_bonus' does NOT start with 'intern_' -> must survive
        assert "internship_bonus" in p.completed_challenges
        assert "intern_01" not in p.completed_challenges

    def test_game_over_resets_error_counter(self):
        p = make_player()
        p._current_errors = Player.MAX_ERRORS_PER_STAGE - 1
        p.record_attempt("intern_x", 1, False, 0)
        assert p.current_errors == 0

    def test_game_over_increments_count(self):
        p = make_player()
        p._current_errors = 1
        p.record_attempt("intern_x", 1, False, 0)
        assert p.game_over_count == 1


# ---------------------------------------------------------------------------
# check_promotion
# ---------------------------------------------------------------------------
class TestCheckPromotion:
    def test_no_promotion_before_threshold(self):
        p = make_player(stage=CareerStage.INTERN)
        p._completed_challenges = ["intern_01_x", "intern_02_x"]  # only 2 of 3
        assert p.check_promotion() is None

    def test_promotion_after_threshold(self):
        p = make_player(stage=CareerStage.INTERN)
        p._completed_challenges = ["intern_01_x", "intern_02_x", "intern_03_x"]
        result = p.check_promotion()
        assert result is not None
        assert result["promoted"] is True
        assert p.stage == CareerStage.JUNIOR

    def test_promotion_resets_errors(self):
        p = make_player(stage=CareerStage.INTERN)
        p._current_errors = 1
        p._completed_challenges = ["intern_01_x", "intern_02_x", "intern_03_x"]
        p.check_promotion()
        assert p.current_errors == 0

    def test_no_promotion_from_distinguished(self):
        p = make_player(stage=CareerStage.DISTINGUISHED)
        p._completed_challenges = [
            "distinguished_01_x", "distinguished_02_x", "distinguished_03_x"
        ]
        # Distinguished has no next stage
        result = p.check_promotion()
        assert result is None

    def test_promotion_message_in_portuguese(self):
        p = make_player(stage=CareerStage.INTERN)
        p._completed_challenges = ["intern_01", "intern_02", "intern_03"]
        result = p.check_promotion()
        assert result is not None
        # message should be in pt-BR
        assert "Estagiario" in result["message"] or "Junior" in result["message"]


# ---------------------------------------------------------------------------
# recover_from_game_over
# ---------------------------------------------------------------------------
class TestRecoverFromGameOver:
    def test_recover_sets_in_progress(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        p.recover_from_game_over()
        assert p.status == GameEnding.IN_PROGRESS

    def test_recover_resets_errors(self):
        p = make_player()
        p._status = GameEnding.GAME_OVER
        p._current_errors = 2
        p.recover_from_game_over()
        assert p.current_errors == 0

    def test_recover_does_nothing_when_in_progress(self):
        p = make_player()
        p.recover_from_game_over()  # should be a no-op
        assert p.status == GameEnding.IN_PROGRESS

    def test_mark_completed(self):
        p = make_player()
        p.mark_completed()
        assert p.status == GameEnding.COMPLETED


# ---------------------------------------------------------------------------
# World state management
# ---------------------------------------------------------------------------
class TestWorldState:
    def test_collect_book_adds(self):
        p = make_player()
        p.collect_book("book_alan_turing")
        assert "book_alan_turing" in p.collected_books

    def test_collect_book_no_duplicates(self):
        p = make_player()
        p.collect_book("book_x")
        p.collect_book("book_x")
        assert p.collected_books.count("book_x") == 1

    def test_complete_region_adds(self):
        p = make_player()
        p.complete_region("Xerox PARC")
        assert "Xerox PARC" in p.completed_regions

    def test_complete_region_no_duplicates(self):
        p = make_player()
        p.complete_region("Google")
        p.complete_region("Google")
        assert p.completed_regions.count("Google") == 1

    def test_set_current_region(self):
        p = make_player()
        p.set_current_region("Netflix")
        assert p.current_region == "Netflix"

    def test_set_current_region_to_none(self):
        p = make_player()
        p.set_current_region("Netflix")
        p.set_current_region(None)
        assert p.current_region is None

    def test_set_world_position(self):
        p = make_player()
        p.set_world_position(500)
        assert p.player_world_x == 500

    # --- update_world_state sentinel ---

    def test_update_world_state_sets_books(self):
        p = make_player()
        p.update_world_state(collected_books=["book_a", "book_b"])
        assert p.collected_books == ["book_a", "book_b"]

    def test_update_world_state_sets_regions(self):
        p = make_player()
        p.update_world_state(completed_regions=["Google", "Netflix"])
        assert p.completed_regions == ["Google", "Netflix"]

    def test_update_world_state_explicit_none_clears_region(self):
        """Passing current_region=None must clear it (sentinel check)."""
        p = make_player()
        p._current_region = "Netflix"
        p.update_world_state(current_region=None)
        assert p.current_region is None

    def test_update_world_state_not_passing_region_keeps_existing(self):
        """Not passing current_region at all must NOT clear the existing value."""
        p = make_player()
        p._current_region = "Netflix"
        p.update_world_state(collected_books=["book_x"])  # no current_region arg
        assert p.current_region == "Netflix"

    def test_update_world_state_sentinel_is_module_level(self):
        from app.domain.player import _UNSET
        assert _UNSET is not None

    def test_reset_world_state(self):
        p = make_player()
        p._collected_books = ["x"]
        p._completed_regions = ["y"]
        p._current_region = "z"
        p._player_world_x = 999
        p.reset_world_state()
        assert p.collected_books == []
        assert p.completed_regions == []
        assert p.current_region is None
        assert p.player_world_x == 100

    def test_collected_books_returns_copy(self):
        p = make_player()
        p.collect_book("book_x")
        copy = p.collected_books
        copy.append("injected")
        assert "injected" not in p.collected_books


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------
class TestPlayerToDict:
    def test_required_keys_present(self):
        p = make_player()
        d = p.to_dict()
        for key in ("id", "name", "stage", "score", "status", "current_errors",
                    "completed_challenges", "collected_books", "completed_regions",
                    "current_region", "player_world_x"):
            assert key in d, f"Missing key: {key}"

    def test_id_is_string(self):
        p = make_player()
        d = p.to_dict()
        assert isinstance(d["id"], str)

    def test_stage_is_string_value(self):
        p = make_player(stage=CareerStage.JUNIOR)
        assert p.to_dict()["stage"] == "Junior"
