"""
Admin script: directly reset password in DB via app infrastructure.
Usage:  python scripts/_force_reset_pwd.py <email> <new_password>
"""
import os, sys

GARAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GARAGE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(GARAGE_DIR, ".env"))

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "cezicolatecnologia@gmail.com"
NEW_PWD = sys.argv[2] if len(sys.argv) > 2 else "Garage@2026"

from app.infrastructure.database.connection import init_engine, get_session_factory
from app.infrastructure.repositories.pg_user_repository import PgUserRepository
from app.infrastructure.auth.password import hash_password

print(f"[FORCE RESET] Conectando ao banco...")
init_engine()
sf = get_session_factory()
repo = PgUserRepository(sf)

print(f"[FORCE RESET] Buscando usuario: {EMAIL}")
user = repo.find_by_email(EMAIL)
if not user:
    print(f"[FORCE RESET] ERRO: usuario '{EMAIL}' nao encontrado.")
    sys.exit(1)

print(f"[FORCE RESET] Encontrado: id={user.id} name='{user.full_name}'")

new_hash = hash_password(NEW_PWD)
print(f"[FORCE RESET] Novo hash gerado: {new_hash[:30]}...")

repo.update_password(user.id, new_hash, "bcrypt")
print(f"[FORCE RESET] Senha atualizada com sucesso!")

# Verify: try to login via HTTP
import urllib.request, json as _json
try:
    body = _json.dumps({"email": EMAIL, "password": NEW_PWD}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/auth/login",
        data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = _json.loads(resp.read())
        uname = data.get("user", {}).get("username", "?")
        print(f"[FORCE RESET] LOGIN CONFIRMADO! username={uname}")
except Exception as e:
    print(f"[FORCE RESET] Aviso: login HTTP nao verificado ({e}). Senha foi salva no BD.")

print(f"\n{'='*50}")
print(f"  Email  : {EMAIL}")
print(f"  Senha  : {NEW_PWD}")
print(f"  Status : OK")
print(f"{'='*50}\n")
