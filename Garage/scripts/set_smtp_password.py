"""Apply a new SMTP_PASSWORD to .env and immediately send a test email.

Usage:
    python scripts/set_smtp_password.py NOVA_APP_PASSWORD
"""
import sys
import os
import re

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def update_env(new_password: str) -> None:
    content = open(ENV_PATH, encoding="utf-8").read()
    updated = re.sub(
        r"^SMTP_PASSWORD=.*$",
        f"SMTP_PASSWORD={new_password.strip()}",
        content,
        flags=re.MULTILINE,
    )
    if updated == content:
        print("AVISO: linha SMTP_PASSWORD nao encontrada. Adicionando ao final...")
        updated = content.rstrip() + f"\nSMTP_PASSWORD={new_password.strip()}\n"
    open(ENV_PATH, "w", encoding="utf-8").write(updated)
    print(f"✅  .env atualizado com nova senha SMTP.")


def test_send(password: str) -> bool:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # Reload env values
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    from_addr = os.environ.get("SMTP_FROM", user)
    to = user  # send test to self

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[GARAGE] Teste de email — funcionando!"
    msg["From"] = from_addr
    msg["To"] = to
    msg.attach(MIMEText(
        "Olá!\n\nEste é um email de teste do sistema Garage.\nSMTP configurado corretamente.\n\n— Bio Code Technology",
        "plain"
    ))
    msg.attach(MIMEText(
        """<!DOCTYPE html><html><body style="background:#0f172a;font-family:monospace;padding:40px;">
        <div style="max-width:480px;margin:0 auto;background:#1e293b;border-radius:12px;padding:32px;text-align:center;">
          <div style="color:#fbbf24;font-size:22px;font-weight:700;letter-spacing:4px;">[GARAGE]</div>
          <hr style="border-color:#334155;margin:20px 0;">
          <p style="color:#e2e8f0;font-size:15px;">✅&nbsp; SMTP configurado com sucesso!</p>
          <p style="color:#94a3b8;font-size:12px;">Bio Code Technology · Garage Game</p>
        </div></body></html>""",
        "html"
    ))

    print(f"\nConectando em {host}:{port} com usuario {user} ...")
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.sendmail(user, to, msg.as_string())
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/set_smtp_password.py NOVA_APP_PASSWORD")
        print("Exemplo: python scripts/set_smtp_password.py abcd efgh ijkl mnop")
        sys.exit(1)

    # Accept with or without spaces
    new_pwd = "".join(sys.argv[1:]).replace(" ", "")
    print(f"Senha recebida: {'*' * len(new_pwd)} ({len(new_pwd)} chars)")

    update_env(new_pwd)

    try:
        test_send(new_pwd)
        print("\n✅  Email de teste enviado com sucesso para biocodetechnology@gmail.com!")
        print("    Verifique a caixa de entrada.")
    except Exception as e:
        print(f"\n❌  Falha ao enviar: {e}")
        print("    Verifique se a App Password foi gerada corretamente em:")
        print("    https://myaccount.google.com/apppasswords")
        sys.exit(1)
