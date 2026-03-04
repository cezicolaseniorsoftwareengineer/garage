"""Payment routes — PIX/Card checkout + Asaas webhook.

Endpoints:
    POST /api/payments/checkout          → generate PIX QR Code or card checkout URL
  POST /api/payments/webhook/asaas     → receive Asaas payment notification
  GET  /api/payments/status/{payment_id} → poll payment status (frontend polling)
"""
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.infrastructure.payment import asaas_client, pix_service

log = logging.getLogger("garage.payment")

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Injected by init_payment_routes
_user_repo = None


def init_payment_routes(user_repo) -> None:
    global _user_repo
    _user_repo = user_repo


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

    The frontend displays the QR Code and polls /status/{payment_id}
    until status == CONFIRMED or RECEIVED, then redirects to the game.
    """
    try:
        result = pix_service.create_checkout(
            user_id=body.user_id,
            user_name=body.user_name,
            user_email=body.user_email,
            plan=body.plan,
            payment_method=body.payment_method,
            cpf_cnpj=body.cpf_cnpj,
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

    Asaas sends a POST with JSON payload when payment status changes.
    We handle PAYMENT_CONFIRMED and PAYMENT_RECEIVED to activate access.

    Security: webhook token validation recommended for production.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event = body.get("event", "")
    payment_data = body.get("payment", {})

    log.info("Asaas webhook received: event=%s payment_id=%s",
             event, payment_data.get("id"))

    # Only act on confirmed/received events
    if event not in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
        return {"received": True, "action": "ignored", "event": event}

    # Extract user_id and plan from externalReference
    external_ref = payment_data.get("externalReference", "")
    if "|" not in external_ref:
        # Static Asaas link (no externalReference) — try to match by customer email
        log.info("Webhook: no externalReference — attempting email-based activation for payment %s",
                 payment_data.get("id"))
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
                            log.info("Static-link sub activated via email match: email=%s plan=%s expires=%s",
                                     customer_email, plan_guess, expires_at)
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
        log.info("Subscription activated via webhook: user=%s plan=%s expires=%s",
                 user_id, plan, expires_at)
        return {
            "received": True,
            "action": "subscription_activated",
            "user_id": user_id,
            "plan": plan,
            "expires_at": expires_at.isoformat(),
        }
    except Exception as exc:
        log.exception("Failed to activate subscription: %s", exc)
        # Return 200 to avoid Asaas retrying — log the error instead
        return {"received": True, "action": "error", "reason": str(exc)}
