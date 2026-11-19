"""VandaPay adapter hardening (ADR-022) — refunds, hold-release void, org approval, category/phone/items,
credit-only issuance and exclusive funding source.

MOCK ONLY: every VandaPay answer comes from MockVandaPayV2 (in-memory, labelled). No network call, no real money.
"""
import json
import uuid

import pytest
from sqlalchemy import select

from app import main as app_main
from app import operations as models
from app import vandapay as vp
from app.main import SessionLocal, User
from test_booking_financial_journey import fresh_employee, reservation_fixture as fin_reservation_fixture
from test_checkout_reviews_zarinpal import auth, login
from test_vandapay import ENV, MockVandaPay, _initiated, _signed


class MockVandaPayV2(MockVandaPay):
    """MOCK: adds cancel + refunds (Idempotency-Key honoured) and an intent ``refunds`` list like the real API."""

    def __init__(self):
        super().__init__()
        self.refund_mode = "succeeded"  # succeeded | pending | partial_refund_unsupported
        self.cancel_conflict = False
        self.refund_idem = {}

    def __call__(self, method, url, headers, body, timeout):
        if method == "POST" and url.endswith("/cancel"):
            self.calls.append((method, url, dict(headers), body))
            pid = url.rsplit("/", 2)[1]
            it = self.intents[pid]
            if self.cancel_conflict or it["status"] not in vp.CANCELLABLE_STATUSES:
                return 409, {"error": {"code": "invalid_state"}}
            it["status"] = "canceled"
            return 200, dict(it)
        if method == "POST" and url.endswith("/refunds"):
            self.calls.append((method, url, dict(headers), body))
            if self.fail_next:
                status, self.fail_next = self.fail_next, None
                return status, {"error": {"code": "mock_error"}}
            pid = url.rsplit("/", 2)[1]
            key = headers.get("Idempotency-Key"); assert key
            if key in self.refund_idem:
                return 200, dict(self.refund_idem[key])
            if self.refund_mode == "partial_refund_unsupported":
                return 422, {"error": {"code": "partial_refund_unsupported"}}
            it = self.intents[pid]; data = json.loads(body)
            refund = {"id": f"re_mock_{uuid.uuid4().hex[:8]}", "object": "refund", "intent_id": pid, "amount": data["amount"], "status": self.refund_mode}
            it.setdefault("refunds", []).append(refund)
            it["refunded_amount"] = it.get("refunded_amount", 0) + data["amount"]
            it["status"] = "refunded" if it["refunded_amount"] == it["amount"] else "partially_refunded"
            self.refund_idem[key] = refund
            return (201 if self.refund_mode == "succeeded" else 202), dict(refund)
        return super().__call__(method, url, headers, body, timeout)

    def posts(self, suffix):
        return [c for c in self.calls if c[0] == "POST" and c[1].endswith(suffix)]


