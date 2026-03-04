import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import psycopg2
from datetime import datetime, timezone, timedelta

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

uid = "ea30c1ed-d758-4bac-9099-b54e016d21ad"
expires = datetime.now(timezone.utc) + timedelta(days=31)

cur.execute("""
    UPDATE users
    SET subscription_status = 'active',
        subscription_plan = 'monthly',
        subscription_expires_at = %s
    WHERE id = %s
""", (expires, uid))

conn.commit()
print(f"Assinatura ativada para user {uid}")
print(f"Expira em: {expires.isoformat()}")

# Confirma
cur.execute("SELECT username, email, subscription_status, subscription_plan, subscription_expires_at FROM users WHERE id = %s", (uid,))
r = cur.fetchone()
print(f"\nStatus atual no banco:")
print(f"  username: {r[0]}")
print(f"  email:    {r[1]}")
print(f"  status:   {r[2]}")
print(f"  plano:    {r[3]}")
print(f"  expira:   {r[4]}")

conn.close()
