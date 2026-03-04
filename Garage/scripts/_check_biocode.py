import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("""
    SELECT id, username, email, subscription_status, subscription_plan,
           subscription_expires_at, email_verified, created_at
    FROM users
    WHERE username ILIKE '%bio%' OR email ILIKE '%bio%' OR username ILIKE '%cezar%'
    ORDER BY created_at DESC LIMIT 10
""")
rows = cur.fetchall()

if not rows:
    print("NENHUM usuário encontrado com 'bio' ou 'cezar'")
else:
    for r in rows:
        print(f"ID:       {r[0]}")
        print(f"Username: {r[1]}")
        print(f"Email:    {r[2]}")
        print(f"Sub status: {r[3]}")
        print(f"Plano:    {r[4]}")
        print(f"Expira:   {r[5]}")
        print(f"Email OK: {r[6]}")
        print(f"Criado:   {r[7]}")
        print("---")

# Busca últimos pagamentos/webhooks registrados
print("\n=== ÚLTIMAS ASSINATURAS ATIVADAS ===")
cur.execute("""
    SELECT id, username, email, subscription_status, subscription_plan, subscription_expires_at
    FROM users
    WHERE subscription_status = 'active'
    ORDER BY subscription_expires_at DESC LIMIT 5
""")
ativos = cur.fetchall()
for r in ativos:
    print(f"  {r[1]} ({r[2]}) - {r[3]} / {r[4]} / expira {r[5]}")

conn.close()