@pytest.fixture()
def mock_vp2(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("PAYMENT_PROVIDER", raising=False)
    monkeypatch.delenv("PUBLIC_WEB_URL", raising=False)
    monkeypatch.delenv("VANDAPAY_INTENT_EXPIRES_IN_SECONDS", raising=False)
    mock = MockVandaPayV2()
    monkeypatch.setattr(app_main, "VANDAPAY_TRANSPORT", mock)
    return mock


def _tenant_id(email="employee@aftab.test"):
    with SessionLocal() as db:
        return db.scalar(select(User.tenant_id).where(User.email == email))


def _captured(client, mock):
    employee, intent, pid, state = _initiated(client, mock)
    mock.intents[pid]["status"] = "succeeded"
    assert client.get(f"/payments/vandapay/return?state={state}").json()["status"] == "captured"
    return employee, intent, pid, state


def _reservation_of(intent_id):
    with SessionLocal() as db:
        return db.get(models.PaymentIntent, intent_id).reservation_id


def _transition(reservation_id, *targets):
    """System-side reservation transitions (supplier cancellation / hold expiry), as the worker or ops would do."""
    with SessionLocal() as db:
        row = db.scalar(select(models.Reservation).where(models.Reservation.id == reservation_id))
        from app.database import set_tenant_context
        set_tenant_context(db, row.tenant_id)
        row = db.get(models.Reservation, reservation_id)
        for target in targets:
            models.transition_reservation(db, row, target, None, f"test-{target}-{uuid.uuid4().hex}")
        db.commit()


def _sweep(tenant_id):
    with SessionLocal() as db:
        return app_main.vandapay_drive_pending(db, tenant_id=tenant_id)


# ---------------------------------------------------------------- 3. category / phone / items / expiry
def test_category_mapping_phone_and_expiry_helpers(monkeypatch):
    assert vp.category_for_service("flight") == "travel.flight"
    assert vp.category_for_service("hotel") == "travel.hotel" and vp.category_for_service("vacation_rental") == "travel.hotel"
    assert vp.category_for_service("tour") == "travel.tour" and vp.category_for_service("train") == "travel.train"
    assert vp.category_for_service("visa") == "travel" and vp.category_for_service(None) == "travel"  # unknown -> previous value
    assert vp.normalize_ir_mobile("+98 912 123 4567") == "09121234567" and vp.normalize_ir_mobile("۰۹۱۲۱۲۳۴۵۶۷") == "09121234567"
    assert vp.normalize_ir_mobile("employee@aftab.test") is None and vp.normalize_ir_mobile("0212345678") is None
    assert vp.intent_expiry_from_env({}) is None  # default = VandaPay's own TTL, field not sent
    assert vp.intent_expiry_from_env({"VANDAPAY_INTENT_EXPIRES_IN_SECONDS": "3600"}) == 3600
    assert vp.intent_expiry_from_env({"VANDAPAY_INTENT_EXPIRES_IN_SECONDS": "60"}) is None
    assert vp.intent_expiry_from_env({"VANDAPAY_INTENT_EXPIRES_IN_SECONDS": "abc"}) is None


def test_create_intent_body_sends_phone_items_expiry_only_when_given():
    sent = []

    def transport(method, url, headers, body, timeout):
        sent.append(json.loads(body))
        return 201, {"id": "pi_x1", "checkout_url": "https://pay.mock/pi_x1", "mode": "test", "amount": 500, "currency": "IRR"}

    client = vp.VandaPayClient(vp.VandaPayConfig("https://vp.mock/api/v1", "sk_test_x", "whsec", "test"), transport=transport)
    client.create_intent(amount_rial=500, order_ref="KS-1", return_url="https://ks/r", metadata={}, idempotency_key="k1", category="travel.flight")
    assert "customer_phone" not in sent[-1] and "items" not in sent[-1] and "expires_in_seconds" not in sent[-1]
    client.create_intent(amount_rial=500, order_ref="KS-1", return_url="https://ks/r", metadata={}, idempotency_key="k2", category="travel.flight",
                         customer_phone="09121234567", items=[{"sku": "o1", "category": "travel.flight", "amount": 500, "quantity": 1}], expires_in_seconds=3600)
    assert sent[-1]["customer_phone"] == "09121234567" and sent[-1]["items"][0]["amount"] == 500 and sent[-1]["expires_in_seconds"] == 3600
    with pytest.raises(vp.VandaPayError):
        client.create_intent(amount_rial=500, order_ref="KS-1", return_url="https://ks/r", metadata={}, idempotency_key="k3", items=[{"amount": 400}])


def test_initiate_sends_explicit_category_line_items_and_metadata(client, mock_vp2, monkeypatch):
    monkeypatch.setenv("VANDAPAY_INTENT_EXPIRES_IN_SECONDS", "2700")
    employee, intent, pid, state = _initiated(client, mock_vp2)
    body = json.loads(mock_vp2.posts("/payment_intents")[-1][3])
    assert body["category"] == "travel.hotel"  # fixture booking is a hotel
    assert body["items"] == [{"sku": body["items"][0]["sku"], "category": "travel.hotel", "amount": intent["amount"], "quantity": 1, "name": "هتل Checkout"}]
    assert body["metadata"]["reservation_id"] == _reservation_of(intent["id"]) and body["metadata"]["internal_funding_amount"] == "0"
    assert body["expires_in_seconds"] == 2700
    assert "customer_phone" not in body  # login identifier is an e-mail: no verified mobile -> never invented


# ---------------------------------------------------------------- 1. refunds
def test_customer_refund_is_not_executed_while_booking_valid_finance_executes_once(client, mock_vp2):
    employee, intent, pid, _ = _captured(client, mock_vp2)
    r = client.post(f"/payments/{intent['id']}/refunds", headers=auth(employee), json={"amount": intent["amount"], "command_id": f"rf-{uuid.uuid4().hex}"})
    assert r.status_code == 202 and r.json()["status"] == "pending_review" and r.json()["provider"] == "vandapay"
    assert mock_vp2.posts("/refunds") == []  # a still-valid booking never refunds itself
    assert client.post(f"/refunds/{r.json()['id']}/execute", headers=auth(employee)).status_code == 403
    finance = login(client, "finance@aftab.test")
    assert client.post(f"/refunds/{r.json()['id']}/execute", headers=auth(finance)).status_code == 409  # review first
    assert client.post(f"/refunds/{r.json()['id']}/review", headers=auth(finance), json={"approve": True}).status_code == 200
    done = client.post(f"/refunds/{r.json()['id']}/execute", headers=auth(finance))
    assert done.status_code == 202 and done.json()["status"] == "succeeded"
    again = client.post(f"/refunds/{r.json()['id']}/execute", headers=auth(finance))
    assert again.json()["status"] == "succeeded" and len(mock_vp2.posts("/refunds")) == 1
    key = mock_vp2.posts("/refunds")[0][2]["Idempotency-Key"]
    assert key == f"karenseir-{_tenant_id()}-refund-{r.json()['id']}"
    with SessionLocal() as db:
        row = db.get(models.PaymentIntent, intent["id"])
        assert row.status == "refunded" and row.refunded_amount == row.captured_amount
    faraz_finance = login(client, "employee@faraz.test")
    assert client.post(f"/refunds/{r.json()['id']}/execute", headers=auth(faraz_finance)).status_code in (403, 404)


def test_cancelled_booking_refund_auto_pending_then_webhook_applies_once(client, mock_vp2):
    employee, intent, pid, _ = _captured(client, mock_vp2)
    reservation_id = _reservation_of(intent["id"])
    _transition(reservation_id, "cancel_requested", "cancelled")
    mock_vp2.refund_mode = "pending"
    r = client.post(f"/payments/{intent['id']}/refunds", headers=auth(employee), json={"amount": intent["amount"], "command_id": f"rf-{uuid.uuid4().hex}"})
    assert r.json()["status"] == "processing" and len(mock_vp2.posts("/refunds")) == 1
    vp_refund = mock_vp2.intents[pid]["refunds"][0]
    event = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "refund.succeeded", "data": {"id": vp_refund["id"], "intent_id": pid, "status": "succeeded", "amount": vp_refund["amount"]}}
    raw, headers = _signed(event)
    assert client.post("/payments/vandapay/webhook", content=raw, headers=headers).status_code == 503  # API still pending
    vp_refund["status"] = "succeeded"
    first = client.post("/payments/vandapay/webhook", content=raw, headers=headers)
    assert first.status_code == 200 and first.json()["outcome"] == "refund_applied"
    assert client.post("/payments/vandapay/webhook", content=raw, headers=headers).json()["outcome"] == "duplicate"
    with SessionLocal() as db:
        row = db.get(models.PaymentIntent, intent["id"]); rec = db.get(models.RefundRecord, r.json()["id"])
        assert rec.status == "succeeded" and rec.provider_reference == vp_refund["id"] and row.refunded_amount == row.amount and row.status == "refunded"


