"""Unit tests for audit logger."""
import json
import os
import threading
import tempfile
import pytest


@pytest.fixture
def tmp_log_dir(monkeypatch, tmp_path):
    """Redirect audit log to a temp directory."""
    import app.infrastructure.audit as audit_mod
    monkeypatch.setattr(audit_mod, "LOG_DIR", tmp_path)
    monkeypatch.setattr(audit_mod, "LOG_FILE", tmp_path / "audit.log")
    return tmp_path


class TestLogEvent:
    def test_creates_log_file(self, tmp_log_dir):
        from app.infrastructure.audit import log_event
        log_event("test_action", "user-1", {"key": "value"})
        log_file = tmp_log_dir / "audit.log"
        assert log_file.exists()

    def test_log_entry_is_valid_json(self, tmp_log_dir):
        from app.infrastructure.audit import log_event
        log_event("login", "uid-42", {"ip": "127.0.0.1"})
        log_file = tmp_log_dir / "audit.log"
        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["action"] == "login"
        assert entry["user_id"] == "uid-42"
        assert entry["payload"]["ip"] == "127.0.0.1"

    def test_multiple_events_appended(self, tmp_log_dir):
        from app.infrastructure.audit import log_event
        log_event("a1", "u1")
        log_event("a2", "u2")
        log_file = tmp_log_dir / "audit.log"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_null_payload_defaults_to_empty_dict(self, tmp_log_dir):
        from app.infrastructure.audit import log_event
        log_event("no_payload", "uid-0")
        log_file = tmp_log_dir / "audit.log"
        entry = json.loads(log_file.read_text().strip())
        assert entry["payload"] == {}

    def test_thread_safe_concurrent_writes(self, tmp_log_dir):
        """20 threads write simultaneously — no corruption, all lines valid JSON."""
        from app.infrastructure.audit import log_event
        errors = []

        def write():
            try:
                log_event("concurrent", "uid", {"t": threading.current_thread().name})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent write errors: {errors}"
        log_file = tmp_log_dir / "audit.log"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 20
        for line in lines:
            json.loads(line)  # must be valid JSON
