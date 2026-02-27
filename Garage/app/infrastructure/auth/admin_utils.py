"""Shared admin authorization utilities.

Single source of truth for admin e-mail lookup.
Used by both auth_routes and admin_routes to prevent drift.
"""
import os


def configured_admin_emails() -> set[str]:
    """
    Return the set of normalized admin e-mails from environment variables.

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
