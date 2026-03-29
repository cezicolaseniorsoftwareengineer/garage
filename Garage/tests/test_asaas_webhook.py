import os
import json
import hmac
import hashlib
from datetime import datetime

from fastapi.testclient import TestClient
import importlib


def sign_payload(secret: str, payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_asaas_webhook_happy_path(monkeypatch):
    os.environ["ENABLE_ASAAS_WEBHOOK"] = "true"
    os.environ["ASAAS_WEBHOOK_SECRET"] = "test_secret"

    # Reload application module so env changes are picked up
    import app.main as am
    importlib.reload(am)
    app = am.app

    # Stub subscription activation to avoid repository side-effects
    def fake_activate_subscription(user_id, plan, user_repo):
        return datetime.now()

    monkeypatch.setattr("app.infrastructure.payment.pix_service.activate_subscription", fake_activate_subscription, raising=False)

    client = TestClient(app)

    payload = {
        "event": "PAYMENT_CONFIRMED",
        "payment": {
            "id": "pay_test_1",
            "externalReference": "user123|monthly",
            "value": 97.0,
        },
    }

    # Sign the exact bytes we'll send
    body_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = sign_payload(os.environ["ASAAS_WEBHOOK_SECRET"], payload)

    headers = {"X-Asaas-Signature": sig, "Content-Type": "application/json"}

    resp = client.post("/api/payments/webhook/asaas", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("received") is True
    assert data.get("action") in ("subscription_activated", "subscription_activated_by_email")
