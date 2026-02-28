"""Teste direto de envio de email via SMTP."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

from app.infrastructure.auth.email_sender import send_verification_email

print("Testando envio real de email...")
print(f"SMTP_USER     = {os.environ.get('SMTP_USER')}")
print(f"SMTP_HOST     = {os.environ.get('SMTP_HOST')}")
print(f"SMTP_PORT     = {os.environ.get('SMTP_PORT')}")
print(f"SMTP_PASSWORD = {'***configurado***' if os.environ.get('SMTP_PASSWORD') else 'VAZIO'}")
print()

try:
    send_verification_email(
        to_email="biocodetechnology@gmail.com",
        code="123456",
        full_name="CeziCola"
    )
    print("EMAIL ENVIADO COM SUCESSO!")
    print("Verifique a caixa de entrada de biocodetechnology@gmail.com")
except Exception as exc:
    print(f"ERRO: {exc}")
