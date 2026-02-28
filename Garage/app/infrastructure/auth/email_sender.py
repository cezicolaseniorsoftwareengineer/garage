"""SMTP email sender for verification codes.

Reads credentials from environment variables:
  SMTP_HOST       (default: smtp.gmail.com)
  SMTP_PORT       (default: 587)
  SMTP_USER       Gmail address used to send
  SMTP_PASSWORD   Gmail App Password (16-char, no spaces)
  SMTP_FROM       Display name <email> (optional)

If SMTP_USER is not set, emails are printed to stdout (dev mode).
"""
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger("garage.email")


def _smtp_config() -> dict:
    """Read SMTP credentials fresh from env on every call (supports hot-reload)."""
    return {
        "host":     os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port":     int(os.environ.get("SMTP_PORT", "587")),
        "user":     os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from":     os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }


def _html_template(full_name: str, code: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:'Courier New',monospace;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="480" style="background:#1e293b;border:1px solid #334155;border-radius:12px;">
        <tr>
          <td style="padding:32px 40px;text-align:center;">
            <div style="color:#fbbf24;font-size:24px;font-weight:700;letter-spacing:4px;">[GARAGE]</div>
            <div style="color:#94a3b8;font-size:11px;margin-top:4px;letter-spacing:2px;">BIO CODE TECHNOLOGY</div>
            <hr style="border:none;border-top:1px solid #334155;margin:24px 0;">
            <p style="color:#e2e8f0;font-size:15px;margin:0 0 8px;">Olá, <strong>{full_name}</strong>!</p>
            <p style="color:#94a3b8;font-size:13px;margin:0 0 28px;">
              Para confirmar seu e-mail e entrar no Vale do Silício,<br>
              use o código abaixo. Ele expira em <strong style="color:#fbbf24;">30 minutos</strong>.
            </p>
            <div style="background:#0f172a;border:2px solid #fbbf24;border-radius:8px;padding:20px 0;margin:0 auto 28px;">
              <span style="color:#fbbf24;font-size:38px;font-weight:700;letter-spacing:12px;">{code}</span>
            </div>
            <p style="color:#64748b;font-size:11px;margin:0;">
              Se você não se cadastrou no Garage, ignore este e-mail.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#0f172a;padding:16px;text-align:center;border-radius:0 0 12px 12px;">
            <span style="color:#475569;font-size:10px;letter-spacing:1px;">
              GARAGE · DE ESTAGIÁRIO A PRINCIPAL ENGINEER · BIO CODE TECHNOLOGY
            </span>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_verification_email(to_email: str, code: str, full_name: str) -> None:
    """Send a 6-digit OTP verification code to the given address.

    Falls back to console print (dev mode) when SMTP is not configured
    or when the SMTP connection fails.
    """
    cfg = _smtp_config()

    if not cfg["user"]:
        # Dev mode: no SMTP configured
        log.info("[DEV MODE] Verification code for %s: %s", to_email, code)
        print(f"[GARAGE][EMAIL DEV] Verification code for {to_email}: {code}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{code}] Confirme seu e-mail — Garage"
    msg["From"] = cfg["from"] or cfg["user"]
    msg["To"] = to_email

    plain = (
        f"Olá {full_name},\n\n"
        f"Seu código de verificação do Garage é: {code}\n\n"
        f"Ele expira em 30 minutos. Se não foi você, ignore este e-mail.\n\n"
        f"— Bio Code Technology"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_html_template(full_name, code), "html"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], to_email, msg.as_string())
        log.info("Verification email sent to %s", to_email)
    except Exception as exc:
        log.error("Failed to send verification email to %s: %s", to_email, exc)
        # Fallback to console so the code is never lost during development
        print(f"[GARAGE][EMAIL FALLBACK] SMTP failed. Code for {to_email}: {code}")
        print(f"[GARAGE][EMAIL FALLBACK] Error: {exc}")
        # Do NOT raise — caller decides whether to abort or continue
