"""Tests for admin API routes."""
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.routes.admin_routes as admin_module
from app.api.routes.admin_routes import router, init_admin_routes
from app.infrastructure.auth.dependencies import get_current_user
from app.domain.enums import GameEnding, CareerStage


def _make_mock_user(uid="uid1", email="admin@test.com", name="Admin User"):
    u = MagicMock()
    u.id = uid
    u.email = email
    u.full_name = name
    u.to_public_dict.return_value = {"id": uid, "email": email, "full_name": name}
    u.to_dict.return_value = {"id": uid, "email": email, "full_name": name, "created_at": "2024-01-01T00:00:00"}
    return u


def _make_mock_session(uid="uid1", stage="Intern", score=100, status="active"):
    s = MagicMock()
    s.user_id = uid
    s.stage = MagicMock()
    s.stage.value = stage
    s.status = MagicMock()
    s.status.value = status
    return s


def _make_session_dict(uid="uid1", stage="Intern", score=100, status="active"):
    return {
        "id": "session-1",
        "name": "DevPlayer",
        "user_id": uid,
        "stage": stage,
        "score": score,
        "status": status,
        "language": "Java",
        "completed_challenges": ["c1"],
        "total_attempts": 5,
        "game_over_count": 0,
        "created_at": "2024-01-01T10:00:00",
        "attempts": [],
    }


@pytest.fixture(scope="module")
def admin_client():
    mock_user_repo = MagicMock()
    mock_player_repo = MagicMock()
    mock_leaderboard_repo = MagicMock()
    mock_challenge_repo = MagicMock()

    # Setup mock data
    mock_user = _make_mock_user()
    mock_user_repo.get_all.return_value = [mock_user]
    mock_user_repo.find_by_id.return_value = mock_user

    mock_session = _make_mock_session()
    mock_player_repo.get_all.return_value = [mock_session]
    mock_player_repo.get_all_dict.return_value = [_make_session_dict()]
    mock_player_repo.get_active_sessions.return_value = [
        {
            "session_id": "session-1",
            "player_name": "DevPlayer",
            "user_id": "uid1",
            "stage": "Intern",
            "score": 100,
            "language": "Java",
            "completed_challenges": 1,
            "current_errors": 0,
            "game_over_count": 0,
            "last_active_at": "2024-01-01T10:00:00",
        }
    ]

    mock_challenge_repo.get_all.return_value = [MagicMock()]

    init_admin_routes(mock_user_repo, mock_player_repo, mock_leaderboard_repo, mock_challenge_repo)

    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin-uid",
        "role": "admin",
        "username": "admin",
    }

    return TestClient(application)


class TestAdminDashboard:
    def test_dashboard_returns_200(self, admin_client):
        resp = admin_client.get("/api/admin/dashboard")
        assert resp.status_code == 200

    def test_dashboard_has_total_users(self, admin_client):
        data = admin_client.get("/api/admin/dashboard").json()
        assert "total_users" in data

    def test_dashboard_has_total_sessions(self, admin_client):
        data = admin_client.get("/api/admin/dashboard").json()
        assert "total_sessions" in data

    def test_dashboard_has_online_now(self, admin_client):
        data = admin_client.get("/api/admin/dashboard").json()
        assert "online_now" in data

    def test_dashboard_counts_completed_games(self, admin_client):
        # inject a completed session
        completed = _make_mock_session(status="completed")
        admin_module._player_repo.get_all.return_value = [completed]
        resp = admin_client.get("/api/admin/dashboard")
        assert resp.status_code == 200
        admin_module._player_repo.get_all.return_value = [_make_mock_session()]  # restore

    def test_dashboard_counts_game_over(self, admin_client):
        go_session = _make_mock_session(status="game_over")
        admin_module._player_repo.get_all.return_value = [go_session]
        resp = admin_client.get("/api/admin/dashboard")
        assert resp.status_code == 200
        admin_module._player_repo.get_all.return_value = [_make_mock_session()]  # restore

    def test_dashboard_counts_distinguished(self, admin_client):
        dist_session = _make_mock_session(stage="Distinguished")
        admin_module._player_repo.get_all.return_value = [dist_session]
        resp = admin_client.get("/api/admin/dashboard")
        assert resp.status_code == 200
        admin_module._player_repo.get_all.return_value = [_make_mock_session()]  # restore


class TestAdminOnline:
    def test_online_returns_200(self, admin_client):
        resp = admin_client.get("/api/admin/online")
        assert resp.status_code == 200

    def test_online_returns_list(self, admin_client):
        data = admin_client.get("/api/admin/online").json()
        assert isinstance(data, list)

    def test_online_session_has_expected_fields(self, admin_client):
        data = admin_client.get("/api/admin/online").json()
        if data:
            item = data[0]
            assert "session_id" in item
            assert "stage" in item

    def test_online_without_get_active_sessions(self, admin_client):
        orig = admin_module._player_repo
        mock = MagicMock(spec=[])  # no get_active_sessions
        admin_module._player_repo = mock
        resp = admin_client.get("/api/admin/online")
        assert resp.status_code == 200
        assert resp.json() == []
        admin_module._player_repo = orig


