"""Game event audit trail -- immutable event log for traceability."""
from app.infrastructure.database.models import GameEventModel


class EventService:
    """Append-only event logger. Must never break game flow on failure."""

    def __init__(self, session_factory):
        self._sf = session_factory

    def log(
        self,
        event_type: str,
        user_id: str | None = None,
        session_id: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """Record a game event. Silently swallows exceptions."""
        try:
            with self._sf() as session:
                event = GameEventModel(
                    user_id=user_id,
                    session_id=session_id,
                    event_type=event_type,
                    payload=payload,
                )
                session.add(event)
                session.commit()
        except Exception:
            # Audit logging must NEVER disrupt gameplay.
            pass

    def get_user_events(self, user_id: str, limit: int = 50) -> list:
        """Retrieve recent events for a given user."""
        with self._sf() as session:
            rows = (
                session.query(GameEventModel)
                .filter(GameEventModel.user_id == user_id)
                .order_by(GameEventModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "event_type": r.event_type,
                    "session_id": r.session_id,
                    "payload": r.payload,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in rows
            ]
