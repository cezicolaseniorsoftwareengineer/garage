"""Tests for FastAPI auth dependencies — get_current_user, get_optional_user."""
import os
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-dependencies")

from app.infrastructure.auth.dependencies import get_current_user, get_optional_user
from app.infrastructure.auth.jwt_handler import create_access_token, create_refresh_token


def _make_app(dependency):
    app = FastAPI()

    @app.get("/test-dep")
    def endpoint(user=Depends(dependency)):
        return {"user": user}

    return TestClient(app)


def _make_access_token(uid="dep-user", username="depuser"):
    return create_access_token(uid, username)


def _make_refresh_token(uid="dep-user"):
    return create_refresh_token(uid)


class TestGetCurrentUser:
    def test_missing_auth_returns_401(self):
        client = _make_app(get_current_user)
        resp = client.get("/test-dep")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        client = _make_app(get_current_user)
        resp = client.get("/test-dep", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_refresh_token_rejected_as_access(self):
        client = _make_app(get_current_user)
        refresh = _make_refresh_token()
        resp = client.get("/test-dep", headers={"Authorization": f"Bearer {refresh}"})
        assert resp.status_code == 401

    def test_valid_access_token_returns_payload(self):
        client = _make_app(get_current_user)
        token = _make_access_token()
        resp = client.get("/test-dep", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["sub"] == "dep-user"


class TestGetOptionalUser:
    def test_missing_auth_returns_none(self):
        client = _make_app(get_optional_user)
        resp = client.get("/test-dep")
        assert resp.status_code == 200
        assert resp.json()["user"] is None

    def test_invalid_token_returns_none(self):
        client = _make_app(get_optional_user)
        resp = client.get("/test-dep", headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 200
        assert resp.json()["user"] is None

    def test_valid_access_token_returns_payload(self):
        client = _make_app(get_optional_user)
        token = _make_access_token(uid="opt-user", username="optuser")
        resp = client.get("/test-dep", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["user"]["sub"] == "opt-user"

    def test_refresh_token_returns_none(self):
        """Refresh tokens should not be accepted as optional access tokens."""
        client = _make_app(get_optional_user)
        refresh = _make_refresh_token()
        resp = client.get("/test-dep", headers={"Authorization": f"Bearer {refresh}"})
        assert resp.status_code == 200
        assert resp.json()["user"] is None
