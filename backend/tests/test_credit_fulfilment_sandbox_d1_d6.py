"""QA 1405-08-18 defects D1 (P0) and D6 (P1).

D1: a booking funded 100% from organization credit (or wallet + credit with a
zero bank remainder) must be fulfillable, capture its credit exactly once, be
listed for the supplier, and - when abandoned - be expired by the reaper with
its reserve released exactly once. Mixed funding still needs the captured bank
part.

D6: the local sandbox payment gateway is QA/staging-only, clearly labelled,
and drives the real ZarinPal-shaped callback/verify path.
"""
from test_booking_financial_journey import fresh_employee, reservation_fixture
import json
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.main import SessionLocal, User
from app import operations as m


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email}); assert response.status_code == 200; return response.json()


def auth(session): return {"Authorization": f"Bearer {session['access_token']}"}


def funded_reservation(client, *, amount=1_000_000, credit=None, wallet=0, limit=None):
    """Reservation for an isolated employee with an organization credit account,
    driven through the real checkout up to the payment step."""
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        tenant_id = db.scalar(select(User.tenant_id).where(User.email == "employee@aftab.test"))
    email = fresh_employee(tenant_id, suffix)
    employee, reservation, traveller = reservation_fixture(client, suffix, amount=amount, customer_email=email)
    credit = amount if credit is None else credit
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == email))
        organization = m.Organization(tenant_id=tenant_id, name=f"سازمان D1 {suffix[:6]}", status="active"); db.add(organization); db.flush()
        db.add(m.EmployeeAssignment(tenant_id=tenant_id, user_id=owner.id, organization_id=organization.id))
        account = m.CreditAccount(tenant_id=tenant_id, organization_id=organization.id, currency="IRR", limit_amount=limit or max(credit, 1) * 2); db.add(account); db.commit()
        account_id = account.id
    if wallet:
        created = client.post("/me/wallets", headers={**auth(employee), "Idempotency-Key": f"d1-wallet-{suffix}"}, json={"currency": "IRR"}).json()
        finance = login(client, "finance@aftab.test")
        assert client.post(f"/wallets/{created['id']}/commands", headers=auth(finance), json={"command_id": f"d1-allocate-{suffix}", "entry_type": "allocate", "amount": wallet}).status_code == 200
    checkout = client.post(f"/reservations/{reservation['id']}/checkout-sessions", headers=auth(employee), json={"command_id": f"d1-checkout-{suffix}"}).json()
    cid = checkout["id"]
    for step, body in (("traveller", {"traveller_ids": [traveller["id"]]}), ("recheck", {}), ("policy", {"acknowledged": True}), ("funding", {"wallet_amount": wallet, "credit_amount": credit}), ("invoice", {}), ("payment", {})):
        response = client.put(f"/checkout-sessions/{cid}/steps/{step}", headers=auth(employee), json={"command_id": f"d1-{step}-{suffix}", **body})
        assert response.status_code == 200, (step, response.text)
    return {"employee": employee, "reservation": reservation, "checkout": response.json(), "account_id": account_id, "tenant_id": tenant_id, "suffix": suffix}


def credit_state(client, ctx):
    return next(item for item in client.get("/me/organization-credit", headers=auth(ctx["employee"])).json() if item["id"] == ctx["account_id"])


def fulfil(client, session, reservation_id, command):
    return client.post(f"/reservations/{reservation_id}/fulfill", headers=auth(session), json={"provider_reference": "manual-ref", "document_reference": "document://d1-voucher", "command_id": command})


def ledger(reservation_id, entry_type):
    with SessionLocal() as db:
        return db.scalars(select(m.FinancialLedgerEntry).where(m.FinancialLedgerEntry.reservation_id == reservation_id, m.FinancialLedgerEntry.entry_type == entry_type)).all()