def test_refund_transient_retry_same_key_and_partial_card_goes_manual(client, mock_vp2):
    employee, intent, pid, _ = _captured(client, mock_vp2)
    reservation_id = _reservation_of(intent["id"])
    _transition(reservation_id, "cancel_requested", "cancelled")
    command = f"rf-{uuid.uuid4().hex}"
    mock_vp2.fail_next = 502
    r = client.post(f"/payments/{intent['id']}/refunds", headers=auth(employee), json={"amount": 500_000, "command_id": command})
    assert r.json()["status"] == "processing"  # outcome unknown -> durable, retried with the same key
    again = client.post(f"/payments/{intent['id']}/refunds", headers=auth(employee), json={"amount": 500_000, "command_id": command})
    assert again.json()["status"] == "succeeded"
    keys = {c[2]["Idempotency-Key"] for c in mock_vp2.posts("/refunds")}
    assert len(keys) == 1 and len(mock_vp2.intents[pid]["refunds"]) == 1
    mock_vp2.refund_mode = "partial_refund_unsupported"
    second = client.post(f"/payments/{intent['id']}/refunds", headers=auth(employee), json={"amount": 300_000, "command_id": f"rf-{uuid.uuid4().hex}"})
    assert second.json()["status"] == "manual_review"
    # manual_review still counts against the refundable remainder (no over-refund)
    over = client.post(f"/payments/{intent['id']}/refunds", headers=auth(employee), json={"amount": intent["amount"] - 500_000, "command_id": f"rf-{uuid.uuid4().hex}"})
    assert over.status_code == 409


