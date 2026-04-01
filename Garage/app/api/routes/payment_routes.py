"""Payment routes — PIX/Card checkout + Asaas webhook.

Endpoints:
    POST /api/payments/checkout          → generate PIX QR Code or card checkout URL
  POST /api/payments/webhook/asaas     → receive Asaas payment notification
  GET  /api/payments/status/{payment_id} → poll payment status (frontend polling)
  POST /api/payments/self-reconcile    → authenticated user verifies own payment in Asaas
  POST /api/payments/reconcile         → admin: activate subscription by email
"""
import logging
import os
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from sqlalchemy import text

from app.infrastructure.payment import asaas_client, pix_service
from app.infrastructure.database.connection import dynamic_session_factory
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.admin_utils import is_admin_username

log = logging.getLogger("garage.payment")

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Injected by init_payment_routes
_user_repo = None


def init_payment_routes(user_repo) -> None:
    global _user_repo
    _user_repo = user_repo


# Feature flag + webhook secrets
ENABLE_ASAAS_WEBHOOK = os.environ.get("ENABLE_ASAAS_WEBHOOK", "false").lower() == "true"
ASAAS_WEBHOOK_SECRET = os.environ.get("ASAAS_WEBHOOK_SECRET", "")
ASAAS_SIGNATURE_HEADER = os.environ.get("ASAAS_SIGNATURE_HEADER", "X-Asaas-Signature")

# In-memory fallback store for webhook idempotency when DB is unavailable
_webhook_in_memory_store: dict = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    user_id: str = Field(..., description="UUID of the authenticated user")
    user_name: str = Field(..., min_length=2, max_length=100)
    user_email: str
    plan: str = Field(..., pattern="^(monthly|annual)$")
    payment_method: str = Field("pix", pattern="^(pix|card)$")
    cpf_cnpj: str | None = Field(None, description="Optional CPF/CNPJ for nota fiscal")


class CheckoutResponse(BaseModel):

    def _normalize_cpf_cnpj(value: str | None) -> str:
        if not value:
            return ""
        return "".join(ch for ch in value if ch.isdigit())
    payment_id: str
    plan: str
    payment_method: str
    value: float
    qr_code_base64: str | None = None
    pix_copy_paste: str | None = None
    checkout_url: str | None = None
    expires_at: str


class PaymentStatusResponse(BaseModel):
    payment_id: str
    status: str        # PENDING | CONFIRMED | RECEIVED | OVERDUE | CANCELLED
    value: float
    plan: str | None = None


# ---------------------------------------------------------------------------
# POST /api/payments/checkout
# ---------------------------------------------------------------------------

