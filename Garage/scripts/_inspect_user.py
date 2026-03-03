"""Inspeciona o estado atual do usuário real para os testes de simulação."""
import httpx, os, json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

BASE = "http://127.0.0.1:8081"
TARGET_EMAIL = "homeopatiaenaturopatia@gmail.com"

# Admin login
r = httpx.post(f"{BASE}/api/auth/login", json={
    "username": os.environ.get("ADMIN_USERNAME", ""),
    "password": os.environ.get("ADMIN_PASSWORD", ""),
})
token = r.json()["access_token"]
hdrs = {"Authorization": f"Bearer {token}"}
print(f"Admin login: OK")

# Buscar usuário
r2 = httpx.get(f"{BASE}/api/admin/users?q=homeopatia", headers=hdrs, timeout=15)
data = r2.json()
users = data.get("users", data) if isinstance(data, dict) else data
users = [u for u in (users or []) if TARGET_EMAIL in u.get("email","")]

if not users:
    print(f"\nUsuário {TARGET_EMAIL} NÃO encontrado no banco.")
else:
    u = users[0]
    print(f"\n{'='*55}")
    print(f"  USUÁRIO REAL ENCONTRADO")
    print(f"{'='*55}")
    print(f"  ID:             {u['id']}")
    print(f"  username:       {u['username']}")
    print(f"  email:          {u['email']}")
    print(f"  email_verified: {u.get('email_verified')}")
    print(f"  created_at:     {u.get('created_at','?')[:10]}")
    user_id = u["id"]

    # Subscription
    r3 = httpx.get(f"{BASE}/api/account/me", headers=hdrs, timeout=10)
    # account/me usa o token do próprio usuário — pular, usar admin endpoint se existir
    # Tentar /api/admin/users/{id}/subscription se houver
    print(f"\n  Anotando user_id={user_id} para uso nos testes.")

print(f"\n{'='*55}")
print("Use este user_id no script de simulação.")
