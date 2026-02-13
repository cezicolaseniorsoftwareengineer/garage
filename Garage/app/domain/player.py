"""Player entity -- session state, career progression, scoring."""
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List

from app.domain.enums import CareerStage, BackendLanguage, GameEnding
from app.domain.character import Character


class Attempt:
    """Record of a single challenge attempt. Immutable."""

    def __init__(
        self,
        challenge_id: str,
        selected_index: int,
        is_correct: bool,
        points_awarded: int,
        timestamp: str | None = None,
    ):
        self._challenge_id = challenge_id
        self._selected_index = selected_index
        self._is_correct = is_correct
        self._points_awarded = points_awarded
        self._timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    @property
    def challenge_id(self) -> str:
        return self._challenge_id

    @property
    def is_correct(self) -> bool:
        return self._is_correct

    @property
    def points_awarded(self) -> int:
        return self._points_awarded

    def to_dict(self) -> dict:
        return {
            "challenge_id": self._challenge_id,
            "selected_index": self._selected_index,
            "is_correct": self._is_correct,
            "points_awarded": self._points_awarded,
            "timestamp": self._timestamp,
        }


class Player:
    """
    Aggregate root. Encapsulates all game state for one player session.
    Enforces invariants: error limits, progression rules, scoring.
    """

    MAX_ERRORS_PER_CHALLENGE = 3
    CHALLENGES_TO_PROMOTE = 3

    def __init__(
        self,
        name: str,
        character: Character,
        language: BackendLanguage,
        player_id: UUID | None = None,
        user_id: str | None = None,
        stage: CareerStage = CareerStage.INTERN,
        score: int = 0,
        current_errors: int = 0,
        completed_challenges: list | None = None,
        attempts: list | None = None,
        game_over_count: int = 0,
        status: GameEnding = GameEnding.IN_PROGRESS,
        created_at: str | None = None,
    ):
        if not name or not name.strip():
            raise ValueError("Player name cannot be empty")

        self._id = player_id or uuid4()
        self._user_id = user_id
        self._name = name.strip()
        self._character = character
        self._language = language
        self._stage = stage
        self._score = score
        self._current_errors = current_errors
        self._completed_challenges: List[str] = completed_challenges or []
        self._attempts: List[Attempt] = attempts or []
        self._game_over_count = game_over_count
        self._status = status
        self._created_at = created_at or datetime.now(timezone.utc).isoformat()

    # --- Properties (Read-Only) ---

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def user_id(self) -> str | None:
        return self._user_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def character(self) -> Character:
        return self._character

    @property
    def language(self) -> BackendLanguage:
        return self._language

    @property
    def stage(self) -> CareerStage:
        return self._stage

    @property
    def score(self) -> int:
        return self._score

    @property
    def current_errors(self) -> int:
        return self._current_errors

    @property
    def completed_challenges(self) -> List[str]:
        return list(self._completed_challenges)

    @property
    def attempts(self) -> List[Attempt]:
        return list(self._attempts)

    @property
    def game_over_count(self) -> int:
        return self._game_over_count

    @property
    def status(self) -> GameEnding:
        return self._status

    # --- Domain Logic ---

    def has_completed(self, challenge_id: str) -> bool:
        return challenge_id in self._completed_challenges

    def can_attempt(self, challenge_id: str, required_stage: CareerStage) -> bool:
        """Player can attempt if stage is sufficient and not already completed."""
        if self._status == GameEnding.GAME_OVER:
            return False
        if required_stage.stage_index() > self._stage.stage_index():
            return False
        if self.has_completed(challenge_id):
            return False
        return True

    def record_attempt(self, challenge_id: str, selected_index: int, is_correct: bool, points: int) -> dict:
        """
        Record a challenge attempt. Returns result dict with outcome.
        Enforces 3-error game over rule.
        """
        if self._status == GameEnding.GAME_OVER:
            raise RuntimeError("Cannot attempt challenges during Game Over state")

        awarded = points if is_correct else 0
        attempt = Attempt(
            challenge_id=challenge_id,
            selected_index=selected_index,
            is_correct=is_correct,
            points_awarded=awarded,
        )
        self._attempts.append(attempt)

        if is_correct:
            self._score += awarded
            if challenge_id not in self._completed_challenges:
                self._completed_challenges.append(challenge_id)
            self._current_errors = 0
            return {
                "outcome": "correct",
                "points_awarded": awarded,
                "total_score": self._score,
                "stage": self._stage.value,
                "promotion": False,
            }
        else:
            self._current_errors += 1
            if self._current_errors >= self.MAX_ERRORS_PER_CHALLENGE:
                return self._trigger_game_over()
            return {
                "outcome": "wrong",
                "errors_remaining": self.MAX_ERRORS_PER_CHALLENGE - self._current_errors,
                "total_score": self._score,
                "stage": self._stage.value,
                "promotion": False,
            }

    def _trigger_game_over(self) -> dict:
        """
        Game Over: reset to start of current stage.
        History is NEVER erased. Learning persists.
        """
        self._game_over_count += 1
        self._current_errors = 0
        # Remove completed challenges from current stage only
        self._completed_challenges = [
            c for c in self._completed_challenges
            if not c.startswith(self._stage.value.lower())
        ]
        self._status = GameEnding.GAME_OVER
        return {
            "outcome": "game_over",
            "message": "3 errors reached. Returning to start of current stage.",
            "stage": self._stage.value,
            "game_over_count": self._game_over_count,
            "total_attempts": len(self._attempts),
            "promotion": False,
        }

    def recover_from_game_over(self) -> None:
        """Allow player to restart from current stage after game over."""
        if self._status == GameEnding.GAME_OVER:
            self._status = GameEnding.IN_PROGRESS
            self._current_errors = 0

    def check_promotion(self) -> dict | None:
        """
        Check if player qualifies for promotion.
        Requires CHALLENGES_TO_PROMOTE completed in current stage.
        """
        stage_challenges = [
            c for c in self._completed_challenges
            if c.startswith(self._stage.value.lower())
        ]
        STAGE_PT = {
            "Intern": "Estagiario",
            "Junior": "Junior",
            "Mid": "Pleno",
            "Senior": "Senior",
            "Staff": "Staff",
            "Principal": "Principal",
            "Distinguished": "Engenheiro Distinto",
        }
        if len(stage_challenges) >= self.CHALLENGES_TO_PROMOTE:
            next_stage = self._stage.next_stage()
            if next_stage:
                self._stage = next_stage
                self._current_errors = 0
                stage_pt = STAGE_PT.get(self._stage.value, self._stage.value)
                return {
                    "promoted": True,
                    "new_stage": self._stage.value,
                    "message": f"Promovido a {stage_pt}!",
                }
        return None

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "id": str(self._id),
            "user_id": self._user_id,
            "name": self._name,
            "character": self._character.to_dict(),
            "language": self._language.value,
            "stage": self._stage.value,
            "score": self._score,
            "current_errors": self._current_errors,
            "max_errors": self.MAX_ERRORS_PER_CHALLENGE,
            "completed_challenges": self._completed_challenges,
            "game_over_count": self._game_over_count,
            "status": self._status.value,
            "total_attempts": len(self._attempts),
            "created_at": self._created_at,
        }
