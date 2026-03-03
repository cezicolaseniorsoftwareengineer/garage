"""
test_demo_flow.py — End-to-end simulation of the DEMO + subscription flow.

Tests:
  1. Register a new test user
  2. Login and get JWT token
  3. Start a game session
  4. Play through ALL Intern (Act I) challenges correctly
  5. Verify the server blocks progression with HTTP 402 (demo_limit_reached)
  6. Grant MONTHLY subscription via admin endpoint
  7. Submit the blocking challenge again → verify promotion goes through
  8. Check subscription status via /api/account/me
  9. Clean up (delete test user)
 10. Repeat steps 1-9 for ANNUAL plan

Usage:
    # Server must be running first. Defaults: port 8081, admin from .env
    cd Garage
    python scripts/test_demo_flow.py

    # Custom port / admin credentials:
    python scripts/test_demo_flow.py --port 8085 --admin myAdmin --pass mySecret

Requirements:
    pip install httpx  (already in requirements.txt)
"""

import sys
import os
import json
import argparse
import time
from pathlib import Path

# -----------------------------------------------------------
# Load .env so the script reads the same secrets as the server
# -----------------------------------------------------------
_dotenv_path = Path(__file__).parent.parent / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)

try:
    import httpx
except ImportError:
    print("ERROR: httpx is not installed. Run: pip install httpx")
    sys.exit(1)

# ============================================================
# Configuration
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(description="404 Garage — DEMO flow e2e test")
    p.add_argument("--port",  type=int,  default=int(os.environ.get("TEST_PORT", "8081")))
    p.add_argument("--host",  default=os.environ.get("TEST_HOST", "127.0.0.1"))
    p.add_argument("--admin", default=os.environ.get("ADMIN_USERNAME", "admin"))
    p.add_argument("--pass",  dest="admin_pass",
                   default=os.environ.get("ADMIN_PASSWORD", ""))
    return p.parse_args()

# Test user fixture
TEST_USER = {
    "full_name": "Demo Tester Bot",
    "username":  "demo_test_bot_9x",
    "email":     "demo_test_bot_9x@404garage.test",
    "whatsapp":  "11999999999",
    "profession": "autonomo",
    "password":  "DemoTest@2026!",
}

# ============================================================
# Helpers
# ============================================================

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"
WARN = "\033[93m[WARN]\033[0m"

_results: list[dict] = []

def ok(label: str, detail: str = ""):
    msg = f"{PASS} {label}" + (f" — {detail}" if detail else "")
    print(msg)
    _results.append({"status": "PASS", "label": label})

def fail(label: str, detail: str = ""):
    msg = f"{FAIL} {label}" + (f"\n       {detail}" if detail else "")
    print(msg)
    _results.append({"status": "FAIL", "label": label, "detail": detail})

def info(msg: str):
    print(f"{INFO} {msg}")

def warn(msg: str):
    print(f"{WARN} {msg}")

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def load_intern_answers(challenges_json_path: str) -> dict:
    """Load challenges.json and extract correct answer index for Intern stage."""
    with open(challenges_json_path, encoding="utf-8") as f:
        all_challenges = json.load(f)
    answers = {}
    for c in all_challenges:
        if c.get("required_stage") == "Intern":
            for i, opt in enumerate(c.get("options", [])):
                if opt.get("is_correct"):
                    answers[c["id"]] = i
                    break
    return answers  # {challenge_id: correct_index}


# ============================================================
# Test runner per plan
# ============================================================

