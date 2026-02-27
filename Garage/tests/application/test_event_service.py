"""Tests for EventService — audit trail event logging."""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockSession:
    def __init__(self, query_result=None):
        self.added = []
        self.committed = False
        self._query_result = query_result

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def flush(self):
        pass

    def query(self, model):
        return MockQuery(self._query_result)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def limit(self, n):
        return self

    def first(self):
        return self._result

    def all(self):
        return [self._result] if self._result else []


# ---------------------------------------------------------------------------
# Patch GameEventModel at import time to avoid needing a real DB
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_models():
    with patch("app.application.event_service.GameEventModel") as mock_model:
        mock_model.return_value = MagicMock()
        yield mock_model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEventServiceLog:
    def test_log_success(self, patch_models):
        from app.application.event_service import EventService

        session = MockSession()
        service = EventService(session_factory=lambda: session)
        service.log("game_started", user_id="u1", session_id="s1", payload={"x": 1})

        assert session.committed
        assert len(session.added) == 1

    def test_log_swallows_exception(self):
        """log() must never raise — it swallows errors silently."""
        from app.application.event_service import EventService

        def bad_factory():
            raise RuntimeError("DB connection failed")

        service = EventService(session_factory=bad_factory)
        # Should not raise
        service.log("some_event")

    def test_log_none_payload(self, patch_models):
        from app.application.event_service import EventService

        session = MockSession()
        service = EventService(session_factory=lambda: session)
        service.log("test_event")
        assert len(session.added) == 1

    def test_get_user_events(self, patch_models):
        from app.application.event_service import EventService

        mock_event = MagicMock()
        mock_event.event_type = "game_started"
        mock_event.session_id = "s1"
        mock_event.payload = {"x": 1}
        mock_event.timestamp = None

        session = MockSession(query_result=mock_event)
        service = EventService(session_factory=lambda: session)
        events = service.get_user_events("u1")

        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0]["event_type"] == "game_started"

    def test_get_user_events_with_timestamp(self, patch_models):
        from app.application.event_service import EventService
        from datetime import datetime, timezone

        mock_event = MagicMock()
        mock_event.event_type = "answer_submitted"
        mock_event.session_id = "s2"
        mock_event.payload = {}
        mock_event.timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)

        session = MockSession(query_result=mock_event)
        service = EventService(session_factory=lambda: session)
        events = service.get_user_events("u1")
        assert events[0]["timestamp"] is not None
