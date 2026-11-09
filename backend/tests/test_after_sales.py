"""Panels Phase 1 after-sales loop: customer request -> ops decision -> two-person finance refund -> customer timeline.

Covers the state machine (every action from every status), C-1 (customers only request), the two-person rule, idempotency,
tenant isolation, money math (penalty, VAT-on-commission reversal per E2E-C) and the reconciliation actions."""
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app import after_sales as A
from app.main import SessionLocal, Tenant, User
from app.operations import (FinancialLedgerEntry, PaymentIntent, PriceBreakdown, ReconciliationRecord, RefundRecord, Reservation,
                            Wallet, wallet_balances)


# ---------------------------------------------------------------------------------------------- helpers
def _user(role: str, tenant_slug: str = "aftab-bank") -> str:
    email = f"as-{role}-{uuid.uuid4().hex[:10]}@{tenant_slug}.test"
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        db.add(User(tenant_id=tenant.id, email=email, name=f"آزمون {role}", role=role)); db.commit()
    return email


def login(client, email: str) -> dict:
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def key() -> dict:
    return {"Idempotency-Key": f"as-{uuid.uuid4().hex}"}


def policy(penalty: int) -> dict:
    return {"verified": True, "source": "supplier-contract-test", "verified_at": datetime.now(timezone.utc).isoformat(),
            "cancellation": {"refundable": True, "penalty_amount": penalty}}


def booking(email: str, *, total=44_550_000, penalty=13_750_000, verified=True, status="issued", breakdown=True) -> str:
    """E2E-C example: supplier 44,000,000 (incl. taxes) + service fee 500,000 + its VAT 50,000; airline commission 1,200,000."""
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        res = Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="flight", status=status, booking_reference=f"KR-{uuid.uuid4().hex[:8].upper()}",
                          price_snapshot_json=json.dumps({"total_amount": total, "currency": "IRR"}),
                          policy_at_booking_json=json.dumps(policy(penalty) if verified else {}))
        db.add(res); db.flush()
        db.add(PaymentIntent(tenant_id=u.tenant_id, reservation_id=res.id, user_id=u.id, command_id=f"as-pay-{uuid.uuid4().hex}", amount=total,
                             captured_amount=total, status="captured", provider_reference=f"ZP-{uuid.uuid4().hex[:6]}"))
        if breakdown:
            db.add(PriceBreakdown(tenant_id=u.tenant_id, booking_id=res.id, total_selling_price=total, service_fee=500_000, supplier_commission=1_200_000,
                                  platform_markup=0, supplier_net_rate_irr=44_000_000))
        db.commit()
        return res.id


def submit(client, h, rid, request_type="cancel", destination="wallet"):
    r = client.post(f"/reservations/{rid}/service-requests", headers={**h, **key()},
                    json={"request_type": request_type, "reason": "تغییر برنامهٔ سفر", "refund_destination": destination})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def act(client, h, req_id, action, expect=200, **body):
    r = client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**h, **key()}, json={"action": action, **body})
    assert r.status_code == expect, r.text
    return r.json()


@pytest.fixture()
def people(client):
    cust = _user("customer"); ops = _user("backoffice_expert"); fin1 = _user("finance_operator"); fin2 = _user("finance_operator")
    return {"cust_email": cust, "cust": login(client, cust), "ops": login(client, ops), "fin1": login(client, fin1), "fin2": login(client, fin2)}


# ---------------------------------------------------------------------------------------------- state machine
@pytest.mark.parametrize("action", sorted(A.TRANSITIONS))
@pytest.mark.parametrize("status", A.REQUEST_STATUSES)
def test_state_machine_allows_exactly_the_declared_transitions(action, status):
    sources, target, _ = A.TRANSITIONS[action]
    if status in sources:
        assert A.next_status(status, action) == target
    else:
        with pytest.raises(A.InvalidTransition):
            A.next_status(status, action)


