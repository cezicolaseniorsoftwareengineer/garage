"""Quick DB diagnostic for pending_registrations table."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# 1. table existence
cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pending_registrations')")
exists = cur.fetchone()[0]
print(f"Table 'pending_registrations' exists: {exists}")

if exists:
    # 2. columns
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'pending_registrations' ORDER BY ordinal_position")
    cols = cur.fetchall()
    print("Columns:")
    for c in cols:
        print(f"  {c[0]:30s} {c[1]}")

    # 3. count
    cur.execute("SELECT COUNT(*) FROM pending_registrations")
    total = cur.fetchone()[0]
    print(f"\nTotal rows: {total}")

    # 4. sample
    cur.execute("SELECT id, username, email, created_at, expires_at FROM pending_registrations ORDER BY created_at DESC LIMIT 10")
    rows = cur.fetchall()
    if rows:
        print("\nMost recent 10 rows:")
        for r in rows:
            print(f"  id={r[0]}  user={r[1]}  email={r[2]}  created={r[3]}  expires={r[4]}")
    else:
        print("\nNo rows found (table is empty).")
else:
    print("Table does NOT exist — needs migration.")

cur.close()
conn.close()
print("\nDone.")
