"""End-to-end test: full payment → subscription → email → game access flow.

Zero real payment required. Uses admin endpoints to simulate every step:

  0.  Healthcheck
  1.  Admin login
  2.  Create test user (pre-verified, skips OTP)
  3.  Login WITHOUT subscription → 402 (gate on) or 200 (gate off)
  4.  Admin grant subscription (simulates Asaas webhook/payment)
  5.  Login WITH subscription → 200 + JWT
  6.  GET /api/account/me → subscription.status=active
  7.  PIX checkout call (skip gracefully if Asaas unreachable)
  8.  Webhook simulation (PAYMENT_CONFIRMED with externalReference)
  9.  Revoke subscription → login blocked again
  10. Cleanup — delete test user

Usage:
  python Garage/scripts/test_payment_flow_e2e.py [--base http://localhost:8081]
  ADMIN_USER=biocode ADMIN_PASS=xxxx python Garage/scripts/test_payment_flow_e2e.py
"""
import argparse
import os
import sys
import time
import uuid
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--base", default=os.environ.get("APP_BASE_URL", "http://localhost:8081"))
args = parser.parse_args()
BASE = args.base.rstrip("/")

ADMIN_USER = os.environ.get("ADMIN_USER", os.environ.get("ADMIN_USERNAME", "biocode"))
ADMIN_PASS = os.environ.get("ADMIN_PASS", os.environ.get("ADMIN_PASSWORD", ""))

OK   = "\033[92m[OK]\033[0m  "
FAIL = "\033[91m[FAIL]\033[0m"
SKIP = "\033[93m[SKIP]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

failures = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {OK} {label}")
    else:
        print(f"  {FAIL} {label}" + (f"\n         detalhe: {detail}" if detail else ""))
        failures.append(label)


def step(n: int, title: str):
    print(f"\n{'=' * 62}")
    print(f"  PASSO {n} — {title}")
    print(f"{'=' * 62}")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _r_error(exc):
    class _R:
        status_code = 0
        text = str(exc)
        def json(self): return {}
    return _R()