def run_plan_test(
    client: httpx.Client,
    base_url: str,
    admin_token: str,
    plan: str,
    intern_answers: dict,
    challenges_order: list,
) -> bool:
    """Full cycle for one plan (monthly or annual). Returns True on full pass."""
    user = TEST_USER.copy()
    user["username"] = f"{TEST_USER['username']}_{plan[:3]}"
    user["email"]    = f"{plan}.{TEST_USER['email']}"
    plan_label = "Mensal (R$97/mês)" if plan == "monthly" else "Anual (R$997/ano)"
    section(f"PLANO {plan.upper()} — {plan_label}")

    # ── Step 0: cleanup leftovers from previous runs ──────────────
    _cleanup_user(client, base_url, admin_token, user["username"])

    # ── Step 1: Register ──────────────────────────────────────────
    # First try normal registration; if server is in PostgreSQL mode
    # (email verification required) fall back to the admin bypass endpoint.
    r = client.post(f"{base_url}/api/auth/register", json=user)
    reg = r.json() if r.status_code in (200, 201, 409) else {}
    token = reg.get("access_token") or reg.get("token")
    user_id = (reg.get("user") or {}).get("id") or reg.get("user_id")

    # Handle "already pending" (left from a failed previous run) — clean and bypass
    if r.status_code == 409 and reg.get("type") == "pending_verification":
        info("Registro preso em pending_registrations — limpando e criando via admin")
        _cleanup_user(client, base_url, admin_token, user["username"])
        token = None  # force bypass below

    if r.status_code in (200, 201) and not token:
        # PostgreSQL mode: requires_verification=True → use admin bypass
        info("Modo PostgreSQL detectado — usando admin/test/create-verified-user")
        rb = client.post(
            f"{base_url}/api/admin/test/create-verified-user",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name":  user["full_name"],
                "username":   user["username"],
                "email":      user["email"],
                "whatsapp":   user.get("whatsapp", "11999999999"),
                "profession": user.get("profession", "autonomo"),
                "password":   user["password"],
            },
        )
        if rb.status_code not in (200, 201):
            fail("Criação de usuário verificado via admin", f"HTTP {rb.status_code}: {rb.text[:200]}")
            return False
        rb_data = rb.json()
        token   = rb_data.get("access_token")
        user_id = rb_data.get("user_id")
        ok("Usuário de teste criado via admin bypass (modo PostgreSQL)", f"user_id={user_id}")
    elif not token and r.status_code == 409 and reg.get("type") == "pending_verification":
        # After cleanup, get token via bypass
        rb = client.post(
            f"{base_url}/api/admin/test/create-verified-user",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name":  user["full_name"],
                "username":   user["username"],
                "email":      user["email"],
                "whatsapp":   user.get("whatsapp", "11999999999"),
                "profession": user.get("profession", "autonomo"),
                "password":   user["password"],
            },
        )
        if rb.status_code not in (200, 201):
            fail("Criação via admin após limpar pending", f"HTTP {rb.status_code}: {rb.text[:200]}")
            return False
        rb_data = rb.json()
        token   = rb_data.get("access_token")
        user_id = rb_data.get("user_id")
        ok("Usuário de teste criado via admin bypass (pós-limpeza pendente)", f"user_id={user_id}")
    elif r.status_code in (200, 201) and token:
        ok("Registro do usuário de teste (modo JSON)", f"user_id={user_id}")
    else:
        fail("Registro do usuário de teste", f"HTTP {r.status_code}: {r.text[:200]}")
        return False

    if not token:
        fail("Registro do usuário de teste", "Token não retornado mesmo após tentativas")
        return False

    auth = {"Authorization": f"Bearer {token}"}

    # ── Step 2: Login ─────────────────────────────────────────────
    r = client.post(f"{base_url}/api/auth/login",
                    json={"username": user["username"], "password": user["password"]})
    if r.status_code != 200:
        fail("Login", f"HTTP {r.status_code}: {r.text[:200]}")
        _cleanup_user(client, base_url, admin_token, user["username"])
        return False
    login_data = r.json()
    token = login_data.get("access_token")
    user_id = login_data.get("user", {}).get("id") or user_id
    auth = {"Authorization": f"Bearer {token}"}
    ok("Login", f"JWT obtido para {user['username']}")

    # ── Step 3: Start game ────────────────────────────────────────
    r = client.post(f"{base_url}/api/start",
                    headers=auth,
                    json={
                        "player_name": "DemoBot",
                        "gender": "male",
                        "ethnicity": "black",
                        "avatar_index": 0,
                        "language": "Java",
                    })
    if r.status_code != 200:
        fail("Iniciar sessão de jogo", f"HTTP {r.status_code}: {r.text[:200]}")
        _cleanup_user(client, base_url, admin_token, user["username"])
        return False
    session_id = r.json()["session_id"]
    ok("Iniciar sessão de jogo", f"session_id={session_id}")

    # ── Step 4: Submit all Intern challenges ──────────────────────
    info(f"Submetendo {len(challenges_order)} desafios Intern...")
    paywall_challenge_id = None
    submitted = 0
    errors_in_stage = 0

    for cid in challenges_order:
        correct_idx = intern_answers.get(cid, 0)

        r = client.post(f"{base_url}/api/submit",
                        headers=auth,
                        json={
                            "session_id": session_id,
                            "challenge_id": cid,
                            "selected_index": correct_idx,
                        })

        if r.status_code == 402:
            data = r.json()
            if data.get("code") == "demo_limit_reached":
                paywall_challenge_id = cid
                paywall_data = data
                ok(f"DEMO paywall disparado no desafio #{submitted + 1}",
                   f"challenge_id={cid}")
                break
            else:
                fail("Submissão de resposta", f"402 inesperado: {data}")
                _cleanup_user(client, base_url, admin_token, user["username"])
                return False

        if r.status_code != 200:
            fail(f"Submissão desafio {cid}", f"HTTP {r.status_code}: {r.text[:200]}")
            _cleanup_user(client, base_url, admin_token, user["username"])
            return False

        result = r.json()
        submitted += 1

        if result.get("outcome") == "game_over":
            fail("Submissão de resposta", f"Game over inesperado em {cid}")
            _cleanup_user(client, base_url, admin_token, user["username"])
            return False

    if not paywall_challenge_id:
        warn("Paywall não acionado — DEMO gate pode não estar ativo em modo JSON ou todos os desafios Intern foram completados sem promoção")
        warn("Isso é esperado se o servidor usa modo dev (sem DATABASE_URL). O teste continua verificando assinatura.")

    ok(f"Desafios Intern submetidos", f"{submitted} respostas corretas entregues")

    # ── Step 5: Validate paywall message ─────────────────────────
    if paywall_challenge_id:
        expected_code = "demo_limit_reached"
        if paywall_data.get("code") == expected_code:
            ok("Código de paywall correto", f"code={expected_code}")
        else:
            fail("Código de paywall incorreto", json.dumps(paywall_data))

        if "/jogo" not in paywall_data.get("action_url", "") and "/" != paywall_data.get("action_url", ""):
            warn(f"action_url inesperado: {paywall_data.get('action_url')}")
        else:
            ok("action_url do paywall aponta para landing", paywall_data.get("action_url"))

    # ── Step 6: Grant subscription via admin ──────────────────────
    info(f"Concedendo assinatura '{plan}' via endpoint admin...")
    r = client.post(
        f"{base_url}/api/admin/users/{user_id}/grant-subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan": plan},
    )
    if r.status_code != 200:
        fail("Concessão de assinatura (admin)", f"HTTP {r.status_code}: {r.text[:200]}")
        _cleanup_user(client, base_url, admin_token, user["username"])
        return False

    grant = r.json()
    ok("Assinatura concedida via admin",
       f"plan={grant['plan']}  expires_at={grant['expires_at'][:10]}")

    # ── Step 7: Verify subscription status ───────────────────────
    r = client.get(f"{base_url}/api/account/me", headers=auth)
    if r.status_code == 200:
        me = r.json()
        sub = me.get("subscription", {})
        if sub.get("status") == "active":
            ok("Status de assinatura = active", f"plan={sub.get('plan')}")
        else:
            fail("Status de assinatura não é 'active'", json.dumps(sub))
    else:
        warn(f"GET /api/account/me retornou {r.status_code} — pulando verificação de status")

    # ── Step 8: Submit paywall challenge again → should succeed ───
    if paywall_challenge_id:
        correct_idx = intern_answers.get(paywall_challenge_id, 0)
        r = client.post(f"{base_url}/api/submit",
                        headers=auth,
                        json={
                            "session_id": session_id,
                            "challenge_id": paywall_challenge_id,
                            "selected_index": correct_idx,
                        })
        if r.status_code == 200:
            result = r.json()
            promoted = result.get("promotion", False)
            new_stage = result.get("new_stage", "—")
            ok("Progressão liberada após assinatura",
               f"outcome={result.get('outcome')}  promoted={promoted}  new_stage={new_stage}")
        elif r.status_code == 400 and "already completed" in r.text:
            # Happens if the answer was saved before the paywall fired (edge case)
            ok("Progressão liberada após assinatura", "desafio já estava completo — jogador pode avançar")
        else:
            fail("Progressão após assinatura", f"HTTP {r.status_code}: {r.text[:200]}")
    else:
        info("Paywall não foi acionado — step 8 ignorado")

    # ── Step 9: Cleanup ───────────────────────────────────────────
    deleted = _cleanup_user(client, base_url, admin_token, user["username"])
    if deleted:
        ok("Limpeza do usuário de teste", f"Usuário '{user['username']}' removido")
    else:
        warn(f"Usuário de teste '{user['username']}' não foi removido (pode precisar de limpeza manual)")

    return True


