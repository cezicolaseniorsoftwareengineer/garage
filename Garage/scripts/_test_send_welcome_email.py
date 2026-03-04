"""Test direct welcome email sending to biocode."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.infrastructure.auth.email_sender import send_subscription_welcome_email
from datetime import datetime, timedelta

TARGET_EMAIL = "biocodetechnology@gmail.com"
FULL_NAME = "Bio Code"
PLAN = "annual"  # or "monthly"
EXPIRES_AT = (datetime.now() + timedelta(days=365)).strftime("%d/%m/%Y")

print(f"[TEST] Enviando e-mail de boas-vindas...")
print(f"  to_email: {TARGET_EMAIL}")
print(f"  full_name: {FULL_NAME}")
print(f"  plan: {PLAN}")
print(f"  expires_at: {EXPIRES_AT}")

# Check env vars
resend_key = os.environ.get("RESEND_API_KEY", "")
smtp_user = os.environ.get("SMTP_USER", "")
print(f"\n[CONFIG]")
print(f"  RESEND_API_KEY: {'SET' if resend_key else 'NOT SET'} ({resend_key[:15]}... {len(resend_key)} chars)")
print(f"  SMTP_USER: {smtp_user or 'NOT SET'}")

try:
    result = send_subscription_welcome_email(
        to_email=TARGET_EMAIL,
        full_name=FULL_NAME,
        plan=PLAN,
        expires_at=EXPIRES_AT,
    )

    if result:
        print("\n[OK] E-mail enviado via Resend ou SMTP")
    else:
        print("\n[WARN] E-mail impresso no console (dev mode)")

    print("\nVerifique:")
    print("1. Caixa de entrada do biocodetechnology@gmail.com")
    print("2. Pasta de SPAM")
    print("3. Console/logs do servidor")

except Exception as exc:
    print(f"\n[ERRO] {type(exc).__name__}: {exc}")
    import traceback
    traceback.print_exc()
