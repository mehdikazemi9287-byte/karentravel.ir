"""Real SMS/OTP delivery transport via Kavenegar's Verify/Lookup API.

Mirrors the existing single-purpose external-adapter pattern already used
for payment/hotel (see ZarinPalAdapter in providers.py, GRSAdapter in
grs_adapter.py): one small class implementing the same IntegrationAdapter
shape (key/mode/timeout_seconds/retry_policy/validate_configuration/
health/execute), so it plugs into the existing configured_adapter() +
ResilientAdapter (rate-limit/circuit-breaker/timeout/retry) wrapping
without any change to that machinery.

KarenSeir remains the sole source of truth for the OTP code, its expiry,
and its verification (backend/app/main.py's request_otp/verify_otp are
unchanged) -- this adapter is transport only: it takes an already-
generated code and a destination and either genuinely delivers it via
Kavenegar or fails closed. It never invents a code, never accepts one,
and never reports success without a real 200/status-200 response from
Kavenegar.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .providers import ProviderContext, ProviderError, ProviderHealth, RetryPolicy

# Iranian mobile numbers: 09xxxxxxxxx, +989xxxxxxxxx, 00989xxxxxxxxx, or
# 989xxxxxxxxx -- exactly the formats the integration brief specifies (plus
# the equally-standard "00" international-dialing spelling of "+"). The
# subscriber part is always 9 digits after the leading "9". Anything else
# is rejected outright, never coerced/guessed.
_IRAN_MOBILE_RE = re.compile(r"^(?:\+98|0098|98|0)9(\d{9})$")

# Kavenegar's own documented Verify/Lookup status codes that map to a
# specific, actionable KarenSeir-side error rather than a generic one.
_KAVENEGAR_ERROR_CODES: dict[int, str] = {
    404: "unknown_method",
    405: "method_not_allowed",
    418: "insufficient_credit",
    424: "template_unavailable",
    426: "account_service_unavailable",
    401: "authentication_error",   # account/API key not active
    403: "authentication_error",   # invalid API key
    412: "authentication_error",   # sender/account not verified for this template
    411: "invalid_receptor",       # receptor is invalid
    414: "rate_limited",           # daily/character send limit reached
    415: "rate_limited",           # send limit exceeded
}


@dataclass(frozen=True)
class KavenegarResult:
    ok: bool
    status: str
    reason: str | None = None
    reference: str = ""


def normalize_iranian_mobile(raw: str) -> str | None:
    """Returns the exact receptor format Kavenegar's API expects
    (989xxxxxxxxx -- no "+", no leading "0"), or None if `raw` is not a
    well-formed Iranian mobile number. Never guesses a fallback."""
    if not raw:
        return None
    digits = re.sub(r"[\s\-()]", "", raw.strip()).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    match = _IRAN_MOBILE_RE.fullmatch(digits)
    if not match:
        return None
    return "989" + match.group(1)


class KavenegarSmsOtpProvider:
    """key/mode/timeout_seconds/retry_policy + validate_configuration/
    health/execute -- the same shape ResilientAdapter already wraps every
    other provider with, so rate-limiting, circuit-breaking, per-call
    timeout and retry are inherited for free (sec 13/11 of the brief) and
    are not reimplemented here."""

    key = "otp"
    mode = "kavenegar"
    retry_policy = RetryPolicy(max_attempts=1)  # Verify/Lookup has no guaranteed send idempotency.

    def __init__(self, *, api_key: str, template: str, sender: str = "", timeout_seconds: float = 8.0) -> None:
        # Read-only references to whatever the caller (configured_adapter)
        # resolved from the environment -- this class never reads env vars
        # itself, so it can be unit-tested with fixture values only.
        self.api_key = (api_key or "").strip()
        self.template = (template or "").strip()
        self.sender = (sender or "").strip()
        self.timeout_seconds = timeout_seconds

    def validate_configuration(self) -> None:
        if not self.api_key:
            raise RuntimeError("kavenegar: KAVENEGAR_API_KEY is not configured")
        if not self.template:
            raise RuntimeError("kavenegar: KAVENEGAR_OTP_TEMPLATE is not configured")

    def health(self) -> ProviderHealth:
        try:
            self.validate_configuration()
        except RuntimeError as exc:
            return ProviderHealth(status="not_connected", mode=self.mode, detail=str(exc))
        return ProviderHealth(status="configured_not_verified", mode=self.mode, detail="Kavenegar Verify/Lookup credentials configured; no send is claimed")

    def _error(self, code: str, message: str, *, retryable: bool, context: ProviderContext, operation: str) -> Mapping[str, Any]:
        return {
            "ok": False, "status": "not_sent", "provider": "kavenegar", "operation": operation,
            "correlation_id": context.correlation_id, "idempotency_key": context.idempotency_key,
            "reason": code,
            "error": ProviderError(code=code, message=message, retryable=retryable, correlation_id=context.correlation_id).__dict__,
        }

    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        # validate_configuration() is called explicitly (not left to raise
        # into ResilientAdapter's generic catch-all) so a missing/invalid
        # key is reported as the precise "invalid_configuration" reason,
        # matching the ZarinPalAdapter convention already in this file.
        try:
            self.validate_configuration()
        except RuntimeError as exc:
            return self._error("invalid_configuration", str(exc), retryable=False, context=context, operation=operation)

        if operation != "send_otp":
            return self._error("unsupported_operation", "Kavenegar adapter only supports send_otp", retryable=False, context=context, operation=operation)

        code = str(payload.get("code", ""))
        if not code:
            return self._error("missing_code", "No OTP code was supplied to the transport", retryable=False, context=context, operation=operation)

        receptor = normalize_iranian_mobile(str(payload.get("destination_reference", "")))
        if receptor is None:
            return self._error("invalid_receptor", "Destination is not a valid Iranian mobile number", retryable=False, context=context, operation=operation)

        # Real Kavenegar Verify/Lookup call. KarenSeir generated `code`
        # already (sec 8) -- this is delivery only, never generation.
        params = {"receptor": receptor, "token": code, "template": self.template}
        url = f"https://api.kavenegar.com/v1/{self.api_key}/verify/lookup.json"
        request = Request(url, data=urlencode(params).encode("utf-8"), headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed Kavenegar host
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return self._map_http_error(exc, context, operation)
        except URLError as exc:
            # DNS failure, connection refused, TLS error, read timeout --
            # ResilientAdapter would also catch an uncaught exception here
            # the same way, but returning explicitly keeps the reason
            # precise instead of the generic transport-error fallback.
            return self._error("provider_unreachable", "Kavenegar transport unavailable", retryable=True, context=context, operation=operation)
        except (ValueError, TimeoutError) as exc:
            return self._error("provider_timeout" if isinstance(exc, TimeoutError) else "provider_invalid_response",
                                "Kavenegar request timed out" if isinstance(exc, TimeoutError) else "Kavenegar returned a non-JSON response",
                                retryable=True, context=context, operation=operation)

        result = (body.get("return") or {}) if isinstance(body, Mapping) else {}
        result = result if isinstance(result, Mapping) else {}
        status_code = result.get("status")
        if status_code == 200:
            entries = body.get("entries") if isinstance(body, Mapping) else None
            entry = entries[0] if isinstance(entries, list) and entries else {}
            if not isinstance(entry, Mapping) or isinstance(entry.get("messageid"), bool) or not str(entry.get("messageid", "")).isdigit() or int(str(entry.get("messageid", "0"))) <= 0:
                return self._error("provider_invalid_response", "Kavenegar response has no valid message reference", retryable=False, context=context, operation=operation)
            return {
                "ok": True, "status": "sent", "provider": "kavenegar", "operation": operation,
                "correlation_id": context.correlation_id, "idempotency_key": context.idempotency_key,
                "reference": str(entry.get("messageid", "")),
            }
        reason = _KAVENEGAR_ERROR_CODES.get(status_code, "provider_rejected")
        return self._error(reason, f"Kavenegar rejected the request ({reason})",
                            retryable=reason == "rate_limited", context=context, operation=operation)

    def _map_http_error(self, exc: HTTPError, context: ProviderContext, operation: str) -> Mapping[str, Any]:
        reason = _KAVENEGAR_ERROR_CODES.get(exc.code, "provider_rejected")
        retryable = exc.code >= 500 or reason == "rate_limited"
        return self._error(reason, f"Kavenegar HTTP {exc.code} ({reason})", retryable=retryable, context=context, operation=operation)
