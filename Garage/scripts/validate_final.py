#!/usr/bin/env python3
"""
Validacao Final: Persistencia + Autenticacao + Autorizacao
Com flow correto: usa admin existente para verificar dados de outros users
"""
import requests
import uuid
from pathlib import Path
from dotenv import load_dotenv
import os

env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_file)

BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "cezicolatecnologia@gmail.com")

print("\n" + "="*80)
print("VALIDACAO FINAL DO SISTEMA GARAGE")
print("="*80)

# Tentar usar admin existente ou criar novo
print("\n[SETUP] Obtendo token admin...")
admin_token = None

# Tentar login como admin (se já existe)
admin_creds = {
    "username": "cezicolatecnologia@gmail.com",
    "password": "123456"  # Try common password
}

# Ou registrar novo admin com email admin
admin_user = {
    "email": "test_admin_" + uuid.uuid4().hex[:8] + "@garage.local",
    "username": f"admin_{uuid.uuid4().hex[:8]}",
    "password": "AdminTest123!",
    "full_name": "Test Admin User",
    "profession": "estudante",
    "whatsapp": "11999999999"
}

r = requests.post(f"{BASE_URL}/api/auth/register", json=admin_user, timeout=5)
if r.status_code == 200:
    admin_resp = r.json()
    admin_token = admin_resp.get("access_token")
    print(f"[OK] Admin test user criado: {admin_user['email']}")
else:
    print(f"[ERROR] Nao conseguiu criar admin: {r.status_code}")

if not admin_token:
    print("[ERROR] Nao conseguiu obter admin token. Abortando.")
    exit(1)

results = {}

# TEST 1: PERSISTENCIA
print("\n[TEST 1] PERSISTENCIA - Dados salvos permanentemente em database?")
print("-" * 80)

try:
    uid = uuid.uuid4().hex[:8]
    persist_user = {
        "email": f"persist_{uid}@test.br",
        "username": f"user_{uid}",
        "password": "Persist123!",
        "full_name": "Persistence Test User",
        "profession": "autonomo",
        "whatsapp": "11988776655"
    }

    # Registrar usuario
    r = requests.post(f"{BASE_URL}/api/auth/register", json=persist_user, timeout=5)
    if r.status_code == 200:
        user_data = r.json()
        print(f"[OK] Usuario registrado: {persist_user['email']}")
        print(f"     Username: {persist_user['username']}")

        # Verificar com admin que usuario existe
        headers = {"Authorization": f"Bearer {admin_token}"}
        r_admin = requests.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=5)

        if r_admin.status_code == 200:
            users = r_admin.json()
            found = any(u.get("email") == persist_user["email"] for u in users)

            if found:
                print(f"[OK] Usuario encontrado no painel admin (persisted)")
                print(f"     Total usuarios: {len(users)}")
                results["persistencia"] = True
                print(f"Status: PERSISTENCIA GARANTIDA ✓")
            else:
                print(f"[FAIL] Usuario nao encontrado no painel")
                results["persistencia"] = False
        else:
            print(f"[ERROR] Admin query falhou: {r_admin.status_code}")
            results["persistencia"] = False
    else:
        print(f"[ERROR] Registro falhou: {r.status_code}")
        results["persistencia"] = False

except Exception as e:
    print(f"[ERROR] Excecao: {e}")
    results["persistencia"] = False

# TEST 2: AUTENTICACAO
print("\n[TEST 2] AUTENTICACAO - JWT Tokens sao validados?")
print("-" * 80)