def test_d1_full_credit_booking_is_ready_fulfilled_and_credit_captured_once(client):
    ctx = funded_reservation(client)
    rid = ctx["reservation"]["id"]
    assert ctx["checkout"]["stage"] == "awaiting_fulfillment" and ctx["checkout"]["payment_intent_id"] is None
    assert credit_state(client, ctx)["reserved"] == 1_000_000
    supplier = login(client, "supplier@aftab.test")
    assert any(row["id"] == rid for row in client.get("/supplier/reservations/ready", headers=auth(supplier)).json())

    first = fulfil(client, supplier, rid, f"d1-fulfil-{ctx['suffix']}")
    assert first.status_code == 200, first.text
    assert first.json()["reservation"]["status"] == "issued" and first.json()["voucher"]["status"] == "issued"
    state = credit_state(client, ctx)
    assert state["reserved"] == 0 and state["consumed"] == 1_000_000

    # Replays (same or new command) never capture twice.
    assert fulfil(client, supplier, rid, f"d1-fulfil-{ctx['suffix']}").status_code == 200
    assert fulfil(client, supplier, rid, f"d1-fulfil-again-{ctx['suffix']}").status_code == 200
    assert len(ledger(rid, "capture")) == 1 and ledger(rid, "release") == []
    assert credit_state(client, ctx)["consumed"] == 1_000_000
    with SessionLocal() as db:
        audit = db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.aggregate_id == rid, m.OutboxEvent.event_type == "reservation.funding.capture")).all()
        assert len(audit) == 1 and json.loads(audit[0].payload_json)["amount"] == 1_000_000
    # Issued reservation is no longer "ready".
    assert all(row["id"] != rid for row in client.get("/supplier/reservations/ready", headers=auth(supplier)).json())


def test_d1_wallet_plus_credit_with_zero_bank_remainder_is_fulfilled(client):
    ctx = funded_reservation(client, amount=1_000_000, credit=600_000, wallet=400_000)
    rid = ctx["reservation"]["id"]
    assert ctx["checkout"]["stage"] == "awaiting_fulfillment"
    response = fulfil(client, login(client, "supplier@aftab.test"), rid, f"d1-wc-{ctx['suffix']}")
    assert response.status_code == 200, response.text
    captures = ledger(rid, "capture")
    assert sorted(entry.amount for entry in captures) == [400_000, 600_000]


def test_d1_abandoned_credit_funding_is_released_by_reaper_exactly_once(client):
    ctx = funded_reservation(client)
    rid = ctx["reservation"]["id"]
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.get(m.Reservation, rid).updated_at = now - timedelta(hours=2); db.commit()
        # Still inside the funded hold: not released, not expired.
        assert rid not in m.sweep_expired_reservations(db, now=now, funded_hold_minutes=60 * 24)
        assert db.get(m.Reservation, rid).status == "reserved"
    assert credit_state(client, ctx)["reserved"] == 1_000_000

    later = now + timedelta(hours=25)
    with SessionLocal() as db:
        assert rid in m.sweep_expired_reservations(db, now=later, funded_hold_minutes=60 * 24)
        assert m.sweep_expired_reservations(db, now=later, funded_hold_minutes=60 * 24) == []
        assert db.get(m.Reservation, rid).status == "expired"
        audit = db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.aggregate_id == rid, m.OutboxEvent.event_type == "reservation.funding.release")).all()
        assert len(audit) == 1
    state = credit_state(client, ctx)
    assert state["reserved"] == 0 and state["consumed"] == 0 and state["available"] == state["limit_amount"]
    assert len(ledger(rid, "release")) == 1 and ledger(rid, "capture") == []
    # A released reservation can never be fulfilled afterwards.
    assert fulfil(client, login(client, "supplier@aftab.test"), rid, f"d1-late-{ctx['suffix']}").status_code == 409
    assert ledger(rid, "capture") == []


def test_d1_reaper_never_releases_fulfilled_or_bank_in_flight_reservations(client):
    issued = funded_reservation(client)
    assert fulfil(client, login(client, "supplier@aftab.test"), issued["reservation"]["id"], f"d1-keep-{issued['suffix']}").status_code == 200
    later = datetime.now(timezone.utc) + timedelta(days=3)
    with SessionLocal() as db:
        # Simulate a stale status left at "reserved" with captured funds: still never released.
        row = db.get(m.Reservation, issued["reservation"]["id"]); row.status = "reserved"; db.commit()
        assert issued["reservation"]["id"] not in m.sweep_expired_reservations(db, now=later, funded_hold_minutes=1)
        row.status = "issued"; db.commit()
    assert ledger(issued["reservation"]["id"], "release") == []


