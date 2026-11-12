"""VandaPay (ونداپی) — «پرداخت با ونداپی» as an additional, fail-closed payment provider.

Owner decisions (VandaPay repo, docs/DECISIONS.md): D13 gateway on all group sites; D14 VandaPay has its
own server/domain, so the API base URL is configuration only (never hard-coded); D15 integrations are built
and tested now but stay OFF until the PSP contract and legal opinion exist.

Merchant API (VandaPay repo: docs/phase1/API.md, backend/openapi.yaml, integrations/README.md):
  POST /payment_intents            Idempotency-Key; {amount (integer rial), order_ref, return_url, metadata}
                                   -> {id, status, amount, currency, mode, checkout_url, ...}
  GET  /payment_intents/{id}       server-to-server truth (scoped to the key's mode)
  POST /payment_intents/{id}/cancel
  Webhook header ``VandaPay-Signature: t=<unix>,v1=<hex>``;
  v1 = hex(HMAC_SHA256(webhook_secret, t + "." + raw_body)); 300 s tolerance; any v1 may match (rotation).

Golden status rule: only ``succeeded`` (and later ``partially_refunded`` / ``refunded``) means money was
taken; ``failed`` / ``expired`` / ``canceled`` mean it was not; everything else — ``unknown`` and any status
we do not recognise included — is PENDING and is never shown or recorded as success.

Configuration (env only, nothing in code):
  VANDAPAY_ENABLED=1         feature flag; default OFF. Anything else -> disabled.
  VANDAPAY_API_BASE          https URL of the VandaPay API (e.g. https://<vandapay-domain>/api/v1). Required.
  VANDAPAY_SECRET_KEY        sk_test_… or sk_live_… (server only). Required.
  VANDAPAY_WEBHOOK_SECRET    webhook signing secret. Required.
  sk_live_ is refused outside ENVIRONMENT=production; sk_test_ is refused in production unless DEMO_MODE.

The HTTP transport is injectable so tests never touch the network.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

log = logging.getLogger("karenseir.vandapay")

PROVIDER_KEY = "vandapay"
LABEL = "پرداخت با ونداپی"
TEST_MODE_LABEL = "حالت آزمایشی ونداپی — پولی جابه‌جا نمی‌شود"
SIGNATURE_HEADER = "VandaPay-Signature"
WEBHOOK_TOLERANCE_SECONDS = 300

PAID_STATUSES = frozenset({"succeeded", "partially_refunded", "refunded"})
FAILED_STATUSES = frozenset({"failed", "expired", "canceled"})
CANCELLABLE_STATUSES = frozenset({"created", "requires_confirmation"})

# transport(method, url, headers, body_bytes_or_None, timeout) -> (http_status, parsed_json_dict)
Transport = Callable[[str, str, dict, Optional[bytes], float], "tuple[int, dict]"]


class VandaPayError(Exception):
    """Base error. ``transient`` = outcome unknown, retry later with the same Idempotency-Key."""

    def __init__(self, message: str, *, code: str = "vandapay_error", status: int = 0, transient: bool = False):
        super().__init__(message[:300])
        self.code = code
        self.status = status
        self.transient = transient


class WebhookSignatureError(Exception):
    """reason: malformed_header | timestamp_out_of_tolerance | signature_mismatch | malformed_body"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _urllib_transport(method: str, url: str, headers: dict, body: Optional[bytes], timeout: float) -> tuple[int, dict]:
    if not url.startswith("https://"):
        raise VandaPayError("VandaPay API URL must be https", code="insecure_url")
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https enforced above
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, (exc.read() or b"")
    except Exception as exc:  # network, TLS, timeout
        raise VandaPayError(f"vandapay unreachable: {exc.__class__.__name__}", code="unreachable", transient=True) from exc
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        parsed = {}
    return status, parsed if isinstance(parsed, dict) else {}


def key_mode(secret_key: str) -> str:
    if secret_key.startswith("sk_live_"):
        return "live"
    if secret_key.startswith("sk_test_"):
        return "test"
    raise ValueError("VANDAPAY_SECRET_KEY must start with sk_test_ or sk_live_")


