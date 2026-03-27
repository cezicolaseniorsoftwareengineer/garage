"""Email sender for OTP verification codes.

Priority chain:
  1. Resend API   (RESEND_API_KEY set)  — transactional, SPF/DKIM verified, no spam
  2. SMTP         (SMTP_USER set)       — Gmail fallback, may land in spam
  3. Dev console  (nothing set)         — prints code to server log

Environment variables:
  RESEND_API_KEY   Resend API key (re_xxxx)
  RESEND_FROM      From address  (default: Garage <onboarding@resend.dev>)
  SMTP_HOST        default: smtp.gmail.com
  SMTP_PORT        default: 587
  SMTP_USER        Gmail address
  SMTP_PASSWORD    Gmail App Password (16-char, no spaces)
  SMTP_FROM        Display name <email> (optional)
"""
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger("garage.email")


# ---------------------------------------------------------------------------
# HTML template (shared by all providers)
# ---------------------------------------------------------------------------
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


def _plain_text(full_name: str, code: str) -> str:
    return (
        f"Olá {full_name},\n\n"
        f"Seu código de verificação do Garage é: {code}\n\n"
        f"Ele expira em 30 minutos. Se não foi você, ignore este e-mail.\n\n"
        f"— Bio Code Technology"
    )


# ---------------------------------------------------------------------------
# Provider 1: Resend  (primary — SPF/DKIM verified, anti-spam)
# ---------------------------------------------------------------------------
def _send_via_resend(to_email: str, code: str, full_name: str) -> bool:
    """Send using Resend API. Returns True on success, raises on failure."""
    import resend  # lazy import — not required in test environments

    resend.api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("RESEND_FROM", "Garage <onboarding@resend.dev>")

    params: resend.Emails.SendParams = {
        "from": from_addr,
        "to": [to_email],
        "subject": f"[{code}] Confirme seu e-mail — Garage",
        "html": _html_template(full_name, code),
        "text": _plain_text(full_name, code),
    }
    result = resend.Emails.send(params)
    email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
    log.info("[RESEND OK] id=%s to=%s", email_id, to_email)
    print(f"[GARAGE][RESEND OK] Sent to {to_email} | id={email_id}")
    return True


# ---------------------------------------------------------------------------
# Provider 2: SMTP  (fallback — Gmail)
# ---------------------------------------------------------------------------
def _send_via_smtp(to_email: str, code: str, full_name: str) -> bool:
    """Send via SMTP with 2 retries. Returns True on success, raises on failure."""
    cfg = {
        "host":     os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port":     int(os.environ.get("SMTP_PORT", "587")),
        "user":     os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from":     os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{code}] Confirme seu e-mail — Garage"
    msg["From"] = cfg["from"] or cfg["user"]
    msg["To"] = to_email
    msg.attach(MIMEText(_plain_text(full_name, code), "plain"))
    msg.attach(MIMEText(_html_template(full_name, code), "html"))

    last_exc = None
    for attempt in range(2):
        if attempt > 0:
            log.warning("[SMTP] retry %d/2 for %s", attempt + 1, to_email)
        try:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
                server.ehlo(); server.starttls(); server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["user"], to_email, msg.as_string())
            log.info("[SMTP OK] attempt=%d to=%s", attempt + 1, to_email)
            print(f"[GARAGE][SMTP OK] Sent to {to_email} (attempt {attempt + 1})")
            return True
        except smtplib.SMTPAuthenticationError as exc:
            log.error("[SMTP AUTH FAIL] user=%s: %s", cfg["user"], exc)
            raise  # no point retrying bad credentials
        except Exception as exc:
            last_exc = exc
            log.warning("[SMTP] attempt %d failed: %s", attempt + 1, exc)

    raise RuntimeError(f"SMTP: all 2 retries exhausted. Last: {last_exc}")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
def _is_resend_sandbox() -> bool:
    """Detect if Resend is in sandbox mode (onboarding@resend.dev from address).

    In sandbox mode, Resend API accepts the call and returns 200 with an email ID,
    but silently drops delivery for any recipient that is not the sandbox owner.
    This makes the fallback chain think the email was sent when it was not.
    """
    from_addr = os.environ.get("RESEND_FROM", "Garage <onboarding@resend.dev>")
    return "resend.dev" in from_addr.lower()


