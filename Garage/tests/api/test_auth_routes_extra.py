"""Extension tests for auth_routes — covers edge cases missing from main test file."""
import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-123456")
os.environ.setdefault("ENV", "test")


def _make_auth_client(user_repo=None, events=None):
    """Build an isolated auth test client."""
    from app.api.routes.auth_routes import router, init_auth_routes
    from app.infrastructure.repositories.user_repository import UserRepository
    import tempfile

    if user_repo is None:
        tmpdir = tempfile.mkdtemp()
        user_repo = UserRepository(os.path.join(tmpdir, "users.json"))

    init_auth_routes(user_repo, event_service=events)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), user_repo


# ---------------------------------------------------------------------------
# Register edge cases
# ---------------------------------------------------------------------------

class TestRegisterEdgeCases:
    def _base_payload(self, suffix=""):
        return {
            "full_name": f"Test User{suffix}",
            "username": f"testuser{suffix}",
            "email": f"test{suffix}@test.com",
            "whatsapp": "11999999999",
            "profession": "estudante",
            "password": "StrongPass123!",
        }

    def test_duplicate_username_returns_409(self):
        client, _ = _make_auth_client()
        payload = self._base_payload()
        client.post("/api/auth/register", json=payload)
        # Second registration with same username
        resp = client.post("/api/auth/register", json={
            **payload,
            "email": "different@test.com",
        })
        assert resp.status_code == 409
        assert "usuario" in resp.json()["detail"].lower()

    def test_duplicate_email_returns_409(self):
        client, _ = _make_auth_client()
        payload = self._base_payload(suffix="dup")
        client.post("/api/auth/register", json=payload)
        # Second registration with same email
        resp = client.post("/api/auth/register", json={
            **payload,
            "username": "differentuser",
        })
        assert resp.status_code == 409
        assert "email" in resp.json()["detail"].lower() or "409" in str(resp.status_code)

    def test_register_with_events_fires_log(self):
        """Covers the `if _events:` branch in register."""
        mock_events = MagicMock()
        client, _ = _make_auth_client(events=mock_events)
        resp = client.post("/api/auth/register", json=self._base_payload(suffix="evts"))
        assert resp.status_code == 200
        mock_events.log.assert_called_once()
        assert "user_registered" in str(mock_events.log.call_args)

    def test_register_duplicate_fullname_with_method(self):
        """Covers line 79: duplicate full_name via exists_full_name."""
        mock_repo = MagicMock()
        mock_repo.exists_username.return_value = False
        mock_repo.exists_email.return_value = False
        mock_repo.exists_full_name.return_value = True  # trigger line 79
        client, _ = _make_auth_client(user_repo=mock_repo)
        resp = client.post("/api/auth/register", json=self._base_payload(suffix="fn"))
        assert resp.status_code == 409
        assert "nome" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Login edge cases
# ---------------------------------------------------------------------------

class TestLoginEdgeCases:
    def _register_and_login(self, client, suffix=""):
        """Helper: register then return the registered user data."""
        payload = {
            "full_name": f"Login User{suffix}",
            "username": f"loginuser{suffix}",
            "email": f"login{suffix}@test.com",
            "whatsapp": "11999999999",
            "profession": "estudante",
            "password": "LoginPass123!",
        }
        client.post("/api/auth/register", json=payload)
        return payload

    def test_login_with_events_fires_log(self):
        """Covers `if _events:` in login."""
        mock_events = MagicMock()
        client, _ = _make_auth_client(events=mock_events)
        payload = self._register_and_login(client, suffix="evts")
        resp = client.post("/api/auth/login", json={
            "username": payload["username"],
            "password": payload["password"],
        })
        assert resp.status_code == 200
        # Check that events.log was called with user_logged_in
        calls = [str(c) for c in mock_events.log.call_args_list]
        assert any("user_logged_in" in c for c in calls)

    def test_login_blocked_user_returns_429(self):
        """Covers `if is_blocked(req.username):` path in login."""
        from unittest.mock import patch as _patch
        client, _ = _make_auth_client()

        with _patch("app.api.routes.auth_routes.is_blocked", return_value=True):
            resp = client.post("/api/auth/login", json={
                "username": "anyblocked",
                "password": "pass",
            })
            assert resp.status_code == 429

    def test_login_wrong_password_returns_401(self):
        client, _ = _make_auth_client()
        payload = self._register_and_login(client, suffix="wrpw")
        resp = client.post("/api/auth/login", json={
            "username": payload["username"],
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user_returns_401(self):
        client, _ = _make_auth_client()
        resp = client.post("/api/auth/login", json={
            "username": "ghost_nonexistent",
            "password": "password123",
        })
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Refresh token edge cases
# ---------------------------------------------------------------------------

class TestRefreshTokenEdgeCases:
    def test_refresh_with_user_in_repo(self):
        """Covers lines 164-171: user found in repo during refresh."""
        client, _ = _make_auth_client()
        # Register and login to get refresh token
        reg_payload = {
            "full_name": "Refresh User",
            "username": "refreshuser",
            "email": "refresh@test.com",
            "whatsapp": "11999999999",
            "profession": "estudante",
            "password": "RefreshPass123!",
        }
        client.post("/api/auth/register", json=reg_payload)
        login_resp = client.post("/api/auth/login", json={
            "username": "refreshuser",
            "password": "RefreshPass123!",
        })
        refresh_token = login_resp.json()["refresh_token"]

        # Use refresh token to get new access token
        resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_refresh_invalid_token_returns_401(self):
        client, _ = _make_auth_client()
        resp = client.post("/api/auth/refresh", json={"refresh_token": "bad.token.here"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /me endpoint edge cases
# ---------------------------------------------------------------------------

class TestMeEndpointEdgeCases:
    def test_me_user_not_found_returns_404(self):
        """Covers line 210: user not found in /me endpoint."""
        from app.infrastructure.auth.jwt_handler import create_access_token

        # Mock user_repo to return None for find_by_id
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        client, _ = _make_auth_client(user_repo=mock_repo)

        # Create a valid token for a user that doesn't exist in repo
        token = create_access_token("ghost-uid", "ghost")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
