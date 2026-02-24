"""Simple in-memory brute-force protection utilities.

This is intentionally lightweight and process-local. It tracks recent failed
attempts per key (username or IP) and provides a blocking decision.
"""
import time
from collections import deque

# Configurable limits
MAX_FAILS = 5
WINDOW_SECONDS = 300  # 5 minutes

# Map key -> deque of timestamps
_fails: dict = {}


def record_failed(key: str) -> None:
    now = time.time()
    q = _fails.get(key)
    if q is None:
        q = deque()
        _fails[key] = q
    q.append(now)
    # Trim old
    while q and q[0] < now - WINDOW_SECONDS:
        q.popleft()


def clear_failed(key: str) -> None:
    if key in _fails:
        del _fails[key]


def is_blocked(key: str) -> bool:
    now = time.time()
    q = _fails.get(key)
    if not q:
        return False
    # Trim old
    while q and q[0] < now - WINDOW_SECONDS:
        q.popleft()
    return len(q) >= MAX_FAILS
