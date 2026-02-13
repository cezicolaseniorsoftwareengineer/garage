"""PostgreSQL-backed player session repository."""
from uuid import UUID
from typing import Optional, List

from app.domain.player import Player, Attempt
from app.domain.character import Character
from app.domain.enums import (
    Gender, Ethnicity, BackendLanguage, CareerStage, GameEnding,
)
from app.infrastructure.database.models import (
    GameSessionModel, CharacterModel, AttemptModel,
)


class PgPlayerRepository:
    """Player session persistence via PostgreSQL (Neon)."""

    def __init__(self, session_factory):
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, player: Player) -> None:
        """Persist the full Player aggregate (character + session + new attempts)."""
        with self._sf() as session:
            # 1) Upsert character
            char_id = str(player.character.id)
            char = session.get(CharacterModel, char_id)
            if not char:
                char = CharacterModel(
                    id=char_id,
                    gender=player.character.gender.value,
                    ethnicity=player.character.ethnicity.value,
                    avatar_index=player.character.avatar_index,
                )
                session.add(char)
                session.flush()

            # 2) Upsert game session
            pid = str(player.id)
            gs = session.get(GameSessionModel, pid)
            if gs:
                gs.name = player.name
                gs.stage = player.stage.value
                gs.score = player.score
                gs.current_errors = player.current_errors
                gs.completed_challenges = list(player.completed_challenges)
                gs.game_over_count = player.game_over_count
                gs.status = player.status.value
            else:
                gs = GameSessionModel(
                    id=pid,
                    user_id=player.user_id,
                    name=player.name,
                    character_id=char_id,
                    language=player.language.value,
                    stage=player.stage.value,
                    score=player.score,
                    current_errors=player.current_errors,
                    completed_challenges=list(player.completed_challenges),
                    game_over_count=player.game_over_count,
                    status=player.status.value,
                )
                session.add(gs)

            # 3) Insert only NEW attempts (append-only)
            existing_count = (
                session.query(AttemptModel)
                .filter(AttemptModel.session_id == pid)
                .count()
            )
            for attempt in player.attempts[existing_count:]:
                ad = attempt.to_dict()
                session.add(AttemptModel(
                    session_id=pid,
                    challenge_id=ad["challenge_id"],
                    selected_index=ad["selected_index"],
                    is_correct=ad["is_correct"],
                    points_awarded=ad["points_awarded"],
                ))

            session.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, player_id: str) -> Optional[Player]:
        """Load a full Player aggregate by session id."""
        with self._sf() as session:
            gs = session.get(GameSessionModel, player_id)
            if not gs:
                return None
            return self._to_domain(gs)

    def find_by_user_id(self, user_id: str) -> List[dict]:
        """Return summary list of all sessions belonging to a user."""
        with self._sf() as session:
            rows = (
                session.query(GameSessionModel)
                .filter(GameSessionModel.user_id == user_id)
                .order_by(GameSessionModel.created_at.desc())
                .all()
            )
            return [
                {
                    "session_id": r.id,
                    "name": r.name,
                    "stage": r.stage,
                    "score": r.score,
                    "status": r.status,
                    "language": r.language,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(gs: GameSessionModel) -> Player:
        char = gs.character
        character = Character(
            gender=Gender(char.gender),
            ethnicity=Ethnicity(char.ethnicity),
            avatar_index=char.avatar_index,
            character_id=UUID(char.id),
        )
        attempts = [
            Attempt(
                challenge_id=a.challenge_id,
                selected_index=a.selected_index,
                is_correct=a.is_correct,
                points_awarded=a.points_awarded,
                timestamp=a.timestamp.isoformat() if a.timestamp else None,
            )
            for a in gs.attempts
        ]
        return Player(
            name=gs.name,
            character=character,
            language=BackendLanguage(gs.language),
            player_id=UUID(gs.id),
            user_id=gs.user_id,
            stage=CareerStage(gs.stage),
            score=gs.score,
            current_errors=gs.current_errors,
            completed_challenges=list(gs.completed_challenges or []),
            attempts=attempts,
            game_over_count=gs.game_over_count,
            status=GameEnding(gs.status),
            created_at=gs.created_at.isoformat() if gs.created_at else None,
        )
