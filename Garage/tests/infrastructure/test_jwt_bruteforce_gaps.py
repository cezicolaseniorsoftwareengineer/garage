"""Extension tests for jwt_handler and bruteforce — covers remaining gap lines."""
import os
import time
import pytest
from collections import deque

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-123456")

from app.infrastructure.auth.jwt_handler import (
    create_access_token,
    verify_token,
    revoke_refresh_token,
    is_refresh_revoked,
    create_refresh_token,
)
from app.infrastructure.auth import bruteforce
from app.infrastructure.auth.bruteforce import (
    record_failed,
    clear_failed,
    is_blocked,
    _fails,
    WINDOW_SECONDS,
)


class TestJwtHandlerGaps:
    def test_verify_token_no_sub_returns_none(self):
        """Line 57: return None when sub is missing from payload."""
        from jose import jwt as jose_jwt
        from app.infrastructure.auth.jwt_handler import SECRET_KEY, ALGORITHM
        from datetime import datetime, timedelta, timezone

        # Mint a token without 'sub' field
        payload_no_sub = {
            "username": "test",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jose_jwt.encode(payload_no_sub, SECRET_KEY, algorithm=ALGORITHM)
        result = verify_token(token)
        assert result is None

    def test_revoke_refresh_token_is_stored(self):
        """Line 74: _revoked_refresh_tokens.add(token) in revoke_refresh_token."""
        token = create_refresh_token("revoke-test-uid")
        # Before revocation: not revoked
        assert not is_refresh_revoked(token)
        # Revoke it
        revoke_refresh_token(token)
        # After revocation: revoked
        assert is_refresh_revoked(token)

    def test_verify_revoked_refresh_token_returns_none(self):
        """Revoked refresh token should not be accepted."""
        token = create_refresh_token("revoke-verify-uid")
        revoke_refresh_token(token)
        result = verify_token(token)
        assert result is None


class TestBruteforceOldEntriesTrimmed:
    def test_old_entries_are_purged_on_record(self):
        """Line 26 (q.popleft): Old failures outside the window are trimmed."""
        key = "old-entry-trim-test"
        _fails.pop(key, None)

        # Inject old failures (far past the window)
        old_time = time.time() - WINDOW_SECONDS - 999
        q = deque([old_time, old_time, old_time])
        _fails[key] = q

        # Record a fresh failure — this triggers the while-trim loop
        record_failed(key)

        # Old entries should be purged, only the fresh one remains
        assert len(_fails[key]) == 1

    def test_clear_failed_removes_key(self):
        key = "clear-test-key"
        record_failed(key)
        assert key in _fails
        clear_failed(key)
        assert key not in _fails

    def test_is_blocked_returns_false_for_unknown_key(self):
        assert not is_blocked("completely-unknown-user-xyz")

    def test_is_blocked_after_many_failures(self):
        key = "blocked-user-test"
        _fails.pop(key, None)
        from app.infrastructure.auth.bruteforce import MAX_FAILS
        for _ in range(MAX_FAILS + 1):
            record_failed(key)
        assert is_blocked(key)
