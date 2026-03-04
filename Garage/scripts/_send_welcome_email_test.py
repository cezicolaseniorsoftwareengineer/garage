#!/usr/bin/env python3
"""Send welcome email to biocode for validation."""
import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Load env
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

# HTML Template (same as in email_sender.py)
def html_template_welcome(full_name: str, plan: str, expires_at: str) -> str:
    plan_label = "Anual · R$ 997/ano · 365 dias" if plan == "annual" else "Mensal · R$ 97/mês · 30 dias"
    game_url = "https://garage-0lw9.onrender.com/jogo"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:'Courier New',monospace;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="480" style="background:#1e293b;border:1px solid #22c55e;border-radius:12px;">
        <tr>
          <td style="padding:32px 40px;text-align:center;">
            <div style="color:#fbbf24;font-size:22px;font-weight:700;letter-spacing:4px;margin-bottom:4px;">[404 GARAGE]</div>
            <div style="color:#94a3b8;font-size:11px;letter-spacing:2px;">BIO CODE TECHNOLOGY</div>
            <hr style="border:none;border-top:1px solid #334155;margin:24px 0;">
            <p style="color:#e2e8f0;font-size:16px;margin:0 0 8px;">Olá, <strong>{full_name}</strong>.</p>
            <p style="color:#94a3b8;font-size:13px;margin:0 0 20px;line-height:1.7;">
              Sua assinatura foi ativada com sucesso.<br>
              Acesso completo a todos os 6 Atos desbloqueado.
            </p>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px 24px;margin:0 auto 24px;text-align:left;">
              <div style="color:#22c55e;font-size:10px;letter-spacing:2px;margin-bottom:8px;">PLANO ATIVO</div>
              <div style="color:#e2e8f0;font-size:15px;font-weight:700;">{plan_label}</div>
              <div style="color:#64748b;font-size:11px;margin-top:6px;">Acesso até: {expires_at}</div>
            </div>
            <a href="{game_url}" style="display:block;background:#22c55e;color:#0a0a0f;padding:14px 32px;border-radius:8px;font-weight:700;font-size:0.95rem;text-decoration:none;letter-spacing:1px;">
              ENTRAR NO JOGO
            </a>
          </td>
        </tr>
        <tr>
          <td style="background:#0f172a;padding:16px;text-align:center;border-radius:0 0 12px 12px;">
            <span style="color:#475569;font-size:10px;letter-spacing:1px;">
              404 GARAGE · DE ESTAGIÁRIO A PRINCIPAL ENGINEER · BIO CODE TECHNOLOGY
            </span>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

# Configuration
TO_EMAIL = "biocodetechnology@gmail.com"
FULL_NAME = "Bio Code"
PLAN = "annual"
EXPIRES_AT = "04/03/2027"

print(f"\n{'='*60}")
print(f"ENVIANDO EMAIL DE BOAS-VINDAS")
print(f"{'='*60}")
print(f"Para:       {TO_EMAIL}")
print(f"Nome:       {FULL_NAME}")
print(f"Plano:      {PLAN.upper()}")
print(f"Acesso até: {EXPIRES_AT}")
print(f"{'='*60}\n")

# Get email config
smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
smtp_port = int(os.environ.get("SMTP_PORT", "587"))
smtp_user = os.environ.get("SMTP_USER", "")
smtp_password = os.environ.get("SMTP_PASSWORD", "")
smtp_from = os.environ.get("SMTP_FROM", smtp_user)

if not smtp_user or not smtp_password:
    print("❌ ERRO: SMTP_USER ou SMTP_PASSWORD não configurados em .env")
    sys.exit(1)

try:
    # Prepare email
    subject = "Acesso ativado - 404 Garage"
    html_body = html_template_welcome(FULL_NAME, PLAN, EXPIRES_AT)
    plain_body = (
        f"Olá {FULL_NAME},\n\n"
        f"Sua assinatura no 404 Garage foi ativada.\n\n"
        f"Plano: {'Anual (365 dias)' if PLAN == 'annual' else 'Mensal (30 dias)'}\n"
        f"Acesso até: {EXPIRES_AT}\n\n"
        f"Entrar no jogo: https://garage-0lw9.onrender.com/jogo\n\n"
        f"404 Garage - De Estagiário a Principal Engineer\n"
        f"Bio Code Technology"
    )

    # Send via SMTP
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    print(f"📧 Conectando ao SMTP ({smtp_host}:{smtp_port})...")
    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, TO_EMAIL, msg.as_string())

    print(f"✅ EMAIL ENVIADO COM SUCESSO!\n")

except Exception as exc:
    print(f"❌ ERRO AO ENVIAR: {exc}\n")
    sys.exit(1)

print(f"{'='*60}")
print(f"URLS NO EMAIL:")
print(f"{'='*60}")
print(f"▶ Jogo:  https://garage-0lw9.onrender.com/jogo")
print(f"▶ Conta: https://garage-0lw9.onrender.com/account")
print(f"{'='*60}\n")
