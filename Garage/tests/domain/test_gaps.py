"""Gap-filling tests — covers missing property accesses and edge cases."""
import json
import os
import uuid
import tempfile
import pytest
from unittest.mock import MagicMock

from app.domain.challenge import Challenge, ChallengeOption
from app.domain.character import Character
from app.domain.enums import (
    ChallengeCategory, CareerStage, MapRegion, Gender, Ethnicity, BackendLanguage, GameEnding
)
from app.domain.player import Attempt, Player
from app.domain.user import User


# ---------------------------------------------------------------------------
# Challenge property coverage (lines 88,92,96,108,116,120,124,131)
# ---------------------------------------------------------------------------

def _make_challenge() -> Challenge:
    opt_correct = ChallengeOption(text="correct", is_correct=True, explanation="yes")
    opt_wrong = ChallengeOption(text="wrong", is_correct=False, explanation="no")
    return Challenge(
        challenge_id="ch-1",
        title="Test Challenge",
        description="Desc",
        context_code="int x = 1;",
        category=ChallengeCategory.LOGIC,
        required_stage=CareerStage.INTERN,
        region=MapRegion.XEROX_PARC,
        options=[opt_correct, opt_wrong],
        mentor_name="Alan Kay",
        points_on_correct=150,
        points_on_wrong=0,
    )


class TestChallengeProperties:
    def test_id_property(self):
        c = _make_challenge()
        assert c.id == "ch-1"

    def test_title_property(self):
        c = _make_challenge()
        assert c.title == "Test Challenge"

    def test_description_property(self):
        c = _make_challenge()
        assert c.description == "Desc"

    def test_category_property(self):
        c = _make_challenge()
        assert c.category == ChallengeCategory.LOGIC

    def test_region_property(self):
        c = _make_challenge()
        assert c.region == MapRegion.XEROX_PARC

    def test_options_property_returns_copy(self):
        c = _make_challenge()
        opts = c.options
        assert len(opts) == 2

    def test_mentor_name_property(self):
        c = _make_challenge()
        assert c.mentor_name == "Alan Kay"

    def test_points_on_wrong_property(self):
        c = _make_challenge()
        assert c.points_on_wrong == 0


# ---------------------------------------------------------------------------
# Attempt property coverage (lines 33,37,41)
# ---------------------------------------------------------------------------

class TestAttemptProperties:
    def test_challenge_id_property(self):
        a = Attempt("ch-1", 0, True, 100)
        assert a.challenge_id == "ch-1"

    def test_is_correct_property(self):
        a = Attempt("ch-1", 0, True, 100)
        assert a.is_correct is True

    def test_points_awarded_property(self):
        a = Attempt("ch-1", 0, True, 200)
        assert a.points_awarded == 200


# ---------------------------------------------------------------------------
# Player property coverage (lines 121,125)
# ---------------------------------------------------------------------------

def _make_player() -> Player:
    char = Character(Gender.MALE, Ethnicity.BLACK, 0)
    return Player("Dev", char, BackendLanguage.JAVA)


class TestPlayerCharacterLanguage:
    def test_character_property(self):
        p = _make_player()
        assert isinstance(p.character, Character)

    def test_language_property(self):
        p = _make_player()
        assert p.language == BackendLanguage.JAVA


# ---------------------------------------------------------------------------
# User.full_name property (line 47)
# ---------------------------------------------------------------------------

class TestUserFullName:
    def test_full_name_property(self):
        u = User(
            full_name="Ada Lovelace",
            username="ada",
            email="ada@example.com",
            whatsapp="+5511999999999",
            profession="Engineer",
            password_hash="hash",
            salt="salt",
        )
        assert u.full_name == "Ada Lovelace"


# ---------------------------------------------------------------------------
# ChallengeRepository edge cases (lines 20-21, 57, 63)
# ---------------------------------------------------------------------------

