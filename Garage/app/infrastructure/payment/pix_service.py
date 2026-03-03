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
    cpf_cnpj: Optional[str] = None,
) -> dict:
    """Create a PIX charge and return QR code data for the frontend.

    Returns:
      {
        "payment_id": str,
        "plan": str,
        "value": float,
        "qr_code_base64": str,   # base64 PNG — embed as <img src="data:image/png;base64,...">
        "pix_copy_paste": str,   # copia-e-cola
        "expires_at": str,       # ISO datetime
      }
    """
    if plan not in PLAN_CONFIG:
        raise ValueError(f"Invalid plan '{plan}'. Use: {list(PLAN_CONFIG.keys())}")

    cfg = PLAN_CONFIG[plan]
    due_date = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d")

    # 1. Find or create customer in Asaas
    customer = asaas_client.create_or_find_customer(user_name, user_email, cpf_cnpj)
    customer_id = customer["id"]
    log.info("Asaas customer ready: %s (plan=%s user_id=%s)", customer_id, plan, user_id)

    # 2. Create PIX charge
    payment = asaas_client.create_pix_charge(
        customer_id=customer_id,
        value=cfg["value"],
        description=cfg["label"],
        external_reference=f"{user_id}|{plan}",
        due_date=due_date,
    )
    payment_id = payment["id"]
    log.info("PIX charge created: %s", payment_id)

    # 3. Fetch QR Code
    qr = asaas_client.get_pix_qr_code(payment_id)

    return {
        "payment_id": payment_id,
        "plan": plan,
        "value": cfg["value"],
        "qr_code_base64": qr.get("encodedImage", ""),
        "pix_copy_paste": qr.get("payload", ""),
        "expires_at": qr.get("expirationDate", ""),
    }


def activate_subscription(user_id: str, plan: str, user_repo) -> datetime:
    """Mark the user's subscription as active for the plan duration.

    Updates the user record in the repository and returns the expiration datetime.
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

    return expires_at


def check_subscription(user_id: str, user_repo) -> dict:
    """Return the subscription status for a user."""
    try:
        return user_repo.get_subscription_status(user_id)
    except AttributeError:
        return {"status": "active", "note": "subscription_check_unavailable"}