def post(path, json=None, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    try:
        return requests.post(f"{BASE}{path}", json=json, headers=h, timeout=15)
    except requests.exceptions.ConnectionError as e:
        return _r_error(e)


def get(path, token=None, params=None):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    try:
        return requests.get(f"{BASE}{path}", headers=h, params=params, timeout=15)
    except requests.exceptions.ConnectionError as e:
        return _r_error(e)


def delete(path, token=None):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    try:
        return requests.delete(f"{BASE}{path}", headers=h, timeout=15)
    except requests.exceptions.ConnectionError as e:
        return _r_error(e)


# ============================================================
# PASSO 0 — Healthcheck
# ============================================================
step(0, "HEALTHCHECK")
r = get("/health")
check("Servidor respondendo (200)", r.status_code == 200, r.text[:120])
if r.status_code != 200:
    print(f"\n  Servidor em {BASE} nao responde. Inicie-o e tente novamente.\n")
    sys.exit(1)
h = r.json()
print(f"  {INFO} persistence={h.get('persistence')} db={h.get('database')} challenges={h.get('challenges_loaded')}")


# ============================================================
# PASSO 1 — Admin login
# ============================================================
step(1, "LOGIN DO ADMIN")
if not ADMIN_PASS:
    print(f"  {SKIP} Defina ADMIN_PASS= (e.g. export ADMIN_PASS=suasenha) antes de rodar.")
    sys.exit(1)

r = post("/api/auth/login", {"username": ADMIN_USER, "password": ADMIN_PASS})
check("Admin login 200", r.status_code == 200, r.text[:200])
admin_token = r.json().get("access_token") if r.status_code == 200 else None
if not admin_token:
    print(f"  {FAIL} Token admin nao obtido — impossivel continuar.")
    sys.exit(1)
print(f"  {INFO} Admin autenticado: {ADMIN_USER}")


# ============================================================
# PASSO 2 — Criar usuario de teste pre-verificado (sem OTP)
# ============================================================
step(2, "CRIAR USUARIO DE TESTE (pre-verificado, sem OTP real)")
suffix = uuid.uuid4().hex[:8]
test_user  = f"testflow_{suffix}"
test_email = f"testflow_{suffix}@garage-test.local"
test_pass  = "Garage@2026Test!"

r = post("/api/admin/test/create-verified-user",
         json={
             "full_name": f"Test Flow {suffix}",
             "username": test_user,
             "email": test_email,
             "whatsapp": "11999990000",
             "profession": "estudante",
             "password": test_pass,
         },
         token=admin_token)

check("Usuario criado (201)", r.status_code == 201, r.text[:300])
test_user_id = r.json().get("user_id") if r.status_code == 201 else None
check("user_id retornado", bool(test_user_id))
print(f"  {INFO} user_id : {test_user_id}")
print(f"  {INFO} login   : {test_user} / {test_pass}")


# ============================================================
# PASSO 3 — Login SEM assinatura
# ============================================================
step(3, "LOGIN SEM ASSINATURA")
r = post("/api/auth/login", {"username": test_user, "password": test_pass})
require_sub = os.environ.get("REQUIRE_SUBSCRIPTION", "false").lower() == "true"
print(f"  {INFO} REQUIRE_SUBSCRIPTION={require_sub} (lido do ambiente local)")

if require_sub:
    check("Login bloqueado — HTTP 402", r.status_code == 402,
          f"recebido {r.status_code}: {r.text[:200]}")
    body402 = r.json() if r.status_code == 402 else {}
    check("code=subscription_required", body402.get("code") == "subscription_required", str(body402))
    check("action_url=/account presente", "/account" in body402.get("action_url", ""), str(body402))
else:
    check(f"Gate OFF — login permitido (HTTP {r.status_code})", r.status_code == 200,
          r.text[:200])
    print(f"  {INFO} Para testar o bloqueio: REQUIRE_SUBSCRIPTION=true no .env")


# ============================================================
# PASSO 4 — Admin ativa assinatura (simula pagamento)
# ============================================================
step(4, "ADMIN ATIVA ASSINATURA (simula pagamento recebido)")
if test_user_id:
    r = post(f"/api/admin/users/{test_user_id}/grant-subscription",
             json={"plan": "monthly", "days": 30},
             token=admin_token)
    check("grant-subscription 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        body = r.json()
        check("success=true", body.get("success") is True)
        check("plan=monthly", body.get("plan") == "monthly")
        check("expires_at presente", bool(body.get("expires_at")))
        print(f"  {INFO} Expira em: {body.get('expires_at')}")
else:
    print(f"  {SKIP} Sem user_id — pulando")


# ============================================================
# PASSO 5 — Login COM assinatura ativa
# ============================================================
step(5, "LOGIN COM ASSINATURA ATIVA")
time.sleep(0.5)
r = post("/api/auth/login", {"username": test_user, "password": test_pass})
check("Login 200 com assinatura ativa", r.status_code == 200, r.text[:300])
player_token = None
if r.status_code == 200:
    player_token = r.json().get("access_token")
    check("JWT token recebido", bool(player_token))
    user_obj = r.json().get("user", {})
    print(f"  {INFO} subscription_status no payload: {user_obj.get('subscription_status', 'n/a')}")


# ============================================================
# PASSO 6 — Area do usuario /api/account/me
# ============================================================
step(6, "AREA DO USUARIO — /api/account/me")
if player_token:
    r = get("/api/account/me", player_token)
    check("GET /api/account/me 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        sub = data.get("subscription", {})
        check("subscription.status = active", sub.get("status") == "active", str(sub))
        check("subscription.expires_at presente", bool(sub.get("expires_at")))
        check("plan_label presente", bool(sub.get("plan_label")))
        print(f"  {INFO} subscription: {sub}")
else:
    print(f"  {SKIP} Sem player token")


# ============================================================
# PASSO 7 — PIX checkout (502 tolerado se Asaas inacessivel)
# ============================================================
step(7, "PIX CHECKOUT — cria cobranca Asaas (real API call)")
if player_token and test_user_id:
    r = post("/api/payments/checkout",
             json={
                 "user_id": test_user_id,
                 "user_name": f"Test Flow {suffix}",
                 "user_email": test_email,
                 "plan": "monthly",
                     "payment_method": "pix",
                     "cpf_cnpj": "52998224725",
             },
             token=player_token)
    if r.status_code == 201:
        body = r.json()
        check("Checkout 201", True)
        check("payment_id presente", bool(body.get("payment_id")))
        check("pix_copy_paste presente", bool(body.get("pix_copy_paste")))
        check("qr_code_base64 presente", bool(body.get("qr_code_base64")))
        print(f"  {INFO} payment_id: {body.get('payment_id')}")
    elif r.status_code == 502:
        print(f"  {SKIP} PIX checkout {r.status_code} (Asaas inacessivel) — tolerado")
        print(f"  {INFO} {r.text[:150]}")
    else:
        check("Checkout 201 (ou 502 tolerado)", False, f"HTTP {r.status_code}: {r.text[:200]}")
else:
    print(f"  {SKIP} Sem player token ou user_id")


# ============================================================
# PASSO 8 — Webhook PAYMENT_CONFIRMED (simulado)
# ============================================================
step(8, "WEBHOOK — simulacao PAYMENT_CONFIRMED")
if test_user_id:
    fake_id = f"pay_test_{uuid.uuid4().hex[:12]}"
    r = post("/api/payments/webhook/asaas", json={
        "event": "PAYMENT_CONFIRMED",
        "payment": {
            "id": fake_id,
            "status": "CONFIRMED",
            "value": 97.00,
            "externalReference": f"{test_user_id}|monthly",
            "customer": "cus_test_000",
        }
    })
    check("Webhook aceito (200)", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        action = r.json().get("action", "")
        check("action=subscription_activated", action == "subscription_activated",
              f"action recebido: '{action}'")
        print(f"  {INFO} Resposta: {r.json()}")
else:
    print(f"  {SKIP} Sem user_id")


# ============================================================
# PASSO 9 — Revogar assinatura → login bloqueado
# ============================================================
step(9, "REVOGAR ASSINATURA -> login bloqueado novamente")
if test_user_id and admin_token:
    r = post(f"/api/admin/users/{test_user_id}/revoke-subscription", token=admin_token)
    check("revoke-subscription 200", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        time.sleep(0.3)
        r_login = post("/api/auth/login", {"username": test_user, "password": test_pass})
        if require_sub:
            check("Login bloqueado apos revoke (402)", r_login.status_code == 402,
                  f"recebido {r_login.status_code}: {r_login.text[:200]}")
        else:
            print(f"  {SKIP} Gate OFF — revoke nao bloqueia com REQUIRE_SUBSCRIPTION=false")
else:
    print(f"  {SKIP} Sem user_id ou admin token")


# ============================================================
# PASSO 10 — Limpeza
# ============================================================
step(10, "LIMPEZA — deletar usuario de teste")
if test_user_id and admin_token:
    r = delete(f"/api/admin/users/{test_user_id}", token=admin_token)
    check("Usuario deletado (200/204)", r.status_code in (200, 204),
          f"HTTP {r.status_code}: {r.text[:100]}")
    print(f"  {INFO} Removido: {test_user} ({test_user_id})")
else:
    print(f"  {SKIP} Nada para limpar")


# ============================================================
# Resumo final
# ============================================================
total = 10
print(f"\n{'=' * 62}")
if failures:
    print(f"\033[91m  RESULTADO: {len(failures)} verificacao(oes) FALHARAM de {total} passos\033[0m")
    for f in failures:
        print(f"    x {f}")
    print()
    sys.exit(1)
else:
    print(f"\033[92m  RESULTADO: TODOS OS PASSOS APROVADOS\033[0m")
    print(f"  Fluxo completo de pagamento -> assinatura -> acesso validado.")
    print(f"  Servidor: {BASE}")
    print()
    sys.exit(0)
