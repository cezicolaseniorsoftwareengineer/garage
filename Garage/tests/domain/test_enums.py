"""Unit tests for CareerStage and GameEnding enums."""
import pytest
from app.domain.enums import CareerStage, GameEnding, BackendLanguage


class TestCareerStage:
    def test_progression_order_length(self):
        assert len(CareerStage.progression_order()) == 7

    def test_intern_is_first(self):
        assert CareerStage.progression_order()[0] == CareerStage.INTERN

    def test_distinguished_is_last(self):
        assert CareerStage.progression_order()[-1] == CareerStage.DISTINGUISHED

    def test_stage_index_intern(self):
        assert CareerStage.INTERN.stage_index() == 0

    def test_stage_index_distinguished(self):
        assert CareerStage.DISTINGUISHED.stage_index() == 6

    def test_next_stage_intern_is_junior(self):
        assert CareerStage.INTERN.next_stage() == CareerStage.JUNIOR

    def test_next_stage_distinguished_is_none(self):
        assert CareerStage.DISTINGUISHED.next_stage() is None

    def test_all_stages_have_next_except_last(self):
        stages = CareerStage.progression_order()
        for s in stages[:-1]:
            assert s.next_stage() is not None

    def test_stage_index_monotonically_increasing(self):
        indices = [s.stage_index() for s in CareerStage.progression_order()]
        assert indices == sorted(indices)
        assert len(set(indices)) == len(indices)  # all unique


class TestGameEnding:
    def test_values_are_strings(self):
        assert GameEnding.COMPLETED.value == "completed"
        assert GameEnding.GAME_OVER.value == "game_over"
        assert GameEnding.IN_PROGRESS.value == "in_progress"


class TestBackendLanguage:
    def test_java_value(self):
        assert BackendLanguage.JAVA.value == "Java"

    def test_all_languages_have_values(self):
        for lang in BackendLanguage:
            assert lang.value  # non-empty string