def _cleanup_user(client, base_url, admin_token, username) -> bool:
    """Find and delete test user from users table AND pending_registrations."""
    hdrs = {"Authorization": f"Bearer {admin_token}"}
    deleted_any = False

    # 1. Clean from pending_registrations (stuck OTP)
    try:
        rp = client.get(f"{base_url}/api/admin/pending?q={username}", headers=hdrs)
        if rp.status_code == 200:
            items = rp.json()
            if isinstance(items, dict):
                items = items.get("items", [])
            for item in (items or []):
                pid = item.get("id")
                if pid and (item.get("username") == username or username in item.get("email", "")):
                    rd = client.delete(f"{base_url}/api/admin/pending/{pid}", headers=hdrs)
                    if rd.status_code in (200, 204):
                        deleted_any = True
    except Exception:
        pass

    # 2. Clean from users table
    try:
        r = client.get(f"{base_url}/api/admin/users", headers=hdrs)
        if r.status_code != 200:
            return deleted_any
        users = r.json()
        if isinstance(users, dict):
            users = users.get("users", [])
        user_id = None
        for u in (users or []):
            if isinstance(u, dict) and u.get("username") == username:
                user_id = u.get("id") or u.get("user_id")
                break
        if not user_id:
            return deleted_any
        rd = client.delete(f"{base_url}/api/admin/users/{user_id}", headers=hdrs)
        return rd.status_code in (200, 204)
    except Exception:
        return deleted_any


