import os
import uuid
from importlib import reload

import pytest
from fastapi.testclient import TestClient


# Ensure JSON fallback (no DATABASE_URL) so tests run without Postgres
os.environ["DATABASE_URL"] = ""

import app.main as main
reload(main)

client = TestClient(main.app)


def make_register_payload():
    uid = uuid.uuid4().hex[:8]
    return {
        "full_name": f"Test User {uid}",
        "username": f"test_{uid}",
        "email": f"test_{uid}@example.com",
        "whatsapp": "5511999999999",
        "profession": "autonomo",
        "password": "secret123",
    }


def test_register_idempotent_replay():
    payload = make_register_payload()
    idem_key = "test-idem-" + uuid.uuid4().hex

    headers = {"Idempotency-Key": idem_key}

    r1 = client.post("/api/auth/register", json=payload, headers=headers)
    assert r1.status_code in (200, 201, 409)
    body1 = r1.json()

    # Replay the same request — should return the same status and body
    r2 = client.post("/api/auth/register", json=payload, headers=headers)
    assert r2.status_code == r1.status_code
    assert r2.json() == body1
