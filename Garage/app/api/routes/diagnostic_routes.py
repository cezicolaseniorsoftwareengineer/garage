"""Diagnostic endpoint to show Asaas configuration in production.

This helps troubleshoot invalid_environment errors by showing exactly
what environment variables are loaded in Render.
"""
import os
import logging
from fastapi import APIRouter

log = logging.getLogger("garage.diagnostic")

router = APIRouter(prefix="/api/diagnostic", tags=["diagnostic"])


@router.get("/asaas-config")
def asaas_config():
    """Show current Asaas configuration (REDACTED for security).

    This endpoint helps diagnose environment variable issues in production.
    Returns redacted versions of sensitive data for troubleshooting.
    """
    api_key = os.environ.get("ASAAS_API_KEY", "")
    base_url = os.environ.get("ASAAS_BASE_URL", "")

    # Redact sensitive parts but show key type and URL
    if api_key:
        key_type = "UNKNOWN"
        if api_key.startswith("$aact_prod_"):
            key_type = "PRODUCTION"
            key_preview = f"$aact_prod_{api_key[12:25]}...{api_key[-10:]}"
        elif api_key.startswith("$aact_test_"):
            key_type = "SANDBOX"
            key_preview = f"$aact_test_{api_key[12:25]}...{api_key[-10:]}"
        else:
            key_preview = f"{api_key[:15]}...{api_key[-5:]}"
    else:
        key_type = "NOT_SET"
        key_preview = "EMPTY"

    # Determine environment based on URL
    url_env = "NOT_SET"
    if base_url:
        if "api.asaas.com" in base_url or "production" in base_url:
            url_env = "PRODUCTION"
        elif "sandbox" in base_url:
            url_env = "SANDBOX"
        else:
            url_env = "UNKNOWN"

    # Check for mismatch
    has_mismatch = False
    if key_type in ("PRODUCTION", "SANDBOX") and url_env in ("PRODUCTION", "SANDBOX"):
        has_mismatch = (key_type != url_env)

    return {
        "status": "error" if has_mismatch or key_type == "NOT_SET" else "ok",
        "asaas_api_key": {
            "type": key_type,
            "preview": key_preview,
            "length": len(api_key),
        },
        "asaas_base_url": {
            "environment": url_env,
            "url": base_url or "NOT_SET",
        },
        "validation": {
            "has_mismatch": has_mismatch,
            "expected": "Key type must match URL environment (both PRODUCTION or both SANDBOX)",
            "recommendation": (
                "MISMATCH DETECTED! Update Render environment variables." if has_mismatch
                else "Configuration looks correct." if key_type != "NOT_SET"
                else "ASAAS_API_KEY is not set in Render."
            ),
        },
        "correct_combinations": [
            {
                "key": "$aact_prod_...",
                "url": "https://api.asaas.com/v3",
                "description": "Production environment"
            },
            {
                "key": "$aact_test_...",
                "url": "https://api-sandbox.asaas.com/v3",
                "description": "Sandbox/test environment"
            }
        ]
    }
