"""Unit tests for start_game use case."""
import pytest
from app.application.start_game import start_game
from app.domain.enums import CareerStage, GameEnding


class TestStartGame:
    def test_creates_player_with_correct_name(self):
        p = start_game("Linus", "male", "white", 0, "Java")
        assert p.name == "Linus"

    def test_creates_player_intern_stage(self):
        p = start_game("Alice", "female", "black", 1, "Python")
        assert p.stage == CareerStage.INTERN

    def test_creates_player_in_progress(self):
        p = start_game("Bob", "male", "asian", 2, "Go")
        assert p.status == GameEnding.IN_PROGRESS

    def test_creates_player_with_user_id(self):
        p = start_game("Dev", "male", "white", 0, "Java", user_id="uid-999")
        assert p.user_id == "uid-999"

    def test_creates_player_without_user_id(self):
        p = start_game("Dev", "female", "black", 0, "Rust")
        assert p.user_id is None

    def test_invalid_gender_raises(self):
        with pytest.raises(ValueError):
            start_game("Dev", "unknown_gender", "white", 0, "Java")

    def test_invalid_ethnicity_raises(self):
        with pytest.raises(ValueError):
            start_game("Dev", "male", "martian", 0, "Java")

    def test_invalid_language_raises(self):
        with pytest.raises(ValueError):
            start_game("Dev", "male", "white", 0, "COBOL")

    def test_invalid_avatar_index_raises(self):
        with pytest.raises(ValueError):
            start_game("Dev", "male", "white", 99, "Java")

    def test_player_has_uuid_id(self):
        p = start_game("Dev", "male", "white", 0, "Java")
        # UUIDs are 36 chars with hyphens
        assert len(str(p.id)) == 36