def test_terminal_statuses_have_no_way_out_and_customer_actions_are_only_requests():
    for status in A.TERMINAL_STATUSES:
        assert all(status not in src for src, _, _ in A.TRANSITIONS.values())
    assert {a for a, (_, _, k) in A.TRANSITIONS.items() if k == "customer"} == {"withdraw", "customer_reply"}
    assert A.TRANSITIONS["withdraw"][0] == frozenset({"submitted"})
    with pytest.raises(A.InvalidTransition):
        A.next_status("approved", "nonexistent")


@pytest.mark.parametrize("action,src,dst", [("prepare", "pending_finance", "awaiting_approval"), ("approve", "awaiting_approval", "succeeded"),
                                            ("decline", "awaiting_approval", "pending_finance"), ("return", "pending_finance", "returned")])
def test_refund_state_machine(action, src, dst):
    assert A.next_refund_status(src, action) == dst
    with pytest.raises(A.InvalidTransition):
        A.next_refund_status("succeeded", action)
    with pytest.raises(A.InvalidTransition):
        A.next_refund_status("pending_finance", "approve")  # never pay without a prepared (maker) step


# ---------------------------------------------------------------------------------------------- money math
def test_money_math_e2e_c_penalty_case():
    assert A.refund_amount_for(44_550_000, 13_750_000) == 30_800_000
    v = A.vat_reversal(refund_amount=30_800_000, customer_total=44_550_000, service_fee=500_000, platform_markup=0, agency_commission=1_200_000)
    assert v["fare_part"] == 44_000_000 and v["fare_refunded"] == 30_800_000
    assert v["agency_commission_reversed"] == 840_000 and v["service_fee_reversed"] == 0
    assert v["vat_base_reversed"] == 840_000 and v["vat_reversed"] == 84_000


def test_money_math_carrier_cancel_returns_service_fee_and_its_vat():
    v = A.vat_reversal(refund_amount=44_550_000, customer_total=44_550_000, service_fee=500_000, platform_markup=0, agency_commission=1_200_000)
    assert v["agency_commission_reversed"] == 1_200_000 and v["service_fee_reversed"] == 500_000
    assert v["vat_reversed"] == 170_000 and v["service_fee_vat_returned_to_customer"] == 50_000


def test_money_math_rounding_and_guards():
    assert A.half_up(5, 2) == 3 and A.half_up(4, 2) == 2 and A.vat_of(15) == 2 and A.vat_of(14) == 1
    for paid, pen in ((100, 101), (100, -1)):
        with pytest.raises(ValueError):
            A.refund_amount_for(paid, pen)
    assert A.vat_reversal(refund_amount=1, customer_total=None, service_fee=None, platform_markup=None, agency_commission=None)["basis"] == "unavailable"
    assert A.vat_reversal(refund_amount=10, customer_total=100, service_fee=200, platform_markup=0, agency_commission=0)["basis"] == "unavailable"


