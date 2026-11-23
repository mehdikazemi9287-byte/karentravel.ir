"""Injast («پرداخت با اینجاست») gateway — fail-closed contract tests.

Every Injast response here comes from MockInjast, an in-memory MOCK of the IPM v1.05.14 merchant API.
No network call is made and no real payment is claimed.
"""
import json
import uuid

import pytest
from sqlalchemy import func, select

from app import injast as ij
from app import main as app_main
from test_checkout_reviews_zarinpal import auth, login, reservation_fixture

MERCHANT = "01516b8a-d261-444e-8fd2-942d7e6d1846"
NID = "0499370899"
ENV = {"INJAST_MODE": "live", "INJAST_MERCHANT_ID": MERCHANT,
       "INJAST_CALLBACK_URL": "https://karenseir.mock.test/api/payments/injast/callback"}


class MockInjast:
    """MOCK Injast API (labelled): stores invoices, never moves money. ``paid`` marks what a customer paid."""

    def __init__(self):
        self.invoices, self.calls, self.fail_next, self.paid, self.verified = {}, [], None, set(), set()

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, body))
        assert url.startswith("https://api.injast.life/service/pay/merchant/")
        data = json.loads(body)
        assert data["merchant_id"] == MERCHANT
        if self.fail_next:
            status, self.fail_next = self.fail_next, None
            return status, {"meta": {"success": False, "error_code": "MOCK"}, "message": "mock"}
        if url.endswith("/merchant/invoice"):
            assert isinstance(data["amount"], str) and data["amount"].isdigit()
            inv = str(uuid.uuid4())
            self.invoices[inv] = data
            return 200, {"meta": {"success": True}, "data": {"invoice_id": inv}}
        if url.endswith("/confirm-pay"):
            inv = data["invoice_id"]
            if inv not in self.invoices:
                return 404, {"meta": {"success": False, "error_code": "NOT_FOUND"}, "message": "not found"}
            if inv in self.verified:
                return 400, {"meta": {"success": False, "error_code": "INVOICE_ALREADY_VERIFIED"}, "message": "already"}
            if inv not in self.paid:
                return 400, {"meta": {"success": False, "error_code": "INVOICE_NOT_PAID"}, "message": "not paid"}
            self.verified.add(inv)
            return 200, {"meta": {"success": True}, "data": {"status": True}}
        return 404, {"meta": {"success": False, "error_code": "NOT_FOUND"}}


@pytest.fixture()
def mock_ij(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    for k in ("PAYMENT_PROVIDER", "PUBLIC_WEB_URL", "VANDAPAY_MODE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(app_main, "DEMO_MODE", True)  # live merchant is only allowed in production or demo
    mock = MockInjast()
    monkeypatch.setattr(app_main, "INJAST_TRANSPORT", mock)
    return mock


def _payment_intent(client, suffix):
    employee, reservation, _, _ = reservation_fixture(client, suffix)
    created = client.post(f"/reservations/{reservation['id']}/payment-intents", headers={**auth(employee), "Idempotency-Key": f"ij-intent-{suffix}"})
    assert created.status_code == 201
    return employee, created.json()


def _initiated(client, mock_ij, nid=NID):
    employee, intent = _payment_intent(client, uuid.uuid4().hex)
    res = client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee), json={"gateway": "injast", "national_id": nid})
    assert res.status_code == 202, res.text
    inv, data = list(mock_ij.invoices.items())[-1]
    state = data["callback_url"].split("state=", 1)[1]
    return employee, intent, inv, data, state


def _cb(client, state, inv, data, status=2, amount=None):
    body = {"invoice_id": inv, "tracking_code": data["tracking_code"], "rrn": "14040110693105144", "status": status,
            "amount": int(data["amount"]) if amount is None else amount, "time": "2026-11-23T10:00:00Z"}
    return client.post(f"/payments/injast/callback?state={state}", json=body)