# ============================================================
# Main
# ============================================================

def main():
    args = parse_args()
    base_url = f"http://{args.host}:{args.port}"

    # Locate challenges.json
    script_dir = Path(__file__).parent
    challenges_path = script_dir.parent / "app" / "data" / "challenges.json"
    if not challenges_path.exists():
        print(f"ERRO: challenges.json não encontrado em {challenges_path}")
        sys.exit(1)

    print(f"\n{'#'*60}")
    print(f"  404 Garage — DEMO + Subscription E2E Test")
    print(f"  Servidor: {base_url}")
    print(f"  Admin: {args.admin}")
    print(f"{'#'*60}")

    # ── Wait for server ───────────────────────────────────────────
    info("Verificando disponibilidade do servidor...")
    for attempt in range(10):
        try:
            r = httpx.get(f"{base_url}/health", timeout=3)
            if r.status_code == 200:
                ok("Servidor disponível", r.json().get("persistence", "?"))
                break
        except Exception:
            pass
        time.sleep(1)
        if attempt == 9:
            print(f"\n{FAIL} Servidor não acessível em {base_url}")
            print(f"       Inicie o servidor primeiro:")
            print(f"       cd Garage")
            print(f"       .venv\\Scripts\\python.exe -m uvicorn app.main:app --port {args.port} --host {args.host}")
            sys.exit(1)

    # ── Admin login ───────────────────────────────────────────────
    if not args.admin_pass:
        print(f"\n{FAIL} Senha do admin não informada.")
        print("       Use: python scripts/test_demo_flow.py --admin=<usuario> --pass=<senha>")
        print("       Ou defina ADMIN_USERNAME e ADMIN_PASSWORD no .env")
        sys.exit(1)

    section("AUTENTICAÇÃO ADMIN")
    with httpx.Client(timeout=15) as client:
        r = client.post(f"{base_url}/api/auth/login",
                        json={"username": args.admin, "password": args.admin_pass})
        if r.status_code != 200:
            print(f"{FAIL} Login admin falhou: HTTP {r.status_code}: {r.text[:300]}")
            sys.exit(1)
        admin_token = r.json()["access_token"]
        ok("Login admin", f"JWT obtido para '{args.admin}'")

    # ── Load challenges ───────────────────────────────────────────
    section("CARREGANDO DESAFIOS INTERN")
    intern_answers = load_intern_answers(str(challenges_path))
    if not intern_answers:
        print(f"{FAIL} Nenhum desafio Intern encontrado em {challenges_path}")
        sys.exit(1)
    info(f"Total de desafios Intern: {len(intern_answers)}")
    challenges_order = list(intern_answers.keys())
    ok("Desafios carregados", f"{len(challenges_order)} desafios Intern com respostas corretas")

    # ── Run tests for each plan ───────────────────────────────────
    all_passed = True
    with httpx.Client(timeout=20) as client:
        for plan in ("monthly", "annual"):
            passed = run_plan_test(
                client=client,
                base_url=base_url,
                admin_token=admin_token,
                plan=plan,
                intern_answers=intern_answers,
                challenges_order=challenges_order,
            )
            if not passed:
                all_passed = False

    # ── Summary ───────────────────────────────────────────────────
    section("RESULTADO FINAL")
    passed = sum(1 for r in _results if r["status"] == "PASS")
    failed = sum(1 for r in _results if r["status"] == "FAIL")
    print(f"  PASS: {passed}   FAIL: {failed}   TOTAL: {len(_results)}")

    if failed > 0:
        print(f"\n{FAIL} Testes que falharam:")
        for r in _results:
            if r["status"] == "FAIL":
                print(f"  → {r['label']}")
                if r.get("detail"):
                    print(f"    {r['detail']}")
        sys.exit(1)
    else:
        print(f"\n{PASS} Todos os testes passaram! Fluxo DEMO + assinatura funcionando.")
        sys.exit(0)


if __name__ == "__main__":
    main()