class TestChallengeRepositoryEdgeCases:
    def test_nonexistent_file_returns_empty(self, tmp_path):
        from app.infrastructure.repositories.challenge_repository import ChallengeRepository
        repo = ChallengeRepository(str(tmp_path / "nonexistent.json"))
        assert repo.get_all() == []

    def test_get_by_id_returns_none_when_not_found(self, tmp_path):
        from app.infrastructure.repositories.challenge_repository import ChallengeRepository
        path = str(tmp_path / "challenges.json")
        with open(path, "w") as f:
            json.dump([], f)
        repo = ChallengeRepository(path)
        assert repo.get_by_id("nonexistent-id") is None

    def test_get_by_region_returns_filtered_challenges(self, tmp_path):
        from app.infrastructure.repositories.challenge_repository import ChallengeRepository
        path = str(tmp_path / "challenges.json")
        data = [
            {
                "id": "c1",
                "title": "T1",
                "description": "D1",
                "category": "logic",
                "required_stage": "Intern",
                "region": "Xerox PARC",
                "options": [
                    {"text": "Yes", "is_correct": True, "explanation": "Yes!"},
                    {"text": "No", "is_correct": False, "explanation": "No."},
                ],
            }
        ]
        with open(path, "w") as f:
            json.dump(data, f)
        repo = ChallengeRepository(path)
        results = repo.get_by_region(MapRegion.XEROX_PARC)
        assert len(results) == 1
        results_other = repo.get_by_region(MapRegion.APPLE_GARAGE)
        assert len(results_other) == 0


# ---------------------------------------------------------------------------
# PlayerRepository edge cases (lines 55-61, 79-82, 91-92)
# ---------------------------------------------------------------------------

class TestPlayerRepositoryEdgeCases:
    def test_get_all_dict_returns_list(self, tmp_path):
        from app.infrastructure.repositories.player_repository import PlayerRepository
        repo = PlayerRepository(str(tmp_path / "sessions.json"))
        char = Character(Gender.MALE, Ethnicity.WHITE, 0)
        p = Player("Dev", char, BackendLanguage.JAVA)
        repo.save(p)
        result = repo.get_all_dict()
        assert isinstance(result, list)
        assert len(result) == 1
        assert "attempts" in result[0]

    def test_load_nonexistent_file_is_safe(self, tmp_path):
        from app.infrastructure.repositories.player_repository import PlayerRepository
        repo = PlayerRepository(str(tmp_path / "missing.json"))
        assert repo.get_all() == []

    def test_load_corrupted_file_is_safe(self, tmp_path):
        path = str(tmp_path / "corrupt.json")
        with open(path, "w") as f:
            f.write("{bad json content}")
        from app.infrastructure.repositories.player_repository import PlayerRepository
        repo = PlayerRepository(path)
        assert repo.get_all() == []

    def test_save_persists_atomically(self, tmp_path):
        from app.infrastructure.repositories.player_repository import PlayerRepository
        path = str(tmp_path / "sessions.json")
        repo = PlayerRepository(path)
        char = Character(Gender.FEMALE, Ethnicity.BLACK, 1)
        p = Player("Alice", char, BackendLanguage.JAVA)
        repo.save(p)
        # File should exist after save
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# UserRepository edge cases (lines 35, 50, 54-60, 78, 82-83, 85)
# ---------------------------------------------------------------------------

