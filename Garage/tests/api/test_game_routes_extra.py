"""Extension tests for game_routes — covers metrics/events branches and edge cases."""
import os
import json
import tempfile
import shutil
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-123456")
os.environ.setdefault("ENV", "test")


def _make_full_app(with_metrics=True, with_events=True):
    """Build an isolated game routes test app with optional metrics/events."""
    from app.infrastructure.repositories.challenge_repository import ChallengeRepository
    from app.infrastructure.repositories.player_repository import PlayerRepository
    from app.infrastructure.repositories.leaderboard_repository import LeaderboardRepository
    from app.infrastructure.repositories.user_repository import UserRepository
    from app.api.routes.game_routes import router as game_router, init_routes
    from app.api.routes.auth_routes import router as auth_router, init_auth_routes

    tmpdir = tempfile.mkdtemp(prefix="garage_ext_test_")

    # Seed challenges
    challenges = [
        {
            "id": f"ext_intern_0{i+1}",
            "title": f"Ext Challenge {i+1}",
            "description": "What is correct?",
            "context_code": None,
            "category": "logic",
            "required_stage": "Intern",
            "region": "Xerox PARC",
            "mentor": "Tester",
            "points_on_correct": 100,
            "points_on_wrong": 0,
            "options": [
                {"text": "Correct", "is_correct": True, "explanation": "Yes!"},
                {"text": "Wrong", "is_correct": False, "explanation": "No"},
            ],
        }
        for i in range(3)
    ]
    with open(os.path.join(tmpdir, "challenges.json"), "w") as f:
        json.dump(challenges, f)
    for name in ("sessions.json", "users.json"):
        with open(os.path.join(tmpdir, name), "w") as f:
            json.dump({}, f)
    with open(os.path.join(tmpdir, "leaderboard.json"), "w") as f:
        json.dump([], f)

    challenge_repo = ChallengeRepository(os.path.join(tmpdir, "challenges.json"))
    player_repo = PlayerRepository(os.path.join(tmpdir, "sessions.json"))
    leaderboard_repo = LeaderboardRepository(os.path.join(tmpdir, "leaderboard.json"))
    user_repo = UserRepository(os.path.join(tmpdir, "users.json"))

    mock_metrics = MagicMock() if with_metrics else None
    mock_events = MagicMock() if with_events else None

    init_routes(player_repo, challenge_repo, leaderboard_repo, mock_metrics, mock_events)
    init_auth_routes(user_repo)

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(auth_router)
    app.include_router(game_router)

    client = TestClient(app)
    return client, mock_metrics, mock_events, tmpdir


def _register_and_get_headers(client):
    payload = {
        "full_name": "Ext Game Player",
        "username": "extgameplayer",
        "email": "extgame@test.com",
        "whatsapp": "11999999999",
        "profession": "estudante",
        "password": "ExtPass123!",
    }
    client.post("/api/auth/register", json=payload)
    login = client.post("/api/auth/login", json={
        "username": "extgameplayer",
        "password": "ExtPass123!",
    })
    if login.status_code != 200:
        # Already registered from previous test, try login directly
        login = client.post("/api/auth/login", json={
            "username": "extgameplayer",
            "password": "ExtPass123!",
        })
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


