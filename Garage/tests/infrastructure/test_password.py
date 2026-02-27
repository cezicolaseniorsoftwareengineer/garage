"""Unit tests for password hashing utilities."""
import pytest
from app.infrastructure.auth.password import (
    hash_password,
    verify_password,
    verify_legacy_sha256,
    is_bcrypt_hash,
)


class TestHashPassword:
    def test_returns_bcrypt_hash(self):
        h = hash_password("secret")
        assert h.startswith("$2b$") or h.startswith("$2a$")

    def test_different_calls_produce_different_hashes(self):
        """bcrypt uses different salts each time."""
        h1 = hash_password("secret")
        h2 = hash_password("secret")
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_wrong_password_returns_false(self):
        h = hash_password("mypassword")
        assert verify_password("wrongpassword", h) is False

    def test_empty_password_returns_false(self):
        h = hash_password("mypassword")
        assert verify_password("", h) is False

    def test_invalid_hash_returns_false(self):
        assert verify_password("pass", "not_a_hash") is False


class TestLegacySha256:
    def test_correct_legacy_password_verifies(self):
        import hashlib
        salt = "abc123"
        pw = "legacy_pass"
        stored = hashlib.sha256((salt + pw).encode()).hexdigest()
        assert verify_legacy_sha256(pw, salt, stored) is True

    def test_wrong_legacy_password_fails(self):
        import hashlib
        salt = "abc123"
        stored = hashlib.sha256((salt + "correct").encode()).hexdigest()
        assert verify_legacy_sha256("wrong", salt, stored) is False


class TestIsBcryptHash:
    def test_bcrypt_hash_detected(self):
        h = hash_password("x")
        assert is_bcrypt_hash(h) is True

    def test_sha256_not_bcrypt(self):
        sha_hash = "a" * 64  # 64-char hex string
        assert is_bcrypt_hash(sha_hash) is False

    def test_empty_string_not_bcrypt(self):
        assert is_bcrypt_hash("") is False
