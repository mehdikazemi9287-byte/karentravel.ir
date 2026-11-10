"""Barook Roozeno adapter: request shape, fail-closed validation, verify rules.
No network: a recording fake transport stands in for Barook."""

from app.barook_adapter import BarookAdapter, configured_barook_adapter, parse_callback, valid_national_code
from app.providers import ProviderContext

CTX = ProviderContext(tenant_id=1, correlation_id="corr-1", idempotency_key="idem-1")
INTENT = "3f1c2a8e-5b7d-4c11-9e0a-1d2b3c4d5e6f"
TOKEN = "cedc09f7-ae3a-47c1-b4c8-06868a849fcb"


def national_code() -> str:
    base = "001234567"
    total = sum(int(base[i]) * (10 - i) for i in range(9)) % 11
    return base + str(total if total < 2 else 11 - total)


class FakeTransport:
    def __init__(self, response):
        self.response, self.calls = response, []

    def post_json(self, url, payload, timeout_seconds):
        self.calls.append((url, dict(payload)))
        return self.response


def adapter(response=None, **overrides):
    options = dict(mode="sandbox", terminal_code="T100", password="secret-pw", callback_url="https://karentravel.ir/payments/barook/callback",
                   payment_month_count=1, transport=FakeTransport(response or {}))
    options.update(overrides)
    return BarookAdapter(**options)


def initiate_payload(**overrides):
    payload = {"payment_intent_id": INTENT, "amount": 25_000_000, "currency": "IRR", "owner_mobile": "۰۹۱۲۳۴۵۶۷۸۹",
               "owner_national_code": national_code(), "owner_name": "مسافر تست", "callback_state": "signed-state"}
    payload.update(overrides)
    return payload


def test_national_code_checksum():
    assert valid_national_code(national_code())
    assert not valid_national_code("1111111111")
    assert not valid_national_code(national_code()[:9] + str((int(national_code()[9]) + 1) % 10))
    assert not valid_national_code("12345")


def test_initiate_sends_document_fields_and_builds_redirect():
    a = adapter({"token": TOKEN, "expireDate": "2026-11-10T18:00:00"})
    result = a.execute("initiate", initiate_payload(), CTX)
    assert result["ok"] and result["status"] == "initiated"
    assert result["redirect_url"] == f"https://api.barook.tech/barook/cpg/redirect/{TOKEN}"
    assert result["authority"] == TOKEN and result["reference"] == INTENT
    url, body = a.transport.calls[0]
    assert url == "https://api.barook.tech/barook/cpg/v2/start-payment"
    assert body["businessServiceSlug"] == "ROOZE_NO_PERSON" and body["totalAmount"] == 25_000_000
    assert body["externalCode"] == INTENT and body["ownerMobile"] == "09123456789"
    assert body["paymentMonthCount"] == 1 and "paymentDayCount" not in body
    assert body["saleItemDto"] == [{"name": "خدمات سفر", "saleCount": 1, "unitType": "عدد", "amount": 25_000_000}]
    assert body["redirectUrl"].startswith("https://karentravel.ir/payments/barook/callback?state=signed-state")


def test_initiate_rejects_bad_customer_data_without_calling_barook():
    for override, reason in [({"owner_national_code": "1111111111"}, "invalid_national_code"), ({"owner_mobile": "0912"}, "invalid_mobile"),
                             ({"items": [{"name": "بلیت", "count": 2, "amount": 1}]}, "items_mismatch"), ({"currency": "USD"}, "invalid_amount")]:
        a = adapter({"token": TOKEN})
        result = a.execute("initiate", initiate_payload(**override), CTX)
        assert not result["ok"] and result["reason"] == reason
        assert a.transport.calls == []


def test_initiate_rejected_when_no_token():
    result = adapter({"_http_status": 400}).execute("initiate", initiate_payload(), CTX)
    assert not result["ok"] and result["reason"] == "request_rejected"


def test_configuration_fails_closed():
    assert adapter().health().status == "configured_not_verified"
    assert adapter(password="").health().status == "configuration_error"
    assert adapter(payment_month_count=None).health().status == "configuration_error"  # neither set
    assert adapter(payment_day_count=30).health().status == "configuration_error"  # both set
    assert adapter(callback_url="http://karentravel.ir/cb").health().status == "configuration_error"
    assert adapter(base_url="https://evil.example/barook").health().status == "configuration_error"
    assert adapter(mode="production").health().status == "configuration_error"  # production needs explicit base URL
    assert adapter(mode="production", base_url="https://gateway.barook.ir").health().status == "configured_not_verified"
    assert "secret-pw" not in repr(adapter())


def test_verify_requires_completed_matching_amount_and_invoice():
    good = {"externalCode": INTENT, "totalAmount": 25_000_000, "status": "COMPLETED"}
    a = adapter(good)
    result = a.execute("verify", {"payment_intent_id": INTENT, "authority": TOKEN, "amount": 25_000_000, "currency": "IRR"}, CTX)
    assert result["ok"] and result["status"] == "verified" and result["amount"] == 25_000_000
    url, body = a.transport.calls[0]
    assert url.endswith("/cpg/v2/verify-payment") and body["token"] == TOKEN and body["externalCode"] == INTENT
    for bad, reason in [({**good, "totalAmount": 1_000}, "amount_mismatch"), ({**good, "status": "PENDING"}, "verify_rejected"),
                        ({**good, "externalCode": "OTHER-1"}, "verify_rejected"), ({"_http_status": 500}, "verify_rejected")]:
        r = adapter(bad).execute("verify", {"payment_intent_id": INTENT, "authority": TOKEN, "amount": 25_000_000, "currency": "IRR"}, CTX)
        assert not r["ok"] and r["reason"] == reason


def test_parse_callback_is_only_a_hint():
    assert parse_callback({"token": TOKEN, "externalCode": "CPG1242", "nationalCode": "******1709", "status": "PENDING"}) == {
        "token": TOKEN, "external_code": "CPG1242", "status": "PENDING", "should_verify": True}
    assert parse_callback({"token": TOKEN, "externalCode": "CPG1242", "status": "CANCELED"})["should_verify"] is False
    assert parse_callback({"token": "x", "externalCode": "CPG1242", "status": "PENDING"}) is None
    assert parse_callback({"token": TOKEN, "externalCode": "CPG1242", "status": "PAID"}) is None


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BAROOK_MODE", raising=False)
    assert configured_barook_adapter() is None
    monkeypatch.setenv("BAROOK_MODE", "sandbox")
    monkeypatch.setenv("BAROOK_TERMINAL_CODE", "T1")
    monkeypatch.setenv("BAROOK_PASSWORD", "p")
    monkeypatch.setenv("BAROOK_CALLBACK_URL", "https://karentravel.ir/cb")
    monkeypatch.setenv("BAROOK_PAYMENT_DAY_COUNT", "30")
    built = configured_barook_adapter()
    assert built is not None and built.health().status == "configured_not_verified"