@dataclass(frozen=True)
class VandaPayConfig:
    api_base: str
    secret_key: str
    webhook_secret: str
    mode: str  # "test" | "live"

    @property
    def is_test(self) -> bool:
        return self.mode == "test"


def config_from_env(environ: Mapping[str, str] = os.environ, *, environment: str = "development",
                    demo_mode: bool = False) -> Optional[VandaPayConfig]:
    """The configuration when VandaPay is switched ON and fully configured, else ``None`` (fail-closed)."""
    if str(environ.get("VANDAPAY_ENABLED", "")).strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    base = (environ.get("VANDAPAY_API_BASE") or "").strip().rstrip("/")
    key = (environ.get("VANDAPAY_SECRET_KEY") or "").strip()
    secret = (environ.get("VANDAPAY_WEBHOOK_SECRET") or "").strip()
    if not base or not key or not secret:
        log.error("VandaPay disabled: VANDAPAY_API_BASE, VANDAPAY_SECRET_KEY and VANDAPAY_WEBHOOK_SECRET are all required")
        return None
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname:
        log.error("VandaPay disabled: VANDAPAY_API_BASE must be an explicit https URL")
        return None
    try:
        mode = key_mode(key)
    except ValueError:
        log.error("VandaPay disabled: VANDAPAY_SECRET_KEY has an unknown prefix")
        return None
    if mode == "live" and environment != "production":
        log.error("VandaPay disabled: sk_live_ key refused outside production")
        return None
    if mode == "test" and environment == "production" and not demo_mode:
        log.error("VandaPay disabled: sk_test_ key refused in production (test money must never create real orders)")
        return None
    return VandaPayConfig(api_base=base, secret_key=key, webhook_secret=secret, mode=mode)