@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
def checkout(body: CheckoutRequest):
    """Generate PIX or card checkout for the selected plan.

    DEPRECATED: Now handled entirely by Asaas links on the frontend to avoid creating fake clients dynamically.
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Endpoint desativado. Pagamentos agora são feitos exclusivamente via Link Asaas direto.",
    )

    normalized_cpf_cnpj = _normalize_cpf_cnpj(body.cpf_cnpj)
    if len(normalized_cpf_cnpj) not in (11, 14):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF/CNPJ obrigatório para gerar cobrança (11 ou 14 dígitos).",
        )
    try:
        result = pix_service.create_checkout(
            user_id=body.user_id,
            user_name=body.user_name,
            user_email=body.user_email,
            plan=body.plan,
            payment_method=body.payment_method,
            cpf_cnpj=normalized_cpf_cnpj,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        log.exception("checkout failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# GET /api/payments/status/{payment_id}
# ---------------------------------------------------------------------------

@router.get("/status/{payment_id}", response_model=PaymentStatusResponse)
def payment_status(payment_id: str):
    """Poll Asaas for the payment status.

    Frontend polls this every 5 s until status in (CONFIRMED, RECEIVED).
    On confirmation, it redirects the user to the game.
    """
    try:
        payment = asaas_client.get_payment(payment_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gateway error: {exc}")

    # Extract plan from externalReference ("user_id|plan")
    ref = payment.get("externalReference", "")
    plan = ref.split("|")[1] if "|" in ref else None

    # Auto-activate if confirmed and user_repo is available
    pmt_status = payment.get("status", "PENDING")
    if pmt_status in ("CONFIRMED", "RECEIVED") and _user_repo and plan:
        user_id = ref.split("|")[0]
        try:
            pix_service.activate_subscription(user_id, plan, _user_repo)
        except Exception as exc:
            log.error("auto-activate failed on status poll: %s", exc)

    return {
        "payment_id": payment_id,
        "status": pmt_status,
        "value": payment.get("value", 0.0),
        "plan": plan,
    }


# ---------------------------------------------------------------------------
# POST /api/payments/webhook/asaas
# ---------------------------------------------------------------------------

@router.post("/webhook/asaas", status_code=200)
async def asaas_webhook(request: Request):
    """Receive payment events from Asaas.

    Security: gated by `ENABLE_ASAAS_WEBHOOK`. Validates HMAC signature and
    applies idempotency to avoid replay processing.
    """
    if not ENABLE_ASAAS_WEBHOOK:
        log.info("Asaas webhook received but disabled by feature flag.")
        # Return 200 to acknowledge but do nothing when disabled.
        return {"received": True, "action": "disabled"}

    # Read raw body for signature validation
    try:
        body_bytes = await request.body()
        body = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Signature validation (HMAC SHA256)
    sig_header = request.headers.get(ASAAS_SIGNATURE_HEADER)
    if not ASAAS_WEBHOOK_SECRET:
        log.error("ASAAS_WEBHOOK_SECRET not configured — rejecting webhook")
        raise HTTPException(status_code=403, detail="Webhook not configured")

    expected_hex = hmac.new(ASAAS_WEBHOOK_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hex, (sig_header or "")):
        # Try base64 variant
        expected_b64 = base64.b64encode(hmac.new(ASAAS_WEBHOOK_SECRET.encode(), body_bytes, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(expected_b64, (sig_header or "")):
            log.warning("Invalid webhook signature: header=%s expected_hex=%s", sig_header, expected_hex)
            raise HTTPException(status_code=403, detail="Invalid signature")

    event = body.get("event", "")
    payment_data = body.get("payment", {})

    log.info("Asaas webhook received: event=%s payment_id=%s", event, payment_data.get("id"))

    # Only act on confirmed/received events
    if event not in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
        return {"received": True, "action": "ignored", "event": event}

    # Idempotency key for webhook processing
    webhook_key = payment_data.get("id") or body.get("id")
    if webhook_key:
        try:
            with dynamic_session_factory() as session:
                sel = text("SELECT status_code FROM idempotency_keys WHERE id = :id")
                row = session.execute(sel, {"id": webhook_key}).fetchone()
                if row and row[0] is not None:
                    log.info("Webhook %s already processed (db).", webhook_key)
                    return {"received": True, "action": "already_processed"}

                ins = text(
                    "INSERT INTO idempotency_keys (id, method, path, created_at) VALUES (:id, 'POST', '/api/payments/webhook/asaas', NOW()) ON CONFLICT (id) DO NOTHING"
                )
                session.execute(ins, {"id": webhook_key})
                session.commit()
        except Exception:
            # DB unavailable — consult fallback store
            entry = _webhook_in_memory_store.get(webhook_key)
            if entry and entry.get("processed"):
                log.info("Webhook %s already processed (in-memory).", webhook_key)
                return {"received": True, "action": "already_processed_fallback"}
            _webhook_in_memory_store[webhook_key] = {"processed": False}

    # Extract user_id and plan from externalReference
    external_ref = payment_data.get("externalReference", "")
    if "|" not in external_ref:
        # Static Asaas link (no externalReference) — try to match by customer email
        log.info("Webhook: no externalReference — attempting email-based activation for payment %s", payment_data.get("id"))
        if _user_repo:
            try:
                customer_id = payment_data.get("customer", "")
                if customer_id:
                    from app.infrastructure.payment import asaas_client as _asaas
                    customer = _asaas.get_customer(customer_id)
                    customer_email = customer.get("email", "")
                    if customer_email:
                        user = _user_repo.find_by_email(customer_email)
                        if user:
                            user_data = user.to_dict() if hasattr(user, "to_dict") else vars(user)
                            uid = user_data.get("id") or str(getattr(user, "id", ""))
                            # Default to monthly for static link (R$97)
                            plan_guess = "annual" if payment_data.get("value", 0) > 500 else "monthly"
                            expires_at = pix_service.activate_subscription(uid, plan_guess, _user_repo)
                            log.info("Static-link sub activated via email match: email=%s plan=%s expires=%s", customer_email, plan_guess, expires_at)

                            # Mark as processed in idempotency store
                            if webhook_key:
                                try:
                                    with dynamic_session_factory() as session:
                                        upd = text(
                                            "UPDATE idempotency_keys SET status_code = :status, response_body = :body, expires_at = (NOW() + interval '24 hours') WHERE id = :id"
                                        )
                                        session.execute(upd, {"status": 200, "body": json.dumps({"action": "subscription_activated_by_email", "email": customer_email}), "id": webhook_key})
                                        session.commit()
                                except Exception:
                                    _webhook_in_memory_store[webhook_key]["processed"] = True

                            return {
                                "received": True,
                                "action": "subscription_activated_by_email",
                                "email": customer_email,
                                "plan": plan_guess,
                                "expires_at": expires_at.isoformat(),
                            }
                        else:
                            log.warning("Webhook email-match: no user found for email=%s", customer_email)
                    else:
                        log.warning("Webhook: customer %s has no email", customer_id)
            except Exception as exc:
                log.error("Webhook email-based fallback failed: %s", exc)
        return {"received": True, "action": "skipped", "reason": "no_external_reference"}

    user_id, plan = external_ref.split("|", 1)

    if not _user_repo:
        log.error("_user_repo not wired — cannot activate subscription")
        return {"received": True, "action": "error", "reason": "repo_unavailable"}

    try:
        expires_at = pix_service.activate_subscription(user_id, plan, _user_repo)
        log.info("Subscription activated via webhook: user=%s plan=%s expires=%s", user_id, plan, expires_at)

        # Mark as processed in idempotency store
        if webhook_key:
            try:
                with dynamic_session_factory() as session:
                    upd = text(
                        "UPDATE idempotency_keys SET status_code = :status, response_body = :body, expires_at = (NOW() + interval '24 hours') WHERE id = :id"
                    )
                    session.execute(upd, {"status": 200, "body": json.dumps({"action": "subscription_activated", "user_id": user_id, "plan": plan}), "id": webhook_key})
                    session.commit()
            except Exception:
                _webhook_in_memory_store[webhook_key]["processed"] = True

        return {
            "received": True,
            "action": "subscription_activated",
            "user_id": user_id,
            "plan": plan,
            "expires_at": expires_at.isoformat(),
        }
    except Exception as exc:
        log.exception("Failed to activate subscription: %s", exc)
        # Do not let Asaas keep retrying uncontrolled failures — return 200 but log
        return {"received": True, "action": "error", "reason": str(exc)}


# ---------------------------------------------------------------------------
# POST /api/payments/self-reconcile
# ---------------------------------------------------------------------------

@router.post("/self-reconcile", status_code=200)
def self_reconcile(current_user: dict = Depends(get_current_user)):
    """Authenticated user: query Asaas directly for confirmed payments and
    activate their subscription if one is found.

    Called by the frontend 'Ja paguei' button so the user never needs admin
    intervention when the webhook delivery failed.
    """
    if not _user_repo:
        raise HTTPException(status_code=503, detail="Repository not available.")

    user_id = current_user["sub"]

    user = _user_repo.find_by_id(user_id) if hasattr(_user_repo, "find_by_id") else None
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check DB first — avoid unnecessary Asaas call if already active
    if hasattr(_user_repo, "get_subscription_status"):
        sub = _user_repo.get_subscription_status(user_id)
        if sub.get("status") == "active":
            return {"activated": False, "already_active": True, "subscription": sub}

    email = getattr(user, "email", None)
    if not email:
        raise HTTPException(status_code=400, detail="User has no e-mail configured.")

    try:
        payments = asaas_client.list_confirmed_payments_by_email(email)
    except Exception as exc:
        log.exception("self-reconcile: Asaas query failed user=%s: %s", user_id, exc)
        raise HTTPException(status_code=502, detail="Failed to reach payment provider. Try again in a moment.")

    if not payments:
        return {"activated": False, "already_active": False, "reason": "no_confirmed_payments"}

    best = payments[0]
    plan_guess = "annual" if best.get("value", 0) > 500 else "monthly"

    try:
        expires_at = pix_service.activate_subscription(user_id, plan_guess, _user_repo)
    except Exception as exc:
        log.exception("self-reconcile: activate_subscription failed user=%s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Subscription activation failed.")

    log.info(
        "self-reconcile: activated user=%s email=%s plan=%s expires=%s",
        user_id, email, plan_guess, expires_at,
    )

    sub = _user_repo.get_subscription_status(user_id) if hasattr(_user_repo, "get_subscription_status") else {}
    return {
        "activated": True,
        "already_active": False,
        "plan": plan_guess,
        "expires_at": expires_at.isoformat(),
        "subscription": sub,
    }


# ---------------------------------------------------------------------------
# POST /api/payments/reconcile
# ---------------------------------------------------------------------------

class ReconcileRequest(BaseModel):
    email: str = Field(..., description="E-mail do usuario a reconciliar")


@router.post("/reconcile", status_code=200)
def reconcile_subscription(
    body: ReconcileRequest,
    current_user: dict = Depends(get_current_user),
):
    """Admin-only: query Asaas for confirmed payments by e-mail and activate
    the subscription if one is found.  Recovers users whose webhook was missed
    (e.g. service was hibernating or Asaas delivery failed).
    """
    if current_user.get("role") != "admin" and not is_admin_username(current_user.get("username")):
        raise HTTPException(status_code=403, detail="Access denied. Admin only.")

    if not _user_repo:
        raise HTTPException(status_code=503, detail="Repository not available.")

    email = body.email.strip().lower()

    # Find the user in our DB
    user = _user_repo.find_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail=f"No user found with email: {email}")

    user_data = user.to_dict() if hasattr(user, "to_dict") else vars(user)
    user_id = str(user_data.get("id", ""))
    if not user_id:
        raise HTTPException(status_code=500, detail="User ID could not be resolved.")

    # Query Asaas for confirmed payments
    try:
        payments = asaas_client.list_confirmed_payments_by_email(email)
    except Exception as exc:
        log.exception("Asaas query failed during reconcile for email=%s: %s", email, exc)
        raise HTTPException(status_code=502, detail="Failed to query Asaas.")

    if not payments:
        return {
            "reconciled": False,
            "reason": "no_confirmed_payments",
            "email": email,
        }

    # Use the first (highest value) payment to determine plan
    best = payments[0]
    plan_guess = "annual" if best.get("value", 0) > 500 else "monthly"

    try:
        expires_at = pix_service.activate_subscription(user_id, plan_guess, _user_repo)
    except Exception as exc:
        log.exception("reconcile: activate_subscription failed user=%s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Subscription activation failed.")

    log.info(
        "Reconcile: activated subscription user=%s email=%s plan=%s expires=%s",
        user_id, email, plan_guess, expires_at,
    )
    return {
        "reconciled": True,
        "email": email,
        "user_id": user_id,
        "plan": plan_guess,
        "expires_at": expires_at.isoformat(),
        "asaas_payments_found": len(payments),
    }
