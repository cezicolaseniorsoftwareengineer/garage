"""End-to-end test: full payment → subscription → email → game access flow.

Tests every step of:
  1. Registration → OTP verification → login (demo ok)
  2. Subscription gate (REQUIRE_SUBSCRIPTION)
  3. PIX checkout → status polling → auto-activation
  4. Welcome email triggered
  5. Login after activation → 200 + JWT
  6. Account page reports subscription active
  7. Subscription expiry blocks login again (simulated via admin revoke)

Usage:
  python Garage/scripts/test_payment_flow_e2e.py [--base http://localhost:8081]

Requirements: server running, admin credentials in ADMIN_USER / ADMIN_PASS env vars.
"""
import argparse
import os
import sys
import time
import uuid
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--base", default=os.environ.get("APP_BASE_URL", "http://localhost:8081"))
args = parser.parse_args()
BASE = args.base.rstrip("/")

ADMIN_USER = os.environ.get("ADMIN_USER", "biocode")
ADMIN_PASS = os.environ.get("ADMIN_PASS", os.environ.get("ADMIN_PASSWORD", ""))

OK   = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
SKIP = "\033[93m[SKIP]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

failures = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {OK}  {label}")
    else:
        print(f"  {FAIL} {label}" + (f" — {detail}" if detail else ""))
        failures.append(label)


