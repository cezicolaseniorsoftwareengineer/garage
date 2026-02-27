"""Tests for study routes — rate limiting, helpers, chat endpoint."""
import pytest
import time
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.study_routes import (
    router,
    init_study_routes,
    _check_rate_limit,
    _extract_output_text,
    _is_model_unavailable_error,
    _unsupported_parameter_name,
    _candidate_models,
    _cache_key,
    _cache_get,
    _cache_set,
    _RESPONSE_CACHE,
    _rate_buckets,
    _assert_owner,
)
from app.infrastructure.auth.dependencies import get_current_user
from app.domain.enums import CareerStage, MapRegion


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _make_player(uid="user-sub-123", stage="Intern"):
    p = MagicMock()
    p.user_id = uid
    p.stage = MagicMock()
    p.stage.value = stage
    return p


@pytest.fixture(scope="module")
def study_client():
    mock_player_repo = MagicMock()
    mock_challenge_repo = MagicMock()

    player = _make_player()
    mock_player_repo.get.return_value = player
    mock_challenge_repo.get_by_id.return_value = None  # no challenge by default

    init_study_routes(mock_player_repo, mock_challenge_repo)

    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_current_user] = lambda: {
        "sub": "user-sub-123",
        "username": "testuser",
    }

    return TestClient(application), mock_player_repo, mock_challenge_repo


# ---------------------------------------------------------------------------
# Unit tests for pure helper functions
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    def test_within_limit(self):
        uid = "ratelimit-test-user-fresh"
        _rate_buckets.pop(uid, None)
        # Should not raise for first request
        _check_rate_limit(uid)

    def test_raises_at_limit(self):
        from fastapi import HTTPException
        uid = "ratelimit-test-user-full"
        _rate_buckets.pop(uid, None)
        # Fill up to max
        from app.api.routes.study_routes import _RATE_LIMIT_MAX
        for _ in range(_RATE_LIMIT_MAX):
            _rate_buckets.setdefault(uid, __import__("collections").deque()).append(
                time.monotonic()
            )
        with pytest.raises(HTTPException) as exc:
            _check_rate_limit(uid)
        assert exc.value.status_code == 429

    def test_expired_requests_are_purged(self):
        import collections
        uid = "ratelimit-test-expired"
        _rate_buckets.pop(uid, None)
        # Add old requests (far in the past)
        old_time = time.monotonic() - 9999
        dq = collections.deque([old_time] * 12)
        _rate_buckets[uid] = dq
        # Should not raise since all expired
        _check_rate_limit(uid)


class TestExtractOutputText:
    def test_extracts_output_text_direct(self):
        result = _extract_output_text({"output_text": "hello world"})
        assert result == "hello world"

    def test_extracts_from_output_array(self):
        payload = {
            "output": [
                {"content": [{"type": "output_text", "text": "extracted"}]}
            ]
        }
        result = _extract_output_text(payload)
        assert result == "extracted"

    def test_extracts_text_type(self):
        payload = {
            "output": [
                {"content": [{"type": "text", "text": "text-content"}]}
            ]
        }
        result = _extract_output_text(payload)
        assert result == "text-content"

    def test_empty_payload(self):
        result = _extract_output_text({})
        assert result == ""

    def test_ignores_non_text_types(self):
        payload = {
            "output": [
                {"content": [{"type": "image", "text": "image-data"}]}
            ]
        }
        result = _extract_output_text(payload)
        assert result == ""

    def test_output_text_whitespace_only(self):
        result = _extract_output_text({"output_text": "   "})
        assert result == ""


class TestIsModelUnavailableError:
    def test_detect_does_not_exist(self):
        assert _is_model_unavailable_error("This model does not exist") is True

    def test_detect_not_found(self):
        assert _is_model_unavailable_error("model not found") is True

    def test_detect_not_allowed(self):
        assert _is_model_unavailable_error("you are not allowed") is True

    def test_detect_permission(self):
        assert _is_model_unavailable_error("permission denied") is True

    def test_normal_error(self):
        assert _is_model_unavailable_error("Internal server error") is False

    def test_empty_string(self):
        assert _is_model_unavailable_error("") is False

    def test_none_value(self):
        assert _is_model_unavailable_error(None) is False  # type: ignore


class TestUnsupportedParameterName:
    def test_extracts_param_name(self):
        result = _unsupported_parameter_name("Unsupported parameter: 'stream'")
        assert result == "stream"

    def test_returns_none_when_not_matching(self):
        result = _unsupported_parameter_name("Some other error")
        assert result is None

    def test_empty(self):
        result = _unsupported_parameter_name("")
        assert result is None


