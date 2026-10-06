"""Agency workspace (attribution only through the sales channel, membership-scoped) and notification requeue."""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app import operations as m
from app.main import SessionLocal
from tests.test_catalog_hotel_content import _token
from tests.test_platform_ops import _event, _trip, _uid


def _fixture():
    uid, tid = _uid("employee@aftab.test"); ouid, otid = _uid("employee@faraz.test")
    with SessionLocal() as db:
        entity = m.LicensedEntity(tenant_id=tid, legal_name="آزمون " + uuid.uuid4().hex[:6]); db.add(entity); db.flush()
        ch_a, ch_b = (m.SalesChannel(tenant_id=tid, name="agency-" + uuid.uuid4().hex[:8], channel_type="AGENCY", licensed_entity_id=entity.id) for _ in range(2)); db.add_all([ch_a, ch_b]); db.flush()
        ag_a, ag_b = m.Agency(tenant_id=tid, display_name="آژانس الف", commission_bps=500), m.Agency(tenant_id=tid, display_name="آژانس ب", commission_bps=300); db.add_all([ag_a, ag_b]); db.flush()
        other = m.Agency(tenant_id=otid, display_name="آژانس tenant دیگر"); db.add(other)
        now = datetime.now(timezone.utc)
        rows = [m.Reservation(tenant_id=tid, user_id=uid, service_type="hotel", status="confirmed", sales_channel_id=ch_a.id, confirmed_at=now, booking_reference="AG-" + uuid.uuid4().hex[:8], price_snapshot_json=json.dumps({"total_amount": 2000000, "currency": "IRR"})),
                m.Reservation(tenant_id=tid, user_id=uid, service_type="tour", status="reserved", sales_channel_id=ch_a.id, price_snapshot_json=json.dumps({"total_amount": 900000, "currency": "IRR"})),
                m.Reservation(tenant_id=tid, user_id=uid, service_type="hotel", status="confirmed", sales_channel_id=ch_a.id, confirmed_at=now, price_snapshot_json="{}"),
                m.Reservation(tenant_id=tid, user_id=uid, service_type="hotel", status="confirmed", sales_channel_id=ch_b.id, confirmed_at=now, price_snapshot_json=json.dumps({"total_amount": 7777777}))]
        db.add_all(rows); db.flush()
        db.add(m.SettlementRecord(tenant_id=tid, reservation_id=rows[0].id, amount=100000, status="paid")); db.commit()
        return ag_a.id, ag_b.id, other.id, ch_a.id, ch_b.id


