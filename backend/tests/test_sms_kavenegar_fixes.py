"""Regression tests for the Kavenegar/OTP fixes of 2026-11-23 (fix/sms-kavenegar-diagnose).

Controlled fixtures only: no network, no real SMS, no real key."""
import io
import json
from urllib.error import HTTPError

import pytest

import app.main as main_module
import app.providers as providers_module
from app.kavenegar_adapter import KavenegarSmsOtpProvider, normalize_digits, normalize_iranian_mobile
from app.providers import ProviderContext, ResilientAdapter

CTX = ProviderContext(tenant_id=7, correlation_id="fix-otp", idempotency_key="fix-otp")
PAYLOAD = {"destination_reference": "+989123456789", "code": "123456"}


class Response:
    def __init__(self, body):
        self.body = body

    def read(self):
        return json.dumps(self.body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def provider(key="controlled-test-key"):
    return KavenegarSmsOtpProvider(api_key=key, template="controlled-template")


def _http_error(status, body_status=None):
    body = json.dumps({"return": {"status": status if body_status is None else body_status, "message": "x"}}).encode()

    def raise_(*args, **kwargs):
        raise HTTPError("https://api.kavenegar.com/v1/redacted/verify/lookup.json", status, "err", {}, io.BytesIO(body))
    return raise_


# ---- status-code table ----

@pytest.mark.parametrize("status,reason,retryable", [
    (414, "provider_bad_request", False),   # too many records per call -- not a rate limit
    (415, "provider_bad_request", False),
    (412, "invalid_sender", False),
    (407, "access_denied", False),
    (409, "provider_busy", True),
    (431, "invalid_token", False),
    (432, "template_token_missing", False),
    (451, "rate_limited", True),
    (501, "owner_only_test_account", False),
])
def test_status_codes_map_to_precise_reasons(monkeypatch, status, reason, retryable):
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", _http_error(status))
    result = provider().execute("send_otp", PAYLOAD, CTX)
    assert result["ok"] is False
    assert result["reason"] == reason
    assert result["error"]["retryable"] is retryable


def test_http_error_body_status_is_preferred_over_http_status(monkeypatch):
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", _http_error(400, body_status=418))
    assert provider().execute("send_otp", PAYLOAD, CTX)["reason"] == "insufficient_credit"


def test_http_error_with_unreadable_body_falls_back_to_http_status(monkeypatch):
    def raise_(*args, **kwargs):
        raise HTTPError("https://api.kavenegar.com/x", 403, "Forbidden", {}, io.BytesIO(b"<html>"))
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", raise_)
    assert provider().execute("send_otp", PAYLOAD, CTX)["reason"] == "authentication_error"


# ---- "sent" only when Kavenegar did not already report failure ----

@pytest.mark.parametrize("entry_status", [6, 11, 13, 14, 100])
def test_failed_entry_status_is_never_reported_as_sent(monkeypatch, entry_status):
    body = {"return": {"status": 200}, "entries": [{"messageid": 123456789, "status": entry_status}]}
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", lambda *a, **k: Response(body))
    result = provider().execute("send_otp", PAYLOAD, CTX)
    assert result["ok"] is False and result["reason"] == "recipient_undeliverable"


@pytest.mark.parametrize("entry_status", [1, 2, 4, 5, 10, None])
def test_queued_or_delivered_entry_status_is_sent(monkeypatch, entry_status):
    entry = {"messageid": 123456789}
    if entry_status is not None:
        entry["status"] = entry_status
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", lambda *a, **k: Response({"return": {"status": 200}, "entries": [entry]}))
    result = provider().execute("send_otp", PAYLOAD, CTX)
    assert result["ok"] is True and result["reference"] == "123456789"


# ---- URL / input hygiene ----

def test_api_key_is_path_escaped(monkeypatch):
    calls = []

    def send(request, **kwargs):
        calls.append(request.full_url)
        return Response({"return": {"status": 200}, "entries": [{"messageid": 1}]})
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", send)
    provider("ab/c?d").execute("send_otp", PAYLOAD, CTX)
    assert calls[0] == "https://api.kavenegar.com/v1/ab%2Fc%3Fd/verify/lookup.json"


@pytest.mark.parametrize("raw", [
    "‎09123456789",            # left-to-right mark from a copied contact
    "0912‌345‌6789",      # zero-width non-joiner
    "‪+98 912 345 6789‬",  # bidi embedding
    "۰۹۱۲ ۳۴۵ ۶۷۸۹",
])
def test_invisible_marks_and_persian_digits_are_normalized(raw):
    assert normalize_iranian_mobile(raw) == "989123456789"


def test_normalize_digits():
    assert normalize_digits("۱۲۳٤٥٦") == "123456"
    assert normalize_digits("abc") == "abc"


# ---- circuit breaker must not lock every user out on per-request errors ----

class FakeRedis:
    def __init__(self):
        self.store = {}

    def exists(self, key):
        return key in self.store

    def eval(self, script, numkeys, key, window):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key, seconds):
        return True

    def setex(self, key, seconds, value):
        self.store[key] = value

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


