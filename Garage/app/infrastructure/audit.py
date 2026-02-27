"""Append-only audit logger for critical events.

Writes newline-delimited JSON entries to `logs/audit.log`.
Thread-safe via a module-level lock (suitable for single-process async workers).
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()

ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "audit.log"


def _ensure_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_event(action: str, user_id: str | None, payload: dict | None = None) -> None:
    _ensure_dir()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user_id": user_id,
        "payload": payload or {},
    }
    # Write as single JSON line (append-only). Lock guarantees no interleaved
    # writes when multiple async tasks flush simultaneously (Windows + Linux).
    with _LOCK:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