def test_d1_mixed_credit_and_bank_requires_captured_bank_part(client, monkeypatch):
    ctx = funded_reservation(client, amount=1_000_000, credit=600_000)
    rid = ctx["reservation"]["id"]
    assert ctx["checkout"]["stage"] == "awaiting_payment"
    intent_id = ctx["checkout"]["payment_intent_id"]
    supplier = login(client, "supplier@aftab.test")
    assert fulfil(client, supplier, rid, f"d1-mixed-early-{ctx['suffix']}").status_code == 409
    assert all(row["id"] != rid for row in client.get("/supplier/reservations/ready", headers=auth(supplier)).json())
    # A captured amount below the bank remainder is still not "paid".
    with SessionLocal() as db:
        intent = db.get(m.PaymentIntent, intent_id); intent.status = "captured"; intent.captured_amount = 100_000; db.commit()
    assert fulfil(client, supplier, rid, f"d1-mixed-short-{ctx['suffix']}").status_code == 409
    assert ledger(rid, "capture") == []
    with SessionLocal() as db:
        intent = db.get(m.PaymentIntent, intent_id); intent.captured_amount = 400_000; db.commit()
    assert any(row["id"] == rid for row in client.get("/supplier/reservations/ready", headers=auth(supplier)).json())
    response = fulfil(client, supplier, rid, f"d1-mixed-ok-{ctx['suffix']}")
    assert response.status_code == 200, response.text
    assert [entry.amount for entry in ledger(rid, "capture")] == [600_000]


def test_d1_settlement_is_exactly_once_capture_and_release_are_exclusive(client):
    ctx = funded_reservation(client)
    rid = ctx["reservation"]["id"]
    with SessionLocal() as db:
        reservation = db.get(m.Reservation, rid)
        m.settle_reservation_funding(db, reservation, "capture")
        m.settle_reservation_funding(db, reservation, "capture")  # same transaction, pending entry
        db.commit()
        m.settle_reservation_funding(db, reservation, "release")  # after capture: refused
        m.settle_reservation_funding(db, reservation, "capture")
        db.commit()
        reserve = db.scalar(select(m.FinancialLedgerEntry).where(m.FinancialLedgerEntry.reservation_id == rid, m.FinancialLedgerEntry.entry_type == "reserve"))
        # A racing writer reusing the deterministic settlement command id for the other action is
        # refused (KT-03: same command_id + different entry_type -> conflict); nothing is posted.
        with pytest.raises(m.LedgerCommandConflict):
            m.apply_organization_credit_command(db, tenant_id=reservation.tenant_id, credit_account_id=reserve.credit_account_id, command_id=f"reservation-settle:{reserve.id}", entry_type="release", amount=reserve.amount, reservation_id=rid)
        # An identical replay still returns the stored capture.
        same = m.apply_organization_credit_command(db, tenant_id=reservation.tenant_id, credit_account_id=reserve.credit_account_id, command_id=f"reservation-settle:{reserve.id}", entry_type="capture", amount=reserve.amount, reservation_id=rid)
        assert same.entry_type == "capture"
        # The settlement path itself still treats the other action as already settled.
        m.settle_reservation_funding(db, reservation, "release")
        db.commit()
    assert len(ledger(rid, "capture")) == 1 and ledger(rid, "release") == []
    state = credit_state(client, ctx)
    assert state["reserved"] == 0 and state["consumed"] == 1_000_000