def send_verification_email(to_email: str, code: str, full_name: str) -> bool:
    """Send a 6-digit OTP to the given address.

    Priority: SMTP (when Resend is sandbox) → Resend → SMTP → dev console.
    Returns True if delivered via email, False if only printed to console.
    """
    resend_key = os.environ.get("RESEND_API_KEY", "")
    smtp_user  = os.environ.get("SMTP_USER", "")

    # ── 0. Sandbox guard: skip Resend when using sandbox from-address ────────
    # Resend sandbox silently accepts API calls but never delivers to
    # non-owner recipients. Prefer SMTP when sandbox is detected.
    if resend_key and _is_resend_sandbox() and smtp_user:
        log.warning("[RESEND SANDBOX] Detected sandbox from-address — skipping Resend, using SMTP")
        print("[GARAGE][RESEND SANDBOX] Skipping Resend (sandbox mode) — sending via SMTP")
        try:
            return _send_via_smtp(to_email, code, full_name)
        except Exception as exc:
            log.error("[SMTP FAIL after sandbox skip] %s: %s", to_email, exc)
            print(f"[GARAGE][SMTP FAIL] {exc}")
            # Fall through to dev console below

    # ── 1. Resend (preferred: SPF/DKIM, no spam — only if NOT sandbox) ───────
    elif resend_key:
        try:
            return _send_via_resend(to_email, code, full_name)
        except Exception as exc:
            log.error("[RESEND FAIL] %s — falling back to SMTP: %s", to_email, exc)
            print(f"[GARAGE][RESEND FAIL] {exc} — trying SMTP fallback")
            # Fall through to SMTP below

    # ── 2. SMTP fallback (Gmail) ─────────────────────────────────────────────
    if smtp_user:
        try:
            return _send_via_smtp(to_email, code, full_name)
        except Exception as exc:
            log.error("[SMTP FAIL] %s: %s", to_email, exc)
            print(f"[GARAGE][SMTP FAIL] {exc}")

    # ── 3. Dev console (no provider configured) ──────────────────────────────
    log.warning("[DEV MODE] No email provider. Code for %s: %s", to_email, code)
    print(f"[GARAGE][DEV] Verification code for {to_email}: {code}")
    return False


# Shared executor for email sending — never shut down so threads can finish
# in background after the HTTP response is returned.
from concurrent.futures import ThreadPoolExecutor as _TPE, Future as _Future

_email_executor = _TPE(max_workers=2, thread_name_prefix="email")


