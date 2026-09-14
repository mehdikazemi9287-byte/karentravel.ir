"""Targeted tests for the Kavenegar SMS/OTP transport (integration brief:
KARENSEIR — KAVENEGAR SMS/OTP INTEGRATION). Scope is strictly the adapter
+ its wiring into configured_adapter()/ADAPTERS['otp'] -- request_otp/
verify_otp themselves are unchanged and are covered by the existing auth
regression suite, not re-tested here."""
import json
import os
from urllib.error import HTTPError, URLError

import pytest

from app.kavenegar_adapter import KavenegarSmsOtpProvider, normalize_iranian_mobile
from app.providers import ProviderContext


def _ctx():
    return ProviderContext(tenant_id=1, correlation_id="corr-1", idempotency_key="otp:test-1")


# ---- phone normalization ----

@pytest.mark.parametrize("raw,expected", [
    ("09123456789", "989123456789"),
    ("+989123456789", "989123456789"),
    ("00989123456789", "989123456789"),
    ("989123456789", "989123456789"),
    (" 0912 345 6789 ", "989123456789"),
    ("0912-345-6789", "989123456789"),
])
def test_valid_iranian_phone_normalization(raw, expected):
    assert normalize_iranian_mobile(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "12345", "not-a-phone", "employee@aftab.test",
    "0812345678",       # landline-shaped, not mobile
    "091234567",        # too short
    "091234567890",     # too long
    "+19123456789",     # wrong country code
])
def test_invalid_phone_rejection(raw):
    assert normalize_iranian_mobile(raw) is None


# ---- provider selection / configuration ----

def test_provider_selected_when_configured(monkeypatch):
    monkeypatch.setenv("KARENSEIR_SMS_PROVIDER", "kavenegar")
    monkeypatch.setenv("KAVENEGAR_API_KEY", "test-key")
    monkeypatch.setenv("KAVENEGAR_OTP_TEMPLATE", "karenseir-otp")
    from app import providers as providers_module
    adapter = providers_module.configured_adapter("otp")
    assert isinstance(adapter, KavenegarSmsOtpProvider)
    assert adapter.health().status == "configured_not_verified"


def test_unavailable_provider_when_config_missing(monkeypatch):
    monkeypatch.delenv("KARENSEIR_SMS_PROVIDER", raising=False)
    from app import providers as providers_module
    adapter = providers_module.configured_adapter("otp")
    # Falls back to the pre-existing fail-closed generic adapter -- never
    # a Kavenegar instance, never a simulated success.
    assert not isinstance(adapter, KavenegarSmsOtpProvider)
    result = adapter.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is False


def test_missing_api_key_is_invalid_configuration_not_fake_success():
    provider = KavenegarSmsOtpProvider(api_key="", template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_configuration"


def test_missing_template_is_invalid_configuration():
    provider = KavenegarSmsOtpProvider(api_key="test-key", template="")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is False and result["error"]["code"] == "invalid_configuration"


def test_invalid_receptor_fails_closed_without_calling_kavenegar(monkeypatch):
    called = []
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", lambda *a, **k: called.append(1) or (_ for _ in ()).throw(AssertionError("must not call Kavenegar for an invalid receptor")))
    provider = KavenegarSmsOtpProvider(api_key="test-key", template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "not-a-phone", "code": "123456"}, _ctx())
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_receptor"
    assert not called


# ---- real (mocked-transport) send outcomes ----

class _FakeHttpResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")
    def read(self):
        return self._body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_successful_kavenegar_send(monkeypatch):
    body = {"return": {"status": 200, "message": "تایید شد"}, "entries": [{"messageid": "msg-1"}]}
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", lambda *a, **k: _FakeHttpResponse(body))
    provider = KavenegarSmsOtpProvider(api_key="test-key", template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is True
    assert result["status"] == "sent"
    assert result["reference"] == "msg-1"


def test_provider_timeout(monkeypatch):
    def raise_timeout(*a, **k):
        raise TimeoutError("timed out")
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", raise_timeout)
    provider = KavenegarSmsOtpProvider(api_key="test-key", template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is False
    assert result["error"]["code"] == "provider_timeout"
    assert result["error"]["retryable"] is True


def test_provider_unreachable(monkeypatch):
    def raise_urlerror(*a, **k):
        raise URLError("connection refused")
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", raise_urlerror)
    provider = KavenegarSmsOtpProvider(api_key="test-key", template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is False
    assert result["error"]["code"] == "provider_unreachable"
    assert result["error"]["retryable"] is True


def test_invalid_api_key_maps_to_authentication_error(monkeypatch):
    body = json.dumps({"return": {"status": 403, "message": "کلید وب سرویس نامعتبر است"}}).encode()
    def raise_http_error(*a, **k):
        raise HTTPError("https://api.kavenegar.com/x", 403, "Forbidden", {}, __import__("io").BytesIO(body))
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", raise_http_error)
    provider = KavenegarSmsOtpProvider(api_key="wrong-key", template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is False
    assert result["error"]["code"] == "authentication_error"
    assert result["error"]["retryable"] is False


def test_rate_limit_maps_to_retryable_error(monkeypatch):
    body = json.dumps({"return": {"status": 414, "message": "محدودیت ارسال"}}).encode()
    def raise_http_error(*a, **k):
        raise HTTPError("https://api.kavenegar.com/x", 414, "Limit", {}, __import__("io").BytesIO(body))
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", raise_http_error)
    provider = KavenegarSmsOtpProvider(api_key="test-key", template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert result["ok"] is False
    assert result["error"]["code"] == "rate_limited"
    assert result["error"]["retryable"] is True


# ---- no secret leakage ----

def test_api_key_never_appears_in_any_returned_error_or_result(monkeypatch):
    secret = "S3CR3T-KAVENEGAR-KEY-DO-NOT-LEAK"
    body = json.dumps({"return": {"status": 403, "message": "invalid key"}}).encode()
    def raise_http_error(*a, **k):
        raise HTTPError(f"https://api.kavenegar.com/v1/{secret}/verify/lookup.json", 403, "Forbidden", {}, __import__("io").BytesIO(body))
    monkeypatch.setattr("app.kavenegar_adapter.urlopen", raise_http_error)
    provider = KavenegarSmsOtpProvider(api_key=secret, template="karenseir-otp")
    result = provider.execute("send_otp", {"destination_reference": "09123456789", "code": "123456"}, _ctx())
    assert secret not in json.dumps(result)
    # health()/str(provider) must not leak it either
    assert secret not in str(provider.health())


def test_unsupported_operation_fails_closed():
    provider = KavenegarSmsOtpProvider(api_key="test-key", template="karenseir-otp")
    result = provider.execute("send_push", {}, _ctx())
    assert result["ok"] is False and result["error"]["code"] == "unsupported_operation"