# ---------------------------------------------------------------------------------------------- full loop
def test_full_cancel_to_wallet_refund_loop_two_person_ledger_and_timeline(client, people):
    p = people
    rid = booking(p["cust_email"])
    opts = client.get(f"/reservations/{rid}/after-sales/options", headers=p["cust"]).json()
    assert opts["cancellable"] and opts["preview"]["penalty_amount"] == 13_750_000 and opts["preview"]["refundable_amount"] == 30_800_000
    assert {d["key"]: d["available"] for d in opts["destinations"]} == {"wallet": True, "bank_transfer": False, "gateway": False}
    req_id = submit(client, p["cust"], rid)
    assert client.get(f"/reservations/{rid}/after-sales/options", headers=p["cust"]).json()["cancellable"] is False

    queue = client.get("/ops/queues/service_requests", headers=p["ops"]).json()
    row = next(i for i in queue["items"] if i["id"] == req_id)
    assert row["next"]["eta"] and row["status"] == "submitted"
    assert client.post(f"/ops/queues/service_requests/items/{req_id}/assign", headers=p["ops"], json={}).status_code == 200
    assert any(i["id"] == req_id for i in client.get("/ops/queues/service_requests?assignee=me", headers=p["ops"]).json()["items"])
    act(client, p["ops"], req_id, "approve", expect=409)  # must be under review first
    act(client, p["ops"], req_id, "start_review")
    act(client, p["ops"], req_id, "request_supplier", supplier_reference="W5-REF")
    act(client, p["ops"], req_id, "record_supplier_response", supplier_refundable_amount=30_800_000, supplier_penalty_amount=13_200_000)
    detail = client.get(f"/ops/service-requests/{req_id}", headers=p["ops"]).json()
    assert "approve" in detail["allowed_actions"] and detail["money"]["customer_total"] == 44_550_000 and "supplier_commission" not in json.dumps(detail["money"])
    out = act(client, p["ops"], req_id, "approve", penalty_mode="policy", reason="طبق قوانین لغو زمان خرید")
    assert out["status"] == "refund_queued" and out["approved_amount"] == 30_800_000 and out["penalty_amount"] == 13_750_000
    refund_id = out["refund"]["id"]
    with SessionLocal() as db:
        assert db.get(Reservation, rid).status == "cancelled"

    fq = client.get("/finance/refunds", headers=p["fin1"]).json()
    assert any(i["id"] == refund_id and i["status"] == "pending_finance" for i in fq["items"])
    prep_key = key()
    prep = client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin1"], **prep_key}, json={"method": "wallet", "note": "کیف پول"})
    assert prep.status_code == 200 and prep.json()["status"] == "awaiting_approval"
    assert client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin1"], **prep_key}, json={"method": "wallet", "note": "کیف پول"}).json() == prep.json()
    assert client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin1"], **prep_key}, json={"method": "bank_transfer", "bank_reference": "1234567"}).status_code == 409
    # the maker can never be the checker
    assert client.post(f"/finance/refunds/{refund_id}/approve", headers={**p["fin1"], **key()}).status_code == 403
    assert client.get(f"/finance/refunds/{refund_id}", headers=p["fin1"]).json()["can_approve"] is False
    approve_key = key()
    paid = client.post(f"/finance/refunds/{refund_id}/approve", headers={**p["fin2"], **approve_key})
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "succeeded"
    again = client.post(f"/finance/refunds/{refund_id}/approve", headers={**p["fin2"], **approve_key})
    assert again.status_code == 200 and again.json() == paid.json()
    assert client.post(f"/finance/refunds/{refund_id}/approve", headers={**p["fin2"], **key()}).status_code == 409

    fd = client.get(f"/finance/refunds/{refund_id}", headers=p["fin2"]).json()
    assert sum(j["debit"] for j in fd["journal"]) == sum(j["credit"] for j in fd["journal"]) == 30_800_000 and len(fd["journal"]) == 2
    tax = fd["tax_document"]
    assert tax["subject"] == "RETURN" and tax["status"] == "PENDING" and tax["basis"] == "price_breakdown"
    assert tax["totals"]["vat_reversed"] == 84_000 and tax["lines"] == [{"code": "AGENCY_COMMISSION", "base_reversed_irr": 840_000, "vat_bps": 1000, "vat_irr": 84_000}]
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == p["cust_email"]))
        w = db.scalar(select(Wallet).where(Wallet.owner_type == "user", Wallet.owner_reference == str(u.id)))
        assert wallet_balances(db, tenant_id=u.tenant_id, wallet_id=w.id)["available"] == 30_800_000
        assert db.scalar(select(func.count()).select_from(FinancialLedgerEntry).where(FinancialLedgerEntry.wallet_id == w.id)) == 1
        assert db.get(Reservation, rid).status == "refunded"
        pay = db.scalar(select(PaymentIntent).where(PaymentIntent.reservation_id == rid))
        assert pay.refunded_amount == 30_800_000 and pay.status == "captured"
        wallet_id = w.id

    mine = client.get(f"/me/service-requests/{req_id}", headers=p["cust"]).json()
    assert mine["status"] == "refund_paid" and mine["refund"]["status"] == "succeeded"
    types = [s["type"] for s in mine["timeline"]["steps"]]
    assert types[:2] == ["submitted", "start_review"] and "approve" in types and "refund_paid" in types
    assert "assign" not in types and "finance_prepare" in types
    assert all(s["actor"] in A.ACTOR_FA.values() for s in mine["timeline"]["steps"])  # customers see roles, not staff names
    assert mine["next"]["title"] and mine["next"]["eta"]
    assert any(r["id"] == refund_id and r["status"] == "succeeded" for r in client.get("/me/refunds", headers=p["cust"]).json())
    hist = client.get(f"/me/wallets/{wallet_id}/history", headers=p["cust"]).json()
    assert hist["items"][0]["label"] == "استرداد" and hist["items"][0]["amount"] == 30_800_000
    tl = client.get(f"/reservations/{rid}/timeline", headers=p["cust"]).json()
    assert [s["to_status"] for s in tl["steps"]][-2:] == ["cancelled", "refunded"] and tl["requests"][0]["id"] == req_id
    act(client, p["ops"], req_id, "close")
    assert client.get(f"/me/service-requests/{req_id}", headers=p["cust"]).json()["next"] is None