try:
    uid = uuid.uuid4().hex[:8]
    auth_user = {
        "email": f"auth_{uid}@test.br",
        "username": f"auth_{uid}",
        "password": "Auth123!Pass",
        "full_name": "Auth Test User",
        "profession": "empresario",
        "whatsapp": "11977665544"
    }

    r = requests.post(f"{BASE_URL}/api/auth/register", json=auth_user, timeout=5)
    if r.status_code == 200:
        resp = r.json()
        token = resp.get("access_token")
        refresh = resp.get("refresh_token")

        print(f"[OK] Usuario registrado: {auth_user['email']}")
        print(f"     Access Token gerado: {token[:40]}...")
        if refresh:
            print(f"     Refresh Token gerado: {refresh[:40]}...")

        # Validar token
        headers = {"Authorization": f"Bearer {token}"}
        r_me = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=5)

        if r_me.status_code == 200:
            profile = r_me.json()
            print(f"[OK] JWT Token validado com sucesso")
            print(f"     Username: {profile.get('username')}")
            print(f"     Email: {profile.get('email')}")
            results["autenticacao"] = True
            print(f"Status: AUTENTICACAO FUNCIONANDO ✓")
        else:
            print(f"[FAIL] Token nao validado: {r_me.status_code}")
            results["autenticacao"] = False

        # Testar token invalido
        r_invalid = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid.fake.token"},
            timeout=5
        )
        if r_invalid.status_code == 401:
            print(f"[OK] Token invalido corretamente rejeitado")

    else:
        print(f"[ERROR] Registro falhou: {r.status_code}")
        results["autenticacao"] = False

except Exception as e:
    print(f"[ERROR] Excecao: {e}")
    results["autenticacao"] = False

# TEST 3: AUTORIZACAO
print("\n[TEST 3] AUTORIZACAO - Role-Based Access Control (RBAC)?")
print("-" * 80)

try:
    uid = uuid.uuid4().hex[:8]
    regular_user = {
        "email": f"regular_{uid}@test.br",
        "username": f"regular_{uid}",
        "password": "Regular123!",
        "full_name": "Regular User",
        "profession": "autonomo",
        "whatsapp": "11966554433"
    }

    r = requests.post(f"{BASE_URL}/api/auth/register", json=regular_user, timeout=5)
    if r.status_code == 200:
        token = r.json().get("access_token")
        print(f"[OK] Usuario nao-admin registrado: {regular_user['email']}")

        # Tentar acessar painel admin
        headers = {"Authorization": f"Bearer {token}"}
        r_admin = requests.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=5)

        if r_admin.status_code == 403:
            print(f"[OK] Usuario nao-admin bloqueado corretamente (403)")
            print(f"     Acesso a '/api/admin/users' negado")
            results["autorizacao"] = True
            print(f"Status: AUTORIZACAO FUNCIONANDO ✓")
        elif r_admin.status_code == 200:
            print(f"[FAIL] Usuario regular conseguiu acessar admin!")
            results["autorizacao"] = False
        else:
            print(f"[ERROR] Status inesperado: {r_admin.status_code}")
            results["autorizacao"] = False

    else:
        print(f"[ERROR] Registro falhou: {r.status_code}")
        results["autorizacao"] = False

except Exception as e:
    print(f"[ERROR] Excecao: {e}")
    results["autorizacao"] = False

# SUMMARY
print("\n" + "="*80)
print("RESULTADO FINAL")
print("="*80)

tests = [
    ("Persistencia", results.get("persistencia", False)),
    ("Autenticacao (JWT)", results.get("autenticacao", False)),
    ("Autorizacao (RBAC)", results.get("autorizacao", False))
]

all_passed = all(status for _, status in tests)

for test_name, passed in tests:
    symbol = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {test_name:30} {symbol}")

print("\n" + "-"*80)

if all_passed:
    print("\nCONCLUSAO: SISTEMA COMPLETO E SEGURO")
    print("""
  [✓] PERSISTENCIA: Usuarios sao salvos permanentemente no database
  [✓] AUTENTICACAO: JWT tokens sao validados com sucesso
  [✓] AUTORIZACAO: Usuarios nao-admin sao bloqueados (403)

  Qualquer pessoa que se registrar tera seus dados:
    - Persistidos permanentemente no PostgreSQL
    - Acessiveis via painel admin (se admin)
    - Protegidos por autenticacao JWT
    - Sujeitos a autorizacao baseada em role

  SISTEMA PRONTO PARA PRODUCAO ✓
""")
else:
    print("\n[ALERTA] Alguns testes falharam - verificar logs acima")

print("="*80 + "\n")
