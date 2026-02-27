"""Unit tests for JWT handler."""
import os
import pytest
from app.infrastructure.auth import jwt_handler


class TestCreateAccessToken:
    def test_returns_string(self):
        token = jwt_handler.create_access_token("uid1", "alice")
        assert isinstance(token, str)

    def test_verify_returns_payload(self):
        token = jwt_handler.create_access_token("uid1", "alice", role="player")
        payload = jwt_handler.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "uid1"
        assert payload["username"] == "alice"
        assert payload["role"] == "player"

    def test_type_is_access(self):
        token = jwt_handler.create_access_token("uid1", "alice")
        payload = jwt_handler.verify_token(token)
        assert payload["type"] == "access"

    def test_invalid_token_returns_none(self):
        assert jwt_handler.verify_token("not.a.jwt") is None

    def test_empty_token_returns_none(self):
        assert jwt_handler.verify_token("") is None


class TestCreateRefreshToken:
    def test_returns_string(self):
        token = jwt_handler.create_refresh_token("uid1")
        assert isinstance(token, str)

    def test_type_is_refresh(self):
        token = jwt_handler.create_refresh_token("uid1")
        payload = jwt_handler.verify_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_sub_is_user_id(self):
        token = jwt_handler.create_refresh_token("uid-abc")
        payload = jwt_handler.verify_token(token)
        assert payload["sub"] == "uid-abc"


class TestTokenRevocation:
    def test_revoked_refresh_token_rejected(self):
        token = jwt_handler.create_refresh_token("uid1")
        assert jwt_handler.verify_token(token) is not None  # valid before revoke
        jwt_handler.revoke_refresh_token(token)
        assert jwt_handler.verify_token(token) is None

    def test_is_refresh_revoked_true_after_revoke(self):
        token = jwt_handler.create_refresh_token("uid2")
        jwt_handler.revoke_refresh_token(token)
        assert jwt_handler.is_refresh_revoked(token) is True

    def test_is_refresh_revoked_false_before_revoke(self):
        token = jwt_handler.create_refresh_token("uid3")
        assert jwt_handler.is_refresh_revoked(token) is False

    def test_access_token_not_checked_for_revocation(self):
        """Access tokens are not revokable via the in-memory set."""
        token = jwt_handler.create_access_token("uid1", "alice")
        jwt_handler.revoke_refresh_token(token)  # treat as refresh (wrong type)
        # verify_token on an access token should succeed even if in revocation set
        payload = jwt_handler.verify_token(token)
        # type == "access" so revocation check is skipped
        assert payload is not None


class TestSecretKeyPresence:
    def test_secret_key_is_set_in_test_env(self):
        """Tests run with JWT_SECRET_KEY set via conftest.py."""
        assert jwt_handler.SECRET_KEY is not None
        assert len(jwt_handler.SECRET_KEY) > 10
