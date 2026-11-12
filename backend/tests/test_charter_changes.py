"""Panels Phase 2b — charter schedule change / cancel: impact preview (allocations, agency and public bookings, passengers), the
2-hour full-refund rule, agency notices (accept / refund to agency credit through maker-checker), cancellation that releases
allocations, queues full refunds to agency credit and opens cancel requests for public bookings; outbox only, no SMS."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import operations as m
from app.agency_b2b import AgencyAccount
from app.charter_blocks import CharterBlock
from app.charter_changes import CharterChangeNotice
from app.charter_quotas import SeatQuota
from app.main import SessionLocal, User

from test_agency_b2b import _user, activate, fund, key, login, make_agency, price_check
from test_charter_blocks import block_body


@pytest.fixture()
def cw(client):
    owner, ops, fin1, fin2, buyer_owner, ops2 = (_user("agency_partner"), _user("backoffice_expert"), _user("finance_operator"), _user("finance_operator"),
                                                 _user("agency_partner"), _user("backoffice_expert"))
    a, buyer = make_agency(owner), make_agency(buyer_owner)
    w = {"agency_id": a, "owner": login(client, owner), "ops": login(client, ops), "fin1": login(client, fin1), "fin2": login(client, fin2), "buyer": buyer,
         "bh": login(client, buyer_owner), "ops2": login(client, ops2)}
    activate(client, w["owner"], w["ops"], a)
    activate(client, w["bh"], w["ops"], buyer, licence_type="BAND_BE")
    fund(client, w["fin1"], w["fin2"], buyer, limit=500_000_000)
    blk = client.post(f"/agency/{a}/charter/blocks", json=block_body(), headers=w["owner"]).json()
    pub = client.post(f"/staff/charter/blocks/{blk['id']}/decision", json={"decision": "approve", "platform_fee_bps": 300}, headers=w["ops"])
    assert pub.status_code == 200, pub.text
    w["block"] = pub.json()
    al = client.post(f"/agency/{a}/charter/blocks/{blk['id']}/allocations", json={"agency_id": buyer, "seats": 4}, headers=w["owner"])
    assert al.status_code == 201, al.text
    offer = client.get(f"/agency/{buyer}/charter/allocations-received", headers=w["bh"]).json()["items"][0]["offer_id"]
    pc = price_check(client, w["bh"], offer, units=2)
    r = client.post(f"/agency/{buyer}/credit-bookings", headers=w["bh"], json={"price_check_id": pc["id"], "command_id": f"cb-{uuid.uuid4().hex}"})
    assert r.status_code == 201, r.text
    w["line"] = r.json()
    w["offer_id"] = offer
    # one public (B2C) booking on the same flight, paid by gateway
    cust = _user("customer")
    ch = login(client, cust)
    cpc = price_check(client, ch, offer, units=1)
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == cust))
        res = m.Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="flight", status="confirmed", booking_reference=f"KR-{uuid.uuid4().hex[:8].upper()}",
                            price_check_id=cpc["id"], price_snapshot_json=json.dumps({"total_amount": cpc["amount"], "currency": "IRR", "units": 1}))
        db.add(res)
        db.flush()
        db.add(m.PaymentIntent(tenant_id=u.tenant_id, reservation_id=res.id, user_id=u.id, command_id=f"cc-pay-{uuid.uuid4().hex}", amount=cpc["amount"],
                               captured_amount=cpc["amount"], status="captured"))
        db.commit()
        w["b2c_res"] = res.id
    w["cust"] = ch
    return w


def change_body(blk, hours=3, **over):
    dep = datetime.fromisoformat(blk["departure_at"]) + timedelta(hours=hours)
    body = {"kind": "change", "new_departure_at": dep.isoformat(), "new_arrival_at": (dep + timedelta(hours=3, minutes=30)).isoformat(), "reason": "تغییر برنامهٔ ایرلاین"}
    body.update(over)
    return body


def apply(client, cw, bid, body, k=None):
    """Maker (ops) asks, a second ops user approves; returns the recorded change."""
    r = client.post(f"/staff/charter/blocks/{bid}/schedule-change", json=body, headers={**cw["ops"], **(k or key())})
    assert r.status_code == 202, r.text
    assert client.post(f"/maker-checker/requests/{r.json()['request_id']}/approve", json={}, headers=cw["ops"]).status_code == 403  # the maker
    ok = client.post(f"/maker-checker/requests/{r.json()['request_id']}/approve", json={}, headers=cw["ops2"])
    assert ok.status_code == 200, ok.text
    return client.get(f"/staff/charter/blocks/{bid}/schedule-changes", headers=cw["ops"]).json()["items"][0]


def balance(agency_id):
    with SessionLocal() as db:
        return db.scalar(select(AgencyAccount.balance_irr).where(AgencyAccount.agency_id == agency_id))


def test_preview_shows_impact_and_writes_nothing(client, cw):
    bid = cw["block"]["id"]
    assert client.post(f"/staff/charter/blocks/{bid}/schedule-change/preview", json=change_body(cw["block"]), headers=cw["owner"]).status_code == 403
    r = client.post(f"/staff/charter/blocks/{bid}/schedule-change/preview", json=change_body(cw["block"], hours=1.5), headers=cw["ops"])
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["shift_minutes"] == 90 and p["full_refund_eligible"] is False and p["money_moves"] is False
    ag = next(x for x in p["agencies"] if x["agency_id"] == cw["buyer"])
    assert ag["allocation_initial"] == 4 and ag["allocation_held"] == 2 and ag["bookings"] == 1 and ag["passengers"] == 2
    assert p["public_bookings"] == 1 and p["public_passengers"] == 1 and p["passengers_total"] == 3
    c = client.post(f"/staff/charter/blocks/{bid}/schedule-change/preview", json={"kind": "cancel", "reason": "لغو پرواز توسط ایرلاین"}, headers=cw["ops"]).json()
    assert c["refund_to_agency_credit_irr"] == cw["line"]["breakdown"]["net_irr"]
    with SessionLocal() as db:
        assert db.get(CharterBlock, bid).status == "published"
        assert db.scalars(select(CharterChangeNotice).where(CharterChangeNotice.block_id == bid)).all() == []
    assert client.post(f"/staff/charter/blocks/{bid}/schedule-change/preview", json=change_body(cw["block"], hours=0), headers=cw["ops"]).status_code == 422


def test_change_over_two_hours_notice_and_refund_to_credit(client, cw):
    bid, buyer, bh = cw["block"]["id"], cw["buyer"], cw["bh"]
    body = change_body(cw["block"], hours=3)
    k = key()
    first = client.post(f"/staff/charter/blocks/{bid}/schedule-change", json=body, headers={**cw["ops"], **k})
    assert first.status_code == 202, first.text
    assert client.post(f"/staff/charter/blocks/{bid}/schedule-change", json=body, headers={**cw["ops"], **k}).json()["request_id"] == first.json()["request_id"]  # replay
    assert client.post(f"/staff/charter/blocks/{bid}/schedule-change", json={**body, "reason": "متن دیگر برای همان کلید"}, headers={**cw["ops"], **k}).status_code == 409
    assert client.post(f"/staff/charter/blocks/{bid}/schedule-change", json=body, headers={**cw["ops"], **key()}).status_code == 409  # one pending at a time
    with SessionLocal() as db:
        assert db.get(CharterBlock, bid).departure_at.replace(tzinfo=timezone.utc) == datetime.fromisoformat(cw["block"]["departure_at"])  # nothing before the checker
    ch = apply(client, cw, bid, body, k)
    assert ch["shift_minutes"] == 180 and ch["full_refund_eligible"] is True
    with SessionLocal() as db:
        b = db.get(CharterBlock, bid)
        offer = db.get(m.Offer, b.offer_id)
        attrs = json.loads(offer.attributes_json)
        assert datetime.fromisoformat(attrs["departure_time"]) == datetime.fromisoformat(body["new_departure_at"])
        assert attrs["charter_block_id"] == bid and offer.status == "active"
        events = {e.event_type for e in db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.aggregate_id == ch["id"]))}
        assert "charter.change" in events
        cust_notes = db.scalars(select(m.NotificationRecord).where(m.NotificationRecord.topic == "trip_change")).all()
        assert any("تغییر کرد" in n.message for n in cust_notes)
    notices = client.get(f"/agency/{buyer}/charter/notices", headers=bh).json()
    n = next(x for x in notices["items"] if x["reservation_id"] == cw["line"]["reservation_id"])
    assert n["status"] == "pending" and n["can_request_refund"] is True and n["passengers"] == 2
    # the charterer sees the change on its block; another agency cannot answer the buyer's notice
    assert client.get(f"/agency/{cw['agency_id']}/charter/blocks/{bid}/schedule-changes", headers=cw["owner"]).json()["items"][0]["id"] == ch["id"]
    assert client.post(f"/agency/{cw['agency_id']}/charter/notices/{n['id']}/accept", json={}, headers=cw["owner"]).status_code == 404
    before = balance(buyer)
    rr = client.post(f"/agency/{buyer}/charter/notices/{n['id']}/refund-request", json={"note": "مسافر زمان تازه را نمی‌خواهد"}, headers={**bh, **key()})
    assert rr.status_code == 202, rr.text
    assert rr.json()["status"] == "refund_pending" and balance(buyer) == before  # nothing moved yet
    mc_id = rr.json()["credit_refund"]["mc_request_id"]
    assert client.post(f"/maker-checker/requests/{mc_id}/approve", json={}, headers=bh).status_code == 403
    assert client.post(f"/maker-checker/requests/{mc_id}/approve", json={}, headers=cw["fin1"]).status_code == 200
    assert balance(buyer) == before + cw["line"]["breakdown"]["net_irr"]
    after = client.get(f"/agency/{buyer}/charter/notices", headers=bh).json()["items"]
    assert next(x for x in after if x["id"] == n["id"])["status"] == "refunded"
    with SessionLocal() as db:
        assert db.get(m.Reservation, cw["line"]["reservation_id"]).status == "refunded"


def test_change_within_two_hours_allows_accept_not_full_refund(client, cw):
    bid, buyer, bh = cw["block"]["id"], cw["buyer"], cw["bh"]
    apply(client, cw, bid, change_body(cw["block"], hours=1))
    n = client.get(f"/agency/{buyer}/charter/notices", headers=bh).json()["items"][0]
    assert n["can_request_refund"] is False
    r = client.post(f"/agency/{buyer}/charter/notices/{n['id']}/refund-request", json={}, headers={**bh, **key()})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "SHIFT_BELOW_POLICY"
    ok = client.post(f"/agency/{buyer}/charter/notices/{n['id']}/accept", json={"note": "پذیرفتیم"}, headers=bh)
    assert ok.status_code == 200 and ok.json()["status"] == "accepted"


def test_cancel_releases_seats_queues_refunds_and_opens_customer_requests(client, cw):
    bid, buyer = cw["block"]["id"], cw["buyer"]
    before = balance(buyer)
    apply(client, cw, bid, {"kind": "cancel", "reason": "لغو پرواز توسط ایرلاین"})
    with SessionLocal() as db:
        b = db.get(CharterBlock, bid)
        assert b.status == "cancelled"
        offer = db.get(m.Offer, b.offer_id)
        assert offer.status == "inactive" and offer.available_units == 0
        assert all(q.status == "released" for q in db.scalars(select(SeatQuota).where(SeatQuota.instance_id == b.instance_id)))
        sr = db.scalar(select(m.BookingServiceRequest).where(m.BookingServiceRequest.reservation_id == cw["b2c_res"]))
        assert sr is not None and sr.request_type == "cancel" and sr.status == "submitted"
        assert db.get(m.Reservation, cw["b2c_res"]).status == "cancel_requested"
    assert client.get(f"/agency/{cw['agency_id']}/charter/blocks/{bid}", headers=cw["owner"]).json()["seats"]["public_available"] == 0
    # the public booking is in the normal ops queue; the agency booking waits for a finance approval
    queue = client.get("/ops/queues/service_requests", headers=cw["ops"]).json()["items"]
    assert any(i["reservation"]["id"] == cw["b2c_res"] for i in queue)
    n = next(x for x in client.get(f"/agency/{buyer}/charter/notices", headers=cw["bh"]).json()["items"] if x["reservation_id"])
    assert n["kind"] == "cancel" and n["status"] == "refund_pending" and balance(buyer) == before
    assert client.post(f"/maker-checker/requests/{n['credit_refund']['mc_request_id']}/approve", json={}, headers=cw["ops2"]).status_code == 403  # maker, no refund:manage
    fin = client.get(f"/finance/agency-credit-refunds/{n['credit_refund']['id']}", headers=cw["fin2"]).json()
    assert fin["can_approve"] is True and fin["refundable_irr"] == cw["line"]["breakdown"]["net_irr"] and fin["free_credit_after_irr"] - fin["free_credit_before_irr"] == fin["refundable_irr"]
    assert fin["settlement_effect"]["commission_reversal_irr"] == cw["line"]["breakdown"]["commission_irr"]
    assert client.post(f"/maker-checker/requests/{n['credit_refund']['mc_request_id']}/approve", json={}, headers=cw["fin2"]).status_code == 200
    assert balance(buyer) == before + cw["line"]["breakdown"]["net_irr"]
    # a cancelled block cannot be changed again
    assert client.post(f"/staff/charter/blocks/{bid}/schedule-change", json={"kind": "cancel", "reason": "دوباره"}, headers={**cw["ops"], **key()}).status_code == 409
    hist = client.get(f"/staff/charter/blocks/{bid}/schedule-changes", headers=cw["ops"]).json()
    assert hist["items"][0]["kind"] == "cancel" and hist["block_status"] == "cancelled"