def _resilient_with_fake_redis(adapter):
    wrapped = ResilientAdapter(adapter, redis_url="redis://unused", rate_limit=1000)
    wrapped._redis = FakeRedis()
    return wrapped


def test_bad_recipients_do_not_open_the_tenant_circuit():
    wrapped = _resilient_with_fake_redis(provider())
    for _ in range(10):
        result = wrapped.execute("send_otp", {"destination_reference": "not-a-phone", "code": "123456"}, CTX)
        assert result["reason"] == "invalid_receptor" and result["client_error"] is True
    _, _, circuit_key = wrapped._keys(CTX.tenant_id)
    assert not wrapped.redis.exists(circuit_key)


def test_owner_only_test_account_rejections_do_not_open_the_circuit(monkeypatch):
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", _http_error(501))
    wrapped = _resilient_with_fake_redis(provider())
    for _ in range(10):
        wrapped.execute("send_otp", PAYLOAD, CTX)
    _, _, circuit_key = wrapped._keys(CTX.tenant_id)
    assert not wrapped.redis.exists(circuit_key)


def test_provider_side_failures_still_open_the_circuit(monkeypatch):
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", _http_error(403))
    wrapped = _resilient_with_fake_redis(provider())
    for _ in range(wrapped.failure_threshold):
        assert wrapped.execute("send_otp", PAYLOAD, CTX)["reason"] == "authentication_error"
    assert wrapped.execute("send_otp", PAYLOAD, CTX)["reason"] == "provider_circuit_open"


# ---- verify accepts a correct code typed with Persian digits ----

class RecordingOTPAdapter:
    def __init__(self):
        self.calls = []

    def execute(self, operation, payload, context):
        self.calls.append(dict(payload))
        return {"ok": True, "status": "sent", "reference": "recording-adapter"}


def test_verify_accepts_persian_digit_code(client, monkeypatch):
    monkeypatch.setattr(main_module, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(main_module, "OTP_MAX_PER_HOUR", 10_000)
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    requested = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "finance@aftab.test"})
    assert requested.status_code == 202 and adapter.calls, "a real challenge must have been issued"
    code = adapter.calls[-1]["code"]
    persian = code.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    verified = client.post("/auth/otp/verify", json={"tenant_slug": "aftab-bank", "challenge_id": requested.json()["challenge_id"], "code": persian, "device_id": "device-persian-digits"})
    assert verified.status_code == 200, verified.text
    assert verified.json().get("access_token") or verified.json().get("mfa_required")


def test_verify_still_rejects_wrong_persian_digit_code(client, monkeypatch):
    monkeypatch.setattr(main_module, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(main_module, "OTP_MAX_PER_HOUR", 10_000)
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    requested = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "finance@aftab.test"})
    assert adapter.calls
    code = adapter.calls[-1]["code"]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    verified = client.post("/auth/otp/verify", json={"tenant_slug": "aftab-bank", "challenge_id": requested.json()["challenge_id"], "code": wrong, "device_id": "device-persian-digits"})
    assert verified.status_code == 401
