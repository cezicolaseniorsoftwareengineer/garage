"""Asaas HTTP client — thin wrapper around the Asaas REST API v3.

Docs: https://docs.asaas.com/reference
Sandbox base URL: https://sandbox.asaas.com/api/v3
Production base URL: https://api.asaas.com/api/v3
"""
import os
import httpx
from typing import Optional

_API_KEY = os.environ.get("ASAAS_API_KEY", "")
_BASE_URL = os.environ.get("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3").rstrip("/")
_TIMEOUT = 20  # seconds


def _headers() -> dict:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": _API_KEY,
    }


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

def create_or_find_customer(name: str, email: str, cpf_cnpj: Optional[str] = None) -> dict:
    """Find existing customer by email or create a new one.

    Returns the Asaas customer object (dict).
    """
    # Try to find first
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(
            f"{_BASE_URL}/customers",
            headers=_headers(),
            params={"email": email},
        )
        resp.raise_for_status()
        data = resp.json()
        customers = data.get("data", [])
        if customers:
            return customers[0]

        # Create
        payload: dict = {"name": name, "email": email}
        if cpf_cnpj:
            payload["cpfCnpj"] = cpf_cnpj.strip().replace(".", "").replace("-", "").replace("/", "")

        resp = client.post(
            f"{_BASE_URL}/customers",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# PIX charge
# ---------------------------------------------------------------------------

def create_pix_charge(
    customer_id: str,
    value: float,
    description: str,
    external_reference: str,
    due_date: str,  # "YYYY-MM-DD"
) -> dict:
    """Create a PIX payment charge.

    Returns Asaas payment object containing:
      - id           : payment ID (save this for webhook matching)
      - pixQrCode    : base64 QR Code image  (populated via get_pix_qr_code)
      - encodedImage : base64 PNG
      - payload      : copia-e-cola string
    """
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{_BASE_URL}/payments",
            headers=_headers(),
            json={
                "customer": customer_id,
                "billingType": "PIX",
                "value": value,
                "dueDate": due_date,
                "description": description,
                "externalReference": external_reference,
            },
        )
        resp.raise_for_status()
        return resp.json()


def get_pix_qr_code(payment_id: str) -> dict:
    """Retrieve the PIX QR Code image + payload for a payment.

    Returns:
      - encodedImage : base64 PNG  (use in <img src="data:image/png;base64,...">)
      - payload      : copia-e-cola string
      - expirationDate : ISO datetime
    """
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(
            f"{_BASE_URL}/payments/{payment_id}/pixQrCode",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


def get_payment(payment_id: str) -> dict:
    """Retrieve a payment status from Asaas."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(
            f"{_BASE_URL}/payments/{payment_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
