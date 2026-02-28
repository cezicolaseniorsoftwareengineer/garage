"""Shared admin authorization utilities.

Single source of truth for admin username/e-mail lookup.
Used by both auth_routes and admin_routes to prevent drift.

Primary check: ADMIN_USERNAME (case-insensitive username match).
Legacy fallback: ADMIN_EMAIL / ADMIN_EMAILS (e-mail match).
"""
import os


# ---------------------------------------------------------------------------
# Username-based (primary) admin check
# ---------------------------------------------------------------------------

def configured_admin_usernames() -> set[str]:
    """Return the set of normalized admin usernames from environment variables.

    Env var:
        ADMIN_USERNAME  – single admin username (case-insensitive)
    """
    usernames: set[str] = set()
    primary = os.environ.get("ADMIN_USERNAME", "").strip().lower()
    if primary:
        usernames.add(primary)
    return usernames


def is_admin_username(username: str | None) -> bool:
    """Return True if *username* is a configured admin account."""
    if not username:
        return False
    return username.strip().lower() in configured_admin_usernames()


# ---------------------------------------------------------------------------
# E-mail-based (legacy fallback) admin check
# ---------------------------------------------------------------------------

def configured_admin_emails() -> set[str]:
    """Return the set of normalized admin e-mails from environment variables.

    Env vars:
        ADMIN_EMAIL   – primary admin e-mail (single value)
        ADMIN_EMAILS  – comma-separated list of additional admin e-mails
    """
    emails: set[str] = set()

    primary = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if primary:
        emails.add(primary)

    aliases = os.environ.get("ADMIN_EMAILS", "").strip()
    if aliases:
        for item in aliases.split(","):
            value = item.strip().lower()
            if value:
                emails.add(value)

    return emails


def is_admin_email(email: str | None) -> bool:
    """Return True if *email* belongs to a configured admin account."""
    if not email:
        return False
    return email.strip().lower() in configured_admin_emails()
