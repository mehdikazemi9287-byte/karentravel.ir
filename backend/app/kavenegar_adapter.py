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
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .providers import ProviderContext, ProviderError, ProviderHealth, RetryPolicy

# Iranian mobile numbers: 09xxxxxxxxx, +989xxxxxxxxx, 00989xxxxxxxxx, or
# 989xxxxxxxxx -- exactly the formats the integration brief specifies (plus
# the equally-standard "00" international-dialing spelling of "+"). The
# subscriber part is always 9 digits after the leading "9". Anything else
# is rejected outright, never coerced/guessed.
_IRAN_MOBILE_RE = re.compile(r"^(?:\+98|0098|98|0)9(\d{9})$")

# Kavenegar return-status codes (the same number is used as the HTTP status
# of an error response, with a JSON body whose return.status repeats it).
# Each maps to a precise KarenSeir-side reason instead of a generic one.
# Earlier versions mapped 414/415 to "rate_limited" and 412 to an auth
# error; in Kavenegar's table 414 is "too many records in one request",
# 415 is "start index out of range" and 412 is "invalid sender line", so
# those were misreported (and 414/415 were retried as if transient).
_KAVENEGAR_ERROR_CODES: dict[int, str] = {
    400: "provider_bad_request",        # parameters incomplete
    401: "authentication_error",        # account disabled
    402: "provider_rejected",           # operation failed
    403: "authentication_error",        # API key invalid
    404: "unknown_method",              # URL path matches no method (e.g. empty key in the path)
    405: "method_not_allowed",          # GET/POST not accepted for this method
    406: "provider_bad_request",        # required parameter empty
    407: "access_denied",               # blocked by the account's security (IP) settings
    409: "provider_busy",               # server could not answer; try later
    411: "invalid_receptor",            # receptor is invalid
    412: "invalid_sender",              # sender line is invalid
    413: "provider_bad_request",        # message empty or too long
    414: "provider_bad_request",        # too many records in one request
    415: "provider_bad_request",        # start index out of range
    417: "provider_bad_request",        # invalid date
    418: "insufficient_credit",
    419: "provider_bad_request",        # array lengths differ
    422: "invalid_token",               # invalid characters in the data
    424: "template_unavailable",        # template not found / not approved
    426: "account_service_unavailable", # method needs an upgraded service plan
    431: "invalid_token",               # code/token structure is invalid
    432: "template_token_missing",      # template text has no %token placeholder
    451: "rate_limited",                # too many calls in a short window
    501: "owner_only_test_account",     # test account: only the owner's own number receives SMS
}
_RETRYABLE_REASONS = frozenset({"rate_limited", "provider_busy"})
# Failures that are about one request/recipient, not about Kavenegar's
# health. They are flagged client_error so ResilientAdapter's tenant-wide
# circuit breaker does not open on them -- otherwise five bad numbers (or
# five legacy accounts without a mobile) in a minute would block OTP for
# every user of the tenant for the circuit period.
_CLIENT_ERROR_REASONS = frozenset({
    "invalid_receptor", "missing_code", "unsupported_operation",
    "owner_only_test_account", "recipient_undeliverable",
})
# entries[].status values that mean the message will not reach the
# recipient even though return.status is 200 (6 failed, 11 undelivered,
# 13 cancelled, 14 blocked by recipient, 100 invalid message id).
_FAILED_ENTRY_STATUSES = frozenset({6, 11, 13, 14, 100})

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
# Whitespace, dashes, brackets, plus the invisible bidi/zero-width marks a
# Persian keyboard or a copy from a contact card often inserts.
_PHONE_NOISE_RE = re.compile(r"[\s\-()\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def normalize_digits(value: str) -> str:
    """Persian/Arabic-Indic digits -> ASCII digits; everything else unchanged."""
    return (value or "").translate(_DIGIT_MAP)


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
    digits = normalize_digits(_PHONE_NOISE_RE.sub("", raw.strip()))
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
            "client_error": code in _CLIENT_ERROR_REASONS,
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
        url = f"https://api.kavenegar.com/v1/{quote(self.api_key, safe='')}/verify/lookup.json"
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
            entry_status = entry.get("status")
            if isinstance(entry_status, int) and not isinstance(entry_status, bool) and entry_status in _FAILED_ENTRY_STATUSES:
                # Accepted by the API but already known not to reach the
                # recipient -- never reported as sent.
                return self._error("recipient_undeliverable", f"Kavenegar message status {entry_status}", retryable=False, context=context, operation=operation)
            return {
                "ok": True, "status": "sent", "provider": "kavenegar", "operation": operation,
                "correlation_id": context.correlation_id, "idempotency_key": context.idempotency_key,
                "reference": str(entry.get("messageid", "")),
            }
        reason = _KAVENEGAR_ERROR_CODES.get(status_code, "provider_rejected")
        return self._error(reason, f"Kavenegar rejected the request ({reason})",
                            retryable=reason in _RETRYABLE_REASONS, context=context, operation=operation)

    def _map_http_error(self, exc: HTTPError, context: ProviderContext, operation: str) -> Mapping[str, Any]:
        # Kavenegar answers errors with an HTTP status equal to its own
        # return.status and a JSON body; prefer the body's code when it is
        # readable, fall back to the HTTP status otherwise.
        status_code = exc.code
        try:
            body = json.loads(exc.read().decode("utf-8"))
            body_status = (body.get("return") or {}).get("status") if isinstance(body, Mapping) else None
            if isinstance(body_status, int) and not isinstance(body_status, bool):
                status_code = body_status
        except Exception:  # noqa: BLE001 - unreadable body: keep the HTTP status
            pass
        reason = _KAVENEGAR_ERROR_CODES.get(status_code, "provider_rejected")
        # An unmapped 5xx is a transient server fault; a mapped code (e.g. 501) keeps its own meaning.
        retryable = reason in _RETRYABLE_REASONS or (exc.code >= 500 and status_code not in _KAVENEGAR_ERROR_CODES)
        return self._error(reason, f"Kavenegar HTTP {exc.code} ({reason})", retryable=retryable, context=context, operation=operation)