def test_bank_transfer_needs_reference_and_gateway_is_refused(client, people):
    p = people
    with SessionLocal() as db:
        from app.commerce import UserBankAccount
        u = db.scalar(select(User).where(User.email == p["cust_email"]))
        db.add(UserBankAccount(tenant_id=u.tenant_id, user_id=u.id, holder_name="آزمون مشتری", sheba="IR060120000000001234567890", sheba_bank="ملت")); db.commit()
    rid = booking(p["cust_email"])
    req_id = submit(client, p["cust"], rid, destination="bank_transfer")
    act(client, p["ops"], req_id, "start_review")
    refund_id = act(client, p["ops"], req_id, "approve", penalty_mode="policy")["refund"]["id"]
    assert client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin1"], **key()}, json={"method": "gateway"}).status_code == 409
    assert client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin1"], **key()}, json={"method": "bank_transfer"}).status_code == 422
    r = client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin1"], **key()}, json={"method": "bank_transfer", "bank_reference": "PAYA-140508-77"})
    assert r.status_code == 200 and r.json()["destination_detail"]["sheba_masked"].startswith("IR06")
    assert "1234567890" not in json.dumps(r.json())
    # checker declines -> back to the maker step; then a fresh prepare + approval pays with the bank reference
    assert client.post(f"/finance/refunds/{refund_id}/decline", headers=p["fin1"], json={"reason": "خودم نمی‌توانم"}).status_code == 403
    assert client.post(f"/finance/refunds/{refund_id}/decline", headers=p["fin2"], json={"reason": "کد پیگیری اشتباه است"}).json()["status"] == "pending_finance"
    client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin2"], **key()}, json={"method": "bank_transfer", "bank_reference": "PAYA-140508-78"})
    paid = client.post(f"/finance/refunds/{refund_id}/approve", headers={**p["fin1"], **key()}).json()
    assert paid["status"] == "succeeded" and paid["bank_reference"] == "PAYA-140508-78"
    assert client.get(f"/me/service-requests/{req_id}", headers=p["cust"]).json()["refund"]["bank_reference"] == "PAYA-140508-78"


