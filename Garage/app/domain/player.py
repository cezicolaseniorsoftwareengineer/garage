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

    MAX_ERRORS_PER_STAGE = 2   # 2 wrong answers within a stage -> game over
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
        # World state persistence
        collected_books: list | None = None,
        completed_regions: list | None = None,
        current_region: str | None = None,
        player_world_x: int = 100,
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
        # World state persistence
        self._collected_books: List[str] = collected_books or []
        self._completed_regions: List[str] = completed_regions or []
        self._current_region = current_region
        self._player_world_x = player_world_x

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

    @property
    def collected_books(self) -> List[str]:
        return list(self._collected_books)

    @property
    def completed_regions(self) -> List[str]:
        return list(self._completed_regions)

    @property
    def current_region(self) -> str | None:
        return self._current_region

    @property
    def player_world_x(self) -> int:
        return self._player_world_x

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
        Enforces 2-error-per-stage game over rule.
        Errors accumulate across all challenges within the same stage.
        Counter only resets on stage promotion or after a game over recovery.
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
            # Errors are NOT reset on correct answer -- they persist for the whole stage.
            return {
                "outcome": "correct",
                "points_awarded": awarded,
                "total_score": self._score,
                "current_errors": self._current_errors,
                "errors_remaining": self.MAX_ERRORS_PER_STAGE - self._current_errors,
                "stage": self._stage.value,
                "promotion": False,
            }
        else:
            self._current_errors += 1
            if self._current_errors >= self.MAX_ERRORS_PER_STAGE:
                return self._trigger_game_over()
            return {
                "outcome": "wrong",
                "current_errors": self._current_errors,
                "errors_remaining": self.MAX_ERRORS_PER_STAGE - self._current_errors,
                "total_score": self._score,
                "stage": self._stage.value,
                "promotion": False,
            }

    def _trigger_game_over(self) -> dict:
        """
        Game Over: 2 wrong answers accumulated in the current stage.
        Resets error counter and removes completed challenges for this stage.
        History is NEVER erased. Learning persists.
        """
        self._game_over_count += 1
        self._current_errors = 0
        # Remove completed challenges from current stage only -- player retries this stage
        self._completed_challenges = [
            c for c in self._completed_challenges
            if not c.startswith(self._stage.value.lower())
        ]
        self._status = GameEnding.GAME_OVER
        return {
            "outcome": "game_over",
            "message": "2 errors in this stage. Returning to start of current stage.",
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

    def mark_completed(self) -> None:
        """Mark this session as completed (player reached Distinguished)."""
        self._status = GameEnding.COMPLETED

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
            "Distinguished": "CEO",
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

    # --- World State Management ---

    def collect_book(self, book_id: str) -> None:
        """Record that a book was collected."""
        if book_id not in self._collected_books:
            self._collected_books.append(book_id)

    def complete_region(self, region_name: str) -> None:
        """Record that a region/company was fully completed."""
        if region_name not in self._completed_regions:
            self._completed_regions.append(region_name)

    def set_current_region(self, region_name: str | None) -> None:
        """Set the current region the player is in (for persistence)."""
        self._current_region = region_name

    def set_world_position(self, x: int) -> None:
        """Set the player's world X position (for persistence)."""
        self._player_world_x = x

    def update_world_state(
        self,
        collected_books: list | None = None,
        completed_regions: list | None = None,
        current_region: str | None = None,
        player_world_x: int | None = None,
    ) -> None:
        """Batch update world state for efficiency."""
        if collected_books is not None:
            self._collected_books = list(collected_books)
        if completed_regions is not None:
            self._completed_regions = list(completed_regions)
        if current_region is not None:
            self._current_region = current_region
        if player_world_x is not None:
            self._player_world_x = player_world_x

    def reset_world_state(self) -> None:
        """Reset world state when starting a new game."""
        self._collected_books = []
        self._completed_regions = []
        self._current_region = None
        self._player_world_x = 100

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
            "max_errors": self.MAX_ERRORS_PER_STAGE,
            "completed_challenges": self._completed_challenges,
            "game_over_count": self._game_over_count,
            "status": self._status.value,
            "total_attempts": len(self._attempts),
            "created_at": self._created_at,
            # World state persistence
            "collected_books": self._collected_books,
            "completed_regions": self._completed_regions,
            "current_region": self._current_region,
            "player_world_x": self._player_world_x,
        }