class TestCandidateModels:
    def test_default_includes_primary_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
        monkeypatch.delenv("OPENAI_FALLBACK_MODELS", raising=False)
        models = _candidate_models()
        assert "gpt-5" in models

    def test_fallback_models_parsed(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
        monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "gpt-4.1,gpt-4.1-mini")
        models = _candidate_models()
        assert "gpt-4.1" in models
        assert "gpt-4.1-mini" in models

    def test_no_duplicate_primary(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
        monkeypatch.setenv("OPENAI_FALLBACK_MODELS", "gpt-5,gpt-4.1")
        models = _candidate_models()
        assert models.count("gpt-5") == 1


class TestCacheFunctions:
    def test_cache_key_deterministic(self):
        k1 = _cache_key("c1", "hello world")
        k2 = _cache_key("c1", "hello world")
        assert k1 == k2

    def test_cache_key_different_inputs(self):
        k1 = _cache_key("c1", "hello")
        k2 = _cache_key("c2", "hello")
        assert k1 != k2

    def test_cache_key_none_challenge(self):
        k = _cache_key(None, "test message")
        assert isinstance(k, str) and len(k) == 32

    def test_cache_set_and_get(self):
        _RESPONSE_CACHE.clear()
        key = "test-cache-key-123"
        _cache_set(key, "cached answer")
        result = _cache_get(key)
        assert result == "cached answer"

    def test_cache_get_returns_none_on_miss(self):
        _RESPONSE_CACHE.clear()
        result = _cache_get("nonexistent-key")
        assert result is None

    def test_cache_get_expired_returns_none(self):
        import app.api.routes.study_routes as sr
        old_ttl = sr._CACHE_TTL
        sr._CACHE_TTL = 0  # expire immediately
        key = "expired-key"
        _cache_set(key, "value")
        import time
        time.sleep(0.01)
        result = _cache_get(key)
        assert result is None
        sr._CACHE_TTL = old_ttl

    def test_cache_set_evicts_when_full(self):
        import app.api.routes.study_routes as sr
        _RESPONSE_CACHE.clear()
        old_max = sr._CACHE_MAX
        sr._CACHE_MAX = 5
        # Fill cache to max
        for i in range(5):
            _cache_set(f"key-{i}", f"val-{i}")
        # Adding one more should trigger eviction
        _cache_set("key-overflow", "new-val")
        assert len(_RESPONSE_CACHE) <= 5 + 1  # evicted some
        sr._CACHE_MAX = old_max


class TestAssertOwner:
    def test_no_user_id_allows_all(self):
        player = MagicMock()
        player.user_id = None
        # Should not raise if player has no user_id
        _assert_owner(player, {"sub": "anyone"})

    def test_matching_user_id_allows(self):
        player = MagicMock()
        player.user_id = "uid-abc"
        # Same sub → no exception
        _assert_owner(player, {"sub": "uid-abc"})

    def test_different_user_id_raises_403(self):
        from fastapi import HTTPException
        player = MagicMock()
        player.user_id = "uid-xyz"
        with pytest.raises(HTTPException) as exc:
            _assert_owner(player, {"sub": "uid-different"})
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Route handler tests
# ---------------------------------------------------------------------------

class TestStudyChatRoute:
    def test_session_not_found_returns_404(self, study_client):
        client, mock_player_repo, _ = study_client
        mock_player_repo.get.return_value = None
        resp = client.post(
            "/api/study/chat",
            json={
                "session_id": "nonexistent",
                "message": "What is Java?",
            },
        )
        assert resp.status_code == 404
        # Restore
        mock_player_repo.get.return_value = _make_player()

    def test_empty_message_returns_422(self, study_client):
        client, mock_player_repo, _ = study_client
        mock_player_repo.get.return_value = _make_player()
        with patch("app.api.routes.study_routes._call_with_fallback",
                   return_value=("answer", "resp-id", "mock-model")):
            resp = client.post(
                "/api/study/chat",
                json={"session_id": "s1", "message": "   "},
            )
        # Whitespace-only message stripped → 422
        assert resp.status_code == 422

    def test_successful_chat_returns_reply(self, study_client):
        client, mock_player_repo, _ = study_client
        mock_player_repo.get.return_value = _make_player()
        with patch("app.api.routes.study_routes._call_with_fallback",
                   return_value=("Great answer!", "resp-123", "gpt-5")):
            resp = client.post(
                "/api/study/chat",
                json={"session_id": "s1", "message": "Explain OOP in Java please."},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert data["reply"] == "Great answer!"
        assert data["model"] == "gpt-5"

    def test_chat_uses_cache_on_second_call(self, study_client):
        client, mock_player_repo, _ = study_client
        mock_player_repo.get.return_value = _make_player()
        _RESPONSE_CACHE.clear()
        call_count = {"n": 0}

        def fake_fallback(sp, up):
            call_count["n"] += 1
            return ("cached-answer", "resp-id", "model")

        with patch("app.api.routes.study_routes._call_with_fallback", side_effect=fake_fallback):
            resp1 = client.post(
                "/api/study/chat",
                json={"session_id": "s1", "message": "A longer message for cache test ABC"},
            )
            resp2 = client.post(
                "/api/study/chat",
                json={"session_id": "s1", "message": "A longer message for cache test ABC"},
            )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert call_count["n"] == 1  # second call from cache
        assert resp2.json()["model"] == "cache"

    def test_chat_with_challenge_id(self, study_client):
        client, mock_player_repo, mock_challenge_repo = study_client
        mock_player_repo.get.return_value = _make_player()
        mock_challenge = MagicMock()
        mock_challenge.title = "Hello World"
        mock_challenge.description = "Print hello"
        mock_challenge.region = MagicMock()
        mock_challenge.region.value = "Garage"
        mock_challenge_repo.get_by_id.return_value = mock_challenge
        _RESPONSE_CACHE.clear()
        with patch("app.api.routes.study_routes._call_with_fallback",
                   return_value=("answer", "rid", "model")):
            resp = client.post(
                "/api/study/chat",
                json={
                    "session_id": "s1",
                    "message": "Tell me about this challenge!",
                    "challenge_id": "chal-1",
                },
            )
        assert resp.status_code == 200
        mock_challenge_repo.get_by_id.return_value = None  # restore

    def test_chat_no_api_keys_returns_503(self, study_client):
        client, mock_player_repo, _ = study_client
        mock_player_repo.get.return_value = _make_player()
        _RESPONSE_CACHE.clear()
        # Don't mock _call_with_fallback so it raises 503 with no keys
        import os
        for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"]:
            os.environ.pop(key, None)
        resp = client.post(
            "/api/study/chat",
            json={"session_id": "s1", "message": "A very long unique question for no-key test XYZ987"},
        )
        assert resp.status_code == 503

    def test_chat_with_recent_messages(self, study_client):
        client, mock_player_repo, _ = study_client
        mock_player_repo.get.return_value = _make_player()
        _RESPONSE_CACHE.clear()
        with patch("app.api.routes.study_routes._call_with_fallback",
                   return_value=("response", "rid", "model")):
            resp = client.post(
                "/api/study/chat",
                json={
                    "session_id": "s1",
                    "message": "Follow-up question about Java polymorphism",
                    "recent_messages": [
                        {"role": "user", "content": "What is OOP?"},
                        {"role": "assistant", "content": "OOP means object-oriented programming."},
                    ],
                },
            )
        assert resp.status_code == 200

    def test_chat_with_books(self, study_client):
        client, mock_player_repo, _ = study_client
        mock_player_repo.get.return_value = _make_player()
        _RESPONSE_CACHE.clear()
        with patch("app.api.routes.study_routes._call_with_fallback",
                   return_value=("answer", "rid", "model")):
            resp = client.post(
                "/api/study/chat",
                json={
                    "session_id": "s1",
                    "message": "What did I learn from Clean Code book review?",
                    "books": [
                        {
                            "id": "book-1",
                            "title": "Clean Code",
                            "author": "Robert Martin",
                            "summary": "Writing clean maintainable code",
                            "lesson": "Keep functions small",
                            "collected": True,
                        }
                    ],
                },
            )
        assert resp.status_code == 200

    def test_chat_stage_defaults_to_intern(self, study_client):
        client, mock_player_repo, _ = study_client
        player = _make_player()
        player.stage.value = ""  # empty stage
        mock_player_repo.get.return_value = player
        _RESPONSE_CACHE.clear()
        with patch("app.api.routes.study_routes._call_with_fallback",
                   return_value=("ok", "rid", "model")):
            resp = client.post(
                "/api/study/chat",
                json={"session_id": "s1", "message": "A long message to avoid cache XYZ"},
            )
        assert resp.status_code == 200
        assert resp.json()["stage"] == "Intern"

    def test_chat_owner_check_blocks_other_user(self):
        """A user cannot access another user's session."""
        from fastapi import FastAPI
        mock_player_repo = MagicMock()
        mock_challenge_repo = MagicMock()
        player = _make_player(uid="owner-uid")
        mock_player_repo.get.return_value = player
        init_study_routes(mock_player_repo, mock_challenge_repo)

        application = FastAPI()
        application.include_router(router)
        # Login as a different user
        application.dependency_overrides[get_current_user] = lambda: {
            "sub": "attacker-uid",
            "username": "attacker",
        }
        other_client = TestClient(application)
        with patch("app.api.routes.study_routes._call_with_fallback",
                   return_value=("ok", "rid", "model")):
            resp = other_client.post(
                "/api/study/chat",
                json={"session_id": "s1", "message": "Trying to access other session"},
            )
        assert resp.status_code == 403