def test_d1_settlement_unique_command_blocks_concurrent_second_writer(client):
    """Two sessions that both pass the read check still cannot both settle:
    the shared per-reserve command id hits uq_ledger_command."""
    from sqlalchemy.exc import IntegrityError
    ctx = funded_reservation(client)
    rid = ctx["reservation"]["id"]
    with SessionLocal() as first:
        reserve = first.scalar(select(m.FinancialLedgerEntry).where(m.FinancialLedgerEntry.reservation_id == rid, m.FinancialLedgerEntry.entry_type == "reserve"))
        tenant_id, account_id, reserve_id, amount = reserve.tenant_id, reserve.credit_account_id, reserve.id, reserve.amount
        m.settle_reservation_funding(first, first.get(m.Reservation, rid), "capture"); first.commit()
    with SessionLocal() as second:
        second.add(m.FinancialLedgerEntry(tenant_id=tenant_id, credit_account_id=account_id, reservation_id=rid, command_id=f"reservation-settle:{reserve_id}", entry_type="release", amount=amount))
        with pytest.raises(IntegrityError):
            second.commit()
    assert ledger(rid, "release") == []


def test_d1_tenant_isolation_for_fulfilment_ready_list_and_credit(client):
    ctx = funded_reservation(client)
    rid = ctx["reservation"]["id"]
    with SessionLocal() as db:
        faraz_tenant = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        email = f"d1-supplier-{ctx['suffix']}@faraz.test"
        db.add(User(tenant_id=faraz_tenant, email=email, name="تأمین‌کننده فراز", role="supplier")); db.commit()
    other = login(client, email)
    assert fulfil(client, other, rid, f"d1-cross-{ctx['suffix']}").status_code == 404
    assert all(row["id"] != rid for row in client.get("/supplier/reservations/ready", headers=auth(other)).json())
    faraz = login(client, "employee@faraz.test")
    assert all(item["id"] != ctx["account_id"] for item in client.get("/me/organization-credit", headers=auth(faraz)).json())
    assert credit_state(client, ctx)["reserved"] == 1_000_000 and ledger(rid, "capture") == []


# ----------------------------------------------------------------- D6 sandbox

@pytest.fixture()
def sandbox(monkeypatch):
    import app.providers as providers
    from app.payment_sandbox import SandboxPaymentAdapter
    monkeypatch.setenv("ENVIRONMENT", "development")
    adapter = SandboxPaymentAdapter(base_url="http://127.0.0.1:8000")
    monkeypatch.setitem(providers.ADAPTERS, "payment", providers.ResilientAdapter(adapter))
    return adapter


def _initiate(client, ctx):
    response = client.post(f"/payments/{ctx['checkout']['payment_intent_id']}/initiate", headers=auth(ctx["employee"]))
    assert response.status_code == 202, response.text
    url = urlparse(response.json()["redirect_url"])
    assert url.scheme == "http" and url.hostname == "127.0.0.1" and url.path.startswith("/payments/sandbox/A")
    return url.path.rsplit("/", 1)[1], parse_qs(url.query)["state"][0]


def test_d6_sandbox_success_runs_real_verify_path_then_fulfils(client, sandbox):
    from app.payment_sandbox import SANDBOX_LABEL
    ctx = funded_reservation(client, amount=1_000_000, credit=600_000)
    authority, state = _initiate(client, ctx)
    page = client.get(f"/payments/sandbox/{authority}", params={"state": state})
    assert page.status_code == 200 and SANDBOX_LABEL in page.text and "400,000" in page.text
    assert page.headers["x-payment-sandbox"] == "true" and "noindex" in page.headers["x-robots-tag"]
    # Callback before any decision: real verify refuses (no fabricated success).
    early = client.get("/payments/zarinpal/callback", params={"state": state, "Authority": authority, "Status": "OK"})
    assert early.status_code == 502
    decided = client.post(f"/payments/sandbox/{authority}/decision", data={"state": state, "decision": "success"})
    assert decided.status_code == 200 and decided.json()["test_mode"] is True
    callback = client.get(decided.json()["callback_url"])
    assert callback.status_code == 200 and callback.json()["payment_status"] == "captured" and callback.json()["ref_id"].startswith("SANDBOX-TEST-")
    assert client.get(decided.json()["callback_url"]).json()["status"] == "duplicate"  # idempotent
    status_body = client.get(f"/payments/{ctx['checkout']['payment_intent_id']}", headers=auth(ctx["employee"])).json()
    assert status_body["captured_amount"] == 400_000 and status_body["receipt_reference"].startswith("SANDBOX-TEST-")
    # A later decision cannot flip the recorded outcome.
    assert client.post(f"/payments/sandbox/{authority}/decision", data={"state": state, "decision": "cancel"}).json()["decision"] == "success"
    response = fulfil(client, login(client, "supplier@aftab.test"), ctx["reservation"]["id"], f"d6-fulfil-{ctx['suffix']}")
    assert response.status_code == 200 and response.json()["reservation"]["status"] == "issued"
    assert [entry.amount for entry in ledger(ctx["reservation"]["id"], "capture")] == [600_000]