# ---------------------------------------------------------------------------------------------- permissions (C-1, maker-checker)
def test_customer_cannot_decide_or_execute_and_ops_cannot_pay(client, people):
    p = people
    rid = booking(p["cust_email"])
    req_id = submit(client, p["cust"], rid)
    for h in (p["cust"], p["fin1"]):
        assert client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**h, **key()}, json={"action": "approve", "penalty_mode": "policy"}).status_code == 403
        assert client.get("/ops/queues/service_requests", headers=h).status_code == 403
    act(client, p["ops"], req_id, "start_review")
    refund_id = act(client, p["ops"], req_id, "approve", penalty_mode="policy")["refund"]["id"]
    for h in (p["cust"], p["ops"]):
        assert client.get("/finance/refunds", headers=h).status_code == 403
        assert client.post(f"/finance/refunds/{refund_id}/execute", headers={**h, **key()}, json={"method": "wallet"}).status_code == 403
        assert client.post(f"/finance/refunds/{refund_id}/approve", headers={**h, **key()}).status_code == 403
    # the customer's own legacy refund path cannot touch this queued refund either
    assert client.post(f"/refunds/{refund_id}/review", headers=p["cust"], json={"approve": True}).status_code == 403


def test_withdraw_and_reject_restore_the_reservation_and_need_reasons(client, people):
    p = people
    rid = booking(p["cust_email"])
    req_id = submit(client, p["cust"], rid)
    out = client.post(f"/me/service-requests/{req_id}/withdraw", headers={**p["cust"], **key()})
    assert out.status_code == 200 and out.json()["status"] == "withdrawn"
    with SessionLocal() as db:
        assert db.get(Reservation, rid).status == "issued"
    req2 = submit(client, p["cust"], rid, request_type="change", destination=None)
    act(client, p["ops"], req2, "start_review")
    assert client.post(f"/me/service-requests/{req2}/withdraw", headers={**p["cust"], **key()}).status_code == 409  # only while submitted
    act(client, p["ops"], req2, "reject", expect=422)
    act(client, p["ops"], req2, "need_customer", reason="تاریخ جدید را مشخص کنید")
    mine = client.get(f"/me/service-requests/{req2}", headers=p["cust"]).json()
    assert mine["status"] == "needs_customer" and mine["can_reply"] and mine["next"]["paused"]
    assert client.post(f"/me/service-requests/{req2}/reply", headers={**p["cust"], **key()}, json={"message": "پانزدهم آذر"}).json()["status"] == "under_review"
    act(client, p["ops"], req2, "reject", reason="پرواز جایگزین در این تاریخ وجود ندارد")
    with SessionLocal() as db:
        assert db.get(Reservation, rid).status == "issued"
    assert client.get(f"/me/service-requests/{req2}", headers=p["cust"]).json()["decision_reason"].startswith("پرواز")


def test_manual_penalty_needs_reason_and_override_above_quote(client, people):
    p = people
    rid = booking(p["cust_email"], verified=False, breakdown=False)
    req_id = submit(client, p["cust"], rid)
    act(client, p["ops"], req_id, "start_review")
    act(client, p["ops"], req_id, "approve", expect=422)  # no verified policy -> manual with reason
    act(client, p["ops"], req_id, "approve", expect=422, penalty_mode="manual", penalty_amount=1_000_000)
    act(client, p["ops"], req_id, "approve", expect=403, penalty_mode="manual", penalty_amount=1_000_000, reason="جریمهٔ اعلامی ایرلاین")
    # finance_operator holds refund:override (spec §4) — platform admin as the supervisor here
    admin = login(client, _user("platform_admin"))
    out = act(client, admin, req_id, "approve", penalty_mode="manual", penalty_amount=1_000_000, reason="جریمهٔ اعلامی ایرلاین طبق ایمیل")
    assert out["penalty_source"] == "manual" and out["approved_amount"] == 43_550_000
    refund_id = out["refund"]["id"]
    fin = client.get(f"/finance/refunds/{refund_id}", headers=p["fin1"]).json()
    assert fin["breakdown"]["basis"] == "unavailable"
    client.post(f"/finance/refunds/{refund_id}/execute", headers={**p["fin1"], **key()}, json={"method": "wallet"})
    paid = client.get(f"/finance/refunds/{refund_id}", headers=p["fin1"]).json()
    client.post(f"/finance/refunds/{refund_id}/approve", headers={**p["fin2"], **key()})
    doc = client.get(f"/finance/refunds/{refund_id}", headers=p["fin1"]).json()["tax_document"]
    assert paid["status"] == "awaiting_approval" and doc["basis"] == "unavailable" and doc["totals"]["vat_reversed"] is None and doc["lines"] == []


