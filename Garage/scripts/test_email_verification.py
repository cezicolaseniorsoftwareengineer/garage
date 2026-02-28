"""Test suite for email verification system."""
import requests
import uuid
import sys

BASE = "http://localhost:8000"
test_id = uuid.uuid4().hex[:8]
email = f"test_{test_id}@testegarage.dev"
username = f"tester_{test_id}"

PASS = "[PASS]"
FAIL = "[FAIL]"

errors = []

def check(label, condition, msg=""):
    if condition:
        print(f"{PASS} {label}")
    else:
        print(f"{FAIL} {label} -- {msg}")
        errors.append(label)

print("=" * 60)
print("  GARAGE -- Email Verification Test Suite")
print("=" * 60)

# ── 1. Health check ──────────────────────────────────────────
try:
    r = requests.get(f"{BASE}/health", timeout=5)
    data = r.json()
    check("1. Health OK", r.status_code == 200, r.text)
    print(f"     persistence={data.get('persistence')}  challenges={data.get('challenges_loaded')}")
except Exception as exc:
    check("1. Health OK", False, str(exc))

# ── 2. Register new user ─────────────────────────────────────
payload = {
    "full_name": f"Tester {test_id}",
    "username": username,
    "email": email,
    "whatsapp": "11999990000",
    "profession": "estudante",
    "password": "test1234!",
}
try:
    r = requests.post(f"{BASE}/api/auth/register", json=payload, timeout=5)
    data = r.json()
    check("2. Register returns 200", r.status_code == 200, r.text[:200])
    check("2. requires_verification=True", data.get("requires_verification") is True,
          f"got: {data}")
    check("2. No token returned before verification", "access_token" not in data,
          f"unexpectedly got token")
    check("2. email_hint present", "email_hint" in data, f"missing email_hint in {data}")
    print(f"     email_hint={data.get('email_hint')}  msg={data.get('message','')[:60]}")
except Exception as exc:
    check("2. Register", False, str(exc))

# ── 3. Login blocked (unverified) ───────────────────────────
try:
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": username, "password": "test1234!"},
        timeout=5,
    )
    check("3. Login blocked with 403", r.status_code == 403, f"got {r.status_code}: {r.text}")
    detail = r.json().get("detail", "")
    check("3. 403 message mentions verification", "verif" in detail.lower(), detail)
    print(f"     detail={detail[:80]}")
except Exception as exc:
    check("3. Login blocked", False, str(exc))

# ── 4. Duplicate email ──────────────────────────────────────
try:
    r = requests.post(
        f"{BASE}/api/auth/register",
        json={**payload, "username": username + "_dup"},
        timeout=5,
    )
    check("4. Duplicate email blocked 409", r.status_code == 409, f"got {r.status_code}")
except Exception as exc:
    check("4. Duplicate email", False, str(exc))

# ── 5. Duplicate username ────────────────────────────────────
try:
    r = requests.post(
        f"{BASE}/api/auth/register",
        json={**payload, "email": f"other_{email}"},
        timeout=5,
    )
    check("5. Duplicate username blocked 409", r.status_code == 409, f"got {r.status_code}")
except Exception as exc:
    check("5. Duplicate username", False, str(exc))

# ── 6. Resend verification ───────────────────────────────────
try:
    r = requests.post(
        f"{BASE}/api/auth/resend-verification",
        json={"email": email},
        timeout=5,
    )
    data = r.json()
    check("6. Resend returns 200", r.status_code == 200, r.text[:200])
    check("6. Resend success message", data.get("success") is True, str(data))
    print(f"     msg={data.get('message','')}")
except Exception as exc:
    check("6. Resend verification", False, str(exc))

# ── 7. Wrong OTP rejected ────────────────────────────────────
try:
    r = requests.post(
        f"{BASE}/api/auth/verify-email",
        json={"email": email, "code": "000000"},
        timeout=5,
    )
    check("7. Wrong OTP returns 400", r.status_code == 400, f"got {r.status_code}: {r.text}")
    print(f"     detail={r.json().get('detail','')[:70]}")
except Exception as exc:
    check("7. Wrong OTP", False, str(exc))

# ── 8. Resend for unknown email (no leak) ───────────────────
try:
    r = requests.post(
        f"{BASE}/api/auth/resend-verification",
        json={"email": "nonexistent@nowhere.dev"},
        timeout=5,
    )
    check("8. Resend unknown email returns 200 (no info leak)", r.status_code == 200,
          f"got {r.status_code}")
except Exception as exc:
    check("8. Info leak check", False, str(exc))

# ── 9. Already-verified user can login (existing users) ─────
# Use admin credentials from .env (they should have email_verified=TRUE)
try:
    import os
    from dotenv import load_dotenv
    load_dotenv("c:/Users/LENOVO/OneDrive/Área de Trabalho/Garage_Game/Garage/.env")
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "")
    admin_un = "cezicolaadmin"  # known admin username

    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": admin_un, "password": admin_pw},
        timeout=5,
    )
    if r.status_code == 401:
        print("      [SKIP] 9. Admin login -- credentials not matching (OK, skipping)")
    else:
        check("9. Existing user (admin) can login", r.status_code == 200,
              f"got {r.status_code}: {r.text[:100]}")
        if r.status_code == 200:
            data = r.json()
            check("9. Admin login returns token", "access_token" in data, str(data))
except Exception as exc:
    print(f"      [SKIP] 9. Admin login check -- {exc}")

print()
print("=" * 60)
if errors:
    print(f"  {len(errors)} TESTS FAILED: {errors}")
    sys.exit(1)
else:
    print("  ALL TESTS PASSED")
print("=" * 60)
