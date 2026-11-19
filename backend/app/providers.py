from __future__ import annotations

import os
import time
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from .config import read_secret


@dataclass(frozen=True)
class ProviderContext:
    tenant_id: int
    correlation_id: str
    idempotency_key: str


@dataclass(frozen=True)
class ProviderHealth:
    status: str
    mode: str
    detail: str


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0


@dataclass(frozen=True)
class ProviderError:
    code: str
    message: str
    retryable: bool
    correlation_id: str


class IntegrationAdapter(Protocol):
    key: str
    mode: str
    timeout_seconds: float
    retry_policy: RetryPolicy

    def validate_configuration(self) -> None: ...
    def health(self) -> ProviderHealth: ...
    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]: ...


class DisabledMockAdapter:
    """Provider-neutral fail-closed adapter; it never simulates successful external work."""

    def __init__(self, key: str, *, mode: str = "mock", timeout_seconds: float = 5.0, retry_policy: RetryPolicy = RetryPolicy()) -> None:
        self.key = key
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy

    def validate_configuration(self) -> None:
        if self.mode not in {"mock", "disabled"}:
            raise RuntimeError(f"{self.key}: real mode requires an authorized adapter and credentials")

    def health(self) -> ProviderHealth:
        return ProviderHealth(status="not_connected", mode=self.mode, detail="No authorized external connection")

    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        self.validate_configuration()
        return {
            "ok": False,
            "status": "not_sent",
            "provider": self.key,
            "operation": operation,
            "correlation_id": context.correlation_id,
            "reason": "external_provider_not_configured",
            "error": ProviderError(code="external_provider_not_configured", message="Authorized external connection is unavailable", retryable=False, correlation_id=context.correlation_id).__dict__,
            "idempotency_key": context.idempotency_key,
        }


