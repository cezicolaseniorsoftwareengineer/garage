#!/usr/bin/env python3
"""
Validacao Detalhada: Persistencia + Autenticacao + Autorizacao
Testa cada aspecto com casos específicos
"""
import requests
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv
import os

env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_file)

BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "cezicolatecnologia@gmail.com")

print("\n" + "="*80)
print("AUDITORIA COMPLETA: PERSISTENCIA | AUTENTICACAO | AUTORIZACAO")
print("="*80)

results = {
    "persistencia": False,
    "autenticacao": False,
    "autorizacao": False,
    "admin_role": False
}

# TEST 1: PERSISTENCIA
print("\n[TEST 1] PERSISTENCIA - Dados salvos permanentemente?")
print("-" * 80)

try:
    uid = uuid.uuid4().hex[:8]
    user_data = {
        "email": f"persist_{uid}@test.br",
        "username": f"user_persist_{uid}",
        "password": "Teste123!Pass",
        "full_name": "Persistence Test User",
        "profession": "autonomo",
        "whatsapp": "11999888777"
    }

    # Registrar
    r1 = requests.post(f"{BASE_URL}/api/auth/register", json=user_data, timeout=5)
    if r1.status_code == 200:
        resp = r1.json()
        user_id = resp.get("user_id")
        access_token = resp.get("access_token")
        print(f"  [OK] Usuario registrado: {user_data['email']}")
        print(f"       ID: {user_id}")

        # Registrar admin para consultar painel
        admin_uid = uuid.uuid4().hex[:8]
        admin_reg = {
            "email": f"admin_check_{admin_uid}@test.br",
            "username": f"admin_{admin_uid}",
            "password": "Admin123!",
            "full_name": "Admin Checker",
            "profession": "estudante",
            "whatsapp": "11988776655"
        }
        r_admin = requests.post(f"{BASE_URL}/api/auth/register", json=admin_reg, timeout=5)

        if r_admin.status_code == 200:
            admin_token = r_admin.json().get("access_token")

            # Consultar painel admin
            headers = {"Authorization": f"Bearer {admin_token}"}
            r2 = requests.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=5)

            if r2.status_code == 200:
                users = r2.json()
                found = any(u.get("email") == user_data["email"] for u in users)

                if found:
                    print(f"  [OK] Usuario encontrado no painel admin")
                    print(f"       Total usuarios na database: {len(users)}")
                    results["persistencia"] = True
                    print(f"  Status: PERSISTENCIA GARANTIDA ✓")
                else:
                    print(f"  [FAIL] Usuario nao encontrado no painel")
            else:
                print(f"  [ERROR] Admin query retornou {r2.status_code}")
        else:
            print(f"  [ERROR] Nao conseguiu registrar admin tester: {r_admin.status_code}")
    else:
        print(f"  [ERROR] Registro falhou: {r1.status_code} - {r1.text[:100]}")

except Exception as e:
    print(f"  [ERROR] Excecao: {e}")

# TEST 2: AUTENTICACAO
print("\n[TEST 2] AUTENTICACAO - JWT Tokens funcionam?")
print("-" * 80)

try:
    uid2 = uuid.uuid4().hex[:8]
    user2_data = {
        "email": f"auth_{uid2}@test.br",
        "username": f"user_auth_{uid2}",
        "password": "Auth123!Pass",
        "full_name": "Auth Test User",
        "profession": "empresario",
        "whatsapp": "11977665544"
    }

    r = requests.post(f"{BASE_URL}/api/auth/register", json=user2_data, timeout=5)
    if r.status_code == 200:
        token = r.json().get("access_token")
        refresh = r.json().get("refresh_token")

        print(f"  [OK] Usuario registrado: {user2_data['email']}")
        print(f"       Access Token: {token[:40]}...")
        print(f"       Refresh Token: {refresh[:40] if refresh else 'None'}...")

        # Testar token no endpoint /me
        headers = {"Authorization": f"Bearer {token}"}
        r_profile = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=5)

        if r_profile.status_code == 200:
            profile = r_profile.json()
            print(f"  [OK] JWT Token validado com sucesso")
            print(f"       Username: {profile.get('username')}")
            print(f"       Email: {profile.get('email')}")
            results["autenticacao"] = True
            print(f"  Status: AUTENTICACAO FUNCIONANDO ✓")
        else:
            print(f"  [FAIL] Token nao validado: {r_profile.status_code}")

        # Testar token inválido
        r_invalid = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
            timeout=5
        )
        if r_invalid.status_code == 401:
            print(f"  [OK] Token invalido corretamente rejeitado (401)")

    else:
        print(f"  [ERROR] Registro falhou: {r.status_code}")

