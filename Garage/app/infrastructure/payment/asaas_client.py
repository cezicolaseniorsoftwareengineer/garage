"""Asaas HTTP client — thin wrapper around the Asaas REST API v3.

Docs: https://docs.asaas.com/reference
Sandbox base URL: https://api-sandbox.asaas.com/v3
Production base URL: https://api.asaas.com/v3
"""
import os
import logging
import httpx
from typing import Optional

log = logging.getLogger("garage.asaas")

_TIMEOUT = 20  # seconds


def _normalize_cpf_cnpj(cpf_cnpj: Optional[str]) -> str:
    if not cpf_cnpj:
        return ""
    return "".join(ch for ch in cpf_cnpj if ch.isdigit())


def _api_key() -> str:
    key = os.environ.get("ASAAS_API_KEY", "")
    if not key:
        log.error("ASAAS_API_KEY environment variable is not set. Cannot authenticate with Asaas API.")
    return key


def _base_url() -> str:
    return os.environ.get("ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3").rstrip("/")


def _headers() -> dict:
    api_key = _api_key()
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": api_key,
    }
    # Debug: warn if token appears empty
    if not api_key:
        log.warning("Headers being sent to Asaas with empty access_token. Authentication will fail.")
    return headers


def _raise_with_detail(resp: httpx.Response) -> None:
    """Raise HTTPStatusError with Asaas response body included in the message."""
    if resp.is_error:
        try:
            body = resp.json()
        except Exception:
            body = resp.text

        # Special handling for 401 access_token errors
        if resp.status_code == 401:
            error_desc = ""
            if isinstance(body, dict) and "errors" in body:
                errors = body.get("errors", [])
                if errors and "description" in errors[0]:
                    error_desc = errors[0]["description"]
            log.error(
                "Asaas 401 Authentication Error: %s | Check that ASAAS_API_KEY environment variable is set correctly.",
                error_desc or body
            )
        else:
            log.error("Asaas %s %s → %s %s", resp.request.method, resp.request.url, resp.status_code, body)

        raise httpx.HTTPStatusError(
            f"Asaas {resp.status_code}: {body}",
            request=resp.request,
            response=resp,
        )


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

def create_or_find_customer(name: str, email: str, cpf_cnpj: Optional[str] = None) -> dict:
    """Find existing customer by email or create a new one."""
    base = _base_url()
    normalized_cpf_cnpj = _normalize_cpf_cnpj(cpf_cnpj)

    if not normalized_cpf_cnpj:
        raise ValueError("CPF/CNPJ is required to create Asaas charges.")

    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{base}/customers", headers=_headers(), params={"email": email})
        _raise_with_detail(resp)
        data = resp.json()
        customers = data.get("data", [])
        if customers:
            existing = customers[0]
            existing_cpf_cnpj = _normalize_cpf_cnpj(existing.get("cpfCnpj"))

            if existing_cpf_cnpj != normalized_cpf_cnpj:
                payload = {
                    "name": existing.get("name") or name,
                    "email": existing.get("email") or email,
                    "cpfCnpj": normalized_cpf_cnpj,
                }
                customer_id = existing.get("id")
                log.info("Updating Asaas customer %s with cpfCnpj for compliance", customer_id)
                resp = client.put(f"{base}/customers/{customer_id}", headers=_headers(), json=payload)
                _raise_with_detail(resp)
                return resp.json()

            return existing

        payload: dict = {"name": name, "email": email}
        payload["cpfCnpj"] = normalized_cpf_cnpj

        resp = client.post(f"{base}/customers", headers=_headers(), json=payload)
        _raise_with_detail(resp)
        return resp.json()


# ---------------------------------------------------------------------------
# Charges
# ---------------------------------------------------------------------------

def create_charge(
    customer_id: str,
    value: float,
    description: str,
    external_reference: str,
    due_date: str,  # "YYYY-MM-DD"
    billing_type: str = "PIX",
) -> dict:
    """Create a payment charge for the provided billing type.

    billing_type examples: PIX, UNDEFINED.
    """
    base = _base_url()
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{base}/payments",
            headers=_headers(),
            json={
                "customer": customer_id,
                "billingType": billing_type,
                "value": value,
                "dueDate": due_date,
                "description": description,
                "externalReference": external_reference,
            },
        )
        _raise_with_detail(resp)
        return resp.json()


def create_pix_charge(
    customer_id: str,
    value: float,
    description: str,
    external_reference: str,
    due_date: str,  # "YYYY-MM-DD"
) -> dict:
    """Create a PIX payment charge."""
    return create_charge(
        customer_id=customer_id,
        value=value,
        description=description,
        external_reference=external_reference,
        due_date=due_date,
        billing_type="PIX",
    )


def get_pix_qr_code(payment_id: str) -> dict:
    """Retrieve the PIX QR Code image + payload for a payment."""
    base = _base_url()
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{base}/payments/{payment_id}/pixQrCode", headers=_headers())
        _raise_with_detail(resp)
        return resp.json()


def get_customer(customer_id: str) -> dict:
    """Retrieve a customer by ID from Asaas."""
    base = _base_url()
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{base}/customers/{customer_id}", headers=_headers())
        _raise_with_detail(resp)
        return resp.json()


def get_payment(payment_id: str) -> dict:
    """Retrieve a payment status from Asaas."""
    base = _base_url()
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{base}/payments/{payment_id}", headers=_headers())
        _raise_with_detail(resp)
        return resp.json()
