"""User metrics tracking service -- aggregate gameplay statistics."""
from datetime import datetime, timezone

from app.infrastructure.database.models import UserMetricsModel
from app.domain.enums import CareerStage


class MetricsService:
    """Updates per-user aggregate statistics after game events."""

    def __init__(self, session_factory):
        self._sf = session_factory

    def on_game_started(self, user_id: str, language: str) -> None:
        with self._sf() as session:
            m = self._get_or_create(session, user_id)
            m.total_games_started += 1
            m.favorite_language = language
            m.last_played_at = datetime.now(timezone.utc)
            session.commit()

    def on_answer_submitted(self, user_id: str, is_correct: bool, points: int) -> None:
        with self._sf() as session:
            m = self._get_or_create(session, user_id)
            m.total_attempts += 1
            if is_correct:
                m.total_correct += 1
                m.total_score_earned += points
            else:
                m.total_wrong += 1
            m.accuracy_rate = (
                m.total_correct / m.total_attempts if m.total_attempts > 0 else 0.0
            )
            m.last_played_at = datetime.now(timezone.utc)
            session.commit()

    def on_game_over(self, user_id: str) -> None:
        with self._sf() as session:
            m = self._get_or_create(session, user_id)
            m.total_game_overs += 1
            session.commit()

    def on_stage_promoted(self, user_id: str, new_stage: str, current_score: int) -> None:
        with self._sf() as session:
            m = self._get_or_create(session, user_id)
            stage_order = [s.value for s in CareerStage.progression_order()]
            new_idx = stage_order.index(new_stage) if new_stage in stage_order else 0
            cur_idx = stage_order.index(m.highest_stage) if m.highest_stage in stage_order else 0
            if new_idx > cur_idx:
                m.highest_stage = new_stage
            if current_score > m.highest_score:
                m.highest_score = current_score
            if new_stage == "Distinguished":
                m.total_games_completed += 1
            session.commit()

    def get_metrics(self, user_id: str) -> dict | None:
        with self._sf() as session:
            m = (
                session.query(UserMetricsModel)
                .filter(UserMetricsModel.user_id == user_id)
                .first()
            )
            if not m:
                return None
            return {
                "total_games_started": m.total_games_started,
                "total_games_completed": m.total_games_completed,
                "total_game_overs": m.total_game_overs,
                "total_attempts": m.total_attempts,
                "total_correct": m.total_correct,
                "total_wrong": m.total_wrong,
                "total_score_earned": m.total_score_earned,
                "highest_score": m.highest_score,
                "highest_stage": m.highest_stage,
                "accuracy_rate": round(m.accuracy_rate * 100, 1),
                "favorite_language": m.favorite_language,
                "last_played_at": m.last_played_at.isoformat() if m.last_played_at else None,
            }

    @staticmethod
    def _get_or_create(session, user_id: str) -> UserMetricsModel:
        m = (
            session.query(UserMetricsModel)
            .filter(UserMetricsModel.user_id == user_id)
            .first()
        )
        if not m:
            m = UserMetricsModel(user_id=user_id)
            session.add(m)
            session.flush()
        return m