# ---------------------------------------------------------------- 2. hold release -> void intent
def test_hold_release_cancels_open_intent_once(client, mock_vp2):
    employee, intent, pid, state = _initiated(client, mock_vp2)
    reservation_id = _reservation_of(intent["id"])
    _transition(reservation_id, "expired")
    with SessionLocal() as db:
        assert db.get(models.PaymentIntent, intent["id"]).status == "cancel_pending"
    stats = _sweep(_tenant_id())
    assert stats["cancel"] >= 1 and mock_vp2.intents[pid]["status"] == "canceled"
    with SessionLocal() as db:
        assert db.get(models.PaymentIntent, intent["id"]).status == "failed"
    calls = len(mock_vp2.posts("/cancel")); _sweep(_tenant_id())
    assert len(mock_vp2.posts("/cancel")) == calls  # nothing left to cancel
    assert client.post(f"/payments/{intent['id']}/initiate", headers=auth(employee)).status_code == 409  # released booking


def test_late_capture_after_hold_release_is_refunded_in_full_never_issued(client, mock_vp2):
    employee, intent, pid, state = _initiated(client, mock_vp2)
    reservation_id = _reservation_of(intent["id"])
    _transition(reservation_id, "expired")
    mock_vp2.intents[pid]["status"] = "succeeded"  # customer paid in the race window
    _sweep(_tenant_id())
    with SessionLocal() as db:
        row = db.get(models.PaymentIntent, intent["id"]); res = db.get(models.Reservation, reservation_id)
        assert row.captured_amount == row.amount and row.refunded_amount == row.amount and row.status == "refunded"
        assert res.status == "expired"
    supplier = login(client, "supplier@aftab.test")
    assert client.post(f"/reservations/{reservation_id}/fulfill", headers=auth(supplier), json={"provider_reference": "manual-ref", "document_reference": "document://voucher-x", "command_id": f"f-{uuid.uuid4().hex}"}).status_code == 409


# ---------------------------------------------------------------- 4. requires_org_approval
def test_requires_org_approval_is_pending_never_issued_and_hold_release_cancels(client, mock_vp2):
    employee, intent, pid, state = _initiated(client, mock_vp2)
    mock_vp2.intents[pid]["status"] = "requires_org_approval"
    event = {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "payment_intent.requires_org_approval", "data": {"id": pid}}
    raw, headers = _signed(event)
    res = client.post("/payments/vandapay/webhook", content=raw, headers=headers)
    assert res.status_code == 200 and res.json()["outcome"] == "pending_org_approval"
    ret = client.get(f"/payments/vandapay/return?state={state}").json()
    assert ret["payment_status"] == "pending_org_approval" and "۴۸" in ret["message"]
    with SessionLocal() as db:
        row = db.get(models.PaymentIntent, intent["id"])
        assert row.status == "initiated" and row.captured_amount == 0
        reservation = db.get(models.Reservation, row.reservation_id)
        events = db.scalars(select(models.TripEventRecord).where(models.TripEventRecord.reservation_id == reservation.id, models.TripEventRecord.event_type == "payment.pending_org_approval")).all()
        assert len(events) == 1  # idempotent (webhook + return)
    supplier = login(client, "supplier@aftab.test")
    assert client.post(f"/reservations/{reservation.id}/fulfill", headers=auth(supplier), json={"provider_reference": "manual-ref", "document_reference": "document://voucher-x", "command_id": f"f-{uuid.uuid4().hex}"}).status_code == 409
    _transition(reservation.id, "expired")
    _sweep(_tenant_id())
    assert mock_vp2.intents[pid]["status"] == "canceled"