def test_d6_sandbox_cancel_and_tampered_decision_never_capture(client, sandbox):
    ctx = funded_reservation(client, amount=1_000_000, credit=0)
    authority, state = _initiate(client, ctx)
    redirected = client.post(f"/payments/sandbox/{authority}/decision", data={"state": state, "decision": "cancel"}, headers={"Accept": "text/html"}, follow_redirects=False)
    assert redirected.status_code == 303 and "Status=NOK" in redirected.headers["location"]
    assert client.get(redirected.headers["location"]).json()["payment_status"] == "failed"
    # Tamper the stored decision to "success" without a valid signature: verify must reject.
    from app.payment_sandbox import DECISION_SCOPE
    with SessionLocal() as db:
        row = db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.scope == DECISION_SCOPE, m.IdempotencyKey.key == authority))
        data = json.loads(row.response_json); data["decision"] = "success"; row.response_json = json.dumps(data); db.commit()
    tampered = client.get("/payments/zarinpal/callback", params={"state": state, "Authority": authority, "Status": "OK"})
    assert tampered.status_code == 502
    with SessionLocal() as db:
        assert db.get(m.PaymentIntent, ctx["checkout"]["payment_intent_id"]).status == "failed"
    # An invalid state token is refused before anything else.
    assert client.get(f"/payments/sandbox/{authority}", params={"state": "x" * 30}).status_code == 401


def test_d6_sandbox_is_refused_in_production_and_routes_hidden(client, monkeypatch):
    import app.providers as providers
    from app.payment_sandbox import SandboxPaymentAdapter
    monkeypatch.setenv("PAYMENT_PROVIDER", "sandbox")
    for environment in ("production", "prod", ""):
        monkeypatch.setenv("ENVIRONMENT", environment)
        with pytest.raises(RuntimeError, match="forbidden"):
            providers.configured_adapter("payment")
    monkeypatch.delenv("ENVIRONMENT")  # unset defaults to production: still refused
    with pytest.raises(RuntimeError, match="forbidden"):
        providers.configured_adapter("payment")
    for environment in ("development", "test", "staging"):
        monkeypatch.setenv("ENVIRONMENT", environment)
        assert providers.configured_adapter("payment").mode == "sandbox_local"
    monkeypatch.setenv("ZARINPAL_MODE", "sandbox")
    with pytest.raises(RuntimeError, match="cannot be combined"):
        providers.configured_adapter("payment")
    monkeypatch.delenv("ZARINPAL_MODE")
    # Even an injected sandbox adapter is inert once ENVIRONMENT says production.
    monkeypatch.setenv("ENVIRONMENT", "production")
    adapter = SandboxPaymentAdapter(base_url="http://127.0.0.1:8000")
    monkeypatch.setitem(providers.ADAPTERS, "payment", adapter)
    assert adapter.health().status == "configuration_error"
    assert client.get(f"/payments/sandbox/A{'a' * 35}", params={"state": "x" * 30}).status_code == 404
    assert client.post(f"/payments/sandbox/A{'a' * 35}/decision", data={"state": "x" * 30, "decision": "success"}).status_code == 404


def test_d6_sandbox_routes_absent_without_sandbox_adapter(client):
    assert client.get(f"/payments/sandbox/A{'b' * 35}", params={"state": "x" * 30}).status_code == 404
