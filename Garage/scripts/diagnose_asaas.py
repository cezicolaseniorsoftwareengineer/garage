#!/usr/bin/env python3
"""Diagnostic script to check Asaas API key configuration and test authentication."""

import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load .env
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(PROJECT_DIR, '.env')
load_dotenv(env_path)

def diagnose():
    """Check Asaas configuration."""
    print("=" * 70)
    print("ASAAS CONFIGURATION DIAGNOSTIC")
    print("=" * 70)

    # 1. Check .env file exists
    if os.path.exists(env_path):
        print(f"✓ .env file found at: {env_path}")
    else:
        print(f"✗ .env file NOT found at: {env_path}")
        return False

    # 2. Check ASAAS_API_KEY is set
    api_key = os.environ.get("ASAAS_API_KEY", "")
    if not api_key:
        print("✗ ASAAS_API_KEY is empty or not set in environment")
        print("  → ACTION: Set ASAAS_API_KEY in .env or Render environment variables")
        return False

    # Show first 20 chars and last 10 chars (for security)
    key_preview = f"{api_key[:20]}...{api_key[-10:]}"
    print(f"✓ ASAAS_API_KEY is set (preview: {key_preview})")

    # 3. Check key type (sandbox vs production)
    if api_key.startswith("$aact_prod_"):
        print("✓ API key type: PRODUCTION ($aact_prod_)")
        key_type = "production"
    elif api_key.startswith("$aact_test_"):
        print("⚠ API key type: SANDBOX/TEST ($aact_test_)")
        key_type = "sandbox"
    else:
        print("⚠ API key format may be incorrect (should start with $aact_ for Asaas)")
        key_type = "unknown"

    # 4. Check ASAAS_BASE_URL
    base_url = os.environ.get("ASAAS_BASE_URL", "")
    if not base_url:
        base_url = "https://api-sandbox.asaas.com/v3"
        print(f"✓ ASAAS_BASE_URL not set, using default sandbox: {base_url}")
        url_type = "sandbox"
    elif "production" in base_url or "api.asaas.com" in base_url:
        print(f"✓ ASAAS_BASE_URL set to PRODUCTION: {base_url}")
        url_type = "production"
    else:
        print(f"ℹ ASAAS_BASE_URL set to: {base_url}")
        url_type = "unknown"

    # 5. CRITICAL: Validate key type matches URL environment
    if key_type != "unknown" and url_type != "unknown":
        if key_type != url_type:
            print(f"\n✗ CRITICAL MISMATCH!")
            print(f"  Key type:  {key_type.upper()} ($aact_{key_type}_...)")
            print(f"  URL type:  {url_type.upper()} ({base_url})")
            print(f"\n  This is causing: 'invalid_environment' error!")
            print(f"  → ACTION: Make sure API_KEY and BASE_URL both match PRODUCTION or both SANDBOX")
            return False
        else:
            print(f"✓ Key and URL environment MATCH ({key_type.upper()})")

    # 6. Test HTTP connection
    try:
        import httpx
        print("\nTesting HTTP connectivity...")
        with httpx.Client(timeout=10) as client:
            # Try a simple request with auth header
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "access_token": api_key,
            }
            # Use a safe endpoint that requires auth: GET /customers with limit=1
            resp = client.get(
                f"{base_url}/customers",
                headers=headers,
                params={"limit": 1}
            )

            if resp.status_code == 200:
                print(f"✓ Successfully authenticated with Asaas API")
                data = resp.json()
                total = data.get("totalCount", "?")
                print(f"  → Account has {total} customer(s)")
                return True
            elif resp.status_code == 401:
                try:
                    body = resp.json()
                    errors = body.get("errors", [])
                    if errors:
                        error_code = errors[0].get('code', '')
                        error_desc = errors[0].get('description', 'Unknown')
                        print(f"✗ AUTHENTICATION FAILED (401)")
                        print(f"  → Error code: {error_code}")
                        print(f"  → Error: {error_desc}")

                        if error_code == "invalid_environment":
                            print(f"\n  This error means:")
                            print(f"    - You're using a {url_type.upper()} API key with a {url_type.upper()} URL")
                            print(f"    - OR the key configured in Render doesn't match the local key")
                except:
                    print(f"✗ AUTHENTICATION FAILED (401)")
                print("  → ACTION: Verify ASAAS_API_KEY is correct and environment matches")
                return False
            else:
                print(f"⚠ Unexpected response status: {resp.status_code}")
                print(f"  → Response: {resp.text}")
                return False
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        print("  → ACTION: Check internet connectivity and base URL")
        return False

if __name__ == "__main__":
    success = diagnose()
    print("\n" + "=" * 70)
    if success:
        print("✓ Asaas configuration is OK")
        sys.exit(0)
    else:
        print("✗ Asaas configuration has issues")
        print("\nNEXT STEPS:")
        print("1. Local development: Check .env file has ASAAS_API_KEY set")
        print("2. Render production: Set ASAAS_API_KEY in Render Environment Variables")
        print("   → Go to: https://dashboard.render.com → Select service → Environment")
        print("3. Verify the API key hasn't expired in Asaas console")
        sys.exit(1)
