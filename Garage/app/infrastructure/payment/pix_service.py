"""PIX payment service — business logic for checkout and subscription activation.

Plans:
  monthly  → R$ 97,00 / mês  (30 days access)
  annual   → R$ 997,00 / ano (365 days access)
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.infrastructure.payment import asaas_client

log = logging.getLogger("garage.payment")

PLAN_CONFIG = {
    "monthly": {
        "value": float(os.environ.get("PRICE_MONTHLY", "97.00")),
        "days": 30,
        "label": "404 Garage — Plano Mensal",
    },
    "annual": {
        "value": float(os.environ.get("PRICE_ANNUAL", "997.00")),
        "days": 365,
        "label": "404 Garage — Plano Anual",
    },
}


def create_checkout(
    user_id: str,
    user_name: str,
    user_email: str,
    plan: str,
        payment_method: str = "pix",
    cpf_cnpj: Optional[str] = None,
) -> dict:
        """Create a charge and return checkout data for the frontend.

    Returns:
      {
        "payment_id": str,
        "plan": str,
                "payment_method": str,
        "value": float,
                "qr_code_base64": str,   # for PIX
                "pix_copy_paste": str,   # for PIX
                "checkout_url": str,     # for card checkout flow
        "expires_at": str,       # ISO datetime
      }
    """
    if plan not in PLAN_CONFIG:
        raise ValueError(f"Invalid plan '{plan}'. Use: {list(PLAN_CONFIG.keys())}")
        if payment_method not in ("pix", "card"):
                raise ValueError("Invalid payment_method. Use: pix or card")

    cfg = PLAN_CONFIG[plan]
    due_date = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d")

    # 1. Find or create customer in Asaas
    customer = asaas_client.create_or_find_customer(user_name, user_email, cpf_cnpj)
    customer_id = customer["id"]
    log.info("Asaas customer ready: %s (plan=%s user_id=%s)", customer_id, plan, user_id)

    billing_type = "PIX" if payment_method == "pix" else "UNDEFINED"

    # 2. Create charge
    payment = asaas_client.create_charge(
        customer_id=customer_id,
        value=cfg["value"],
        description=cfg["label"],
        external_reference=f"{user_id}|{plan}",
        due_date=due_date,
        billing_type=billing_type,
    )
    payment_id = payment["id"]
    log.info("Charge created: %s method=%s billing=%s", payment_id, payment_method, billing_type)

    response = {
        "payment_id": payment_id,
        "plan": plan,
        "payment_method": payment_method,
        "value": cfg["value"],
        "qr_code_base64": "",
        "pix_copy_paste": "",
        "checkout_url": payment.get("invoiceUrl", ""),
        "expires_at": payment.get("dueDate", ""),
    }

    if payment_method == "pix":
        # 3. Fetch QR Code
        qr = asaas_client.get_pix_qr_code(payment_id)
        response["qr_code_base64"] = qr.get("encodedImage", "")
        response["pix_copy_paste"] = qr.get("payload", "")
        response["expires_at"] = qr.get("expirationDate", "") or response["expires_at"]

    return response


def activate_subscription(user_id: str, plan: str, user_repo) -> datetime:
    """Mark the user's subscription as active for the plan duration.

    Updates the user record in the repository, sends welcome email (fire-and-forget)
    and returns the expiration datetime.
    """
    cfg = PLAN_CONFIG.get(plan, PLAN_CONFIG["monthly"])
    expires_at = datetime.now(timezone.utc) + timedelta(days=cfg["days"])

    try:
        user_repo.activate_subscription(
            user_id=user_id,
            plan=plan,
            expires_at=expires_at,
        )
        log.info("Subscription activated: user=%s plan=%s expires=%s", user_id, plan, expires_at)
    except AttributeError:
        # Fallback: repo doesn't have activate_subscription yet (JSON fallback)
        log.warning("user_repo.activate_subscription not available — JSON fallback active")

    # Send welcome email in background thread (fire-and-forget — never blocks payment flow)
    try:
        user = user_repo.find_by_id(user_id) if hasattr(user_repo, "find_by_id") else None
        if user:
            from app.infrastructure.auth.email_sender import send_subscription_welcome_email
            import threading
            threading.Thread(
                target=send_subscription_welcome_email,
                kwargs={
                    "to_email": user.email,
                    "full_name": getattr(user, "full_name", None) or getattr(user, "username", "Dev"),
                    "plan": plan,
                    "expires_at": expires_at.strftime("%d/%m/%Y"),
                },
                daemon=True,
            ).start()
            log.info("Welcome email queued: user=%s email=%s", user_id, user.email)
    except Exception as exc:
        log.warning("Welcome email failed (non-fatal): %s", exc)

    return expires_at


def check_subscription(user_id: str, user_repo) -> dict:
    """Return the subscription status for a user."""
    try:
        return user_repo.get_subscription_status(user_id)
    except AttributeError:
        return {"status": "active", "note": "subscription_check_unavailable"}