def send_verification_email_timed(
    to_email: str, code: str, full_name: str, timeout_secs: float = 8.0
) -> bool | None:
    """Send OTP email with a time limit for synchronous confirmation.

    Returns:
        True  — email confirmed sent within timeout
        False — no provider configured (dev console only)
        None  — sending started but not confirmed within timeout (still running in background)
    """
    from concurrent.futures import TimeoutError as FutureTimeout

    # Quick check: any provider available at all?
    resend_key = os.environ.get("RESEND_API_KEY", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    if not resend_key and not smtp_user:
        log.warning("[DEV MODE] No email provider. Code for %s: %s", to_email, code)
        print(f"[GARAGE][DEV] Verification code for {to_email}: {code}")
        return False

    future = _email_executor.submit(send_verification_email, to_email, code, full_name)
    try:
        result = future.result(timeout=timeout_secs)
        return result
    except FutureTimeout:
        log.info("[EMAIL TIMEOUT] %s: email send did not complete in %.1fs — continuing in background", to_email, timeout_secs)
        print(f"[GARAGE][EMAIL TIMEOUT] Sending to {to_email} continues in background (>{timeout_secs}s)")
        # Thread continues running — email will be sent, just not confirmed yet
        return None
    except Exception as exc:
        log.error("[EMAIL TIMED EXCEPTION] %s: %s", to_email, exc)
        return False


# ---------------------------------------------------------------------------
# Password-reset email (same dispatch chain, different subject/body)
# ---------------------------------------------------------------------------
def _html_template_reset(full_name: str, code: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:'Courier New',monospace;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="480" style="background:#1e293b;border:1px solid #334155;border-radius:12px;">
        <tr>
          <td style="padding:32px 40px;text-align:center;">
            <div style="color:#ef4444;font-size:24px;font-weight:700;letter-spacing:4px;">[GARAGE]</div>
            <div style="color:#94a3b8;font-size:11px;margin-top:4px;letter-spacing:2px;">REDEFINIÇÃO DE SENHA</div>
            <hr style="border:none;border-top:1px solid #334155;margin:24px 0;">
            <p style="color:#e2e8f0;font-size:15px;margin:0 0 8px;">Olá, <strong>{full_name}</strong>!</p>
            <p style="color:#94a3b8;font-size:13px;margin:0 0 28px;">
              Use o código abaixo para redefinir sua senha.<br>
              Ele expira em <strong style="color:#ef4444;">30 minutos</strong>.
            </p>
            <div style="background:#0f172a;border:2px solid #ef4444;border-radius:8px;padding:20px 0;margin:0 auto 28px;">
              <span style="color:#ef4444;font-size:38px;font-weight:700;letter-spacing:12px;">{code}</span>
            </div>
            <p style="color:#64748b;font-size:11px;margin:0;">
              Se você não solicitou a redefinição, ignore este e-mail.
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


def _send_reset_via_smtp(to_email: str, code: str, full_name: str) -> bool:
    """Send password-reset OTP via SMTP with 2 retries. Returns True on success, raises on failure."""
    subject = f"[{code}] Redefinição de senha — Garage"
    html_body = _html_template_reset(full_name, code)
    plain_body = (
        f"Olá {full_name},\n\n"
        f"Seu código para redefinição de senha do Garage é: {code}\n\n"
        f"Ele expira em 30 minutos. Se não foi você, ignore este e-mail.\n\n"
        f"— Bio Code Technology"
    )
    cfg = {
        "host":     os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port":     int(os.environ.get("SMTP_PORT", "587")),
        "user":     os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from":     os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from"] or cfg["user"]
    msg["To"] = to_email
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    last_exc = None
    for attempt in range(2):
        if attempt > 0:
            log.warning("[SMTP RESET] retry %d/2 for %s", attempt + 1, to_email)
        try:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
                server.ehlo(); server.starttls(); server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["user"], to_email, msg.as_string())
            log.info("[SMTP RESET OK] attempt=%d to=%s", attempt + 1, to_email)
            print(f"[GARAGE][SMTP RESET OK] Sent to {to_email} (attempt {attempt + 1})")
            return True
        except smtplib.SMTPAuthenticationError as exc:
            log.error("[SMTP RESET AUTH FAIL] user=%s: %s", cfg["user"], exc)
            raise
        except Exception as exc:
            last_exc = exc
            log.warning("[SMTP RESET] attempt %d failed: %s", attempt + 1, exc)

    raise RuntimeError(f"SMTP RESET: all 2 retries exhausted. Last: {last_exc}")


def send_password_reset_email(to_email: str, code: str, full_name: str) -> bool:
    """Send a password-reset OTP.

    Priority: SMTP (when Resend is sandbox) -> Resend -> SMTP -> dev console.
    Returns True if delivered via email, False if only printed to console.
    """
    resend_key = os.environ.get("RESEND_API_KEY", "")
    smtp_user  = os.environ.get("SMTP_USER", "")

    subject = f"[{code}] Redefinição de senha — Garage"
    html_body = _html_template_reset(full_name, code)
    plain_body = (
        f"Olá {full_name},\n\n"
        f"Seu código para redefinição de senha do Garage é: {code}\n\n"
        f"Ele expira em 30 minutos. Se não foi você, ignore este e-mail.\n\n"
        f"— Bio Code Technology"
    )

    # -- 0. Sandbox guard: skip Resend when using sandbox from-address --------
    if resend_key and _is_resend_sandbox() and smtp_user:
        log.warning("[RESEND SANDBOX] Detected sandbox from-address — skipping Resend for reset, using SMTP")
        print("[GARAGE][RESEND SANDBOX] Skipping Resend (sandbox mode) — sending reset via SMTP")
        try:
            return _send_reset_via_smtp(to_email, code, full_name)
        except Exception as exc:
            log.error("[SMTP RESET FAIL after sandbox skip] %s: %s", to_email, exc)
            print(f"[GARAGE][SMTP RESET FAIL] {exc}")

    # -- 1. Resend (preferred: SPF/DKIM — only if NOT sandbox) -----------------
    elif resend_key:
        try:
            import resend
            resend.api_key = resend_key
            from_addr = os.environ.get("RESEND_FROM", "Garage <onboarding@resend.dev>")
            resend.Emails.send({"from": from_addr, "to": [to_email],
                                "subject": subject, "html": html_body, "text": plain_body})
            log.info("[RESEND RESET OK] to=%s", to_email)
            return True
        except Exception as exc:
            log.error("[RESEND RESET FAIL] %s — falling back to SMTP: %s", to_email, exc)
            print(f"[GARAGE][RESEND RESET FAIL] {exc} — trying SMTP fallback")

    # -- 2. SMTP fallback (Gmail) ----------------------------------------------
    if smtp_user:
        try:
            return _send_reset_via_smtp(to_email, code, full_name)
        except Exception as exc:
            log.error("[SMTP RESET FAIL] %s: %s", to_email, exc)
            print(f"[GARAGE][SMTP RESET FAIL] {exc}")

    # -- 3. Dev console (no provider configured) --------------------------------
    log.warning("[DEV MODE] Reset code for %s: %s", to_email, code)
    print(f"[GARAGE][DEV] Password reset code for {to_email}: {code}")
    return False


def send_password_reset_email_timed(
    to_email: str, code: str, full_name: str, timeout_secs: float = 8.0
) -> bool | None:
    """Send password-reset OTP with a time limit for synchronous confirmation.

    Returns:
        True  — email confirmed sent within timeout
        False — no provider configured (dev console only)
        None  — sending started but not confirmed within timeout (still running in background)
    """
    from concurrent.futures import TimeoutError as FutureTimeout

    resend_key = os.environ.get("RESEND_API_KEY", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    if not resend_key and not smtp_user:
        log.warning("[DEV MODE] No email provider. Reset code for %s: %s", to_email, code)
        print(f"[GARAGE][DEV] Password reset code for {to_email}: {code}")
        return False

    future = _email_executor.submit(send_password_reset_email, to_email, code, full_name)
    try:
        result = future.result(timeout=timeout_secs)
        return result
    except FutureTimeout:
        log.info("[EMAIL RESET TIMEOUT] %s: reset email send did not complete in %.1fs — continuing in background", to_email, timeout_secs)
        print(f"[GARAGE][EMAIL RESET TIMEOUT] Sending to {to_email} continues in background (>{timeout_secs}s)")
        return None
    except Exception as exc:
        log.error("[EMAIL RESET TIMED EXCEPTION] %s: %s", to_email, exc)
        return False


# ---------------------------------------------------------------------------
# Subscription welcome email
# ---------------------------------------------------------------------------
PLAN_LABELS = {
    "monthly": "Mensal · R$ 97/mês · 30 dias",
    "annual":  "Anual · R$ 997/ano · 365 dias",
}


def _app_base_url() -> str:
    """Return the base URL for the app, configurable via APP_BASE_URL env var."""
    return os.environ.get("APP_BASE_URL", "https://garage.onrender.com").rstrip("/")


def _html_template_welcome(full_name: str, plan: str, expires_at: str) -> str:
    plan_label = PLAN_LABELS.get(plan, plan)
    base = _app_base_url()
    game_url = f"{base}/jogo"
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


def send_subscription_welcome_email(
    to_email: str,
    full_name: str,
    plan: str,
    expires_at: str,
) -> bool:
    """Send a welcome email after subscription activation.

    Priority: Resend → SMTP → dev console.
    """
    plan_label = PLAN_LABELS.get(plan, plan)
    base = _app_base_url()
    subject = "Acesso ativado - 404 Garage"
    html_body = _html_template_welcome(full_name, plan, expires_at)
    plain_body = (
        f"Olá {full_name},\n\n"
        f"Sua assinatura no 404 Garage foi ativada.\n\n"
        f"Plano: {plan_label}\n"
        f"Acesso até: {expires_at}\n\n"
        f"Entrar no jogo: {base}/jogo\n\n"
        f"404 Garage - De Estagiário a Principal Engineer\n"
        f"Bio Code Technology"
    )

    resend_key = os.environ.get("RESEND_API_KEY", "")
    smtp_user  = os.environ.get("SMTP_USER", "")

    if resend_key:
        try:
            import resend
            resend.api_key = resend_key
            from_addr = os.environ.get("RESEND_FROM", "Garage <onboarding@resend.dev>")
            resend.Emails.send({"from": from_addr, "to": [to_email],
                                "subject": subject, "html": html_body, "text": plain_body})
            log.info("[RESEND WELCOME OK] to=%s plan=%s", to_email, plan)
            return True
        except Exception as exc:
            log.error("[RESEND WELCOME FAIL] %s: %s", to_email, exc)

    if smtp_user:
        try:
            cfg = {
                "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
                "port": int(os.environ.get("SMTP_PORT", "587")),
                "user": smtp_user,
                "password": os.environ.get("SMTP_PASSWORD", ""),
                "from": os.environ.get("SMTP_FROM", smtp_user),
            }
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = cfg["from"]
            msg["To"] = to_email
            msg.attach(MIMEText(plain_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
                server.ehlo(); server.starttls(); server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["user"], to_email, msg.as_string())
            log.info("[SMTP WELCOME OK] to=%s plan=%s", to_email, plan)
            return True
        except Exception as exc:
            log.error("[SMTP WELCOME FAIL] %s: %s", to_email, exc)

    log.warning("[DEV MODE] Welcome email for %s (%s) not sent — no provider", to_email, plan)
    print(f"[GARAGE][DEV] Subscription welcome for {to_email}: plan={plan} expires={expires_at}")
    return False
