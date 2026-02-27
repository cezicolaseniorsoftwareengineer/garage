"""Unit tests for brute-force protection."""
import time
import pytest
from app.infrastructure.auth import bruteforce


@pytest.fixture(autouse=True)
def clear_state():
    """Always start with a clean brute-force state."""
    bruteforce._fails.clear()
    yield
    bruteforce._fails.clear()


class TestRecordFailed:
    def test_records_one_failure(self):
        bruteforce.record_failed("user1")
        assert not bruteforce.is_blocked("user1")  # 1 of 5 -> not blocked

    def test_different_keys_are_independent(self):
        for _ in range(bruteforce.MAX_FAILS):
            bruteforce.record_failed("user_a")
        assert bruteforce.is_blocked("user_a")
        assert not bruteforce.is_blocked("user_b")


class TestIsBlocked:
    def test_not_blocked_initially(self):
        assert not bruteforce.is_blocked("new_user")

    def test_blocked_after_max_fails(self):
        for _ in range(bruteforce.MAX_FAILS):
            bruteforce.record_failed("target")
        assert bruteforce.is_blocked("target")

    def test_one_below_max_not_blocked(self):
        for _ in range(bruteforce.MAX_FAILS - 1):
            bruteforce.record_failed("target")
        assert not bruteforce.is_blocked("target")


class TestClearFailed:
    def test_clear_removes_block(self):
        for _ in range(bruteforce.MAX_FAILS):
            bruteforce.record_failed("to_clear")
        assert bruteforce.is_blocked("to_clear")
        bruteforce.clear_failed("to_clear")
        assert not bruteforce.is_blocked("to_clear")

    def test_clear_non_existent_key_is_safe(self):
        bruteforce.clear_failed("ghost_user")  # should not raise


class TestWindowExpiry:
    def test_old_failures_do_not_count(self, monkeypatch):
        """
        Simulate failures at t=0 (expired) and verify they are purged
        when is_blocked is called at t=WINDOW+1.
        """
        from collections import deque
        fake_time = bruteforce.WINDOW_SECONDS + 10  # well past window

        # Record MAX_FAILS failures but all with timestamp=0 (expired)
        bruteforce._fails["stale"] = deque([0.0] * bruteforce.MAX_FAILS)

        # Now monkeypatch time.time to return a future timestamp
        monkeypatch.setattr(bruteforce.time, "time", lambda: fake_time)

        assert not bruteforce.is_blocked("stale")  # expired entries purged
