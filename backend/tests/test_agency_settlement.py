"""Panels Phase 2b — agency periodic settlement: statement lines (VAT on commission only, dated rate at the sale date), maker-checker
issue / adjustment / settle by two different finance users, immutability after issue, disputes and their timeline, refund to agency
credit from the after-sales loop (idempotent, never above the booking net) and how it shows in the next statement."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import agency_settlement as S
from app import operations as m
from app.agency_b2b import AgencyAccount, AgencyLedgerEntry, VatRate
from app.main import SessionLocal

from test_agency_b2b import _user, activate, flight_offer, fund, key, login, make_agency, price_check

TODAY = date.today().isoformat()


@pytest.fixture()
def sw(client):
    owner, agent, ops, fin1, fin2 = _user("agency_partner"), _user("agency_partner"), _user("backoffice_expert"), _user("finance_operator"), _user("finance_operator")
    a = make_agency(owner, commission_bps=120, agent_email=agent)
    w = {"agency_id": a, "owner": login(client, owner), "agent": login(client, agent), "ops": login(client, ops), "fin1": login(client, fin1), "fin2": login(client, fin2),
         "agent_email": agent}
    activate(client, w["owner"], w["ops"], a)
    fund(client, w["fin1"], w["fin2"], a, limit=500_000_000)
    return w


def book(client, w, amount=10_000_000, units=1) -> dict:
    offer = flight_offer(w["agent_email"], amount)
    pc = price_check(client, w["agent"], offer, units=units)
    r = client.post(f"/agency/{w['agency_id']}/credit-bookings", headers=w["agent"], json={"price_check_id": pc["id"], "command_id": f"cb-{uuid.uuid4().hex}"})
    assert r.status_code == 201, r.text
    return r.json()


def approve(client, h, request_id) -> dict:
    r = client.post(f"/maker-checker/requests/{request_id}/approve", json={}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def draft(client, w, start=TODAY, end=TODAY):
    return client.post("/finance/agency-settlements", headers=w["fin1"], json={"agency_id": w["agency_id"], "period_start": start, "period_end": end})


def balance(agency_id) -> int:
    with SessionLocal() as db:
        return db.scalar(select(AgencyAccount.balance_irr).where(AgencyAccount.agency_id == agency_id))


def by_type(st, t):
    return [x for x in st["lines"] if x["line_type"] == t]


def test_statement_issue_dispute_adjust_settle_and_next_period(client, sw):
    a = sw["agency_id"]
    book(client, sw, 10_000_000)
    r = draft(client, sw)
    assert r.status_code == 201, r.text
    st = r.json()
    # OPENING 0, SALE +net, COMMISSION −1.2%, VAT −10% of the commission only (never of the fare)
    assert by_type(st, "OPENING")[0]["amount_irr"] == 0
    assert by_type(st, "SALE")[0]["amount_irr"] == 10_000_000
    assert by_type(st, "COMMISSION")[0]["amount_irr"] == -120_000
    vat = by_type(st, "VAT")[0]
    assert vat["amount_irr"] == -12_000 and vat["vat_rate_bps"] == 1000 and vat["amount_irr"] != -1_000_000
    assert st["net_irr"] == 9_868_000 and st["status"] == "draft" and st["direction"] == "agency_pays"
    # the agency never sees a draft; an agent never sees settlements
    assert client.get(f"/agency/{a}/settlement-statements", headers=sw["owner"]).json()["items"] == []
    assert client.get(f"/agency/{a}/settlement-statements/{st['id']}", headers=sw["owner"]).status_code == 404
    assert client.get(f"/agency/{a}/settlement-statements", headers=sw["agent"]).status_code == 403
    # issue = maker-checker: the maker cannot approve, a second finance user can; ops cannot ask at all
    assert client.post(f"/finance/agency-settlements/{st['id']}/issue-request", json={}, headers={**sw["ops"], **key()}).status_code == 403
    k = key()
    ir = client.post(f"/finance/agency-settlements/{st['id']}/issue-request", json={}, headers={**sw["fin1"], **k})
    assert ir.status_code == 202, ir.text
    assert client.post(f"/finance/agency-settlements/{st['id']}/issue-request", json={}, headers={**sw["fin1"], **k}).json()["request_id"] == ir.json()["request_id"]
    assert client.post(f"/maker-checker/requests/{ir.json()['request_id']}/approve", json={}, headers=sw["fin1"]).status_code == 403
    assert client.get(f"/finance/agency-settlements/{st['id']}", headers=sw["fin1"]).json()["status"] == "draft"  # nothing before the checker
    approve(client, sw["fin2"], ir.json()["request_id"])
    issued = client.get(f"/agency/{a}/settlement-statements/{st['id']}", headers=sw["owner"]).json()
    assert issued["status"] == "issued" and issued["can_act"] is True
    lines_before = [(x["id"], x["amount_irr"]) for x in issued["lines"]]
    # one open statement at a time
    assert draft(client, sw).status_code == 409
    # dispute on the commission line → disputed; acceptance is blocked while it is open
    comm = by_type(issued, "COMMISSION")[0]
    assert client.post(f"/agency/{a}/settlement-statements/{st['id']}/disputes", headers=sw["agent"], json={"line_id": comm["id"], "reason": "نرخ کمیسیون قرارداد ۱.۷٪ است", "claimed_amount_irr": 50_000}).status_code == 403
    d = client.post(f"/agency/{a}/settlement-statements/{st['id']}/disputes", headers=sw["owner"], json={"line_id": comm["id"], "reason": "نرخ کمیسیون قرارداد ۱.۷٪ است", "claimed_amount_irr": 50_000})
    assert d.status_code == 201, d.text
    assert client.post(f"/agency/{a}/settlement-statements/{st['id']}/disputes", headers=sw["owner"], json={"line_id": comm["id"], "reason": "دوباره همان ردیف", "claimed_amount_irr": 1}).status_code == 409
    assert client.post(f"/agency/{a}/settlement-statements/{st['id']}/accept", json={}, headers=sw["owner"]).status_code == 409
    queue = client.get("/finance/agency-settlement-disputes", headers=sw["fin1"]).json()["items"]
    assert any(x["id"] == d.json()["id"] and x["status"] == "open" for x in queue)
    # accept with adjustment: an adjustment needs a second finance user, then becomes a NEW line (old lines untouched)
    res = client.post(f"/finance/agency-settlement-disputes/{d.json()['id']}/resolve", headers={**sw["fin1"], **key()},
                      json={"decision": "accept", "reason": "قرارداد بررسی شد؛ اصلاح می‌شود"})
    assert res.status_code == 200, res.text
    assert res.json()["dispute"]["status"] == "adjustment_pending" and res.json()["statement_status"] == "disputed"
    mc_id = res.json()["dispute"]["mc_request_id"]
    assert client.post(f"/maker-checker/requests/{mc_id}/approve", json={}, headers=sw["fin1"]).status_code == 403
    approve(client, sw["fin2"], mc_id)
    after = client.get(f"/agency/{a}/settlement-statements/{st['id']}", headers=sw["owner"]).json()
    assert after["status"] == "issued" and after["net_irr"] == 9_818_000
    assert [(x["id"], x["amount_irr"]) for x in after["lines"]][:len(lines_before)] == lines_before
    adj = by_type(after, "ADJUSTMENT")
    assert len(adj) == 1 and adj[0]["amount_irr"] == -50_000
    assert [e["type"] for e in after["timeline"]][-4:] == ["dispute_opened", "dispute_adjustment_requested", "dispute_accepted", "disputes_closed"]
    # the agency accepts; settle needs the bank reference of the agency's payment and a second finance user
    assert client.post(f"/agency/{a}/settlement-statements/{st['id']}/accept", json={"note": "تأیید"}, headers=sw["owner"]).json()["status"] == "accepted"
    assert client.post(f"/finance/agency-settlements/{st['id']}/settle-request", json={}, headers={**sw["fin1"], **key()}).status_code == 422
    sr = client.post(f"/finance/agency-settlements/{st['id']}/settle-request", json={"bank_reference": "PAYA-778812"}, headers={**sw["fin1"], **key()})
    assert sr.status_code == 202, sr.text
    assert balance(a) == -10_000_000
    approve(client, sw["fin2"], sr.json()["request_id"])
    done = client.get(f"/finance/agency-settlements/{st['id']}", headers=sw["fin1"]).json()
    assert done["status"] == "settled" and done["settle_reference"] == "PAYA-778812"
    assert balance(a) == 0  # commission+VAT 132,000 + adjustment 50,000 + payment 9,818,000 restore the period's credit use
    with SessionLocal() as db:
        types = [e.entry_type for e in db.scalars(select(AgencyLedgerEntry).where(AgencyLedgerEntry.agency_id == a))]
    assert {"COMMISSION", "ADJ_CREDIT", "SETTLE_IN"} <= set(types)
    # no adjustment after settlement
    assert client.post(f"/finance/agency-settlements/{st['id']}/adjustments", json={"amount_irr": 1000, "reason": "دیرهنگام"}, headers={**sw["fin1"], **key()}).status_code == 409
    # the next statement starts where this one stopped: opening + previous settlement postings net to zero
    nxt = draft(client, sw).json()
    assert by_type(nxt, "OPENING")[0]["amount_irr"] == 10_000_000
    assert {x["line_type"] for x in nxt["lines"]} == {"OPENING", "COMMISSION_CREDITED", "ADJUSTMENT_POSTED", "SETTLEMENT_PAYMENT"}
    assert nxt["net_irr"] == 0
    with SessionLocal() as db:
        events = {e.event_type for e in db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.aggregate_id == st["id"]))}
    assert {"agency_settlement.issued", "agency_settlement.accepted", "agency_settlement.settled"} <= events


def test_dispute_reject_and_negative_net_stays_as_agency_credit(client, sw):
    a = sw["agency_id"]
    fund(client, sw["fin1"], sw["fin2"], a, topup=10_000_000)  # prepaid: the sale is already paid
    book(client, sw, 10_000_000)
    st = draft(client, sw).json()
    assert by_type(st, "PAYMENT")[0]["amount_irr"] == -10_000_000
    assert st["net_irr"] == -132_000 and st["direction"] == "platform_owes"
    approve(client, sw["fin2"], client.post(f"/finance/agency-settlements/{st['id']}/issue-request", json={}, headers={**sw["fin1"], **key()}).json()["request_id"])
    sale = by_type(client.get(f"/agency/{a}/settlement-statements/{st['id']}", headers=sw["owner"]).json(), "SALE")[0]
    d = client.post(f"/agency/{a}/settlement-statements/{st['id']}/disputes", headers=sw["owner"], json={"line_id": sale["id"], "reason": "این رزرو لغو شده بود", "claimed_amount_irr": 10_000_000}).json()
    assert client.post(f"/finance/agency-settlement-disputes/{d['id']}/resolve", headers={**sw["fin1"], **key()}, json={"decision": "reject"}).status_code == 422  # reason required
    r = client.post(f"/finance/agency-settlement-disputes/{d['id']}/resolve", headers={**sw["fin1"], **key()}, json={"decision": "reject", "reason": "رزرو لغو نشده و صادر شده است"})
    assert r.status_code == 200 and r.json()["dispute"]["status"] == "rejected" and r.json()["statement_status"] == "issued"
    client.post(f"/agency/{a}/settlement-statements/{st['id']}/accept", json={}, headers=sw["owner"])
    # nothing to collect: no bank reference needed; the platform's debt stays in the agency account
    sr = client.post(f"/finance/agency-settlements/{st['id']}/settle-request", json={}, headers={**sw["fin1"], **key()})
    assert sr.status_code == 202, sr.text
    approve(client, sw["fin2"], sr.json()["request_id"])
    assert balance(a) == 132_000


def test_vat_comes_from_the_dated_table_at_the_sale_date(client, sw, monkeypatch):
    book(client, sw, 10_000_000)
    seen = []

    def dated(day, db=None, tenant_id=None):
        seen.append(day)
        return VatRate("TEST-900", 900, "جدول تاریخ‌دار آزمون")
    monkeypatch.setattr(S, "vat_rate_on", dated)
    st = draft(client, sw).json()
    assert by_type(st, "VAT")[0]["amount_irr"] == -10_800 and by_type(st, "VAT")[0]["vat_rate_id"] == "TEST-900"
    assert seen and all(isinstance(x, date) for x in seen)

    def missing(day, db=None, tenant_id=None):
        raise LookupError(day.isoformat())
    monkeypatch.setattr(S, "vat_rate_on", missing)
    r = draft(client, sw)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "VAT_RATE_MISSING"  # no rate = no statement, nothing guessed


def test_draft_rules_and_isolation(client, sw):
    a = sw["agency_id"]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert draft(client, sw, end=tomorrow).status_code == 422
    assert client.post("/finance/agency-settlements", headers=sw["ops"], json={"agency_id": a, "period_start": TODAY, "period_end": TODAY}).status_code == 403
    first = draft(client, sw).json()
    second = draft(client, sw).json()  # a new draft supersedes the old one
    assert client.get(f"/finance/agency-settlements/{first['id']}", headers=sw["fin1"]).json()["status"] == "superseded"
    # another agency's owner and another tenant's finance never see it
    other = _user("agency_partner")
    oa = make_agency(other)
    oh = login(client, other)
    assert client.get(f"/agency/{a}/settlement-statements", headers=oh).status_code == 404
    assert client.get(f"/agency/{oa}/settlement-statements/{second['id']}", headers=oh).status_code == 404
    far = login(client, _user("finance_operator", tenant_slug="faraz-industries"))
    assert client.get(f"/finance/agency-settlements/{second['id']}", headers=far).status_code == 404
    assert all(x["id"] != second["id"] for x in client.get("/finance/agency-settlements", headers=far).json()["items"])


def _cancel_quote(reservation_id: str, penalty: int) -> None:
    with SessionLocal() as db:
        res = db.get(m.Reservation, reservation_id)
        res.policy_at_booking_json = json.dumps({"verified": True, "source": "contract-test", "verified_at": datetime.now(timezone.utc).isoformat(),
                                                 "cancellation": {"refundable": True, "penalty_amount": penalty}})
        db.commit()


def test_refund_to_agency_credit_from_after_sales_and_next_statement(client, sw):
    a = sw["agency_id"]
    line = book(client, sw, 10_000_000)
    rid = line["reservation_id"]
    _cancel_quote(rid, 2_000_000)
    r = client.post(f"/reservations/{rid}/service-requests", headers={**sw["agent"], **key()}, json={"request_type": "cancel", "reason": "انصراف مسافر"})
    assert r.status_code == 202, r.text
    req_id = r.json()["id"]
    assert client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**sw["ops"], **key()}, json={"action": "start_review"}).status_code == 200
    detail = client.get(f"/ops/service-requests/{req_id}", headers=sw["ops"]).json()
    assert detail["agency_credit"]["required"] is True and detail["agency_credit"]["remaining_irr"] == 10_000_000
    ok = client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**sw["ops"], **key()},
                     json={"action": "approve", "penalty_mode": "policy", "refund_destination": "agency_credit"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["status"] == "refund_queued" and body["refund"]["destination"] == "agency_credit" and body["refund"]["amount"] == 8_000_000
    assert body["refund"]["status"] == "pending_approval"
    assert balance(a) == -10_000_000  # nothing moved yet
    mc_id = body["refund"]["mc_request_id"]
    assert client.post(f"/maker-checker/requests/{mc_id}/approve", json={}, headers=sw["ops"]).status_code == 403  # maker, and no refund:manage
    approve(client, sw["fin1"], mc_id)
    assert client.post(f"/maker-checker/requests/{mc_id}/approve", json={}, headers=sw["fin1"]).status_code == 200  # replay: no second credit
    assert balance(a) == -2_000_000
    with SessionLocal() as db:
        assert db.get(m.Reservation, rid).status == "refunded"
        assert db.get(m.BookingServiceRequest, req_id).status == "refund_paid"
        refunds = db.scalars(select(AgencyLedgerEntry).where(AgencyLedgerEntry.agency_id == a, AgencyLedgerEntry.entry_type == "REFUND")).all()
        assert len(refunds) == 1 and refunds[0].amount_irr == 8_000_000
        row = db.scalar(select(S.AgencyCreditRefund).where(S.AgencyCreditRefund.service_request_id == req_id))
        line_row = db.get(S.AgencyBookingLine, row.booking_line_id)
        # never more than the booking net in total
        with pytest.raises(ValueError):
            S.queue_credit_refund(db, user=type("U", (), {"id": row.created_by_user_id, "tenant_id": row.tenant_id})(), line=line_row, amount=3_000_000, penalty=0,
                                  source="service_request", key=f"x-{uuid.uuid4().hex}", audit=lambda *a, **k: None)
    mine = client.get(f"/me/service-requests/{req_id}", headers=sw["agent"]).json()
    assert mine["refund"]["destination"] == "agency_credit" and any(s["type"] == "refund_paid" for s in mine["timeline"]["steps"])
    # the next statement shows the credit back and reverses commission/VAT only on the refunded part (penalty keeps its commission)
    st = draft(client, sw).json()
    assert by_type(st, "REFUND")[0]["amount_irr"] == -8_000_000
    assert by_type(st, "COMMISSION_REVERSAL")[0]["amount_irr"] == 96_000 and by_type(st, "VAT_REVERSAL")[0]["amount_irr"] == 9_600
    assert st["net_irr"] == 10_000_000 - 120_000 - 12_000 - 8_000_000 + 96_000 + 9_600
    listing = client.get(f"/agency/{a}/settlement-statements", headers=sw["owner"]).json()["credit_refunds"]
    assert listing[0]["status"] == "executed" and listing[0]["amount_irr"] == 8_000_000


def test_rejected_credit_refund_can_be_requeued(client, sw):
    line = book(client, sw, 5_000_000)
    rid = line["reservation_id"]
    _cancel_quote(rid, 0)
    req_id = client.post(f"/reservations/{rid}/service-requests", headers={**sw["agent"], **key()}, json={"request_type": "cancel", "reason": "لغو"}).json()["id"]
    client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**sw["ops"], **key()}, json={"action": "start_review"})
    body = client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**sw["ops"], **key()}, json={"action": "approve", "penalty_mode": "policy"}).json()
    assert body["refund"]["destination"] == "agency_credit"  # paid from the agency account: no other destination exists
    rej = client.post(f"/maker-checker/requests/{body['refund']['mc_request_id']}/reject", json={"note": "مدرک لغو ناقص است"}, headers=sw["fin1"])
    assert rej.status_code == 200
    items = client.get("/finance/agency-credit-refunds", headers=sw["fin1"]).json()["items"]
    row = next(i for i in items if i["id"] == body["refund"]["id"])
    assert row["status"] == "rejected"
    rq = client.post(f"/finance/agency-credit-refunds/{row['id']}/requeue", headers=sw["ops"])
    assert rq.status_code == 202 and rq.json()["status"] == "pending_approval" and rq.json()["mc_request_id"] != row["mc_request_id"]
    approve(client, sw["fin2"], rq.json()["mc_request_id"])
    assert balance(sw["agency_id"]) == 0
    with SessionLocal() as db:
        assert db.get(m.BookingServiceRequest, req_id).status == "refund_paid"


def test_staff_cannot_send_agency_credit_for_a_customer_paid_booking(client):
    from test_after_sales import booking, login as alogin, _user as auser
    cust = auser("customer")
    ch = alogin(client, cust)
    ops = alogin(client, auser("backoffice_expert"))
    rid = booking(cust)
    req = client.post(f"/reservations/{rid}/service-requests", headers={**ch, **key()}, json={"request_type": "cancel", "reason": "لغو سفر", "refund_destination": "wallet"}).json()["id"]
    client.post(f"/backoffice/booking-requests/{req}/actions", headers={**ops, **key()}, json={"action": "start_review"})
    assert client.get(f"/ops/service-requests/{req}", headers=ops).json()["agency_credit"] is None
    r = client.post(f"/backoffice/booking-requests/{req}/actions", headers={**ops, **key()}, json={"action": "approve", "penalty_mode": "policy", "refund_destination": "agency_credit"})
    assert r.status_code == 422