def _intent_row(pid):
    from app.main import SessionLocal
    from app import operations as models
    with SessionLocal() as db:
        row = db.get(models.PaymentIntent, pid)
        events = db.scalar(select(func.count()).select_from(models.PaymentEvent).where(models.PaymentEvent.payment_intent_id == pid, models.PaymentEvent.event_type == "captured"))
        return row.status, row.captured_amount, row.provider_key, events


# ----------------------------------------------------------------- national id / config / adapter
@pytest.mark.parametrize("value,expected", [("0499370899", "0499370899"), ("۰۴۹۹۳۷۰۸۹۹", "0499370899"), ("٠٤٩٩٣٧٠٨٩٩", "0499370899"),
                                            ("049-937-0899", "0499370899"), ("499370899", "0499370899"), ("0012345678", None),
                                            ("1111111111", None), ("04993708a9", None), ("", None), (None, None), ("04993708990", None)])
def test_national_id_checksum_and_digits(value, expected):
    assert ij.normalize_national_id(value) == expected


def test_config_fail_closed():
    assert ij.config_from_env({}) is None
    assert ij.config_from_env({"INJAST_MODE": "test", "INJAST_MERCHANT_ID": MERCHANT}, environment="production") is None
    assert ij.config_from_env({"INJAST_MODE": "live"}, environment="production") is None
    assert ij.config_from_env({"INJAST_MODE": "live", "INJAST_MERCHANT_ID": "not-a-uuid"}, environment="production") is None
    assert ij.config_from_env({"INJAST_MODE": "live", "INJAST_MERCHANT_ID": MERCHANT, "INJAST_API_BASE": "http://x.test"}, environment="production") is None
    assert ij.config_from_env({"INJAST_MODE": "live", "INJAST_MERCHANT_ID": MERCHANT}, environment="development") is None
    cfg = ij.config_from_env({"INJAST_MODE": "live", "INJAST_MERCHANT_ID": MERCHANT}, environment="production")
    assert cfg.api_base == ij.DEFAULT_API_BASE and cfg.pay_base == ij.DEFAULT_PAY_BASE


def test_adapter_requests_and_errors():
    mock = MockInjast()
    c = ij.InjastClient(ij.InjastConfig(merchant_id=MERCHANT), transport=mock)
    inv = c.create_invoice(amount_rial=1000000, national_id="۰۴۹۹۳۷۰۸۹۹", tracking_code="KSabc-1", callback_url="https://k.test/cb")
    assert mock.invoices[inv]["amount"] == "1000000" and mock.invoices[inv]["national_id"] == NID
    assert c.payment_url(inv, NID) == f"https://pay.injast.life?invoice_id={inv}&national_id={NID}"
    with pytest.raises(ij.InjastError) as e:
        c.confirm_pay(inv)
    assert e.value.code == "INVOICE_NOT_PAID" and not e.value.transient
    mock.paid.add(inv)
    assert c.confirm_pay(inv) == "confirmed" and c.confirm_pay(inv) == "already_verified"
    mock.fail_next = 503
    with pytest.raises(ij.InjastError) as e:
        c.confirm_pay(inv)
    assert e.value.transient
    for bad in ({"amount_rial": 0}, {"national_id": "0012345678"}, {"callback_url": "http://k.test"}, {"tracking_code": "x"}):
        args = {"amount_rial": 10, "national_id": NID, "tracking_code": "KSabc-1", "callback_url": "https://k.test/cb", **bad}
        with pytest.raises(ij.InjastError):
            c.create_invoice(**args)


def test_parse_callback_strict():
    good = {"invoice_id": str(uuid.uuid4()), "tracking_code": "KSabc-1", "rrn": "1404", "status": 2, "amount": 1000, "time": "t"}
    assert ij.parse_callback(json.dumps(good).encode())["status"] == 2
    for bad in ({"status": 9}, {"status": "2"}, {"amount": -1}, {"invoice_id": "x"}, {"tracking_code": "a b c d"}):
        assert ij.parse_callback(json.dumps({**good, **bad}).encode()) is None
    assert ij.parse_callback(b"not json") is None and ij.parse_callback(b"[]") is None


