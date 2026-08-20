from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import FrozenSet


ROLE_PERMISSIONS: dict[str, FrozenSet[str]] = {
    "employee": frozenset({"reservation:read", "reservation:create", "reservation:manage", "trip:read"}),
    "customer": frozenset({"reservation:read", "reservation:create", "reservation:manage", "trip:read"}),
    "manager": frozenset({"reservation:read", "approval:decide", "trip:read"}),
    "welfare_manager": frozenset({"reservation:read", "approval:decide", "credit:read", "trip:read"}),
    "organization_admin": frozenset({"reservation:read", "approval:decide", "credit:manage", "member:manage", "trip:read"}),
    "agency_partner": frozenset({"inventory:read", "reservation:fulfill", "agency:manage", "credit:read"}),
    "supplier": frozenset({"inventory:manage", "reservation:fulfill"}),
    "backoffice_expert": frozenset({"reservation:read", "reservation:manage", "approval:decide", "support:manage", "trip:event:create", "backoffice:read"}),
    "finance_operator": frozenset({"credit:read", "ledger:read", "settlement:manage", "refund:manage", "approval:decide"}),
    "tenant_admin": frozenset({"tenant:manage", "member:manage", "reservation:read", "credit:manage", "backoffice:read"}),
    "platform_admin": frozenset({"platform:manage"}),
}


def role_has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, frozenset())
    return permission in permissions or "platform:manage" in permissions


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("password must be at least 10 characters")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return "pbkdf2_sha256$600000$" + base64.urlsafe_b64encode(salt).decode("ascii") + "$" + base64.urlsafe_b64encode(digest).decode("ascii")


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, cost, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256" or cost != "600000":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def opaque_reference(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(18)}"
