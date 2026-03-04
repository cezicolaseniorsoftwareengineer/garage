"""Real E2E for biocode account (production-safe, no real money).

Flow covered:
  1) Admin login
  2) Locate biocode user by email
  3) Optional revoke subscription (to simulate blocked user before payment)
  4) Simulate payment confirmation (webhook PAYMENT_CONFIRMED)
  5) Validate subscription active and expiration window (30d or 365d)
  6) Trigger one extra welcome email via admin grant endpoint (same plan)

Notes:
- No real PIX payment is created; webhook is simulated intentionally.
- Email arrival cannot be verified by API; user confirms inbox out-of-band.

Usage:
  ADMIN_USER=cezar ADMIN_PASS=*** python Garage/scripts/test_payment_flow_biocode_real.py \
      --base https://garage-0lw9.onrender.com --plan monthly

  ADMIN_USER=cezar ADMIN_PASS=*** python Garage/scripts/test_payment_flow_biocode_real.py \
      --base https://garage-0lw9.onrender.com --plan annual
"""

from __future__ import annotations

import argparse
import os
import time
import uuid
from datetime import datetime, timezone

import requests

TARGET_EMAIL = "biocodetechnology@gmail.com"
TARGET_USERNAME = "biocode"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get("APP_BASE_URL", "https://garage-0lw9.onrender.com"))
    parser.add_argument("--plan", choices=["monthly", "annual"], default="monthly")
    parser.add_argument(
        "--skip-revoke",
        action="store_true",
        help="Do not revoke before simulating payment.",
    )
    return parser.parse_args()


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def _headers(self, token: str | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get(self, path: str, token: str | None = None):
        return requests.get(f"{self.base}{path}", headers=self._headers(token), timeout=20)

    def post(self, path: str, payload: dict | None = None, token: str | None = None):
        return requests.post(f"{self.base}{path}", json=payload or {}, headers=self._headers(token), timeout=20)


def _ok(label: str, detail: str = ""):
    suffix = f" | {detail}" if detail else ""
    print(f"[OK]  {label}{suffix}")


def _fail(label: str, detail: str = ""):
    suffix = f" | {detail}" if detail else ""
    print(f"[FAIL] {label}{suffix}")


def _must(condition: bool, label: str, detail: str = ""):
    if not condition:
        _fail(label, detail)
        raise SystemExit(1)
    _ok(label, detail)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _days_remaining(expires_at: datetime | None) -> int | None:
    if not expires_at:
        return None
    now = datetime.now(timezone.utc)
    delta = expires_at - now
    return int(delta.total_seconds() // 86400)


def _find_user(users: list[dict], email: str, username: str) -> dict | None:
    email_l = email.lower()
    username_l = username.lower()
    for user in users:
        user_email = str(user.get("email", "")).lower()
        user_name = str(user.get("username", "")).lower()
        if user_email == email_l or user_name == username_l:
            return user
    return None


def main() -> int:
    args = _parse_args()
    admin_user = os.environ.get("ADMIN_USER", "")
    admin_pass = os.environ.get("ADMIN_PASS", os.environ.get("ADMIN_PASSWORD", ""))

    _must(bool(admin_user and admin_pass), "Credenciais admin presentes", "Defina ADMIN_USER e ADMIN_PASS")

    c = Client(args.base)

    print("\n=== PASSO 0: health ===")
    r = c.get("/health")
    _must(r.status_code == 200, "Servidor online", f"HTTP {r.status_code}")

    print("\n=== PASSO 1: admin login ===")
    r = c.post("/api/auth/login", {"username": admin_user, "password": admin_pass})
    _must(r.status_code == 200, "Admin login", f"HTTP {r.status_code}")
    body = r.json()
    token = body.get("access_token")
    _must(bool(token), "Token admin recebido")

    print("\n=== PASSO 2: localizar/criar usuário biocode ===")
    r = c.get("/api/admin/users", token=token)
    _must(r.status_code == 200, "Listar usuários admin", f"HTTP {r.status_code}")
    users = r.json() if isinstance(r.json(), list) else []
    target = _find_user(users, TARGET_EMAIL, TARGET_USERNAME)

    if not target:
        create_password = os.environ.get("BIOCODE_PASSWORD", "Garage@2026Bio!")
        create_payload = {
            "full_name": "Bio Code",
            "username": TARGET_USERNAME,
            "email": TARGET_EMAIL,
            "whatsapp": "11999990000",
            "profession": "empresario",
            "password": create_password,
        }
        r_create = c.post("/api/admin/test/create-verified-user", create_payload, token=token)
        _must(r_create.status_code in (200, 201), "Criar biocode (se ausente)", f"HTTP {r_create.status_code}")

        r = c.get("/api/admin/users", token=token)
        _must(r.status_code == 200, "Reler usuários após criação", f"HTTP {r.status_code}")
        users = r.json() if isinstance(r.json(), list) else []
        target = _find_user(users, TARGET_EMAIL, TARGET_USERNAME)

    _must(bool(target), "Usuário biocode encontrado", f"{TARGET_USERNAME} / {TARGET_EMAIL}")

    user_id = target["id"]
    before_status = target.get("subscription_status")
    before_plan = target.get("subscription_plan")
    before_exp = _parse_iso(target.get("subscription_expires_at"))
    _ok("Estado inicial", f"status={before_status} plan={before_plan} exp={target.get('subscription_expires_at')}")

    if not args.skip_revoke:
        print("\n=== PASSO 3: revogar (simular bloqueio antes do pagamento) ===")
        r = c.post(f"/api/admin/users/{user_id}/revoke-subscription", token=token)
        _must(r.status_code == 200, "Revoke subscription", f"HTTP {r.status_code}")
        time.sleep(0.6)

    print("\n=== PASSO 4: simular pagamento confirmado (sem dinheiro) ===")
    fake_payment_id = f"pay_biocode_{uuid.uuid4().hex[:12]}"
    webhook_payload = {
        "event": "PAYMENT_CONFIRMED",
        "payment": {
            "id": fake_payment_id,
            "status": "CONFIRMED",
            "value": 997.0 if args.plan == "annual" else 97.0,
            "externalReference": f"{user_id}|{args.plan}",
            "customer": "cus_biocode_test",
        },
    }
    r = c.post("/api/payments/webhook/asaas", webhook_payload)
    _must(r.status_code == 200, "Webhook aceito", f"HTTP {r.status_code}")
    action = r.json().get("action") if isinstance(r.json(), dict) else None
    _must(action == "subscription_activated", "Webhook ativou assinatura", f"action={action}")

    print("\n=== PASSO 5: validar assinatura ativa + janela ===")
    time.sleep(1.2)
    r = c.get("/api/admin/users", token=token)
    _must(r.status_code == 200, "Reler usuários", f"HTTP {r.status_code}")
    users_after = r.json() if isinstance(r.json(), list) else []
    target_after = _find_user(users_after, TARGET_EMAIL, TARGET_USERNAME)
    _must(bool(target_after), "Usuário biocode ainda encontrado")

    status_after = target_after.get("subscription_status")
    plan_after = target_after.get("subscription_plan")
    exp_after_raw = target_after.get("subscription_expires_at")
    exp_after = _parse_iso(exp_after_raw)

    _must(status_after == "active", "Status ativo", f"status={status_after}")
    _must(plan_after == args.plan, "Plano correto", f"plan={plan_after}")

    remaining_days = _days_remaining(exp_after)
    _must(remaining_days is not None, "Expiração presente", str(exp_after_raw))

    if args.plan == "monthly":
        _must(27 <= remaining_days <= 31, "Janela mensal válida", f"dias_restantes={remaining_days}")
    else:
        _must(360 <= remaining_days <= 366, "Janela anual válida", f"dias_restantes={remaining_days}")

    print("\n=== PASSO 6: validar acesso do usuário ao jogo (token real) ===")
    r_imp = c.post(f"/api/admin/users/{user_id}/impersonate", token=token)
    _must(r_imp.status_code == 200, "Impersonate biocode", f"HTTP {r_imp.status_code}")
    user_token = r_imp.json().get("access_token") if isinstance(r_imp.json(), dict) else None
    _must(bool(user_token), "Token do usuário recebido")

    r_me = c.get("/api/account/me", token=user_token)
    _must(r_me.status_code == 200, "GET /api/account/me com token do usuário", f"HTTP {r_me.status_code}")
    sub_me = r_me.json().get("subscription", {}) if isinstance(r_me.json(), dict) else {}
    _must(sub_me.get("status") == "active", "Conta com assinatura ativa em /account/me", str(sub_me))

    print("\n=== PASSO 7: disparo extra de email de boas-vindas ===")
    # Reenviamos o evento PAYMENT_CONFIRMED para acionar novamente
    # activate_subscription + send_subscription_welcome_email sem cobrança real.
    fake_payment_id_2 = f"pay_biocode_resend_{uuid.uuid4().hex[:10]}"
    webhook_payload_2 = {
        "event": "PAYMENT_CONFIRMED",
        "payment": {
            "id": fake_payment_id_2,
            "status": "CONFIRMED",
            "value": 997.0 if args.plan == "annual" else 97.0,
            "externalReference": f"{user_id}|{args.plan}",
            "customer": "cus_biocode_test",
        },
    }
    r = c.post("/api/payments/webhook/asaas", webhook_payload_2)
    _must(r.status_code == 200, "Webhook extra aceito (reenvio de e-mail)", f"HTTP {r.status_code}")

    print("\n=== RESULTADO ===")
    print("[OK] Fluxo real (sem cobrança) concluído para biocode")
    print(f"[OK] user_id={user_id}")
    print(f"[OK] plano={args.plan}")
    print(f"[OK] expiração={exp_after_raw}")
    print("[INFO] Verifique caixa de entrada/SPAM do biocodetechnology@gmail.com")
    print("[INFO] Quando o e-mail chegar, me envie o código/conteúdo e eu continuo do próximo passo.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
