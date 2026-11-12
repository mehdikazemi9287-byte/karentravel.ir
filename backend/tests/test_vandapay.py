"""VandaPay («پرداخت با ونداپی») provider — fail-closed contract tests.

Every VandaPay response here comes from MockVandaPay, an in-memory MOCK of the VandaPay merchant API.
No network call is made and no real payment is claimed. Webhook signature vectors are the shared ones
from the VandaPay repo (integrations/test-vectors/webhook.json), copied into tests/fixtures.
"""
import json
import time
import uuid
from pathlib import Path

import pytest

from app import main as app_main
from app import vandapay as vp
from tests.test_checkout_reviews_zarinpal import auth, login, reservation_fixture

VECTORS = json.loads((Path(__file__).parent / "fixtures" / "vandapay_webhook_vectors.json").read_text(encoding="utf-8"))
ENV = {"VANDAPAY_ENABLED": "1", "VANDAPAY_API_BASE": "https://vandapay.mock.test/api/v1",
       "VANDAPAY_SECRET_KEY": "sk_test_MOCK_ONLY", "VANDAPAY_WEBHOOK_SECRET": "whsec_MOCK_ONLY",
       "VANDAPAY_RETURN_URL": "https://karenseir.mock.test/api/payments/vandapay/return"}


class MockVandaPay:
    """MOCK VandaPay API (labelled): stores intents, honours Idempotency-Key, never moves money."""

    def __init__(self, mode="test"):
        self.mode, self.intents, self.idem, self.calls, self.fail_next = mode, {}, {}, [], None

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, dict(headers), body))
        assert url.startswith("https://vandapay.mock.test/api/v1/")
        assert headers["Authorization"] == "Bearer sk_test_MOCK_ONLY"
        if self.fail_next:
            status, self.fail_next = self.fail_next, None
            return status, {"error": {"code": "mock_error"}}
        if method == "POST" and url.endswith("/payment_intents"):
            key = headers.get("Idempotency-Key"); assert key
            if key in self.idem:
                return 200, dict(self.intents[self.idem[key]])
            data = json.loads(body)
            pid = f"pi_mock_{uuid.uuid4().hex[:10]}"
            self.intents[pid] = {"id": pid, "status": "created", "amount": data["amount"], "currency": "IRR", "mode": self.mode,
                                 "metadata": data["metadata"], "order_ref": data["order_ref"], "refunded_amount": 0,
                                 "checkout_url": f"https://pay.vandapay.mock.test/pay/{pid}"}
            self.idem[key] = pid
            return 201, dict(self.intents[pid])
        if method == "GET" and "/payment_intents/" in url:
            pid = url.rsplit("/", 1)[1]
            return (200, dict(self.intents[pid])) if pid in self.intents else (404, {"error": {"code": "not_found"}})
        return 404, {"error": {"code": "not_found"}}


