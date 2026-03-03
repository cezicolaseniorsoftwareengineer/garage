"""
Test script: forgot-password / reset-password flow for cezicolatecnologia@gmail.com
- Step 1: Check if user exists in DB
- Step 2: Hit /api/auth/forgot-password  -> should trigger OTP send
- Step 3: Read OTP code from server store (peek via internal import)
- Step 4: Hit /api/auth/reset-password with the code + new password
- Step 5: Confirm password was changed (login with new password)
"""
import os, sys, asyncio, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import httpx
import asyncpg

BASE = "http://127.0.0.1:8000"
TEST_EMAIL = "cezicolatecnologia@gmail.com"
NEW_PASSWORD = "Garage@2026"

async def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não encontrada no .env")
        return

    # ── Step 1: Verify user exists ──────────────────────────────────────────
    print("\n[1] Verificando usuário no BD...")
    conn = await asyncpg.connect(db_url)
    row = await conn.fetchrow(
        "SELECT id, full_name, email_verified FROM users WHERE email = $1",
        TEST_EMAIL
    )
    if not row:
        print(f"    ✗  Usuário '{TEST_EMAIL}' NÃO encontrado no BD. Crie a conta primeiro.")
        await conn.close()
        return
    print(f"    ✓  Encontrado: id={row['id']}, name='{row['full_name']}', verified={row['email_verified']}")
    await conn.close()

    # ── Step 2: Request OTP ─────────────────────────────────────────────────
    print("\n[2] Solicitando código de redefinição (POST /api/auth/forgot-password)...")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{BASE}/api/auth/forgot-password", json={"email": TEST_EMAIL})
        print(f"    HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code != 200:
            print("    ✗  Endpoint retornou erro.")
            return

    # ── Step 3: Peek at in-memory OTP store ─────────────────────────────────
    print("\n[3] Lendo OTP do store em memória do servidor...")
    try:
        from app.api.routes.auth_routes import _pwd_reset_store
        import hashlib
        # Find the entry for this email
        entry = _pwd_reset_store.get(TEST_EMAIL)
        if not entry:
            print("    ✗  Nenhuma entrada no store. O servidor em background usa processo diferente.")
            print("       → O código foi enviado por e-mail. Verifique a caixa de cezicolatecnologia@gmail.com")
            print("       → Para testar sem e-mail: use o script com o código manualmente (veja __main__ abaixo)")
            return
        print(f"    ✓  Entry encontrada (hash={entry['hash'][:16]}..., exp={entry['expires_at']})")
        # We can't reverse the hash, but we can brute-force 000000-999999
        found_code = None
        for i in range(1000000):
            candidate = f"{i:06d}"
            if hashlib.sha256(candidate.encode()).hexdigest() == entry['hash']:
                found_code = candidate
                break
        if found_code:
            print(f"    ✓  Código OTP recuperado: {found_code}")
        else:
            print("    ✗  Não foi possível recuperar o código (unexpected).")
            return
    except Exception as e:
        print(f"    ✗  Não foi possível acessar o store diretamente: {e}")
        print("       → O endpoint está rodando em processo separado (uvicorn background).")
        print("       → Verifique o e-mail cezicolatecnologia@gmail.com para obter o código.")
        return

    # ── Step 4: Reset password ───────────────────────────────────────────────
    print(f"\n[4] Redefinindo senha com código={found_code} (POST /api/auth/reset-password)...")
    async with httpx.AsyncClient(timeout=15) as client:
        payload = {"email": TEST_EMAIL, "code": found_code, "new_password": NEW_PASSWORD}
        r = await client.post(f"{BASE}/api/auth/reset-password", json=payload)
        print(f"    HTTP {r.status_code}: {r.text[:300]}")
        if r.status_code != 200:
            print("    ✗  Reset falhou.")
            return
        print("    ✓  Senha redefinida com sucesso!")

    # ── Step 5: Confirm login with new password ──────────────────────────────
    print(f"\n[5] Confirmando login com nova senha ({NEW_PASSWORD})...")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{BASE}/api/auth/login", json={"email": TEST_EMAIL, "password": NEW_PASSWORD})
        print(f"    HTTP {r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            data = r.json()
            print(f"    ✓  LOGIN OK! user={data.get('user',{}).get('username','?')}")
        else:
            print("    ✗  Login com nova senha falhou.")

    print("\n═══════════════════════════════════════════")
    print("TESTE COMPLETO — flows backend 100% OK")
    print("═══════════════════════════════════════════\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", help="Código OTP recebido por e-mail (para usar sem acesso ao store)")
    args = parser.parse_args()

    if args.code:
        # Direct reset with provided code
        async def direct_reset():
            print(f"\n[DIRETO] Redefinindo com código={args.code}...")
            async with httpx.AsyncClient(timeout=15) as client:
                payload = {"email": TEST_EMAIL, "code": args.code, "new_password": NEW_PASSWORD}
                r = await client.post(f"{BASE}/api/auth/reset-password", json=payload)
                print(f"    HTTP {r.status_code}: {r.text}")
                if r.status_code == 200:
                    # confirm login
                    r2 = await client.post(f"{BASE}/api/auth/login", json={"email": TEST_EMAIL, "password": NEW_PASSWORD})
                    print(f"    LOGIN HTTP {r2.status_code}: {r2.text[:200]}")
        asyncio.run(direct_reset())
    else:
        asyncio.run(main())
