"""Teste de cadastro real com biocodetechnology@gmail.com."""
import requests
import sys
import time

BASE = "http://localhost:8000"

# --- Dados do teste ---
EMAIL = "biocodetechnology@gmail.com"
USERNAME = "biocode_cezi"
FULL_NAME = "CeziCola BioCode"
PASSWORD = "biocode2024!"

print("=" * 62)
print("  GARAGE -- Teste de Cadastro Real")
print(f"  Email: {EMAIL}")
print("=" * 62)

# --- 1. Tentar cadastro ---
print("\n[1] Tentando cadastrar...")
r = requests.post(f"{BASE}/api/auth/register", json={
    "full_name": FULL_NAME,
    "username": USERNAME,
    "email": EMAIL,
    "whatsapp": "11999999999",
    "profession": "empresario",
    "password": PASSWORD,
}, timeout=10)

print(f"    Status: {r.status_code}")
data = r.json()

if r.status_code == 409:
    print(f"    >> Ja cadastrado: {data.get('detail')}")
    print("\n[2] Tentando login com conta existente...")
    r2 = requests.post(f"{BASE}/api/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD,
    }, timeout=10)
    print(f"    Status: {r2.status_code}")
    d2 = r2.json()
    if r2.status_code == 200:
        print(f"    >> Login OK! token={d2.get('access_token','')[:40]}...")
        print(f"    >> user: {d2.get('user')}")
    elif r2.status_code == 403:
        print(f"    >> Conta existe mas email NAO verificado.")
        print(f"    >> Mensagem: {d2.get('detail')}")
        print(f"\n[3] Reenviando codigo de verificacao...")
        r3 = requests.post(f"{BASE}/api/auth/resend-verification", json={"email": EMAIL}, timeout=10)
        print(f"    Status: {r3.status_code}  |  {r3.json().get('message')}")
        print(f"\n    *** VERIFIQUE O CONSOLE DO SERVIDOR ***")
        print(f"    O codigo aparecera como:")
        print(f"    [GARAGE][EMAIL DEV] Verification code for {EMAIL}: XXXXXX")
    else:
        print(f"    >> Erro inesperado: {d2.get('detail')}")
    sys.exit(0)

if r.status_code != 200:
    print(f"    >> ERRO: {data.get('detail', data)}")
    sys.exit(1)

# --- Cadastro bem sucedido ---
print(f"    >> requires_verification = {data.get('requires_verification')}")
print(f"    >> email_hint = {data.get('email_hint')}")
print(f"    >> mensagem = {data.get('message')}")
print()
print("    *** VERIFIQUE O CONSOLE DO SERVIDOR para o codigo OTP ***")
print(f"    O codigo aparecera como:")
print(f"    [GARAGE][EMAIL DEV] Verification code for {EMAIL}: XXXXXX")
print()

# --- 2. Tentar login antes de verificar ---
print("[2] Tentando login SEM verificar (deve bloquear)...")
r2 = requests.post(f"{BASE}/api/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=10)
print(f"    Status: {r2.status_code}  (esperado: 403)")
if r2.status_code == 403:
    print(f"    >> Bloqueado corretamente: {r2.json().get('detail')[:80]}")
else:
    print(f"    >> ATENCAO: esperado 403, recebeu {r2.status_code}")

# --- 3. Solicitar codigo manualmente ---
print()
print("[3] Aguardando voce digitar o codigo OTP do console do servidor...")
code = input("    Digite o codigo de 6 digitos: ").strip()

if not code or len(code) != 6 or not code.isdigit():
    print("    Codigo invalido. Encerrando.")
    sys.exit(1)

# --- 4. Verificar OTP ---
print(f"\n[4] Enviando OTP {code} para verificacao...")
r4 = requests.post(f"{BASE}/api/auth/verify-email", json={"email": EMAIL, "code": code}, timeout=10)
print(f"    Status: {r4.status_code}")
d4 = r4.json()
if r4.status_code == 200:
    print(f"    >> VERIFICADO! {d4.get('message')}")
    print(f"    >> token={d4.get('access_token','')[:40]}...")
    print(f"    >> user={d4.get('user')}")
else:
    print(f"    >> Erro: {d4.get('detail')}")
    sys.exit(1)

# --- 5. Login pos-verificacao ---
print(f"\n[5] Login pos-verificacao...")
r5 = requests.post(f"{BASE}/api/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=10)
print(f"    Status: {r5.status_code}  (esperado: 200)")
if r5.status_code == 200:
    d5 = r5.json()
    print(f"    >> Login OK!")
    print(f"    >> user: {d5.get('user')}")
else:
    print(f"    >> Erro: {r5.json().get('detail')}")

print()
print("=" * 62)
print("  FLUXO COMPLETO OK")
print("=" * 62)