@pytest.fixture()
def mock_vp(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    mock = MockVandaPay()
    monkeypatch.setattr(app_main, "VANDAPAY_TRANSPORT", mock)
    return mock


def _payment_intent(client, suffix):
    employee, reservation, _, _ = reservation_fixture(client, suffix)
    created = client.post(f"/reservations/{reservation['id']}/payment-intents", headers={**auth(employee), "Idempotency-Key": f"vp-intent-{suffix}"})
    assert created.status_code == 201
    return employee, created.json()


def _signed(event, secret=ENV["VANDAPAY_WEBHOOK_SECRET"], ts=None):
    raw = json.dumps(event, ensure_ascii=False).encode("utf-8")
    ts = int(time.time()) if ts is None else ts
    return raw, {"VandaPay-Signature": f"t={ts},v1={vp.compute_signature(secret, ts, raw)}", "Content-Type": "application/json"}


# ---------------------------------------------------------------- config / flag
def test_flag_off_by_default_and_fail_closed_config():
    assert vp.config_from_env({}) is None
    full = {k: v for k, v in ENV.items() if k != "VANDAPAY_RETURN_URL"}
    assert vp.config_from_env({**full, "VANDAPAY_ENABLED": "0"}) is None
    assert vp.config_from_env({k: v for k, v in full.items() if k != "VANDAPAY_ENABLED"}) is None
    assert vp.config_from_env({**full, "VANDAPAY_API_BASE": ""}) is None  # base URL is configuration only (D14)
    assert vp.config_from_env({**full, "VANDAPAY_API_BASE": "http://insecure.test"}) is None
    assert vp.config_from_env({**full, "VANDAPAY_WEBHOOK_SECRET": ""}) is None
    assert vp.config_from_env({**full, "VANDAPAY_SECRET_KEY": "pk_wrong"}) is None
    assert vp.config_from_env({**full, "VANDAPAY_SECRET_KEY": "sk_live_x"}, environment="development") is None
    assert vp.config_from_env(full, environment="production") is None  # sk_test_ refused in production
    assert vp.config_from_env(full, environment="production", demo_mode=True).mode == "test"
    assert vp.config_from_env({**full, "VANDAPAY_SECRET_KEY": "sk_live_x"}, environment="production").mode == "live"
    cfg = vp.config_from_env(full)
    assert cfg.mode == "test" and cfg.is_test and cfg.api_base == "https://vandapay.mock.test/api/v1"


def test_flag_off_hides_method_and_endpoints_refuse(client, monkeypatch):
    monkeypatch.delenv("VANDAPAY_ENABLED", raising=False)
    suffix = uuid.uuid4().hex
    employee, intent = _payment_intent(client, suffix)
    assert client.get("/payments/methods", headers=auth(employee)).json() == {"methods": []}
    assert client.post(f"/payments/{intent['id']}/vandapay/initiate", headers=auth(employee)).status_code == 404
    assert client.get("/payments/vandapay/return?state=" + "x" * 30).status_code == 404
    assert client.post("/payments/vandapay/webhook", content=b"{}").status_code == 404


# ---------------------------------------------------------------- signature vectors
def test_shared_signature_vectors():
    for v in VECTORS["sign_vectors"]:
        assert vp.compute_signature(v["secret"], v["timestamp"], v["body"]) == v["signature"]
    for case in VECTORS["verify_cases"]:
        secret = case.get("secret", VECTORS["secret"])
        if case["valid"]:
            vp.verify_signature(case["body"], case["header"], secret, now=case["now"])
        else:
            with pytest.raises(vp.WebhookSignatureError) as exc:
                vp.verify_signature(case["body"], case["header"], secret, now=case["now"])
            assert exc.value.reason == case["error"], case["name"]


# ---------------------------------------------------------------- journey
def test_initiate_is_idempotent_server_side_and_test_mode_labelled(client, mock_vp):
    suffix = uuid.uuid4().hex
    employee, intent = _payment_intent(client, suffix)
    methods = client.get("/payments/methods", headers=auth(employee)).json()["methods"]
    assert methods[0]["key"] == "vandapay" and methods[0]["mode"] == "test" and "آزمایشی" in methods[0]["test_mode_label"]
    first = client.post(f"/payments/{intent['id']}/vandapay/initiate", headers=auth(employee))
    assert first.status_code == 202 and first.json()["redirect_url"].startswith("https://pay.vandapay.mock.test/pay/")
    assert first.json()["mode"] == "test" and first.json()["test_mode_label"]
    post = [c for c in mock_vp.calls if c[0] == "POST"][0]
    assert post[2]["Idempotency-Key"].startswith("karenseir-") and json.loads(post[3])["amount"] == intent["amount"]
    again = client.post(f"/payments/{intent['id']}/vandapay/initiate", headers=auth(employee))
    assert again.json()["status"] == "initiated" and len([c for c in mock_vp.calls if c[0] == "POST"]) == 1
    other = login(client, "employee@faraz.test")
    assert client.post(f"/payments/{intent['id']}/vandapay/initiate", headers=auth(other)).status_code == 404


def test_initiate_transient_error_is_503_and_nothing_recorded(client, mock_vp):
    suffix = uuid.uuid4().hex
    employee, intent = _payment_intent(client, suffix)
    mock_vp.fail_next = 502
    assert client.post(f"/payments/{intent['id']}/vandapay/initiate", headers=auth(employee)).status_code == 503
    from app.main import SessionLocal
    from app import operations as models
    with SessionLocal() as db:
        row = db.get(models.PaymentIntent, intent["id"])
        assert row.status == "created" and row.provider_authority is None and row.captured_amount == 0


def _initiated(client, mock_vp):
    suffix = uuid.uuid4().hex
    employee, intent = _payment_intent(client, suffix)
    res = client.post(f"/payments/{intent['id']}/vandapay/initiate", headers=auth(employee)).json()
    pid = res["redirect_url"].rsplit("/", 1)[1]
    post = [c for c in mock_vp.calls if c[0] == "POST"][-1]
    state = json.loads(post[3])["return_url"].split("state=", 1)[1]
    return employee, intent, pid, state


def test_return_unknown_and_pending_never_success(client, mock_vp):
    employee, intent, pid, state = _initiated(client, mock_vp)
    for st in ("unknown", "processing", "card_pending", "something_new"):
        mock_vp.intents[pid]["status"] = st
        r = client.get(f"/payments/vandapay/return?state={state}&status=succeeded")  # browser status ignored
        assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["payment_status"] == "pending_review"


def test_return_succeeded_captures_once(client, mock_vp):
    employee, intent, pid, state = _initiated(client, mock_vp)
    mock_vp.intents[pid]["status"] = "succeeded"
    r = client.get(f"/payments/vandapay/return?state={state}")
    assert r.json() == {"status": "captured", "payment_status": "captured"}
    assert client.get(f"/payments/vandapay/return?state={state}").json()["status"] == "duplicate"


@pytest.mark.parametrize("tamper", ["amount", "currency", "mode", "metadata", "refunded"])
def test_return_rejects_mismatch(client, mock_vp, tamper):
    employee, intent, pid, state = _initiated(client, mock_vp)
    live = mock_vp.intents[pid]; live["status"] = "succeeded"
    if tamper == "amount": live["amount"] += 10
    if tamper == "currency": live["currency"] = "USD"
    if tamper == "mode": live["mode"] = "live"
    if tamper == "metadata": live["metadata"] = {**live["metadata"], "payment_intent_id": "someone-else"}
    if tamper == "refunded": live["refunded_amount"] = 1
    assert client.get(f"/payments/vandapay/return?state={state}").status_code == 409


def test_return_failed_and_forged_state(client, mock_vp):
    employee, intent, pid, state = _initiated(client, mock_vp)
    mock_vp.intents[pid]["status"] = "expired"
    assert client.get(f"/payments/vandapay/return?state={state}").json()["status"] == "failed"
    assert client.get("/payments/vandapay/return?state=" + "a" * 40).status_code == 401


def test_webhook_signature_dedupe_and_reread(client, mock_vp):
    employee, intent, pid, state = _initiated(client, mock_vp)
    # Event claims success but API still says processing -> 503 so VandaPay retries; nothing captured.
    mock_vp.intents[pid]["status"] = "processing"
    event = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "payment_intent.succeeded", "data": {"id": pid, "status": "succeeded", "amount": 1}}
    raw, headers = _signed(event)
    assert client.post("/payments/vandapay/webhook", content=raw, headers=headers).status_code == 503
    # bad signature / stale timestamp / missing header
    bad_raw, bad_headers = _signed(event, secret="whsec_wrong")
    assert client.post("/payments/vandapay/webhook", content=bad_raw, headers=bad_headers).status_code == 400
    old_raw, old_headers = _signed(event, ts=int(time.time()) - 301)
    assert client.post("/payments/vandapay/webhook", content=old_raw, headers=old_headers).status_code == 400
    assert client.post("/payments/vandapay/webhook", content=raw).status_code == 400
    # API confirms -> captured once; re-delivery is a duplicate
    mock_vp.intents[pid]["status"] = "succeeded"
    first = client.post("/payments/vandapay/webhook", content=raw, headers=headers)
    assert first.status_code == 200 and first.json()["outcome"] == "captured"
    assert client.post("/payments/vandapay/webhook", content=raw, headers=headers).json()["outcome"] == "duplicate"
    # browser return afterwards does not capture twice
    assert client.get(f"/payments/vandapay/return?state={state}").json()["status"] == "duplicate"


def test_webhook_unknown_intent_and_test_event(client, mock_vp):
    raw, headers = _signed({"id": "evt_t", "type": "webhook.test", "data": {}})
    assert client.post("/payments/vandapay/webhook", content=raw, headers=headers).json()["outcome"] == "ignored"
    raw, headers = _signed({"id": "evt_u", "type": "payment_intent.succeeded", "data": {"id": "pi_not_ours"}})
    assert client.post("/payments/vandapay/webhook", content=raw, headers=headers).json()["outcome"] == "intent_lookup_failed"
