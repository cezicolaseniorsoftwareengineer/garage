"""Unit tests for User entity."""
import pytest
from app.domain.user import User


def _make_user(**kwargs):
    salt = User.generate_salt()
    password = kwargs.pop("password", "secret123")
    pw_hash = User.hash_password(password, salt)
    defaults = {
        "full_name": "Alice Dev",
        "username": "alicedev",
        "email": "alice@example.com",
        "whatsapp": "11987654321",
        "profession": "estudante",
        "password_hash": pw_hash,
        "salt": salt,
    }
    defaults.update(kwargs)
    return User(**defaults), password


class TestUserCreation:
    def test_username_normalized_lowercase(self):
        u, _ = _make_user(username="AliceDEV")
        assert u.username == "alicedev"

    def test_email_normalized_lowercase(self):
        u, _ = _make_user(email="Alice@EXAMPLE.COM")
        assert u.email == "alice@example.com"

    def test_id_auto_generated(self):
        u, _ = _make_user()
        assert u.id and len(u.id) > 10

    def test_explicit_id_preserved(self):
        u, _ = _make_user(user_id="explicit-id-123")
        assert u.id == "explicit-id-123"


class TestUserPassword:
    def test_correct_password_verifies(self):
        u, pw = _make_user()
        assert u.verify_password(pw) is True

    def test_wrong_password_fails(self):
        u, _ = _make_user()
        assert u.verify_password("wrongpassword") is False

    def test_generate_salt_is_unique(self):
        s1 = User.generate_salt()
        s2 = User.generate_salt()
        assert s1 != s2

    def test_hash_is_deterministic(self):
        salt = "fixed_salt"
        h1 = User.hash_password("pass", salt)
        h2 = User.hash_password("pass", salt)
        assert h1 == h2

    def test_hash_differs_with_different_password(self):
        salt = "fixed_salt"
        assert User.hash_password("pass1", salt) != User.hash_password("pass2", salt)


class TestUserSerialization:
    def test_to_dict_contains_hash(self):
        u, _ = _make_user()
        d = u.to_dict()
        assert "password_hash" in d
        assert "salt" in d

    def test_to_public_dict_excludes_credentials(self):
        u, _ = _make_user()
        d = u.to_public_dict()
        assert "password_hash" not in d
        assert "salt" not in d
        assert "id" in d
        assert "username" in d
