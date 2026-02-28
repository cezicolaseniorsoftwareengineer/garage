import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute(
    "SELECT id, username, email, email_verified FROM users WHERE lower(username) = %s OR lower(email) = %s",
    ("drcezar", "biocodetechnology@gmail.com"),
)
rows = cur.fetchall()
for r in rows:
    print(f"id={r[0]}  username={r[1]}  email={r[2]}  verified={r[3]}")
if not rows:
    print("Nenhum registro encontrado — username e email livres.")

cur.close()
conn.close()
