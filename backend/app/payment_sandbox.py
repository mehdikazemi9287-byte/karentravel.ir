"""Local sandbox payment gateway for QA/staging only (QA defect D6).

Enabled with PAYMENT_PROVIDER=sandbox and ONLY when ENVIRONMENT is
development/test/staging. In any other environment (production is the default
when ENVIRONMENT is unset) the configuration is refused loudly and the process
does not start.

The adapter mirrors ZarinPal's contract so the real return/verify code path in
main.py (signed JWT state, authority match, amount check, PaymentEvent
idempotency, trip/commerce side effects) is exercised unchanged:

    initiate -> redirect to /payments/sandbox/{authority}?state=...
             -> tester presses success / failure / cancel
             -> decision is recorded with an HMAC signature
             -> 303 to /payments/zarinpal/callback?state=&Authority=&Status=
             -> main verifies via adapter.execute("verify"), which only
                succeeds for a recorded, signature-valid "success" decision
                with the same amount.

Nothing here talks to a bank and every surface says so:
"درگاه آزمایشی — پرداخت واقعی نیست".
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import string
from typing import Any, Mapping
from urllib.parse import urlencode, urlparse

from .config import read_secret
from .providers import ProviderContext, ProviderError, ProviderHealth, RetryPolicy

SANDBOX_LABEL = "درگاه آزمایشی — پرداخت واقعی نیست"
SANDBOX_MODE = "sandbox_local"
SANDBOX_ENVIRONMENTS = frozenset({"development", "test", "staging"})
DECISION_SCOPE = "payment.sandbox.decision"
DECISIONS = {"success": "OK", "failure": "NOK", "cancel": "NOK"}
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
logger = logging.getLogger("karenseir.payment.sandbox")


def current_environment() -> str:
    # Same fail-closed default as main.ENVIRONMENT.
    return os.getenv("ENVIRONMENT", "production").strip().lower()


def sandbox_requested() -> bool:
    return os.getenv("PAYMENT_PROVIDER", "").strip().lower() == "sandbox"


def sandbox_environment_allowed(environment: str | None = None) -> bool:
    return (environment or current_environment()) in SANDBOX_ENVIRONMENTS


def is_sandbox_adapter(adapter: Any) -> bool:
    """True for the sandbox adapter itself or a ResilientAdapter wrapping it,
    and only while the environment still allows it."""
    inner = getattr(adapter, "adapter", adapter)
    return isinstance(inner, SandboxPaymentAdapter) and sandbox_environment_allowed()


def is_loopback_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and (parsed.hostname or "") in LOOPBACK_HOSTS and sandbox_environment_allowed()


def _signing_key() -> bytes:
    secret = read_secret("JWT_SECRET", "development-only-change-before-production")
    return hashlib.sha256(f"karenseir-payment-sandbox:{secret}".encode("utf-8")).digest()


def decision_signature(authority: str, payment_intent_id: str, amount: int, decision: str) -> str:
    return hmac.new(_signing_key(), f"{authority}:{payment_intent_id}:{int(amount)}:{decision}".encode("utf-8"), hashlib.sha256).hexdigest()


def sandbox_ref_id(authority: str) -> str:
    return "SANDBOX-TEST-" + hashlib.sha256(f"ref:{authority}".encode("utf-8")).hexdigest()[:16].upper()


def new_authority() -> str:
    alphabet = string.ascii_letters + string.digits
    return "A" + "".join(secrets.choice(alphabet) for _ in range(35))


def build_sandbox_adapter() -> "SandboxPaymentAdapter":
    environment = current_environment()
    if not sandbox_environment_allowed(environment):
        message = f"PAYMENT_PROVIDER=sandbox is forbidden when ENVIRONMENT={environment!r}; the sandbox gateway only runs in development/test/staging"
        logger.critical(message)
        raise RuntimeError(message)
    if os.getenv("ZARINPAL_MODE", "disabled") != "disabled":
        raise RuntimeError("PAYMENT_PROVIDER=sandbox cannot be combined with ZARINPAL_MODE; choose one payment adapter")
    adapter = SandboxPaymentAdapter(base_url=os.getenv("SANDBOX_PAYMENT_BASE_URL", "http://127.0.0.1:8000"))
    adapter.validate_configuration()
    logger.warning("payment_sandbox_enabled", extra={"environment": environment, "label": SANDBOX_LABEL})
    return adapter


class SandboxPaymentAdapter:
    """ZarinPal-shaped local test gateway. Never moves money; success is only
    reported after a human pressed the success button on the sandbox page."""

    key = "payment"
    mode = SANDBOX_MODE
    timeout_seconds = 5.0
    retry_policy = RetryPolicy(max_attempts=1)

    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url.strip().rstrip("/")

    def validate_configuration(self) -> None:
        if not sandbox_environment_allowed():
            raise RuntimeError("payment sandbox: forbidden outside development/test/staging")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"} or parsed.query:
            raise RuntimeError("payment sandbox: SANDBOX_PAYMENT_BASE_URL must be an explicit origin")
        if parsed.scheme == "http" and parsed.hostname not in LOOPBACK_HOSTS:
            raise RuntimeError("payment sandbox: plain HTTP is only allowed on loopback")

    def health(self) -> ProviderHealth:
        try:
            self.validate_configuration()
        except RuntimeError as exc:
            return ProviderHealth(status="configuration_error", mode=self.mode, detail=str(exc))
        return ProviderHealth(status="available", mode=self.mode, detail=f"TEST ONLY — {SANDBOX_LABEL}")

    def _fail(self, reason: str, context: ProviderContext) -> Mapping[str, Any]:
        return {"ok": False, "status": "failed", "provider": "sandbox", "test_mode": True, "reason": reason,
                "error": ProviderError(reason, f"Sandbox gateway: {reason}", False, context.correlation_id).__dict__}

    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        try:
            self.validate_configuration()
        except RuntimeError:
            return self._fail("sandbox_forbidden", context)
        amount = int(payload.get("amount", 0) or 0)
        if amount <= 0 or payload.get("currency") != "IRR":
            return self._fail("invalid_amount", context)
        if operation == "initiate":
            authority = new_authority()
            query = urlencode({"state": str(payload.get("callback_state", ""))})
            return {"ok": True, "status": "initiated", "provider": "sandbox", "test_mode": True, "label": SANDBOX_LABEL,
                    "reference": authority, "authority": authority,
                    "redirect_url": f"{self.base_url}/payments/sandbox/{authority}?{query}"}
        if operation == "verify":
            authority = str(payload.get("authority", ""))
            decision = self.read_decision(context.tenant_id, authority)
            if decision is None:
                return self._fail("no_decision", context)
            intent_id = str(payload.get("payment_intent_id", ""))
            expected = decision_signature(authority, intent_id, amount, "success")
            if decision.get("decision") != "success" or decision.get("payment_intent_id") != intent_id or int(decision.get("amount", -1)) != amount or not hmac.compare_digest(str(decision.get("signature", "")), expected):
                return self._fail("verify_rejected", context)
            return {"ok": True, "status": "verified", "provider": "sandbox", "test_mode": True, "already_verified": False,
                    "authority": authority, "ref_id": sandbox_ref_id(authority), "amount": amount}
        return self._fail("unsupported_operation", context)

    @staticmethod
    def read_decision(tenant_id: int, authority: str) -> dict | None:
        from sqlalchemy import select
        from .database import SessionLocal, set_tenant_context
        from .operations import IdempotencyKey
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            row = db.scalar(select(IdempotencyKey).where(IdempotencyKey.tenant_id == tenant_id, IdempotencyKey.scope == DECISION_SCOPE, IdempotencyKey.key == authority))
            if row is None:
                return None
            data = json.loads(row.response_json or "{}")
            data["signature"] = row.request_hash
            return data