def test_agency_workspace_attribution_membership_and_isolation(client):
    ag_a, ag_b, other, ch_a, ch_b = _fixture()
    agent, admin = _token(client, "agency@aftab.test"), _token(client, "tenant-admin@aftab.test")
    agent_id, _ = _uid("agency@aftab.test")
    # no membership -> sees nothing, cannot open any agency
    assert [a for a in client.get("/agency/workspace", headers=agent).json()["agencies"] if a["id"] in (ag_a, ag_b)] == []
    assert client.get(f"/agency/{ag_a}/bookings", headers=agent).status_code == 404
    # only tenant administration can link a channel or add a member
    assert client.put(f"/agency/{ag_a}/sales-channel", json={"sales_channel_id": ch_a}, headers=agent).status_code == 403
    assert client.post(f"/agency/{ag_a}/members", json={"user_id": agent_id}, headers=agent).status_code == 403
    assert client.post(f"/agency/{ag_a}/members", json={"user_id": _uid("employee@aftab.test")[0]}, headers=admin).status_code == 422   # not an agency user
    assert client.post(f"/agency/{other}/members", json={"user_id": agent_id}, headers=admin).status_code == 404                        # other tenant's agency
    assert client.post(f"/agency/{ag_a}/members", json={"user_id": agent_id}, headers=admin).status_code == 201
    assert client.get(f"/agency/{ag_a}/bookings", headers=agent).json() == {"sales_channel_linked": False, "items": []}                 # not linked yet: nothing is attributed
    assert client.put(f"/agency/{ag_a}/sales-channel", json={"sales_channel_id": "00000000-0000-4000-8000-000000000000"}, headers=admin).status_code == 422
    assert client.put(f"/agency/{ag_a}/sales-channel", json={"sales_channel_id": ch_a}, headers=admin).status_code == 200
    assert client.put(f"/agency/{ag_b}/sales-channel", json={"sales_channel_id": ch_a}, headers=admin).status_code == 409             # one channel, one agency
    assert client.put(f"/agency/{ag_b}/sales-channel", json={"sales_channel_id": ch_b}, headers=admin).status_code == 200
    bookings = client.get(f"/agency/{ag_a}/bookings", headers=agent).json()["items"]
    assert len(bookings) == 3 and all(b["total_amount"] != 7777777 for b in bookings) and {b["total_amount"] for b in bookings} == {2000000, 900000, None}
    com = client.get(f"/agency/{ag_a}/commissions", headers=agent).json()
    assert com["settled"] is False and com["totals"] == [{"currency": "IRR", "commission_amount": 100000}] and len(com["items"]) == 1   # 5% of the one confirmed, priced booking
    assert client.get(f"/agency/{ag_a}/customers", headers=agent).json()["items"][0]["bookings"] == 3
    assert [s["amount"] for s in client.get(f"/agency/{ag_a}/settlements", headers=agent).json()["items"]] == [100000]
    report = client.get(f"/agency/{ag_a}/report", headers=agent).json()
    assert report["bookings"] == 3 and report["by_status"] == {"confirmed": 2, "reserved": 1} and report["confirmed_sales"] == [{"currency": "IRR", "amount": 2000000}]
    # object level inside the tenant, role level, tenant level
    for path in ("bookings", "commissions", "customers", "settlements", "report"):
        assert client.get(f"/agency/{ag_b}/{path}", headers=agent).status_code == 404, path
        assert client.get(f"/agency/{ag_a}/{path}", headers=_token(client, "employee@aftab.test")).status_code == 403
        assert client.get(f"/agency/{ag_a}/{path}").status_code in (401, 403)
        assert client.get(f"/agency/{other}/{path}", headers=admin).status_code in (403, 404)
    visible = [a["id"] for a in client.get("/agency/workspace", headers=agent).json()["agencies"]]
    assert ag_a in visible and ag_b not in visible and other not in visible


def test_notification_requeue_only_for_dead_letter_and_scoped(client):
    trip, ops = _trip("employee@aftab.test"), _token(client, "backoffice@aftab.test")
    event = client.post(f"/operations/trips/{trip}/events", json=_event(), headers=ops).json()
    sms = next(d for d in client.get("/operations/notification-deliveries", params={"trip_event_id": event["id"]}, headers=ops).json()["items"] if d["channel"] == "sms")
    assert client.post(f"/operations/notification-deliveries/{sms['id']}/requeue", headers=ops).status_code == 409        # not dead-lettered
    with SessionLocal() as db:
        a = db.get(m.NotificationDeliveryAttempt, sms["id"]); a.status, a.error_code = "dead_letter", "provider_not_configured"
        db.commit()
    assert client.post(f"/operations/notification-deliveries/{sms['id']}/requeue", headers=_token(client, "employee@aftab.test")).status_code == 403
    assert client.post(f"/operations/notification-deliveries/{sms['id']}/requeue").status_code in (401, 403)
    done = client.post(f"/operations/notification-deliveries/{sms['id']}/requeue", headers=ops)
    assert done.status_code == 200 and done.json()["delivery_status"] == "retry"
    with SessionLocal() as db:
        outbox = db.scalar(select(m.OutboxEvent).where(m.OutboxEvent.event_type == "trip.event.recorded", m.OutboxEvent.payload_json.contains(event["id"])))
        assert outbox.status == "retry" and outbox.attempts == 0
    assert client.post("/operations/notification-deliveries/nope/requeue", headers=ops).status_code == 404