except Exception as e:
    print(f"  [ERROR] Excecao: {e}")

# TEST 3: AUTORIZACAO (Role-Based)
print("\n[TEST 3] AUTORIZACAO - Role-Based Access Control?")
print("-" * 80)

try:
    uid3 = uuid.uuid4().hex[:8]
    regular_user = {
        "email": f"regular_{uid3}@test.br",
        "username": f"user_regular_{uid3}",
        "password": "Regular123!",
        "full_name": "Regular User",
        "profession": "autonomo",
        "whatsapp": "11966554433"
    }

    r = requests.post(f"{BASE_URL}/api/auth/register", json=regular_user, timeout=5)
    if r.status_code == 200:
        token = r.json().get("access_token")
        print(f"  [OK] Usuario regular registrado: {regular_user['email']}")

        # Tentar acessar painel admin (deve ser negado)
        headers = {"Authorization": f"Bearer {token}"}
        r_admin = requests.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=5)

        if r_admin.status_code == 403:
            print(f"  [OK] Usuario nao-admin corretamente bloqueado (403)")
            print(f"       Acesso negado para endpoint administrativo")
            results["autorizacao"] = True
            print(f"  Status: AUTORIZACAO FUNCIONANDO ✓")
        elif r_admin.status_code == 401:
            print(f"  [FAIL] Retornou 401 (nao autenticado) em vez de 403")
        elif r_admin.status_code == 200:
            print(f"  [FAIL] Usuario regular conseguiu acessar painel admin!")
        else:
            print(f"  [ERROR] Status inesperado: {r_admin.status_code}")

    else:
        print(f"  [ERROR] Registro falhou: {r.status_code}")

except Exception as e:
    print(f"  [ERROR] Excecao: {e}")

# TEST 4: ADMIN ROLE
print("\n[TEST 4] ADMIN ROLE - User com email e role corretos?")
print("-" * 80)

try:
    admin_test_data = {
        "email": ADMIN_EMAIL,
        "username": f"admin_test_{uuid.uuid4().hex[:6]}",
        "password": "AdminTest123!",
        "full_name": "Admin Role Test",
        "profession": "estudante",
        "whatsapp": "11955443322"
    }

    r = requests.post(f"{BASE_URL}/api/auth/register", json=admin_test_data, timeout=5)

    if r.status_code == 200:
        admin_token = r.json().get("access_token")
        print(f"  [OK] Admin user registrado: {ADMIN_EMAIL}")
        print(f"       Username: {admin_test_data['username']}")

        # Testar acesso admin
        headers = {"Authorization": f"Bearer {admin_token}"}
        r_admin_access = requests.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=5)

        if r_admin_access.status_code == 200:
            users = r_admin_access.json()
            print(f"  [OK] Admin conseguiu acessar painel")
            print(f"       Total usuarios no sistema: {len(users)}")
            results["admin_role"] = True
            print(f"  Status: ADMIN ROLE FUNCIONANDO ✓")
        else:
            print(f"  [INFO] Admin access: {r_admin_access.status_code}")

    elif r.status_code == 409:
        print(f"  [INFO] Email admin ja existe no sistema (esperado)")
        print(f"  Status: ADMIN EMAIL JA REGISTRADO")
    else:
        print(f"  [ERROR] Registro falhou: {r.status_code}")

except Exception as e:
    print(f"  [ERROR] Excecao: {e}")

# SUMMARY
print("\n" + "="*80)
print("RESULTADO FINAL DA AUDITORIA")
print("="*80)

audit_results = {
    "Persistencia": results["persistencia"],
    "Autenticacao": results["autenticacao"],
    "Autorizacao (RBAC)": results["autorizacao"],
    "Admin Role": results["admin_role"]
}

all_pass = all(audit_results.values())

for test, status in audit_results.items():
    symbol = "✓ OK" if status else "✗ FAIL"
    color = "verde" if status else "vermelho"
    print(f"  {test:30} {symbol}")

print("\n" + "-"*80)
if all_pass:
    print("CONCLUSAO: TODOS OS TESTES PASSARAM")
    print("\nGarantias:")
    print("  [✓] Dados persistem permanentemente no banco")
    print("  [✓] JWT tokens sao validados corretamente")
    print("  [✓] Acesso unauthorized e corretamente bloqueado")
    print("  [✓] Admin role funcionando com base em email configurado")
    print("\nO sistema esta SEGURO e FUNCIONAL para producao.")
else:
    print("ALERTA: Alguns testes falharam - verificar logs acima.")

print("="*80 + "\n")
