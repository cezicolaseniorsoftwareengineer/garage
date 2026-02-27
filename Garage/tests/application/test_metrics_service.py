"""Tests for MetricsService — user gameplay statistics."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_metrics_model(user_id="u1"):
    m = MagicMock()
    m.user_id = user_id
    m.total_games_started = 0
    m.total_games_completed = 0
    m.total_game_overs = 0
    m.total_attempts = 0
    m.total_correct = 0
    m.total_wrong = 0
    m.total_score_earned = 0
    m.highest_score = 0
    m.highest_stage = "Intern"
    m.accuracy_rate = 0.0
    m.favorite_language = None
    m.last_played_at = None
    return m


class MockSession:
    def __init__(self, existing_record=None):
        self.added = []
        self._existing = existing_record

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def flush(self):
        pass

    def query(self, model):
        return MockQuery(self._existing)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args):
        return self

    def first(self):
        return self._result


@pytest.fixture
def mock_model_cls():
    with patch("app.application.metrics_service.UserMetricsModel") as cls:
        cls.return_value = _make_metrics_model()
        yield cls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMetricsOnGameStarted:
    def test_new_user_creates_record(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        session = MockSession(existing_record=None)
        service = MetricsService(session_factory=lambda: session)
        service.on_game_started("u1", "Java")

        # A new model was created via the constructor
        mock_model_cls.assert_called_once_with(user_id="u1")

    def test_existing_user_increments(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.total_games_started = 3
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_game_started("u1", "Python")

        assert existing.total_games_started == 4
        assert existing.favorite_language == "Python"

    def test_sets_last_played_at(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_game_started("u1", "Java")

        assert existing.last_played_at is not None


class TestMetricsOnAnswerSubmitted:
    def test_correct_answer_updates_metrics(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.total_attempts = 2
        existing.total_correct = 1
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_answer_submitted("u1", is_correct=True, points=100)

        assert existing.total_attempts == 3
        assert existing.total_correct == 2
        assert existing.total_score_earned == 100

    def test_wrong_answer_increments_wrong(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_answer_submitted("u1", is_correct=False, points=0)

        assert existing.total_wrong == 1

    def test_accuracy_rate_calculated(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.total_attempts = 3
        existing.total_correct = 3
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_answer_submitted("u1", is_correct=True, points=50)
        # after: 4 attempts, 4 correct → 100%
        assert existing.accuracy_rate == 1.0

    def test_zero_attempts_accuracy_is_zero(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.total_attempts = 0
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        # After this call: 1 attempt, 0 correct
        service.on_answer_submitted("u1", is_correct=False, points=0)
        assert existing.accuracy_rate == 0.0


class TestMetricsOnGameOver:
    def test_increments_game_overs(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.total_game_overs = 2
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_game_over("u1")

        assert existing.total_game_overs == 3


class TestMetricsOnStagePromoted:
    def test_updates_highest_stage(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.highest_stage = "Intern"
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_stage_promoted("u1", "Junior", 500)

        assert existing.highest_stage == "Junior"

    def test_does_not_downgrade_stage(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.highest_stage = "Senior"
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_stage_promoted("u1", "Junior", 100)  # trying to go back

        assert existing.highest_stage == "Senior"

    def test_updates_highest_score(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.highest_score = 200
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_stage_promoted("u1", "Mid", 999)

        assert existing.highest_score == 999

    def test_distinguished_increments_completed(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.total_games_completed = 0
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        service.on_stage_promoted("u1", "Distinguished", 5000)

        assert existing.total_games_completed == 1


class TestGetMetrics:
    def test_returns_none_when_no_record(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        session = MockSession(existing_record=None)
        service = MetricsService(session_factory=lambda: session)
        result = service.get_metrics("u-not-found")
        assert result is None

    def test_returns_dict_when_found(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.last_played_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        existing.accuracy_rate = 0.75
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        result = service.get_metrics("u1")

        assert result is not None
        assert "total_games_started" in result
        assert "accuracy_rate" in result
        assert result["accuracy_rate"] == 75.0

    def test_last_played_at_none(self, mock_model_cls):
        from app.application.metrics_service import MetricsService

        existing = _make_metrics_model("u1")
        existing.last_played_at = None
        session = MockSession(existing_record=existing)
        service = MetricsService(session_factory=lambda: session)
        result = service.get_metrics("u1")

        assert result["last_played_at"] is None