# ----------------------------------------------------------------- API
def test_disabled_injast_is_not_offered_and_refuses(client, monkeypatch):
    monkeypatch.delenv("INJAST_MODE", raising=False)
    employee, intent = _payment_intent(client, uuid.uuid4().hex)
    assert all(m["key"] != "injast" for m in client.get("/payments/methods", headers=auth(employee)).json()["methods"])
    assert client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee), json={"gateway": "injast", "national_id": NID}).status_code == 503
    assert client.post("/payments/injast/callback?state=" + "x" * 30, json={}).status_code == 404


def test_initiate_validates_national_id_and_is_idempotent(client, mock_ij):
    employee, intent = _payment_intent(client, uuid.uuid4().hex)
    methods = client.get("/payments/methods", headers=auth(employee)).json()["methods"]
    assert any(m["key"] == "injast" and m["requires"] == ["national_id"] for m in methods)
    assert client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee), json={"gateway": "injast", "national_id": "0012345678"}).status_code == 422
    assert not mock_ij.invoices
    first = client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee), json={"gateway": "injast", "national_id": "۰۴۹۹۳۷۰۸۹۹"})
    assert first.status_code == 202 and first.json()["redirect_url"].startswith("https://pay.injast.life?invoice_id=")
    inv, data = list(mock_ij.invoices.items())[-1]
    assert data["amount"] == str(intent["amount"]) and data["callback_url"].startswith(ENV["INJAST_CALLBACK_URL"] + "?state=")
    again = client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee), json={"gateway": "injast", "national_id": NID})
    assert again.json()["redirect_url"] == first.json()["redirect_url"] and len(mock_ij.invoices) == 1
    assert client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee), json={"gateway": "injast", "national_id": "0013542419"}).status_code == 409
    other = login(client, "employee@faraz.test")
    assert client.post(f"/payments/{intent['id']}/initiate", headers=auth(other), json={"gateway": "injast", "national_id": NID}).status_code == 404
    from app.main import SessionLocal
    from app import operations as models
    with SessionLocal() as db:  # the national id itself is never stored in clear
        rows = db.scalars(select(models.IdempotencyKey).where(models.IdempotencyKey.scope.like("payment.injast%"))).all()
        assert rows and all(NID not in (r.response_json or "") for r in rows)


def test_initiate_transient_error_is_503_and_intent_untouched(client, mock_ij):
    employee, intent = _payment_intent(client, uuid.uuid4().hex)
    mock_ij.fail_next = 502
    assert client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee), json={"gateway": "injast", "national_id": NID}).status_code == 503
    assert _intent_row(intent["id"])[0] == "created"


def test_forged_paid_callback_without_payment_records_nothing(client, mock_ij):
    employee, intent, inv, data, state = _initiated(client, mock_ij)
    r = _cb(client, state, inv, data, status=2)  # customer never paid: confirm-pay refuses
    assert r.status_code == 200 and r.json()["outcome"] == "rejected"
    assert _intent_row(intent["id"])[:2] == ("initiated", 0)


def test_paid_callback_confirms_and_captures_once(client, mock_ij):
    employee, intent, inv, data, state = _initiated(client, mock_ij)
    mock_ij.paid.add(inv)
    assert _cb(client, state, inv, data).json()["outcome"] == "captured"
    assert _cb(client, state, inv, data).json()["outcome"] == "duplicate"  # replay
    assert _cb(client, state, inv, data, status=5).json()["outcome"] == "duplicate"
    assert _intent_row(intent["id"]) == ("captured", intent["amount"], "injast", 1)
    assert len([c for c in mock_ij.calls if c[1].endswith("/confirm-pay")]) == 1
    status = client.get(f"/payments/{intent['id']}", headers=auth(employee)).json()
    assert status["status"] == "captured"