# ---------------------------------------------------------------- 5. federated org credit (credit-only issuance and the
# exclusive bank remainder are enforced on main by funding_references: fully_funded_without_bank / bank_payable)
def _org_credit_employee(client, suffix, *, amount, limit):
    tenant_id = _tenant_id()
    email = fresh_employee(tenant_id, suffix)
    employee, reservation, traveller = fin_reservation_fixture(client, suffix, amount=amount, customer_email=email)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == email))
        org = models.Organization(tenant_id=tenant_id, name=f"سازمان {suffix[:6]}", status="active"); db.add(org); db.flush()
        db.add(models.EmployeeAssignment(tenant_id=tenant_id, user_id=owner.id, organization_id=org.id))
        acct = models.CreditAccount(tenant_id=tenant_id, organization_id=org.id, currency="IRR", limit_amount=limit); db.add(acct); db.commit()
        org_id, acct_id = org.id, acct.id
    checkout = client.post(f"/reservations/{reservation['id']}/checkout-sessions", headers=auth(employee), json={"command_id": f"co-{suffix}"}).json()
    for step, extra in (("traveller", {"traveller_ids": [traveller["id"]]}), ("recheck", {}), ("policy", {"acknowledged": True})):
        assert client.put(f"/checkout-sessions/{checkout['id']}/steps/{step}", headers=auth(employee), json={"command_id": f"{step}-{suffix}", **extra}).status_code == 200
    return employee, reservation, checkout["id"], org_id, acct_id


def test_federated_org_credit_is_never_reserved_internally(client, monkeypatch):
    suffix = uuid.uuid4().hex
    employee, reservation, checkout_id, org_id, _ = _org_credit_employee(client, suffix, amount=1_000_000, limit=2_000_000)
    monkeypatch.setenv("VANDAPAY_FEDERATED_CREDIT_ORGANIZATION_IDS", f"other,{org_id}")
    r = client.put(f"/checkout-sessions/{checkout_id}/steps/funding", headers=auth(employee), json={"command_id": f"fund-{suffix}", "credit_amount": 1_000_000})
    assert r.status_code == 409 and "ونداپی" in r.json()["detail"]
    credit = client.get("/me/organization-credit", headers=auth(employee)).json()
    assert all(c["reserved"] == 0 for c in credit)


def test_external_refund_made_in_vandapay_panel_is_recorded(client, mock_vp2):
    employee, intent, pid, _ = _captured(client, mock_vp2)
    it = mock_vp2.intents[pid]
    it.setdefault("refunds", []).append({"id": "re_panel_1", "intent_id": pid, "amount": 200_000, "status": "succeeded"})
    it["refunded_amount"] = 200_000; it["status"] = "partially_refunded"
    raw, headers = _signed({"id": f"evt_{uuid.uuid4().hex[:8]}", "type": "refund.succeeded", "data": {"id": "re_panel_1", "intent_id": pid}})
    assert client.post("/payments/vandapay/webhook", content=raw, headers=headers).json()["outcome"] == "refund_applied"
    with SessionLocal() as db:
        row = db.get(models.PaymentIntent, intent["id"])
        assert row.refunded_amount == 200_000 and row.status == "captured"


def test_flag_off_sweep_is_noop(client, monkeypatch):
    monkeypatch.setenv("VANDAPAY_MODE", "disabled")
    assert app_main.vandapay_sweep() == {"enabled": False}