def _start_session(client, headers):
    resp = client.post("/api/start", json={
        "player_name": "ExtDev",
        "gender": "male",
        "ethnicity": "white",
        "avatar_index": 0,
        "language": "Java",
    }, headers=headers)
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestStartGameWithMetricsEvents:
    """Covers lines 97, 99 — metrics and events fired on start."""

    def test_metrics_on_game_started_called(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app()
        try:
            headers, _ = _register_and_get_headers(client)
            resp = client.post("/api/start", json={
                "player_name": "MetricsDev",
                "gender": "male",
                "ethnicity": "white",
                "avatar_index": 0,
                "language": "Java",
            }, headers=headers)
            assert resp.status_code == 200
            mock_metrics.on_game_started.assert_called_once()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_events_on_game_started_called(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app()
        try:
            headers, _ = _register_and_get_headers(client)
            client.post("/api/start", json={
                "player_name": "EventsDev",
                "gender": "male",
                "ethnicity": "white",
                "avatar_index": 0,
                "language": "Java",
            }, headers=headers)
            calls = [str(c) for c in mock_events.log.call_args_list]
            assert any("game_started" in c for c in calls)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSubmitAnswerWithMetricsEvents:
    """Covers lines 156-159 — metrics/events in submit answer."""

    def test_metrics_on_answer_correct_called(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app()
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)

            # Get a challenge id
            from app.infrastructure.repositories.challenge_repository import ChallengeRepository
            # The challenge id is ext_intern_01
            resp = client.post("/api/submit", json={
                "session_id": sid,
                "challenge_id": "ext_intern_01",
                "selected_index": 0,  # correct
            }, headers=headers)
            assert resp.status_code == 200
            mock_metrics.on_answer_submitted.assert_called()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_events_on_answer_submitted_called(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app()
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            client.post("/api/submit", json={
                "session_id": sid,
                "challenge_id": "ext_intern_01",
                "selected_index": 0,
            }, headers=headers)
            calls = [str(c) for c in mock_events.log.call_args_list]
            assert any("answer_submitted" in c for c in calls)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_metrics_on_game_over_called(self):
        """Covers metrics.on_game_over when result is game_over."""
        client, mock_metrics, mock_events, tmpdir = _make_full_app()
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            # Submit 3 wrong answers to trigger game over
            for _ in range(3):
                client.post("/api/submit", json={
                    "session_id": sid,
                    "challenge_id": "ext_intern_01",
                    "selected_index": 1,  # wrong
                }, headers=headers)
            mock_metrics.on_game_over.assert_called()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestRecoverWithEvents:
    """Covers lines 167, 172 — events in recover."""

    def test_recover_fires_event(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app()
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            # Force game over by submitting 3 wrong answers
            for _ in range(3):
                client.post("/api/submit", json={
                    "session_id": sid,
                    "challenge_id": "ext_intern_01",
                    "selected_index": 1,
                }, headers=headers)
            # Recover
            resp = client.post("/api/recover", json={"session_id": sid}, headers=headers)
            assert resp.status_code == 200
            calls = [str(c) for c in mock_events.log.call_args_list]
            assert any("game_recovered" in c for c in calls)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSaveWorldStateWithEvents:
    """Covers lines 187-191 — events in save_world_state."""

    def test_save_world_state_fires_event(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app()
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            resp = client.post("/api/save-world-state", json={
                "session_id": sid,
                "collected_books": ["book-1"],
                "completed_regions": ["Garage"],
                "current_region": "Xerox PARC",
                "player_world_x": 200,
            }, headers=headers)
            assert resp.status_code == 200
            calls = [str(c) for c in mock_events.log.call_args_list]
            assert any("world_state_saved" in c for c in calls)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestBeaconEndpoint:
    """Covers lines 196-255 — beacon endpoint auth and flow."""

    def test_beacon_no_session_id_returns_400(self):
        client, _, _, tmpdir = _make_full_app()
        try:
            resp = client.post("/api/save-world-state-beacon", json={
                "session_id": "",
                "access_token": "anytoken",
            })
            assert resp.status_code == 400
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_beacon_no_access_token_returns_401(self):
        client, _, _, tmpdir = _make_full_app()
        try:
            resp = client.post("/api/save-world-state-beacon", json={
                "session_id": "some-session-id",
            })
            assert resp.status_code == 401
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_beacon_invalid_token_returns_401(self):
        client, _, _, tmpdir = _make_full_app()
        try:
            resp = client.post("/api/save-world-state-beacon", json={
                "session_id": "some-session",
                "access_token": "not.a.valid.token",
            })
            assert resp.status_code == 401
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_beacon_session_not_found_returns_404(self):
        client, _, _, tmpdir = _make_full_app()
        try:
            from app.infrastructure.auth.jwt_handler import create_access_token
            token = create_access_token("uid-test", "beaconuser")
            resp = client.post("/api/save-world-state-beacon", json={
                "session_id": "nonexistent-beacon-session",
                "access_token": token,
            })
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_beacon_success_updates_state(self):
        client, _, _, tmpdir = _make_full_app()
        try:
            headers, token = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            resp = client.post("/api/save-world-state-beacon", json={
                "session_id": sid,
                "access_token": token,
                "collected_books": ["book-1"],
                "completed_regions": [],
                "current_region": "Garage",
                "player_world_x": 100,
            })
            assert resp.status_code == 200
            assert resp.json()["saved"] is True
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestAssertOwnerRaise:
    """Covers line 74 — _assert_owner raises 403 for wrong user."""

    def test_submit_from_different_user_returns_403(self):
        """A player can't submit on another player's session."""
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            # User 1 creates a session
            from app.infrastructure.repositories.user_repository import UserRepository
            from app.api.routes.auth_routes import init_auth_routes
            headers1, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers1)

            # Register user 2
            from app.infrastructure.auth.jwt_handler import create_access_token
            # Manually mint a token for a different sub
            other_token = create_access_token("completely-different-uid", "user2")
            headers2 = {"Authorization": f"Bearer {other_token}"}

            resp = client.post("/api/submit", json={
                "session_id": sid,
                "challenge_id": "ext_intern_01",
                "selected_index": 0,
            }, headers=headers2)
            assert resp.status_code == 403
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestProgressEndpoint:
    """Covers /progress/{session_id} endpoint."""

    def test_progress_returns_200_for_owner(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            resp = client.get(f"/api/progress/{sid}", headers=headers)
            assert resp.status_code == 200
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_progress_not_found_returns_404(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            resp = client.get("/api/progress/nonexistent-session-id", headers=headers)
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestMeMetricsAndSessions:
    """Covers /me/metrics and /me/sessions endpoints."""

    def test_me_metrics_no_metrics_service_returns_empty(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            resp = client.get("/api/me/metrics", headers=headers)
            assert resp.status_code == 200
            assert resp.json() == {}
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_me_metrics_with_metrics_service(self):
        client, mock_metrics, _, tmpdir = _make_full_app(with_metrics=True, with_events=False)
        try:
            mock_metrics.get_metrics.return_value = {"total_games_started": 1}
            headers, _ = _register_and_get_headers(client)
            resp = client.get("/api/me/metrics", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("total_games_started") == 1
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_me_sessions_returns_list(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            _start_session(client, headers)
            resp = client.get("/api/me/sessions", headers=headers)
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestResetEndpoint:
    """Covers /reset endpoint — lines 339-373."""

    def test_reset_not_found_returns_404(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            resp = client.post("/api/reset", json={"session_id": "no-such-session"}, headers=headers)
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_reset_creates_new_session(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app(with_metrics=True, with_events=True)
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            resp = client.post("/api/reset", json={"session_id": sid}, headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "session_id" in data
            assert data["session_id"] != sid  # new session
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_reset_fires_event(self):
        client, mock_metrics, mock_events, tmpdir = _make_full_app(with_metrics=True, with_events=True)
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            client.post("/api/reset", json={"session_id": sid}, headers=headers)
            calls = [str(c) for c in mock_events.log.call_args_list]
            assert any("game_reset" in c for c in calls)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestHeartbeatEndpoint:
    """Covers /heartbeat endpoint."""

    def test_heartbeat_success(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            resp = client.post("/api/heartbeat", json={"session_id": sid}, headers=headers)
            assert resp.status_code == 200
            assert resp.json()["heartbeat"] is True
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_heartbeat_not_found_returns_404(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            resp = client.post("/api/heartbeat", json={"session_id": "no-session"}, headers=headers)
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestMapEndpoint:
    """Covers /map endpoint."""

    def test_map_returns_regions_and_bosses(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            resp = client.get("/api/map")
            assert resp.status_code == 200
            data = resp.json()
            assert "regions" in data
            assert "bosses" in data
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestChallengeNotFoundInSubmit:
    """Covers lines 143-147 — challenge not found raises 404."""

    def test_submit_nonexistent_challenge_returns_404(self):
        client, _, _, tmpdir = _make_full_app(with_metrics=False, with_events=False)
        try:
            headers, _ = _register_and_get_headers(client)
            sid = _start_session(client, headers)
            resp = client.post("/api/submit", json={
                "session_id": sid,
                "challenge_id": "totally-nonexistent-challenge",
                "selected_index": 0,
            }, headers=headers)
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
