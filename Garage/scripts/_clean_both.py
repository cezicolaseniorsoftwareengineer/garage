"""Remove BioCode and HomeoNat from all tables for clean re-registration."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import psycopg2

TARGETS = [
    ("biocodetechnology@gmail.com",      "BioCode"),
    ("homeopatiaenaturopatia@gmail.com", "HomeoNat"),
]

conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30)
cur = conn.cursor()

for email, uname in TARGETS:
    cur.execute("DELETE FROM pending_registrations WHERE email=%s OR username=%s", (email, uname))
    p = cur.rowcount
    cur.execute("DELETE FROM users WHERE email=%s OR username=%s", (email, uname))
    u = cur.rowcount
    print(f"{email}: pending={p} users={u} removidos")

conn.commit()
cur.close()
conn.close()
print("OK - ambos podem se cadastrar novamente")
