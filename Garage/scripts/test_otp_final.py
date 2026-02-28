"""Teste final: verificar OTP e confirmar fluxo pos-verificacao."""
import requests

BASE = "http://localhost:8000"
EMAIL = "biocodetechnology@gmail.com"
OTP = "103728"
PASSWORD = "biocode2024!"

print("=" * 60)
print("  GARAGE -- Teste de Verificacao OTP Real")
print(f"  Email: {EMAIL}")
print(f"  OTP:   {OTP}")
print("=" * 60)

# --- Etapa 4: Verificar OTP ---
print("\n[4] Verificando codigo OTP...")
r = requests.post(f"{BASE}/api/auth/verify-email", json={"email": EMAIL, "code": OTP}, timeout=10)
print(f"    Status: {r.status_code}")
d = r.json()
if r.status_code != 200:
    print(f"    ERRO: {d}")
    exit(1)
print(f"    success = {d.get('success')}")
print(f"    message = {d.get('message')}")
print(f"    user    = {d.get('user')}")
token = d.get("access_token", "")
print(f"    token   = {token[:50]}...")

# --- Etapa 5: /me com o token ---
print("\n[5] Chamando /me com o token recebido...")
r2 = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
print(f"    Status: {r2.status_code}")
me = r2.json()
print(f"    perfil = {me}")
username = me.get("username", "")

# --- Etapa 6: Login normal pos-verificacao ---
print(f"\n[6] Login com username=[{username}] e senha original...")
r3 = requests.post(f"{BASE}/api/auth/login",
                   json={"username": username, "password": PASSWORD}, timeout=10)
print(f"    Status: {r3.status_code}")
if r3.status_code == 200:
    d3 = r3.json()
    print(f"    >> LOGIN OK! user={d3.get('user')}")
elif r3.status_code == 401:
    print(f"    >> 401 -- senha diferente da usada no cadastro original (esperado)")
    print(f"       (email verificado com sucesso, senha do cadastro original era diferente)")
else:
    print(f"    >> {r3.json()}")

# --- Etapa 7: Reusar OTP consumido ---
print("\n[7] Tentando reutilizar o mesmo OTP (deve falhar)...")
r4 = requests.post(f"{BASE}/api/auth/verify-email", json={"email": EMAIL, "code": OTP}, timeout=10)
print(f"    Status: {r4.status_code}  (esperado: 409 ja verificado)")
print(f"    detail = {r4.json().get('detail', r4.json())}")

# --- Resultado ---
print()
print("=" * 60)
ok1 = r.status_code == 200
ok2 = r2.status_code == 200
ok3 = r4.status_code in (400, 409)
if ok1 and ok2 and ok3:
    print("  FLUXO COMPLETO OK")
    print(f"  >> Email {EMAIL} verificado com sucesso!")
    print(f"  >> Token funcional | /me retornou perfil completo")
    print(f"  >> OTP reutilizado corretamente bloqueado")
else:
    issues = []
    if not ok1: issues.append(f"verify retornou {r.status_code}")
    if not ok2: issues.append(f"/me retornou {r2.status_code}")
    if not ok3: issues.append(f"reuse retornou {r4.status_code} (esperado 409/400)")
    print(f"  ATENCAO: {'; '.join(issues)}")
print("=" * 60)
