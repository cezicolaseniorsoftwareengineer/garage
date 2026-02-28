"""Ensure the admin user exists in the DB with the correct password.

Reads ADMIN_USERNAME and ADMIN_PASSWORD from .env.
Creates the user if missing, or updates the password hash if already exists.
Always sets email_verified=True for the admin account.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import psycopg2
from app.infrastructure.auth.password import hash_password

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "cezar").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL", "cezicolatecnologia@gmail.com").strip()

if not ADMIN_PASSWORD:
    print("ERRO: ADMIN_PASSWORD nao configurado no .env")
    sys.exit(1)

pwd_hash = hash_password(ADMIN_PASSWORD)

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("SELECT id, username, email FROM users WHERE lower(username) = %s", (ADMIN_USERNAME.lower(),))
row = cur.fetchone()

if row:
    user_id = row[0]
    print(f"Encontrado: id={user_id}, username={row[1]}, email={row[2]}")
    cur.execute(
        "UPDATE users SET password_hash = %s, salt = 'bcrypt', email_verified = TRUE WHERE id = %s",
        (pwd_hash, user_id),
    )
    conn.commit()
    print(f"✅ Senha do admin '{row[1]}' atualizada com sucesso.")
else:
    user_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO users (id, full_name, username, email, whatsapp, profession,
                           password_hash, salt, email_verified, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'bcrypt', TRUE, NOW())
        """,
        (user_id, "Cezar Admin", ADMIN_USERNAME, ADMIN_EMAIL,
         "00000000000", "autonomo", pwd_hash),
    )
    conn.commit()
    print(f"✅ Usuário admin '{ADMIN_USERNAME}' criado com sucesso. id={user_id}")

cur.close()
conn.close()