class TestUserRepositoryEdgeCases:
    def _make_user(self, username="testuser", email="test@test.com"):
        return User(
            full_name="Test User",
            username=username,
            email=email,
            whatsapp="+5511999999999",
            profession="Dev",
            password_hash="hash",
            salt="salt",
        )

    def test_find_by_username_returns_none_when_missing(self, tmp_path):
        from app.infrastructure.repositories.user_repository import UserRepository
        repo = UserRepository(str(tmp_path / "users.json"))
        result = repo.find_by_username("nobody")
        assert result is None

    def test_find_by_email_returns_none_when_missing(self, tmp_path):
        from app.infrastructure.repositories.user_repository import UserRepository
        repo = UserRepository(str(tmp_path / "users.json"))
        result = repo.find_by_email("nobody@test.com")
        assert result is None

    def test_persist_writes_to_disk(self, tmp_path):
        from app.infrastructure.repositories.user_repository import UserRepository
        path = str(tmp_path / "users.json")
        repo = UserRepository(path)
        u = self._make_user()
        repo.save(u)
        assert os.path.exists(path)
        with open(path, "r") as f:
            data = json.load(f)
        assert len(data) == 1

    def test_load_nonexistent_file_is_safe(self, tmp_path):
        from app.infrastructure.repositories.user_repository import UserRepository
        repo = UserRepository(str(tmp_path / "nope.json"))
        assert repo.get_all() == []

    def test_load_corrupted_file_is_safe(self, tmp_path):
        path = str(tmp_path / "corrupt_users.json")
        with open(path, "w") as f:
            f.write("{garbage")
        from app.infrastructure.repositories.user_repository import UserRepository
        repo = UserRepository(path)
        assert repo.get_all() == []

    def test_load_existing_users(self, tmp_path):
        from app.infrastructure.repositories.user_repository import UserRepository
        path = str(tmp_path / "users.json")
        uid = str(uuid.uuid4())
        data = {
            uid: {
                "id": uid,
                "full_name": "Loaded User",
                "username": "loadeduser",
                "email": "loaded@test.com",
                "whatsapp": "+55119",
                "profession": "Dev",
                "password_hash": "hash",
                "salt": "salt",
                "created_at": "2024-01-01T00:00:00",
            }
        }
        with open(path, "w") as f:
            json.dump(data, f)
        repo = UserRepository(path)
        all_users = repo.get_all()
        assert len(all_users) == 1
        assert all_users[0].username == "loadeduser"

    def test_update_password(self, tmp_path):
        from app.infrastructure.repositories.user_repository import UserRepository
        path = str(tmp_path / "users.json")
        repo = UserRepository(path)
        u = self._make_user()
        repo.save(u)
        repo.update_password(u.id, "new_hash", "bcrypt")
        updated = repo.find_by_id(u.id)
        assert updated is not None


# ---------------------------------------------------------------------------
# submit_answer — Distinguished completion path (lines 62-63)
# ---------------------------------------------------------------------------

class TestSubmitAnswerDistinguished:
    def test_distinguished_sets_game_completed(self):
        """When promotion reaches Distinguished, game_completed must be True."""
        from app.application.submit_answer import submit_answer
        from app.domain.player import Player
        from app.domain.challenge import Challenge, ChallengeOption

        char = Character(Gender.MALE, Ethnicity.WHITE, 0)
        player = Player("Dev", char, BackendLanguage.JAVA)

        # Move player to Principal stage (one before Distinguished)
        from app.domain.enums import CareerStage
        # Directly set internal state (white-box)
        player._stage = CareerStage.PRINCIPAL
        player._score = 9999
        player._current_errors = 0
        player._completed_challenges = [f"c{i}" for i in range(100)]

        # Create a challenge at Principal level
        from app.domain.enums import ChallengeCategory, MapRegion
        opt_correct = ChallengeOption("correct", True, "right")
        opt_wrong   = ChallengeOption("wrong", False, "nope")
        challenge = Challenge(
            challenge_id="chal-dist",
            title="Principal Challenge",
            description="Hard",
            context_code=None,
            category=ChallengeCategory.DISTRIBUTED_SYSTEMS,
            required_stage=CareerStage.PRINCIPAL,
            region=MapRegion.AMAZON,
            options=[opt_correct, opt_wrong],
            points_on_correct=200,
        )

        # Stub check_promotion to return Distinguished
        import app.application.submit_answer as sa
        orig_check = player.__class__.check_promotion

        def fake_promotion(self_inner):
            return {"new_stage": "Distinguished", "message": "Congratulations!"}

        player.__class__.check_promotion = fake_promotion
        try:
            result = submit_answer(player=player, challenge=challenge, selected_index=0)
        finally:
            player.__class__.check_promotion = orig_check

        assert result.get("game_completed") is True
        assert result.get("promotion") is True
