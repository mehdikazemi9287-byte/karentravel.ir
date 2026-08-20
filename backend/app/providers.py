from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse


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
        attempts = max(1, self.retry_policy.max_attempts)
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


def configured_adapter(key: str) -> DisabledMockAdapter:
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
ADAPTERS["otp"] = _resilient(configured_adapter("otp") if configured_mode("otp") == "sandbox" else OTPAdapter("otp", mode=configured_mode("otp")))
ADAPTERS["sms"] = _resilient(configured_adapter("sms") if configured_mode("sms") == "sandbox" else NotificationAdapter("sms", mode=configured_mode("sms")))
ADAPTERS["push"] = _resilient(configured_adapter("push") if configured_mode("push") == "sandbox" else NotificationAdapter("push", mode=configured_mode("push")))