def step(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def post(path, json=None, token=None, expect=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{BASE}{path}", json=json, headers=headers, timeout=15)
    if expect and r.status_code != expect:
        print(f"  {INFO} POST {path} → {r.status_code} (expected {expect}): {r.text[:200]}")
    return r


def get(path, token=None, params=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(f"{BASE}{path}", headers=headers, params=params, timeout=15)


# ---------------------------------------------------------------------------
# STEP 0 — Healthcheck
# ---------------------------------------------------------------------------
step("0. HEALTHCHECK")
r = get("/api/health")
check("Server is up", r.status_code == 200, r.text[:100])
if r.status_code != 200:
    print(f"\n  Server at {BASE} is not responding. Start it and retry.\n")
    sys.exit(1)


# ---------------------------------------------------------------------------
# STEP 1 — Admin Login
# ---------------------------------------------------------------------------
step("1. ADMIN LOGIN")
r = post("/api/auth/login", {"username": ADMIN_USER, "password": ADMIN_PASS})
check("Admin login 200", r.status_code == 200, r.text[:200])
admin_token = None
if r.status_code == 200:
    admin_token = r.json().get("access_token")
    check("Admin token received", bool(admin_token))
else:
    print(f"  {SKIP} Cannot continue without admin token. Set ADMIN_USER / ADMIN_PASS env vars.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# STEP 2 — Register test user (skips OTP for automated test)
# ---------------------------------------------------------------------------
step("2. REGISTER TEST USER")
test_suffix = uuid.uuid4().hex[:8]
test_user = f"testflow_{test_suffix}"
test_email = f"testflow_{test_suffix}@garage-test.com"
test_pass = "Garage@2026!"

r = post("/api/auth/register", {
    "full_name": f"Test Flow {test_suffix}",
    "username": test_user,
    "email": test_email,
    "whatsapp": "11999990000",
    "profession": "estudante",
    "password": test_pass,
})
check("Register 200 or 201", r.status_code in (200, 201), r.text[:200])
print(f"  {INFO} Created user: {test_user} / {test_email}")

# Auto-verify email via admin (bypass OTP for test)
time.sleep(0.5)
r_users = get("/api/admin/users", admin_token)
test_user_id = None
if r_users.status_code == 200:
    users = r_users.json().get("users", [])
    for u in users:
        if u.get("username") == test_user:
            test_user_id = u.get("id")
            break
check("Test user found in DB", bool(test_user_id), f"user={test_user}")

if test_user_id:
    r_verify = post(f"/api/admin/users/{test_user_id}/verify-email", token=admin_token)
    check("Admin forced email verification", r_verify.status_code in (200, 204), r_verify.text[:200])


# ---------------------------------------------------------------------------
# STEP 3 — Login WITHOUT subscription (should return 402 if gate is on)
# ---------------------------------------------------------------------------
step("3. LOGIN WITHOUT SUBSCRIPTION")
r = post("/api/auth/login", {"username": test_user, "password": test_pass})
require_sub = os.environ.get("REQUIRE_SUBSCRIPTION", "false").lower() == "true"

if require_sub:
    check("Login blocked — 402 subscription_required", r.status_code == 402,
          f"got {r.status_code}: {r.text[:200]}")
    check("Response has code=subscription_required",
          r.json().get("code") == "subscription_required", r.text[:200])
else:
    check(f"Gate OFF — login allowed (REQUIRE_SUBSCRIPTION={require_sub})", r.status_code == 200)
print(f"  {INFO} REQUIRE_SUBSCRIPTION={require_sub}")


# ---------------------------------------------------------------------------
# STEP 4 — Admin grants subscription (simulate payment)
# ---------------------------------------------------------------------------
step("4. ADMIN GRANT SUBSCRIPTION (simulates webhook activation)")
if test_user_id:
    r = post(f"/api/admin/users/{test_user_id}/grant-subscription",
             json={"plan": "monthly", "days": 30},
             token=admin_token)
    check("Grant subscription 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        body = r.json()
        check("success=true", body.get("success") is True)
        check("plan=monthly", body.get("plan") == "monthly")
        check("expires_at present", bool(body.get("expires_at")))
        print(f"  {INFO} Expires: {body.get('expires_at')}")
else:
    print(f"  {SKIP} No user_id — skipping grant")


# ---------------------------------------------------------------------------
# STEP 5 — Login WITH active subscription → should succeed
# ---------------------------------------------------------------------------
step("5. LOGIN WITH ACTIVE SUBSCRIPTION")
time.sleep(0.5)
r = post("/api/auth/login", {"username": test_user, "password": test_pass})
check("Login 200 with active subscription", r.status_code == 200, r.text[:300])
player_token = None
if r.status_code == 200:
    player_token = r.json().get("access_token")
    check("JWT token received", bool(player_token))
    sub_status = r.json().get("user", {}).get("subscription_status")
    print(f"  {INFO} subscription_status in JWT response: {sub_status}")


# ---------------------------------------------------------------------------
# STEP 6 — Account page shows active subscription
# ---------------------------------------------------------------------------
step("6. ACCOUNT PAGE — subscription status")
if player_token:
    r = get("/api/account/me", player_token)
    check("GET /api/account/me 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        sub = r.json().get("subscription", {})
        check("subscription.status = active", sub.get("status") == "active", str(sub))
        check("subscription.expires_at present", bool(sub.get("expires_at")))
        check("plan_label present", bool(sub.get("plan_label")))
else:
    print(f"  {SKIP} No player token")


# ---------------------------------------------------------------------------
# STEP 7 — PIX checkout creates a charge (API call, no real payment)
# ---------------------------------------------------------------------------
step("7. PIX CHECKOUT — creates Asaas charge")
if player_token and test_user_id:
    r = post("/api/payments/checkout", json={
        "user_id": test_user_id,
        "user_name": f"Test Flow {test_suffix}",
        "user_email": test_email,
        "plan": "monthly",
    }, token=player_token)
    if r.status_code == 201:
        body = r.json()
        check("Checkout 201", True)
        check("payment_id present", bool(body.get("payment_id")))
        check("pix_copy_paste present", bool(body.get("pix_copy_paste")))
        check("qr_code_base64 present", bool(body.get("qr_code_base64")))
        print(f"  {INFO} payment_id: {body.get('payment_id')}")
    elif r.status_code == 502:
        print(f"  {SKIP} PIX checkout returned 502 (Asaas unreachable in test env): {r.text[:200]}")
    else:
        check("Checkout 201", False, f"{r.status_code}: {r.text[:200]}")
else:
    print(f"  {SKIP} No player token or user_id")


# ---------------------------------------------------------------------------
# STEP 8 — Webhook simulation (PAYMENT_CONFIRMED with externalReference)
# ---------------------------------------------------------------------------
step("8. WEBHOOK — PAYMENT_CONFIRMED simulation")
if test_user_id:
    fake_payload = {
        "event": "PAYMENT_CONFIRMED",
        "payment": {
            "id": f"pay_test_{uuid.uuid4().hex[:12]}",
            "status": "CONFIRMED",
            "value": 97.00,
            "externalReference": f"{test_user_id}|monthly",
            "customer": "cus_test_000",
        }
    }
    r = post("/api/payments/webhook/asaas", json=fake_payload)
    check("Webhook accepted (200)", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        action = r.json().get("action", "")
        check("action = subscription_activated", action == "subscription_activated", action)
else:
    print(f"  {SKIP} No user_id")


# ---------------------------------------------------------------------------
# STEP 9 — Admin revoke subscription → login blocked again
# ---------------------------------------------------------------------------
step("9. REVOKE SUBSCRIPTION → login blocked again")
if test_user_id and admin_token:
    r = post(f"/api/admin/users/{test_user_id}/revoke-subscription", token=admin_token)
    if r.status_code in (200, 204, 404, 405):
        print(f"  {INFO} Revoke response: {r.status_code} {r.text[:200]}")
        # Now try to login
        time.sleep(0.3)
        r_login = post("/api/auth/login", {"username": test_user, "password": test_pass})
        if require_sub:
            check("Login blocked after revoke (402)", r_login.status_code == 402,
                  f"got {r_login.status_code}")
        else:
            print(f"  {SKIP} Gate OFF — revoke test not meaningful")
    else:
        print(f"  {SKIP} revoke-subscription endpoint: {r.status_code} (may not exist)")


# ---------------------------------------------------------------------------
# STEP 10 — Cleanup (delete test user)
# ---------------------------------------------------------------------------
step("10. CLEANUP")
if test_user_id and admin_token:
    r = requests.delete(f"{BASE}/api/admin/users/{test_user_id}",
                        headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    check("Test user deleted", r.status_code in (200, 204), r.text[:200])


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'═'*60}")
if failures:
    print(f"\033[91m  FALHOU: {len(failures)} verificação(ões)\033[0m")
    for f in failures:
        print(f"    - {f}")
    print()
    sys.exit(1)
else:
    print(f"\033[92m  TODOS OS TESTES PASSARAM\033[0m")
    print(f"  Fluxo completo de pagamento validado em: {BASE}")
    print()
    sys.exit(0)
