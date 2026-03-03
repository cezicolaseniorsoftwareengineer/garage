"""Diagnóstico completo da tabela pending_registrations."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# 1. Table existence
cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='pending_registrations')")
exists = cur.fetchone()[0]
print(f"[1] Table 'pending_registrations' exists: {exists}")

if not exists:
    print("     => PROBLEMA: tabela nao existe. Precisa rodar migracao.")
    cur.close(); conn.close(); sys.exit(1)

# 2. Columns
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='pending_registrations' ORDER BY ordinal_position")
cols = cur.fetchall()
print("[2] Columns:")
for c in cols:
    print(f"     {c[0]:30s} {c[1]}")

# 3. Counts
cur.execute("SELECT COUNT(*) FROM pending_registrations")
total = cur.fetchone()[0]
print(f"[3] Total rows: {total}")

cur.execute("SELECT COUNT(*) FROM pending_registrations WHERE expires_at > NOW()")
active = cur.fetchone()[0]
print(f"[4] Active (not expired): {active}")

cur.execute("SELECT COUNT(*) FROM pending_registrations WHERE expires_at <= NOW()")
expired = cur.fetchone()[0]
print(f"[5] Expired: {expired}")

# 4. Sample
cur.execute("SELECT id, username, email, created_at, expires_at FROM pending_registrations ORDER BY created_at DESC LIMIT 10")
rows = cur.fetchall()
if rows:
    print(f"[6] Last {len(rows)} records:")
    for r in rows:
        print(f"     id={r[0][:8]}... user={r[1]}  email={r[2]}  created={str(r[3])[:16]}  expires={str(r[4])[:16]}")
else:
    print("[6] Table is EMPTY (nenhum pendente)")

# 5. Test the search() method via repo
print("\n[7] Testing PgPendingRepository.search() via app layer...")
try:
    from app.infrastructure.database.base import get_session_factory
    from app.infrastructure.repositories.pg_pending_repository import PgPendingRepository
    sf = get_session_factory(os.environ['DATABASE_URL'])
    repo = PgPendingRepository(sf)
    result = repo.search(q="", include_expired=True)
    print(f"     repo.search() returned {len(result)} items — OK")
    active_count = repo.count_active()
    print(f"     repo.count_active() = {active_count}")
except Exception as e:
    print(f"     ERRO no repo: {e}")

cur.close()
conn.close()
print("\n[OK] Diagnostico concluido.")
