"""Delete a user by email — cleanup script."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import psycopg2

EMAIL = "biocodetechnology@gmail.com"

url = os.environ["DATABASE_URL"]
conn = psycopg2.connect(url)
cur = conn.cursor()

cur.execute(
    "SELECT id, username, email, email_verified FROM users WHERE email = %s",
    (EMAIL,),
)
row = cur.fetchone()

if row:
    user_id, username, email, verified = row
    print(f"Encontrado: id={user_id}, username={username}, email={email}, verified={verified}")
    # Apaga em cascata usando savepoints para ignorar tabelas inexistentes
    for table in ("email_verifications", "user_metrics", "player_progress", "sessions", "game_events", "audit_logs", "players"):
        cur.execute("SAVEPOINT sp1")
        try:
            cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
            cur.execute("RELEASE SAVEPOINT sp1")
            print(f"  - {table}: OK")
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp1")
            print(f"  - {table}: ignorado ({e.__class__.__name__})")
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    print("✅ Usuário apagado com sucesso.")
else:
    print("⚠️  Usuário não encontrado.")

cur.close()
conn.close()