def test_finance_return_sends_back_to_ops_and_reapproval_queues_a_new_refund(client, people):
    p = people
    rid = booking(p["cust_email"])
    req_id = submit(client, p["cust"], rid)
    act(client, p["ops"], req_id, "start_review")
    first = act(client, p["ops"], req_id, "approve", penalty_mode="policy")["refund"]["id"]
    assert client.post(f"/finance/refunds/{first}/return", headers=p["fin1"], json={"reason": "مبلغ جریمه با پاسخ ایرلاین نمی‌خواند"}).json()["status"] == "returned"
    assert client.get(f"/ops/service-requests/{req_id}", headers=p["ops"]).json()["status"] == "under_review"
    act(client, p["ops"], req_id, "reject", expect=409, reason="رزرو لغو شده است")
    second = act(client, p["ops"], req_id, "approve", penalty_mode="policy")["refund"]["id"]
    assert second != first
    with SessionLocal() as db:
        assert db.get(RefundRecord, first).status == "returned" and db.get(RefundRecord, second).status == "pending_finance"


def test_action_idempotency_key_is_bound_to_the_request(client, people):
    p = people
    rid = booking(p["cust_email"])
    req_id = submit(client, p["cust"], rid)
    k = key()
    a = client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**p["ops"], **k}, json={"action": "start_review"})
    b = client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**p["ops"], **k}, json={"action": "start_review"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**p["ops"], **k}, json={"action": "close"}).status_code == 409


# ---------------------------------------------------------------------------------------------- tenant isolation
def test_other_tenant_staff_and_customers_see_nothing(client, people):
    p = people
    rid = booking(p["cust_email"])
    req_id = submit(client, p["cust"], rid)
    act(client, p["ops"], req_id, "start_review")
    refund_id = act(client, p["ops"], req_id, "approve", penalty_mode="policy")["refund"]["id"]
    ops_b = login(client, _user("backoffice_expert", "faraz-industries")); fin_b = login(client, _user("finance_operator", "faraz-industries"))
    cust_b = login(client, _user("customer", "faraz-industries")); cust_a2 = login(client, _user("customer"))
    assert client.get(f"/ops/service-requests/{req_id}", headers=ops_b).status_code == 404
    assert all(i["id"] != req_id for i in client.get("/ops/queues/service_requests", headers=ops_b).json()["items"])
    assert client.post(f"/ops/queues/service_requests/items/{req_id}/assign", headers=ops_b, json={}).status_code == 404
    assert client.get(f"/finance/refunds/{refund_id}", headers=fin_b).status_code == 404
    assert client.post(f"/finance/refunds/{refund_id}/execute", headers={**fin_b, **key()}, json={"method": "wallet"}).status_code == 404
    assert all(i["id"] != refund_id for i in client.get("/finance/refunds?status=all", headers=fin_b).json()["items"])
    for h in (cust_b, cust_a2):
        assert client.get(f"/me/service-requests/{req_id}", headers=h).status_code == 404
        assert client.get(f"/reservations/{rid}/after-sales/options", headers=h).status_code == 404
        assert client.get(f"/reservations/{rid}/timeline", headers=h).status_code == 404
        assert client.post(f"/me/service-requests/{req_id}/withdraw", headers={**h, **key()}).status_code == 404
    # assigning to a user of another tenant is refused
    with SessionLocal() as db:
        other = db.scalar(select(User).where(User.tenant_id != db.scalar(select(User.tenant_id).where(User.email == p["cust_email"])), User.role == "backoffice_expert"))
    assert client.post(f"/ops/queues/service_requests/items/{req_id}/assign", headers=p["ops"], json={"user_id": other.id}).status_code == 422


