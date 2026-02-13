"""PostgreSQL-backed leaderboard repository."""
from typing import List

from app.infrastructure.database.models import LeaderboardEntryModel


class PgLeaderboardRepository:
    """Leaderboard persistence via PostgreSQL (Neon)."""

    def __init__(self, session_factory):
        self._sf = session_factory

    def submit(
        self,
        player_name: str,
        score: int,
        stage: str,
        language: str,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Insert a new leaderboard entry and return rank info."""
        with self._sf() as session:
            entry = LeaderboardEntryModel(
                user_id=user_id,
                session_id=session_id,
                player_name=player_name,
                score=score,
                stage=stage,
                language=language,
            )
            session.add(entry)
            session.commit()

            rank = (
                session.query(LeaderboardEntryModel)
                .filter(LeaderboardEntryModel.score > score)
                .count()
            ) + 1
            total = session.query(LeaderboardEntryModel).count()

            return {"rank": rank, "total_entries": total}

    def get_top(self, limit: int = 10) -> List[dict]:
        """Return the top N leaderboard entries by score descending."""
        with self._sf() as session:
            rows = (
                session.query(LeaderboardEntryModel)
                .order_by(LeaderboardEntryModel.score.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "player_name": r.player_name,
                    "score": r.score,
                    "stage": r.stage,
                    "language": r.language,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in rows
            ]

    def get_user_best(self, user_id: str) -> dict | None:
        """Return the best leaderboard entry for a given user."""
        with self._sf() as session:
            row = (
                session.query(LeaderboardEntryModel)
                .filter(LeaderboardEntryModel.user_id == user_id)
                .order_by(LeaderboardEntryModel.score.desc())
                .first()
            )
            if not row:
                return None
            return {
                "player_name": row.player_name,
                "score": row.score,
                "stage": row.stage,
                "language": row.language,
            }