def test_amount_mismatch_and_wrong_tracking_and_forged_state(client, mock_ij):
    employee, intent, inv, data, state = _initiated(client, mock_ij)
    mock_ij.paid.add(inv)
    assert _cb(client, state, inv, data, amount=int(data["amount"]) - 1).json()["outcome"] == "amount_mismatch"
    bad = dict(data, tracking_code="KSforged-1")
    assert _cb(client, state, inv, bad).json()["outcome"] == "unknown_invoice"
    assert _cb(client, state, str(uuid.uuid4()), data).json()["outcome"] == "unknown_invoice"
    assert _cb(client, "x" * 40, inv, data).json()["outcome"] == "invalid_state"
    assert not [c for c in mock_ij.calls if c[1].endswith("/confirm-pay")]
    assert _intent_row(intent["id"])[:2] == ("initiated", 0)


def test_already_verified_only_accepted_after_our_own_confirm(client, mock_ij):
    # (a) verified by somebody else / unknown: never assumed -> manual review, no money recorded
    employee, intent, inv, data, state = _initiated(client, mock_ij)
    mock_ij.paid.add(inv); mock_ij.verified.add(inv)
    assert _cb(client, state, inv, data).json()["outcome"] == "manual_review"
    assert _intent_row(intent["id"])[:2] == ("initiated", 0)
    # (b) our confirm reached Injast but the answer was lost -> the sweep's retry sees ALREADY_VERIFIED and records it
    employee, intent, inv, data, state = _initiated(client, mock_ij)
    mock_ij.paid.add(inv)
    real = mock_ij.__call__

    def lose_answer(method, url, headers, body, timeout):
        status, parsed = real(method, url, headers, body, timeout)
        if url.endswith("/confirm-pay") and status == 200:
            return 504, {}
        return status, parsed
    app_main.INJAST_TRANSPORT = lose_answer
    assert _cb(client, state, inv, data).json()["outcome"] == "pending"
    assert _intent_row(intent["id"])[0] == "initiated"
    app_main.INJAST_TRANSPORT = mock_ij
    from app.main import SessionLocal
    with SessionLocal() as db:
        tenant_id = db.get(__import__("app.operations", fromlist=["PaymentIntent"]).PaymentIntent, intent["id"]).tenant_id
    with SessionLocal() as db:
        assert app_main.injast_drive_pending(db, tenant_id=tenant_id, min_age_seconds=0)["confirm"] >= 1
    assert _intent_row(intent["id"])[:2] == ("captured", intent["amount"])


def test_failed_and_expired_callbacks(client, mock_ij):
    employee, intent, inv, data, state = _initiated(client, mock_ij)
    assert _cb(client, state, inv, data, status=3).json()["outcome"] == "pending"
    assert _intent_row(intent["id"])[0] == "initiated"
    assert _cb(client, state, inv, data, status=4).json()["outcome"] == "failed"
    assert _intent_row(intent["id"])[0] == "failed"
    assert not [c for c in mock_ij.calls if c[1].endswith("/confirm-pay")]
    # the callback is unsigned, so that "expired" may have been forged: a real payment of OUR invoice still counts
    mock_ij.paid.add(inv)
    assert _cb(client, state, inv, data).json()["outcome"] == "captured"
    assert _intent_row(intent["id"])[:2] == ("captured", intent["amount"])


def test_callback_redirects_browser_to_status_page(client, mock_ij, monkeypatch):
    monkeypatch.setenv("PUBLIC_WEB_URL", "https://karentravel.mock.test")
    employee, intent, inv, data, state = _initiated(client, mock_ij)
    r = client.post(f"/payments/injast/callback?state={state}", json={"invoice_id": inv, "tracking_code": data["tracking_code"], "status": 4, "amount": int(data["amount"])}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == f"https://karentravel.mock.test/payments/{intent['id']}"
    assert "state" not in r.headers["location"]


def test_vandapay_default_path_unchanged_without_gateway(client, mock_ij):
    employee, intent = _payment_intent(client, uuid.uuid4().hex)
    r = client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee))  # no body = old behaviour
    assert r.status_code != 422 and not mock_ij.invoices
