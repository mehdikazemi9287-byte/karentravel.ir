"""Notification foundation: taxonomy, template versioning, channel fan-out,
PENDING_EXTERNAL_PROVIDER (no fabricated SMS/Push), idempotency, tenant isolation."""
import uuid

import pytest

from app.main import SessionLocal
from app import operations as om


def login(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _emit(tenant_id, recipient, event_type="payment_success", **kw):
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, tenant_id)
        ev = om.emit_notification_event(
            db, tenant_id=tenant_id, event_type=event_type, recipient_user_id=recipient,
            payload=kw.get("payload", {"booking_reference": "KS-1", "amount": 100, "currency": "IRR"}),
            dedupe_key=kw.get("dedupe_key", f"t-{uuid.uuid4().hex}"), topic=kw.get("topic", "account_activity"))
        db.commit()
        return ev.id, ev.dedupe_key


def test_fanout_creates_record_and_attempts():
    eid, _ = _emit(1, 1)
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, 1)
        ev = db.get(om.NotificationEvent, eid)
        assert ev.status == "dispatched"
        recs = db.query(om.NotificationRecord).filter(om.NotificationRecord.tenant_id == 1).all()
        assert any(r.title == "پرداخت موفق" and "100" in r.message for r in recs)
        attempts = db.query(om.NotificationDeliveryAttempt).join(
            om.NotificationRecord, om.NotificationDeliveryAttempt.notification_id == om.NotificationRecord.id).filter(
            om.NotificationRecord.title == "پرداخت موفق").all()
        by_channel = {a.channel: a.status for a in attempts}
        assert by_channel.get("web") == "delivered"
        assert by_channel.get("app") == "delivered"
        # no configured push/SMS provider -> honest pending, never "delivered"
        assert by_channel.get("push") == "pending_external"
        assert by_channel.get("sms") == "pending_external"


def test_no_outbox_event_when_all_external_channels_pending():
    with SessionLocal() as db:
        before = db.query(om.OutboxEvent).filter(om.OutboxEvent.aggregate_type == "notification").count()
    _emit(1, 1, dedupe_key=f"noout-{uuid.uuid4().hex}")
    with SessionLocal() as db:
        after = db.query(om.OutboxEvent).filter(om.OutboxEvent.aggregate_type == "notification").count()
    assert after == before  # push/sms disabled => nothing for the worker, no dead-letter spam


def test_idempotent_dedupe():
    key = f"idem-{uuid.uuid4().hex}"
    a, _ = _emit(1, 1, dedupe_key=key)
    b, _ = _emit(1, 1, dedupe_key=key)
    assert a == b
    with SessionLocal() as db:
        assert db.query(om.NotificationEvent).filter(om.NotificationEvent.dedupe_key == key).count() == 1


def test_unknown_event_type_rejected():
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, 1)
        with pytest.raises(ValueError):
            om.emit_notification_event(db, tenant_id=1, event_type="totally_made_up",
                                       recipient_user_id=1, payload={}, dedupe_key="x")


def test_template_render_missing_key_is_empty():
    assert om.render_notification_template("a {x} b {y}", {"x": "1"}) == "a 1 b "
    assert om.render_notification_template("no placeholders", {}) == "no placeholders"


def test_recipient_feed_isolation(client):
    _emit(1, 1, dedupe_key=f"feed-{uuid.uuid4().hex}")
    me = login(client, "employee@aftab.test")            # user 1, tenant 1
    other = login(client, "employee@faraz.test")         # tenant 2
    mine = client.get("/me/notification-events", headers=me)
    assert mine.status_code == 200 and len(mine.json()) >= 1
    assert all(e["event_type"] in om.NOTIFICATION_EVENT_TYPES for e in mine.json())
    assert client.get("/me/notification-events", headers=other).json() == []


def test_admin_template_versioning(client):
    admin = login(client, "org-admin@aftab.test")        # organization_admin has member:manage
    base = client.get("/admin/notification-templates", headers=admin)
    assert base.status_code == 200 and len(base.json()) > 0
    up = client.put("/admin/notification-templates", headers=admin, json={
        "event_type": "payment_success", "channel": "web", "locale": "fa",
        "title_template": "پرداخت شد ✅", "body_template": "مبلغ {amount} دریافت شد."})
    assert up.status_code == 200
    v = up.json()["version"]
    up2 = client.put("/admin/notification-templates", headers=admin, json={
        "event_type": "payment_success", "channel": "web", "locale": "fa",
        "title_template": "v-next", "body_template": "x {amount}"})
    assert up2.json()["version"] == v + 1
    rows = [r for r in client.get("/admin/notification-templates", headers=admin).json()
            if r["event_type"] == "payment_success" and r["channel"] == "web" and r["locale"] == "fa"]
    active = [r for r in rows if r["active"]]
    assert len(active) == 1 and active[0]["title_template"] == "v-next"


def test_admin_template_forbidden_for_plain_user(client):
    cust = login(client, "employee@aftab.test")
    assert client.get("/admin/notification-templates", headers=cust).status_code == 403
    assert client.put("/admin/notification-templates", headers=cust, json={
        "event_type": "payment_success", "channel": "web",
        "title_template": "x", "body_template": "y"}).status_code == 403


def test_new_active_template_used_by_emit(client):
    admin = login(client, "org-admin@aftab.test")
    client.put("/admin/notification-templates", headers=admin, json={
        "event_type": "refund_completed", "channel": "web", "locale": "fa",
        "title_template": "استرداد شد", "body_template": "CUSTOM {amount}"})
    _emit(1, 1, event_type="refund_completed", dedupe_key=f"rf-{uuid.uuid4().hex}",
          payload={"amount": 555, "currency": "IRR", "booking_reference": "KS-9"})
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, 1)
        rec = db.query(om.NotificationRecord).filter(
            om.NotificationRecord.title == "استرداد شد").order_by(om.NotificationRecord.created_at.desc()).first()
        assert rec and rec.message == "CUSTOM 555"