class SandboxAdapter(DisabledMockAdapter):
    """Validated sandbox configuration that still fails closed without a concrete transport."""

    def __init__(self, key: str, *, endpoint: str, secret_reference: str) -> None:
        super().__init__(key, mode="sandbox")
        self.endpoint = endpoint
        self.secret_reference = secret_reference

    def validate_configuration(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise RuntimeError(f"{self.key}: sandbox endpoint must be explicit HTTPS")
        if not self.secret_reference.startswith(("vault://", "aws-sm://", "gcp-sm://", "azure-kv://")):
            raise RuntimeError(f"{self.key}: sandbox requires a secret-manager reference")

    def health(self) -> ProviderHealth:
        self.validate_configuration()
        return ProviderHealth(status="configured_not_connected", mode=self.mode, detail="Sandbox contract validated; transport disabled")

    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        self.validate_configuration()
        result = {
            "ok": False, "status": "not_sent", "provider": self.key, "operation": operation,
            "correlation_id": context.correlation_id, "idempotency_key": context.idempotency_key,
            "reason": "sandbox_transport_not_configured",
            "error": ProviderError(code="sandbox_transport_not_configured", message="Validated sandbox has no authorized transport", retryable=False, correlation_id=context.correlation_id).__dict__,
        }
        return result


class OTPAdapter(DisabledMockAdapter):
    def send_code(self, destination_reference: str, code: str, context: ProviderContext) -> Mapping[str, Any]:
        return self.execute("send_otp", {"destination_reference": destination_reference, "code": code}, context)


class NotificationAdapter(DisabledMockAdapter):
    def deliver(self, channel: str, notification_id: str, context: ProviderContext) -> Mapping[str, Any]:
        return self.execute(f"deliver_{channel}", {"notification_id": notification_id}, context)


class VandaPayTransport(Protocol):
    def request(self, method: str, url: str, headers: Mapping[str, str], payload: Mapping[str, Any] | None, timeout_seconds: float) -> tuple[int, Mapping[str, Any]]: ...


class VandaPayHttpTransport:
    def request(self, method: str, url: str, headers: Mapping[str, str], payload: Mapping[str, Any] | None, timeout_seconds: float) -> tuple[int, Mapping[str, Any]]:
        from urllib.error import HTTPError
        data = json.dumps(dict(payload)).encode("utf-8") if payload is not None else None
        req = Request(url, data=data, headers=dict(headers), method=method)
        try:
            with urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310 - base URL is operator configuration, HTTPS enforced
                return response.status, json.loads(response.read().decode("utf-8") or "{}")
        except HTTPError as exc:
            try: body = json.loads(exc.read().decode("utf-8") or "{}")
            except ValueError: body = {}
            return exc.code, body


class VandaPayAdapter:
    """VandaPay Payment Intents (hosted checkout). Server-side only; the secret key never reaches the browser.

    Success is decided only by a server-side GET of the intent (status == "succeeded", same amount and order_ref),
    never by the browser return or by an unsigned message. See vandapay docs/integration-plans/karenseir.md.
    """
    key = "payment"
    provider = "vandapay"
    retry_policy = RetryPolicy(max_attempts=1)
    PAID = {"succeeded"}
    PENDING = {"created", "requires_confirmation", "processing", "card_pending", "unknown"}
    FAILED = {"failed", "canceled", "cancelled", "expired"}

    def __init__(self, *, mode: str, secret_key: str, base_url: str, return_url: str, category: str = "travel", transport: VandaPayTransport | None = None, timeout_seconds: float = 10.0) -> None:
        self.mode = mode
        self.secret_key = secret_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.return_url = return_url.strip()
        self.category = category.strip() or "travel"
        self.transport = transport or VandaPayHttpTransport()
        self.timeout_seconds = timeout_seconds

    def validate(self) -> None:
        if self.mode not in {"test", "live"}: raise RuntimeError("vandapay: mode must be test or live")
        prefix = "sk_test_" if self.mode == "test" else "sk_live_"
        if not self.secret_key.startswith(prefix) or len(self.secret_key) < len(prefix) + 8: raise RuntimeError(f"vandapay: secret key must start with {prefix}")
        for name, value in (("base URL", self.base_url), ("return URL", self.return_url)):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.hostname: raise RuntimeError(f"vandapay: {name} must be explicit HTTPS")

    def health(self) -> ProviderHealth:
        try: self.validate()
        except RuntimeError as exc: return ProviderHealth(status="configuration_error", mode=self.mode, detail=str(exc))
        return ProviderHealth(status="configured_not_verified", mode=self.mode, detail="VandaPay credentials configured; no payment is claimed until server-side verification")

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json", "Accept": "application/json"}
        if idempotency_key: headers["Idempotency-Key"] = idempotency_key[:120]
        return headers

    def _fail(self, status: str, reason: str, message: str, context: ProviderContext, retryable: bool = False) -> Mapping[str, Any]:
        return {"ok": False, "status": status, "provider": "vandapay", "reason": reason, "error": ProviderError(reason, message, retryable, context.correlation_id).__dict__}

    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        try: self.validate()
        except RuntimeError as exc: return self._fail("not_sent", "invalid_configuration", str(exc), context)
        amount = int(payload.get("amount") or 0)
        if amount <= 0 or payload.get("currency") != "IRR": return self._fail("not_sent", "invalid_amount", "Positive IRR amount is required", context)
        if operation == "initiate":
            state = str(payload.get("callback_state", ""))
            sep = "&" if "?" in self.return_url else "?"
            body = {"amount": amount, "order_ref": str(payload["payment_intent_id"]), "return_url": f"{self.return_url}{sep}state={state}", "category": str(payload.get("category") or self.category), "description": str(payload.get("description") or "رزرو کارن تراول")[:140], "metadata": {"karenseir_payment_intent_id": str(payload["payment_intent_id"]), "tenant_id": context.tenant_id}}
            try: code, data = self.transport.request("POST", f"{self.base_url}/payment_intents", self._headers(context.idempotency_key), body, self.timeout_seconds)
            except Exception: return self._fail("unknown", "transport_error", "VandaPay unreachable; outcome unknown — reuse the same Idempotency-Key", context, True)
            intent_id = str(data.get("id", "")); checkout = str(data.get("checkout_url", ""))
            if code not in {200, 201} or not intent_id or urlparse(checkout).scheme != "https" or int(data.get("amount", 0)) != amount:
                return self._fail("failed", "request_rejected", "VandaPay rejected the payment intent", context)
            return {"ok": True, "status": "initiated", "provider": "vandapay", "reference": intent_id, "authority": intent_id, "redirect_url": checkout, "expires_at": data.get("expires_at")}
        if operation == "verify":
            authority = str(payload.get("authority", ""))
            if not re.fullmatch(r"[A-Za-z0-9_\-]{6,160}", authority): return self._fail("failed", "authority_mismatch", "VandaPay intent id is invalid", context)
            try: code, data = self.transport.request("GET", f"{self.base_url}/payment_intents/{authority}", self._headers(), None, self.timeout_seconds)
            except Exception: return self._fail("unknown", "transport_error", "VandaPay unreachable", context, True)
            if code != 200 or str(data.get("id")) != authority: return self._fail("failed", "verify_rejected", "VandaPay intent lookup failed", context)
            if str(data.get("order_ref")) != str(payload.get("payment_intent_id")) or int(data.get("amount", 0)) != amount: return self._fail("failed", "amount_or_reference_mismatch", "VandaPay intent does not match this payment", context)
            remote = str(data.get("status", ""))
            if remote in self.PAID: return {"ok": True, "status": "verified", "provider": "vandapay", "authority": authority, "ref_id": authority, "amount": amount, "remote_status": remote}
            if remote in self.FAILED: return {"ok": False, "status": "failed", "provider": "vandapay", "reason": "payment_failed", "remote_status": remote}
            return {"ok": False, "status": "pending", "provider": "vandapay", "reason": "payment_pending", "remote_status": remote}
        if operation == "cancel":
            authority = str(payload.get("authority", ""))
            try: code, data = self.transport.request("POST", f"{self.base_url}/payment_intents/{authority}/cancel", self._headers(context.idempotency_key), {}, self.timeout_seconds)
            except Exception: return self._fail("unknown", "transport_error", "VandaPay unreachable", context, True)
            return {"ok": code == 200, "status": str(data.get("status", "unknown")), "provider": "vandapay"}
        return self._fail("not_sent", "unsupported_operation", "Unsupported operation", context)


def vandapay_webhook_event(raw_body: bytes, header: str | None, secret: str, tolerance_seconds: int = 300, now: int | None = None) -> Mapping[str, Any]:
    """Verify ``VandaPay-Signature: t=<unix>,v1=<hex>`` (HMAC-SHA256 of f"{t}.{raw_body}") and return the event. Raises ValueError."""
    import hashlib, hmac, time as _time
    if not secret: raise ValueError("webhook secret is not configured")
    ts, sigs = None, []
    for part in (header or "").split(","):
        k, _, v = part.partition("="); k, v = k.strip(), v.strip()
        if k == "t" and re.fullmatch(r"\d{1,12}", v): ts = int(v)
        elif k == "v1" and v: sigs.append(v)
    if ts is None or not sigs: raise ValueError("malformed signature header")
    current = int(_time.time()) if now is None else now
    if abs(current - ts) > tolerance_seconds: raise ValueError("timestamp outside tolerance")
    expected = hmac.new(secret.encode("utf-8"), str(ts).encode("ascii") + b"." + raw_body, hashlib.sha256).hexdigest()
    ok = False
    for sig in sigs:
        if hmac.compare_digest(expected.encode("ascii"), sig.encode("utf-8")): ok = True
    if not ok: raise ValueError("signature mismatch")
    event = json.loads(raw_body.decode("utf-8"))
    if not isinstance(event, dict) or not event.get("id") or not str(event.get("type", "")).startswith("payment_intent."): raise ValueError("unsupported event")
    return event


class ZarinPalTransport(Protocol):
    def post_json(self, url: str, payload: Mapping[str, Any], timeout_seconds: float) -> Mapping[str, Any]: ...


class ZarinPalHttpTransport:
    def post_json(self, url: str, payload: Mapping[str, Any], timeout_seconds: float) -> Mapping[str, Any]:
        request = Request(url, data=json.dumps(dict(payload)).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - endpoints are fixed by mode
            return json.loads(response.read().decode("utf-8"))


class ZarinPalAdapter:
    key = "payment"
    retry_policy = RetryPolicy(max_attempts=2)

    def __init__(self, *, mode: str, merchant_id: str, callback_url: str, transport: ZarinPalTransport | None = None, timeout_seconds: float = 8.0) -> None:
        self.mode = mode
        self.merchant_id = merchant_id.strip()
        self.callback_url = callback_url.strip()
        self.transport = transport or ZarinPalHttpTransport()
        self.timeout_seconds = timeout_seconds

    @property
    def api_base(self) -> str:
        return "https://sandbox.zarinpal.com/pg/v4/payment" if self.mode == "sandbox" else "https://payment.zarinpal.com/pg/v4/payment"

    @property
    def redirect_base(self) -> str:
        return "https://sandbox.zarinpal.com/pg/StartPay" if self.mode == "sandbox" else "https://www.zarinpal.com/pg/StartPay"

    def validate_configuration(self) -> None:
        if self.mode not in {"sandbox", "production"}: raise RuntimeError("zarinpal: mode must be sandbox or production")
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", self.merchant_id): raise RuntimeError("zarinpal: merchant id is missing or invalid")
        parsed = urlparse(self.callback_url)
        if parsed.scheme != "https" or not parsed.hostname: raise RuntimeError("zarinpal: callback URL must be explicit HTTPS")

    def health(self) -> ProviderHealth:
        try: self.validate_configuration()
        except RuntimeError as exc: return ProviderHealth(status="configuration_error", mode=self.mode, detail=str(exc))
        return ProviderHealth(status="configured_not_verified", mode=self.mode, detail="Credentials configured; no purchase is claimed")

    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        try: self.validate_configuration()
        except RuntimeError as exc: return {"ok": False, "status": "not_sent", "provider": "zarinpal", "reason": "invalid_configuration", "error": ProviderError("invalid_configuration", str(exc), False, context.correlation_id).__dict__}
        amount = int(payload.get("amount", 0))
        if amount <= 0 or payload.get("currency") != "IRR": return {"ok": False, "status": "not_sent", "provider": "zarinpal", "reason": "invalid_amount", "error": ProviderError("invalid_amount", "Positive IRR amount is required", False, context.correlation_id).__dict__}
        if operation == "initiate":
            callback_parts = urlsplit(self.callback_url); callback_query = dict(parse_qsl(callback_parts.query, keep_blank_values=True)); callback_query["state"] = str(payload.get("callback_state", "")); callback_url = urlunsplit((callback_parts.scheme, callback_parts.netloc, callback_parts.path, urlencode(callback_query), ""))
            response = self.transport.post_json(f"{self.api_base}/request.json", {"merchant_id": self.merchant_id, "amount": amount, "callback_url": callback_url, "description": str(payload.get("description", "KarenSeir payment"))[:255], "metadata": {"payment_intent_id": str(payload["payment_intent_id"])}}, self.timeout_seconds)
            data = response.get("data") if isinstance(response, Mapping) else None; authority = str((data or {}).get("authority", "")); code = int((data or {}).get("code", 0) or 0)
            if code != 100 or not re.fullmatch(r"A[0-9A-Za-z]{35}", authority): return {"ok": False, "status": "failed", "provider": "zarinpal", "reason": "request_rejected", "error": ProviderError("request_rejected", "ZarinPal request was rejected", False, context.correlation_id).__dict__}
            return {"ok": True, "status": "initiated", "provider": "zarinpal", "reference": authority, "authority": authority, "redirect_url": f"{self.redirect_base}/{authority}"}
        if operation == "verify":
            authority = str(payload.get("authority", ""))
            if not re.fullmatch(r"A[0-9A-Za-z]{35}", authority): return {"ok": False, "status": "failed", "provider": "zarinpal", "reason": "authority_mismatch", "error": ProviderError("authority_mismatch", "Authority is invalid", False, context.correlation_id).__dict__}
            response = self.transport.post_json(f"{self.api_base}/verify.json", {"merchant_id": self.merchant_id, "amount": amount, "authority": authority}, self.timeout_seconds)
            data = response.get("data") if isinstance(response, Mapping) else None; code = int((data or {}).get("code", 0) or 0); ref_id = str((data or {}).get("ref_id", ""))
            if code not in {100, 101} or not ref_id: return {"ok": False, "status": "failed", "provider": "zarinpal", "reason": "verify_rejected", "error": ProviderError("verify_rejected", "ZarinPal verification failed", False, context.correlation_id).__dict__}
            return {"ok": True, "status": "verified", "provider": "zarinpal", "already_verified": code == 101, "authority": authority, "ref_id": ref_id, "amount": amount}
        return {"ok": False, "status": "not_sent", "provider": "zarinpal", "reason": "unsupported_operation", "error": ProviderError("unsupported_operation", "Unsupported operation", False, context.correlation_id).__dict__}


class ResilientAdapter:
    """Distributed provider throttle/circuit wrapper; it never converts failure to success."""

    _RATE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""
    _pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="karenseir-provider")

    def __init__(self, adapter: IntegrationAdapter, *, redis_url: str = "", rate_limit: int = 60, rate_window_seconds: int = 60, failure_threshold: int = 5, circuit_seconds: int = 30) -> None:
        self.adapter = adapter
        self.key = adapter.key
        self.mode = adapter.mode
        self.timeout_seconds = adapter.timeout_seconds
        self.retry_policy = adapter.retry_policy
        self.redis_url = redis_url
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self.failure_threshold = failure_threshold
        self.circuit_seconds = circuit_seconds
        self._redis = None

    @property
    def redis(self):
        if self._redis is None and self.redis_url:
            from redis import Redis
            self._redis = Redis.from_url(self.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        return self._redis

    def validate_configuration(self) -> None:
        self.adapter.validate_configuration()

    def _keys(self, tenant_id: int) -> tuple[str, str, str]:
        prefix = f"karenseir:provider:{self.key}:tenant:{tenant_id}"
        return f"{prefix}:rate", f"{prefix}:failures", f"{prefix}:circuit"

    def health(self) -> ProviderHealth:
        base = self.adapter.health()
        if not self.redis:
            return base
        try:
            self.redis.ping()
            return base
        except Exception:
            return ProviderHealth(status="resilience_store_unavailable", mode=base.mode, detail="Redis resilience state unavailable")

    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        rate_key, failure_key, circuit_key = self._keys(context.tenant_id)
        if self.redis:
            try:
                if self.redis.exists(circuit_key):
                    return self._failure("provider_circuit_open", context, retryable=True)
                count = int(self.redis.eval(self._RATE_SCRIPT, 1, rate_key, self.rate_window_seconds))
                if count > self.rate_limit:
                    return self._failure("provider_rate_limited", context, retryable=True)
            except Exception:
                return self._failure("provider_resilience_unavailable", context, retryable=True)
        read_operations = {"search", "verify", "health", "price_check", "check_price", "availability"}
        safe_retry = operation in read_operations or operation.startswith(("get_", "list_", "search_"))
        attempts = max(1, self.retry_policy.max_attempts) if safe_retry else 1
        for attempt in range(1, attempts + 1):
            try:
                future = self._pool.submit(self.adapter.execute, operation, payload, context)
                result = future.result(timeout=self.timeout_seconds)
            except FutureTimeout:
                future.cancel()
                result = self._failure("provider_timeout", context, retryable=True)
            except Exception:
                result = self._failure("provider_transport_error", context, retryable=True)
            error = result.get("error") if isinstance(result, Mapping) else None
            retryable = bool(error.get("retryable")) if isinstance(error, Mapping) else False
            if result.get("ok"):
                if self.redis:
                    try: self.redis.delete(failure_key, circuit_key)
                    except Exception: pass
                return result
            if not retryable or attempt == attempts:
                self._record_failure(failure_key, circuit_key)
                return result
            delay = min(self.retry_policy.initial_backoff_seconds * (2 ** (attempt - 1)), self.retry_policy.max_backoff_seconds)
            time.sleep(delay)
        return self._failure("provider_failed", context, retryable=True)

    def _record_failure(self, failure_key: str, circuit_key: str) -> None:
        if not self.redis: return
        try:
            failures = int(self.redis.incr(failure_key))
            if failures == 1: self.redis.expire(failure_key, 60)
            if failures >= self.failure_threshold: self.redis.setex(circuit_key, self.circuit_seconds, "open")
        except Exception:
            pass

    def _failure(self, reason: str, context: ProviderContext, *, retryable: bool) -> Mapping[str, Any]:
        return {"ok": False, "status": "not_sent", "provider": self.key, "correlation_id": context.correlation_id, "idempotency_key": context.idempotency_key, "reason": reason, "error": ProviderError(code=reason, message="Provider operation unavailable", retryable=retryable, correlation_id=context.correlation_id).__dict__}


def configured_mode(key: str) -> str:
    return os.getenv(f"{key.upper()}_PROVIDER_MODE", os.getenv("NOTIFICATION_PROVIDER_MODE", "disabled") if key in {"sms", "push", "email"} else "disabled")


def validate_provider_modes(environment: str, demo_mode: bool, keys: tuple[str, ...]) -> None:
    if environment == "production" and not demo_mode:
        mocked = sorted(key for key in keys if configured_mode(key) == "mock")
        if mocked:
            raise RuntimeError(f"Mock providers are forbidden in production: {', '.join(mocked)}")


def configured_adapter(key: str) -> IntegrationAdapter:
    if key == "payment" and os.getenv("PAYMENT_PROVIDER", "").strip().lower() == "sandbox":
        # QA/staging-only local test gateway; refuses (raises) outside development/test/staging.
        from .payment_sandbox import build_sandbox_adapter
        return build_sandbox_adapter()
    if key == "payment" and os.getenv("VANDAPAY_MODE", "disabled") != "disabled":
        return VandaPayAdapter(mode=os.getenv("VANDAPAY_MODE", "disabled"), secret_key=read_secret("VANDAPAY_SECRET_KEY"), base_url=os.getenv("VANDAPAY_BASE_URL", "https://api.vandapay.ir/api/v1"), return_url=os.getenv("VANDAPAY_RETURN_URL", ""), category=os.getenv("VANDAPAY_CATEGORY", "travel"))
    if key == "payment" and os.getenv("ZARINPAL_MODE", "disabled") != "disabled":
        return ZarinPalAdapter(mode=os.getenv("ZARINPAL_MODE", "disabled"), merchant_id=read_secret("ZARINPAL_MERCHANT_ID"), callback_url=os.getenv("ZARINPAL_CALLBACK_URL", ""))
    if key == "hotel" and os.getenv("GRS_MODE", "disabled") != "disabled":
        from .grs_contract import GRSConfig
        from .grs_adapter import GRSAdapter
        return GRSAdapter(config=GRSConfig.from_env())
    if key == "otp" and os.getenv("KARENSEIR_SMS_PROVIDER", "") == "kavenegar":
        from .kavenegar_adapter import KavenegarSmsOtpProvider
        return KavenegarSmsOtpProvider(
            api_key=read_secret("KAVENEGAR_API_KEY"),
            template=os.getenv("KAVENEGAR_OTP_TEMPLATE", ""),
            sender=os.getenv("KAVENEGAR_SENDER", ""),
        )
    mode = configured_mode(key)
    if mode in {"disabled", "mock"}:
        return DisabledMockAdapter(key, mode=mode)
    if mode == "sandbox":
        return SandboxAdapter(key, endpoint=os.getenv(f"{key.upper()}_PROVIDER_ENDPOINT", ""), secret_reference=os.getenv(f"{key.upper()}_PROVIDER_SECRET_REF", ""))
    raise RuntimeError(f"{key}: mode requires an authorized production adapter")


_resilience_url = os.getenv("PROVIDER_RESILIENCE_REDIS_URL", os.getenv("REDIS_URL", ""))
def _resilient(adapter: IntegrationAdapter) -> ResilientAdapter:
    limit = int(os.getenv(f"{adapter.key.upper()}_PROVIDER_RATE_LIMIT", "60"))
    return ResilientAdapter(adapter, redis_url=_resilience_url, rate_limit=max(1, limit))

ADAPTERS = {key: _resilient(configured_adapter(key)) for key in ("flight", "hotel", "tour_hotel", "train", "payment", "email", "supplier_inventory", "voucher_issuance")}
ADAPTERS["otp"] = _resilient(
    configured_adapter("otp")
    if configured_mode("otp") == "sandbox" or os.getenv("KARENSEIR_SMS_PROVIDER", "") == "kavenegar"
    else OTPAdapter("otp", mode=configured_mode("otp"))
)
ADAPTERS["sms"] = _resilient(configured_adapter("sms") if configured_mode("sms") == "sandbox" else NotificationAdapter("sms", mode=configured_mode("sms")))
ADAPTERS["push"] = _resilient(configured_adapter("push") if configured_mode("push") == "sandbox" else NotificationAdapter("push", mode=configured_mode("push")))