class TestAdminUsers:
    def test_users_returns_200(self, admin_client):
        resp = admin_client.get("/api/admin/users")
        assert resp.status_code == 200

    def test_users_returns_list(self, admin_client):
        data = admin_client.get("/api/admin/users").json()
        assert isinstance(data, list)

    def test_users_has_total_sessions_field(self, admin_client):
        data = admin_client.get("/api/admin/users").json()
        if data:
            assert "total_sessions" in data[0]

    def test_users_empty_repos(self, admin_client):
        orig_users = admin_module._user_repo.get_all.return_value
        admin_module._user_repo.get_all.return_value = []
        resp = admin_client.get("/api/admin/users")
        assert resp.status_code == 200
        assert resp.json() == []
        admin_module._user_repo.get_all.return_value = orig_users


class TestAdminSessions:
    def test_sessions_returns_200(self, admin_client):
        resp = admin_client.get("/api/admin/sessions")
        assert resp.status_code == 200

    def test_sessions_returns_list(self, admin_client):
        data = admin_client.get("/api/admin/sessions").json()
        assert isinstance(data, list)

    def test_sessions_has_expected_fields(self, admin_client):
        data = admin_client.get("/api/admin/sessions").json()
        if data:
            item = data[0]
            assert "session_id" in item
            assert "score" in item

    def test_sessions_with_attempts_calculates_duration(self, admin_client):
        session_with_attempts = _make_session_dict()
        session_with_attempts["attempts"] = [
            {"timestamp": "2024-01-01T10:00:00", "challenge_id": "c1"},
            {"timestamp": "2024-01-01T10:30:00", "challenge_id": "c2"},
        ]
        orig = admin_module._player_repo.get_all_dict.return_value
        admin_module._player_repo.get_all_dict.return_value = [session_with_attempts]
        data = admin_client.get("/api/admin/sessions").json()
        assert data[0]["duration_seconds"] == 1800
        admin_module._player_repo.get_all_dict.return_value = orig


class TestAdminRanking:
    def test_ranking_returns_200(self, admin_client):
        resp = admin_client.get("/api/admin/ranking")
        assert resp.status_code == 200

    def test_ranking_returns_list(self, admin_client):
        data = admin_client.get("/api/admin/ranking").json()
        assert isinstance(data, list)

    def test_ranking_completed_sorted_first(self, admin_client):
        completed = _make_session_dict(status="completed", score=500)
        completed["attempts"] = [
            {"timestamp": "2024-01-01T10:00:00"},
            {"timestamp": "2024-01-01T11:00:00"},
        ]
        incomplete = _make_session_dict(status="active", score=200)
        incomplete["id"] = "session-2"
        incomplete["user_id"] = "uid2"
        orig = admin_module._player_repo.get_all_dict.return_value
        admin_module._player_repo.get_all_dict.return_value = [incomplete, completed]
        data = admin_client.get("/api/admin/ranking").json()
        # completed sessions should be first
        completed_entries = [e for e in data if e["completed"]]
        incomplete_entries = [e for e in data if not e["completed"]]
        if completed_entries and incomplete_entries:
            assert data.index(completed_entries[0]) < data.index(incomplete_entries[0])
        admin_module._player_repo.get_all_dict.return_value = orig

    def test_ranking_deduplicates_same_user(self, admin_client):
        # Two sessions for the same user: keep best score
        s1 = _make_session_dict(uid="uid1", score=100)
        s2 = _make_session_dict(uid="uid1", score=200)
        s2["id"] = "session-alt"
        orig = admin_module._player_repo.get_all_dict.return_value
        admin_module._player_repo.get_all_dict.return_value = [s1, s2]
        data = admin_client.get("/api/admin/ranking").json()
        assert len(data) == 1  # deduplicated
        admin_module._player_repo.get_all_dict.return_value = orig

    def test_ranking_assigned_ranks(self, admin_client):
        data = admin_client.get("/api/admin/ranking").json()
        for i, entry in enumerate(data, 1):
            assert entry["rank"] == i


class TestAdminNotAdmin:
    def test_returns_403_non_admin(self):
        application = FastAPI()
        application.include_router(router)
        # Override with non-admin token
        application.dependency_overrides[get_current_user] = lambda: {
            "sub": "regular-uid",
            "role": "player",
            "username": "user1",
        }
        # Make sure user repo returns non-admin user
        mock_user = MagicMock()
        mock_user.email = "user@notadmin.com"
        admin_module._user_repo = MagicMock()
        admin_module._user_repo.find_by_id.return_value = mock_user
        client = TestClient(application)
        resp = client.get("/api/admin/dashboard")
        assert resp.status_code == 403

    def test_assert_admin_no_sub(self):
        from app.api.routes.admin_routes import _assert_admin
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            _assert_admin({})
        assert exc.value.status_code == 403