class VandaPayClient:
    def __init__(self, config: VandaPayConfig, *, transport: Optional[Transport] = None, timeout_seconds: float = 15.0):
        self.config = config
        self._send = transport or _urllib_transport
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, body: Optional[dict] = None, idempotency_key: Optional[str] = None) -> dict:
        headers = {"Authorization": f"Bearer {self.config.secret_key}", "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        status, parsed = self._send(method, self.config.api_base + path, headers, data, self.timeout_seconds)
        if 200 <= status < 300:
            return parsed
        if status == 429 or status >= 500:
            raise VandaPayError(f"vandapay temporary error HTTP {status}", code=f"http_{status}", status=status, transient=True)
        err = parsed.get("error") if isinstance(parsed.get("error"), dict) else {}
        raise VandaPayError(str(err.get("message") or f"vandapay HTTP {status}"), code=str(err.get("code") or f"http_{status}"), status=status)

    def create_intent(self, *, amount_rial: int, order_ref: str, return_url: str, metadata: dict,
                      idempotency_key: str, description: str = "", category: str = "") -> dict:
        if type(amount_rial) is not int or amount_rial <= 0:
            raise VandaPayError("amount must be a positive integer rial", code="invalid_amount")
        if not return_url.startswith("https://"):
            raise VandaPayError("return_url must be https", code="insecure_return_url")
        body: dict[str, Any] = {"amount": amount_rial, "order_ref": order_ref, "return_url": return_url, "metadata": metadata}
        if description:
            body["description"] = description[:200]
        if category:
            body["category"] = category
        res = self._request("POST", "/payment_intents", body, idempotency_key=idempotency_key)
        intent_id, url = res.get("id"), res.get("checkout_url")
        if not isinstance(intent_id, str) or not intent_id or not isinstance(url, str) or not url.startswith("https://"):
            raise VandaPayError("vandapay did not return an intent id and an https checkout_url", code="bad_response")
        if res.get("mode") != self.config.mode:
            raise VandaPayError("vandapay intent mode differs from the key mode", code="mode_mismatch")
        if res.get("amount") != amount_rial or res.get("currency", "IRR") != "IRR":
            raise VandaPayError("vandapay intent amount/currency differs from the order", code="amount_mismatch")
        return res

    def retrieve(self, intent_id: str) -> dict:
        if not intent_id or not isinstance(intent_id, str) or not re.fullmatch(r"[A-Za-z0-9_\-]{3,120}", intent_id):
            raise VandaPayError("invalid intent id", code="invalid_intent_id")
        return self._request("GET", f"/payment_intents/{urllib.parse.quote(intent_id, safe='')}")

    def cancel(self, intent_id: str, *, idempotency_key: str) -> dict:
        return self._request("POST", f"/payment_intents/{urllib.parse.quote(intent_id, safe='')}/cancel", {}, idempotency_key=idempotency_key)


def evaluate_intent(intent: Mapping[str, Any], *, expected_id: str, expected_amount_rial: int, mode: str,
                    expected_metadata: Optional[Mapping[str, str]] = None) -> tuple[str, str]:
    """Classify a server-fetched intent against OUR order. Returns (outcome, reason).

    outcome is one of: "paid" (all checks pass), "failed" (money not taken), "pending" (not final — incl.
    unknown), "mismatch" (does not belong to / match this order; never paid).
    """
    if intent.get("id") != expected_id:
        return "mismatch", "reference_mismatch"
    if intent.get("mode") != mode:
        return "mismatch", "mode_mismatch"
    meta = intent.get("metadata") if isinstance(intent.get("metadata"), dict) else {}
    for k, v in (expected_metadata or {}).items():
        if str(meta.get(k)) != str(v):
            return "mismatch", f"metadata_mismatch:{k}"
    status = intent.get("status")
    if status in FAILED_STATUSES:
        return "failed", f"status_{status}"
    if status in ("partially_refunded", "refunded"):
        return "mismatch", "refunded_before_fulfilment"
    if status != "succeeded":
        return "pending", f"status_{status}"
    amount = intent.get("amount")
    if type(amount) is not int or amount != int(expected_amount_rial) or intent.get("currency") != "IRR":
        return "mismatch", "amount_mismatch"
    if int(intent.get("refunded_amount") or 0) != 0:
        return "mismatch", "refunded_before_fulfilment"
    return "paid", "ok"


_TS_RE = re.compile(r"^\d{1,12}$")


def compute_signature(secret: str, timestamp: int, raw_body: bytes | str) -> str:
    body = raw_body.encode("utf-8") if isinstance(raw_body, str) else bytes(raw_body)
    msg = str(int(timestamp)).encode("ascii") + b"." + body
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_signature(raw_body: bytes | str, header: Optional[str], secret: str, *,
                     tolerance_seconds: int = WEBHOOK_TOLERANCE_SECONDS, now: Optional[int] = None) -> int:
    """Same rules as the VandaPay SDKs (shared test vectors). Returns the signed timestamp or raises."""
    if not secret:
        raise WebhookSignatureError("signature_mismatch")
    if not header or not isinstance(header, str):
        raise WebhookSignatureError("malformed_header")
    ts, sigs = None, []
    for part in header.split(","):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if key == "t":
            if not _TS_RE.match(value):
                raise WebhookSignatureError("malformed_header")
            ts = int(value)
        elif key == "v1" and value:
            sigs.append(value)
    if ts is None or not sigs:
        raise WebhookSignatureError("malformed_header")
    current = int(time.time()) if now is None else int(now)
    if abs(current - ts) > tolerance_seconds:
        raise WebhookSignatureError("timestamp_out_of_tolerance")
    expected = compute_signature(secret, ts, raw_body).encode("ascii")
    ok = False
    for s in sigs:  # every v1 is checked (no early exit)
        if hmac.compare_digest(expected, s.encode("utf-8")):
            ok = True
    if not ok:
        raise WebhookSignatureError("signature_mismatch")
    return ts


def parse_event(raw_body: bytes, header: Optional[str], secret: str, *, now: Optional[int] = None) -> dict:
    verify_signature(raw_body, header, secret, now=now)
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise WebhookSignatureError("malformed_body") from exc
    if not isinstance(event, dict):
        raise WebhookSignatureError("malformed_body")
    return event


def intent_id_of_event(event: Mapping[str, Any]) -> Optional[str]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    etype = str(event.get("type") or "")
    raw = data.get("id") if etype.startswith("payment_intent.") else (data.get("intent_id") or data.get("payment_intent"))
    return raw if isinstance(raw, str) and raw else None