# ---------------------------------------------------------------------------------------------- reconciliation actions (FIN-04)
def test_reconciliation_link_unlink_resolve_with_audit(client, people):
    p = people
    rid = booking(p["cust_email"])
    with SessionLocal() as db:
        pay = db.scalar(select(PaymentIntent).where(PaymentIntent.reservation_id == rid))
        pay_id, tenant_id = pay.id, pay.tenant_id
        rec = ReconciliationRecord(tenant_id=tenant_id, source_type="payment", source_id=str(uuid.uuid4()), external_reference="ZP-SETTLE-1",
                                   external_amount=44_550_000, status="DISPUTED", discrepancy_reason="no booking", command_id=f"as-rec-{uuid.uuid4().hex}")
        db.add(rec); db.commit(); rec_id = rec.id
    assert client.post(f"/finance/reconciliation/{rec_id}/link", headers=p["ops"], json={"target_type": "payment", "target_id": pay_id, "reason": "مبلغ و زمان یکسان"}).status_code == 403
    linked = client.post(f"/finance/reconciliation/{rec_id}/link", headers=p["fin1"], json={"target_type": "payment", "target_id": pay_id, "reason": "مبلغ و زمان یکسان"}).json()
    assert linked["status"] == "MATCHED" and linked["link"]["target_id"] == pay_id
    assert client.post(f"/finance/reconciliation/{rec_id}/resolution", headers=p["fin1"], json={"resolution_type": "other", "reason": "تطبیق شد"}).status_code == 409
    un = client.post(f"/finance/reconciliation/{rec_id}/unlink", headers=p["fin1"], json={"reason": "اشتباهی وصل شد"}).json()
    assert un["status"] == "DISPUTED" and un["link"] is None
    wrong = client.post(f"/finance/reconciliation/{rec_id}/link", headers=p["fin1"], json={"target_type": "reservation", "target_id": rid, "reason": "رزرو مرتبط"}).json()
    assert wrong["status"] == "MATCHED"
    client.post(f"/finance/reconciliation/{rec_id}/unlink", headers=p["fin1"], json={"reason": "برای حل دستی"})
    done = client.post(f"/finance/reconciliation/{rec_id}/resolution", headers=p["fin2"], json={"resolution_type": "gateway_fee", "reason": "کارمزد درگاه کسر شده بود"}).json()
    assert done["status"] == "RESOLVED" and done["resolution_note"].startswith("کارمزد درگاه")
    assert [e["event"] for e in done["audit_trail"]] == ["linked", "unlinked", "linked", "unlinked", "resolved"]
    fin_b = login(client, _user("finance_operator", "faraz-industries"))
    assert client.post(f"/finance/reconciliation/{rec_id}/unlink", headers=fin_b, json={"reason": "تلاش از مجموعهٔ دیگر"}).status_code == 404
    assert any(r["id"] == rec_id for r in client.get("/finance/reconciliation/records", headers=p["fin1"]).json()["items"])


def test_customer_price_breakdown_hides_cost_markup_commission_and_margin(client, people):
    p = people
    rid = booking(p["cust_email"])
    body = client.get(f"/reservations/{rid}/price-breakdown", headers=p["cust"]).json()
    assert body["total_selling_price"] == 44_550_000 and body["service_fee"] == 500_000
    for hidden in ("supplier_commission", "agent_commission", "platform_markup", "supplier_net_rate_irr", "total_cost", "gross_margin", "net_margin", "wl_revenue_share"):
        assert hidden not in body
