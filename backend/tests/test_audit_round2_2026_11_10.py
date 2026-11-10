"""Regression tests for the second 2026-11-10 fix round: KT-04, KT-05, KT-07, review N2, N4, N5, N6.

Each test is negative-first: rows the caller must not see, a privileged DB role, a top-up by the
same person who requested it, a reused command id, an out-of-scope id that must look missing.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

import app.main as main_module
from app import operations as m
from app.db_role_guard import assert_restricted_api_role, restricted_role_problems
from app.main import AuditEvent, SessionLocal, User

from test_audit_urgent_2026_11_10 import _fulfill, _issued_reservation, _new_supplier, _new_user, _paid_reservation, _reissue, _tenant_id
from test_booking_orchestration import active_supplier, auth, login
from test_credit_fulfilment_sandbox_d1_d6 import funded_reservation


# ---------------------------------------------------------------- KT-04 / N2 supplier queue
def _queue(client, token, **params):
    return client.get("/supplier/reservations/ready", headers=auth(token), params=params)


def _raw_paid_reservation(tenant_id, user_id, supplier_ids, created_at, mode="manual_supplier"):
    """Reservation + booking items + captured payment written directly (fast bulk fixture)."""
    with SessionLocal() as db:
        r = m.Reservation(tenant_id=tenant_id, user_id=user_id, service_type="package" if len(supplier_ids) > 1 else "flight", status="reserved", booking_reference=f"KS-T{uuid.uuid4().hex[:10].upper()}", price_snapshot_json=json.dumps({"total_amount": 1000, "currency": "IRR"}), created_at=created_at)
        db.add(r); db.flush()
        for sid in supplier_ids:
            db.add(m.BookingItem(tenant_id=tenant_id, reservation_id=r.id, item_type="flight", snapshot_json=json.dumps({"title": "T", "supplier_id": sid, "fulfillment_mode": mode})))
        db.add(m.PaymentIntent(tenant_id=tenant_id, user_id=user_id, reservation_id=r.id, command_id=uuid.uuid4().hex, amount=1000, captured_amount=1000, status="captured", currency="IRR", provider_key="mock"))
        db.commit()
        return r.id


def test_booking_item_scope_columns_follow_snapshot():
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == "employee@aftab.test"))
    rid = _raw_paid_reservation(_tenant_id(), uid, ["sup-col-test"], datetime.now(timezone.utc))
    with SessionLocal() as db:
        item = db.scalar(select(m.BookingItem).where(m.BookingItem.reservation_id == rid))
        assert (item.supplier_id, item.fulfillment_mode) == ("sup-col-test", "manual_supplier")
        item.snapshot_json = json.dumps({"supplier_id": "sup-col-other", "fulfillment_mode": "provider"}); db.commit()
        db.refresh(item)
        assert (item.supplier_id, item.fulfillment_mode) == ("sup-col-other", "provider")


def test_queue_filters_scope_before_limit_and_paginates(client):
    tenant_id = _tenant_id()
    owner_email = _new_user("supplier", "queue-owner")
    own_supplier = _new_supplier(member_email=owner_email)
    other_supplier = _new_supplier()
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == "employee@aftab.test"))
    base = datetime.now(timezone.utc) - timedelta(days=3)
    own = [_raw_paid_reservation(tenant_id, uid, [own_supplier], base + timedelta(minutes=i)) for i in range(3)]
    # 205 newer reservations of another supplier: the old query took the newest 200 tenant-wide and lost `own`.
    for i in range(205):
        _raw_paid_reservation(tenant_id, uid, [other_supplier], base + timedelta(hours=1, seconds=i))
    token = login(client, owner_email)["access_token"]
    full = _queue(client, token)
    assert full.status_code == 200
    assert [row["id"] for row in full.json()] == list(reversed(own))
    page1 = _queue(client, token, limit=2)
    assert [row["id"] for row in page1.json()] == [own[2], own[1]]
    cursor = page1.headers["X-Next-Cursor"]
    page2 = _queue(client, token, limit=2, before=cursor)
    assert [row["id"] for row in page2.json()] == [own[0]] and "X-Next-Cursor" not in page2.headers
    assert _queue(client, token, before="not-a-cursor").status_code == 422


def test_queue_hides_mixed_supplier_packages_and_lists_single_supplier_package_once(client):
    tenant_id = _tenant_id()
    owner_email = _new_user("supplier", "queue-pkg")
    mine = _new_supplier(member_email=owner_email)
    theirs = _new_supplier()
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == "employee@aftab.test"))
    now = datetime.now(timezone.utc)
    mixed = _raw_paid_reservation(tenant_id, uid, [mine, theirs], now)
    single = _raw_paid_reservation(tenant_id, uid, [mine, mine], now - timedelta(seconds=1))
    provider_leg = _raw_paid_reservation(tenant_id, uid, [mine], now - timedelta(seconds=2), mode="provider")
    ids = [row["id"] for row in _queue(client, login(client, owner_email)["access_token"]).json()]
    assert mixed not in ids and provider_leg not in ids
    assert ids.count(single) == 1


# ---------------------------------------------------------------- N6 uniform 404
def test_out_of_scope_reissue_and_fulfil_look_like_missing(client):
    rid, _ = _issued_reservation(client)
    outsider = login(client, _new_user("supplier", "n6"))["access_token"]
    missing = _reissue(client, outsider, str(uuid.uuid4()))
    denied = _reissue(client, outsider, rid)
    assert missing.status_code == denied.status_code == 404 and missing.json() == denied.json()
    paid, _ = _paid_reservation(client)
    a = _fulfill(client, outsider, str(uuid.uuid4()))
    b = _fulfill(client, outsider, paid)
    assert a.status_code == b.status_code == 404 and a.json() == b.json()


# ---------------------------------------------------------------- KT-05 API DB role guard
class _FakeConn:
    def __init__(self, superuser, bypass, owned):
        self.dialect = SimpleNamespace(name="postgresql"); self._row = SimpleNamespace(current_user="x", rolsuper=superuser, rolbypassrls=bypass); self._owned = owned
    def execute(self, _stmt):
        return SimpleNamespace(one=lambda: self._row)
    def scalar(self, _stmt):
        return self._owned


@pytest.mark.parametrize("superuser,bypass,owned,expected", [
    (True, False, 0, ["superuser"]), (False, True, 0, ["bypassrls"]), (False, False, 12, ["owns 12 tables"]), (False, False, 0, []),
])
def test_role_guard_rules(superuser, bypass, owned, expected):
    conn = _FakeConn(superuser, bypass, owned)
    assert restricted_role_problems(conn) == expected
    if expected:
        with pytest.raises(RuntimeError):
            assert_restricted_api_role(conn)
    else:
        assert_restricted_api_role(conn)


def test_role_guard_on_real_postgres_roles():
    import os
    from sqlalchemy import create_engine
    api_url, owner_url = os.getenv("TEST_POSTGRES_URL"), os.getenv("TEST_POSTGRES_OWNER_URL")
    if not api_url or not owner_url:
        pytest.skip("TEST_POSTGRES_URL / TEST_POSTGRES_OWNER_URL not set")
    with create_engine(api_url).connect() as c:
        assert restricted_role_problems(c) == []
    with create_engine(owner_url).connect() as c:
        assert restricted_role_problems(c)


# ---------------------------------------------------------------- KT-07 wallet funding maker-checker
def _wallet(tag):
    with SessionLocal() as db:
        w = m.Wallet(tenant_id=_tenant_id(), owner_type="organization", owner_reference=f"kt07-{tag}-{uuid.uuid4().hex[:8]}"); db.add(w); db.commit()
        return w.id


def _fund(client, token, wallet_id, amount, command_id=None):
    return client.post(f"/wallets/{wallet_id}/commands", headers=auth(token), json={"command_id": command_id or f"kt07-{uuid.uuid4().hex}", "entry_type": "allocate", "amount": amount})


def _available(wallet_id):
    with SessionLocal() as db:
        return m.wallet_balances(db, tenant_id=_tenant_id(), wallet_id=wallet_id)["available"]


def test_large_top_up_waits_for_a_second_finance_user(client, monkeypatch):
    monkeypatch.setattr(main_module, "WALLET_FUNDING_APPROVAL_THRESHOLD", 5_000)
    maker = login(client, _new_user("finance_operator", "maker"))["access_token"]
    checker = login(client, _new_user("finance_operator", "checker"))["access_token"]
    wid = _wallet("large")
    small = _fund(client, maker, wid, 1_000)
    assert small.status_code == 200 and small.json()["status"] == "posted" and _available(wid) == 1_000
    cmd = f"kt07-large-{uuid.uuid4().hex}"
    pending = _fund(client, maker, wid, 5_000, cmd)
    assert pending.status_code == 202 and pending.json()["status"] == "pending" and _available(wid) == 1_000
    assert _fund(client, maker, wid, 5_000, cmd).status_code == 202  # identical replay
    assert _fund(client, maker, wid, 6_000, cmd).status_code == 409  # same key, other amount
    rid = pending.json()["request_id"]
    assert rid in [r["request_id"] for r in client.get("/wallet-funding-requests", headers=auth(checker)).json()]
    decide = lambda token, d="approve": client.post(f"/wallet-funding-requests/{rid}/decision", headers=auth(token), json={"decision": d})
    assert decide(maker).status_code == 403 and _available(wid) == 1_000
    assert decide(login(client, "employee@aftab.test")["access_token"]).status_code == 403
    approved = decide(checker)
    assert approved.status_code == 200 and approved.json()["status"] == "approved" and _available(wid) == 6_000
    assert decide(checker).status_code == 200 and _available(wid) == 6_000  # idempotent
    assert decide(checker, "reject").status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(m.FinancialLedgerEntry).where(m.FinancialLedgerEntry.wallet_id == wid)) == 2


def test_daily_operator_total_routes_further_top_ups_to_approval(client, monkeypatch):
    monkeypatch.setattr(main_module, "WALLET_FUNDING_DAILY_MAX_PER_OPERATOR", 3_000)
    maker = login(client, _new_user("finance_operator", "daily"))["access_token"]
    wid = _wallet("daily")
    assert _fund(client, maker, wid, 2_000).status_code == 200
    assert _fund(client, maker, wid, 1_000).status_code == 200
    over = _fund(client, maker, wid, 1)
    assert over.status_code == 202 and over.json()["status"] == "pending" and _available(wid) == 3_000


def test_rejected_top_up_posts_nothing(client, monkeypatch):
    monkeypatch.setattr(main_module, "WALLET_FUNDING_APPROVAL_THRESHOLD", 10)
    maker = login(client, _new_user("finance_operator", "rej-maker"))["access_token"]
    checker = login(client, _new_user("finance_operator", "rej-checker"))["access_token"]
    wid = _wallet("reject")
    rid = _fund(client, maker, wid, 50).json()["request_id"]
    r = client.post(f"/wallet-funding-requests/{rid}/decision", headers=auth(checker), json={"decision": "reject", "reason": "سند ناقص"})
    assert r.status_code == 200 and r.json()["status"] == "rejected" and _available(wid) == 0
    assert client.post(f"/wallet-funding-requests/{rid}/decision", headers=auth(checker), json={"decision": "approve"}).status_code == 409


# ---------------------------------------------------------------- N4 / N5 command-id conflict handling
def test_checkout_command_conflict_gets_its_own_message(client, monkeypatch):
    def boom(*_a, **_k):
        raise m.LedgerCommandConflict("conflict")
    monkeypatch.setattr(m, "apply_organization_credit_command", boom)
    with pytest.raises(AssertionError) as info:
        funded_reservation(client)
    assert "COMMAND_ID_CONFLICT" in str(info.value) and "funding" in str(info.value)


def test_settlement_conflict_is_logged(client, monkeypatch, caplog):
    ctx = funded_reservation(client)
    def boom(*_a, **_k):
        raise m.LedgerCommandConflict("conflict")
    monkeypatch.setattr(m, "apply_organization_credit_command", boom)
    with caplog.at_level(logging.WARNING, logger="karenseir.funding"), SessionLocal() as db:
        reservation = db.get(m.Reservation, ctx["reservation"]["id"])
        m.settle_reservation_funding(db, reservation, "capture")
        db.rollback()
    assert any(rec.getMessage() == "reservation_funding_settlement_conflict" for rec in caplog.records)
