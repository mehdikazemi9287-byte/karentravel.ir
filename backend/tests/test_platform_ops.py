"""Trip Operations Center, unified change log, support workspace, finance/supplier read models: behaviour, RBAC, tenant and object isolation."""
import json
import uuid

from sqlalchemy import select

from app import operations as m
from app.main import AuditEvent, SessionLocal, User
from tests.test_catalog_hotel_content import _token


def _uid(email):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email)); return u.id, u.tenant_id


def _trip(email, title="سفر آزمون"):
    uid, tid = _uid(email)
    with SessionLocal() as db:
        trip = m.Trip(tenant_id=tid, user_id=uid, title=title, destination="شیراز"); db.add(trip); db.commit(); return trip.id


def _event(**over):
    return {"command_id": "cmd-" + uuid.uuid4().hex, "category": "schedule_change", "severity": "critical", "source": "supplier", "old_value": {"حرکت": "1405-08-01 08:00"}, "new_value": {"حرکت": "1405-08-01 14:30"},
            "reason": "اعلام ایرلاین", "requires_action": True, **over}


def test_trip_event_lifecycle_single_source_of_truth(client):
    trip = _trip("employee@aftab.test")
    ops, customer = _token(client, "backoffice@aftab.test"), _token(client, "employee@aftab.test")
    body = _event()
    created = client.post(f"/operations/trips/{trip}/events", json=body, headers=ops)
    assert created.status_code == 201, created.text
    e = created.json()
    assert (e["category"], e["severity"], e["source"], e["old_value"], e["new_value"], e["acknowledged"]) == ("schedule_change", "critical", "supplier", body["old_value"], body["new_value"], False)
    assert e["actor"]["role"] == "backoffice_expert" and e["created_at"] and e["trip_id"] == trip
    assert client.post(f"/operations/trips/{trip}/events", json=body, headers=ops).json()["id"] == e["id"]                      # idempotent replay
    assert client.post(f"/operations/trips/{trip}/events", json={**body, "new_value": {"حرکت": "دیگر"}}, headers=ops).status_code == 409  # same key, different change
    # the customer, support and operations read the same row
    mine = client.get(f"/trips/{trip}/changes", headers=customer).json()
    assert mine["recorded_only"] is True and mine["unacknowledged"] == 1 and mine["changes"][0]["id"] == e["id"] and "actor" not in mine["changes"][0] and "visibility" not in mine["changes"][0]
    assert mine["changes"][0]["old_value"] == body["old_value"] and mine["changes"][0]["new_value"] == body["new_value"]
    assert client.get(f"/operations/trips/{trip}/timeline", headers=ops).json()["events"][0]["id"] == e["id"]
    assert any(x["id"] == e["id"] for x in client.get(f"/trips/{trip}/timeline", headers=customer).json()["events"])           # legacy timeline: same table
    center = client.get("/operations/trip-events", params={"unacknowledged": True, "severity": "critical", "trip_id": trip}, headers=ops).json()
    assert center["total"] == 1 and center["summary"]["critical_unacknowledged"] >= 1
    # notification fan-out: one notification, one attempt per channel, deep link, nothing sent
    deliveries = client.get("/operations/notification-deliveries", params={"trip_event_id": e["id"]}, headers=ops).json()["items"]
    assert {d["channel"] for d in deliveries} == {"in_app", "push", "sms"} and all(d["deep_link"] == f"/trips/{trip}" and d["template"] == "important_trip_changes" and d["read"] is False and d["attempt"] == 1 for d in deliveries)
    assert {d["channel"]: d["delivery_status"] for d in deliveries}["sms"] == "not_sent"
    # AI grounding = recorded events only
    ai = client.get("/ai/trip-changes-context", params={"trip_id": trip}, headers=customer).json()
    assert ai["generated_transactional_data"] is False and [c["id"] for c in ai["recorded_changes"]] == [e["id"]] and ai["answer_policy"] == "explain_only_recorded_events_cite_event_id"
    # acknowledgement by the owner, audited, reflected everywhere and marks the notification read
    ack = client.post(f"/trips/{trip}/events/{e['id']}/acknowledge", headers=customer).json()
    assert ack["acknowledged"] is True and client.post(f"/trips/{trip}/events/{e['id']}/acknowledge", headers=customer).json()["acknowledged_at"] == ack["acknowledged_at"]
    assert client.get(f"/trips/{trip}/changes", headers=customer).json()["unacknowledged"] == 0
    assert client.get("/operations/trip-events", params={"unacknowledged": True, "trip_id": trip}, headers=ops).json()["total"] == 0
    assert all(d["read"] for d in client.get("/operations/notification-deliveries", params={"trip_event_id": e["id"]}, headers=ops).json()["items"])
    with SessionLocal() as db:
        actions = [a.action for a in db.scalars(select(AuditEvent).where(AuditEvent.entity == "trip_event", AuditEvent.detail.contains(e["id"])))]
    assert sorted(actions) == ["trip_event.acknowledged", "trip_event.recorded"]
    empty = _trip("employee@aftab.test", "سفر بدون تغییر")
    assert client.get(f"/trips/{empty}/changes", headers=customer).json()["changes"] == []
    assert client.get("/ai/trip-changes-context", params={"trip_id": empty}, headers=customer).json()["answer_policy"] == "state_no_recorded_change"


def test_trip_event_validation_and_every_category(client):
    trip, ops = _trip("employee@aftab.test"), _token(client, "backoffice@aftab.test")
    post = lambda **o: client.post(f"/operations/trips/{trip}/events", json=_event(**o), headers=ops)  # noqa: E731
    for cat in ("schedule_change", "hotel_change", "room_change", "transfer_change", "tour_change", "document_change"):
        assert post(category=cat).status_code == 201
        assert post(category=cat, new_value=None).status_code == 422 and post(category=cat, new_value={"حرکت": "1405-08-01 08:00"}).status_code == 422
    assert post(category="cancellation", new_value=None).status_code == 201 and post(category="cancellation", old_value=None).status_code == 422
    for cat in ("payment_issue", "supplier_issue", "support_intervention"):
        assert post(category=cat, old_value=None, new_value={"وضعیت": "در حال پیگیری"}).status_code == 201
    for bad in ({"category": "weather"}, {"severity": "urgent"}, {"source": "ai"}, {"reason": ""}, {"old_value": {}}, {"new_value": {"k": "x" * 301}}, {"price": 1}, {"reservation_id": "00000000-0000-4000-8000-000000000000"}, {"command_id": "x"}):
        assert post(**bad).status_code == 422, bad
    internal = post(category="supplier_issue", old_value=None, new_value={"تأمین‌کننده": "بدون پاسخ"}, visibility="internal").json()
    customer = _token(client, "employee@aftab.test")
    assert internal["id"] not in [c["id"] for c in client.get(f"/trips/{trip}/changes", headers=customer).json()["changes"]]
    assert client.post(f"/trips/{trip}/events/{internal['id']}/acknowledge", headers=customer).status_code == 404
    assert client.get("/operations/notification-deliveries", params={"trip_event_id": internal["id"]}, headers=ops).json()["items"] == []  # internal events notify nobody


def test_trip_ops_rbac_tenant_and_object_isolation(client):
    trip, other_tenant_trip = _trip("employee@aftab.test"), _trip("employee@faraz.test")
    ops = _token(client, "backoffice@aftab.test")
    event = client.post(f"/operations/trips/{trip}/events", json=_event(), headers=ops).json()
    for path in (f"/operations/trips/{trip}/events",):
        assert client.post(path, json=_event()).status_code in (401, 403)
        for email in ("employee@aftab.test", "supplier@aftab.test", "agency@aftab.test", "finance@aftab.test", "org-admin@aftab.test"):
            assert client.post(path, json=_event(), headers=_token(client, email)).status_code == 403, email
    for email in ("employee@aftab.test", "supplier@aftab.test", "agency@aftab.test", "finance@aftab.test", "welfare@aftab.test"):
        h = _token(client, email)
        assert client.get("/operations/trip-events", headers=h).status_code == 403 and client.get(f"/operations/trips/{trip}/timeline", headers=h).status_code == 403
        assert client.get("/operations/notification-deliveries", headers=h).status_code == 403
    # cross-tenant: staff of tenant A can neither read nor write tenant B's trip, and never sees its events
    assert client.post(f"/operations/trips/{other_tenant_trip}/events", json=_event(), headers=ops).status_code == 404
    assert client.get(f"/operations/trips/{other_tenant_trip}/timeline", headers=ops).status_code == 404
    assert client.get("/operations/trip-events", params={"trip_id": other_tenant_trip}, headers=ops).json()["total"] == 0
    # object level: another customer of the same tenant, and a customer of another tenant
    for email in ("welfare@aftab.test", "employee@faraz.test"):
        h = _token(client, email)
        assert client.get(f"/trips/{trip}/changes", headers=h).status_code == 404
        assert client.post(f"/trips/{trip}/events/{event['id']}/acknowledge", headers=h).status_code == 404
        assert client.get("/ai/trip-changes-context", params={"trip_id": trip}, headers=h).status_code == 404
    assert client.get(f"/trips/{trip}/changes").status_code in (401, 403)
    # a reservation of another customer cannot be attached to this trip
    uid, tid = _uid("welfare@aftab.test")
    with SessionLocal() as db:
        r = m.Reservation(tenant_id=tid, user_id=uid, service_type="hotel"); db.add(r); db.commit(); rid = r.id
    assert client.post(f"/operations/trips/{trip}/events", json=_event(reservation_id=rid), headers=ops).status_code == 422
    with SessionLocal() as db:
        assert db.get(m.TripEventRecord, event["id"]).acknowledged_at is None


def test_support_workspace_internal_notes_and_escalation(client):
    trip = _trip("employee@aftab.test")
    customer, agent = _token(client, "employee@aftab.test"), _token(client, "backoffice@aftab.test")
    uid, tid = _uid("employee@aftab.test")
    with SessionLocal() as db:
        case = m.SupportCase(tenant_id=tid, user_id=uid, trip_id=trip, subject="تأخیر پرواز", command_id="case-" + uuid.uuid4().hex); db.add(case); db.flush()
        db.add(m.SupportThreadMessage(tenant_id=tid, case_id=case.id, sender_type="customer", sender_user_id=uid, body="پروازم تغییر کرده؟")); db.commit(); cid = case.id
    assert client.post(f"/support/cases/{cid}/internal-notes", json={"body": "با ایرلاین تماس گرفته شد"}, headers=customer).status_code == 403
    note = client.post(f"/support/cases/{cid}/internal-notes", json={"body": "با ایرلاین تماس گرفته شد"}, headers=agent)
    assert note.status_code == 201 and note.json()["visible_to_customer"] is False
    seen_by_customer = client.get(f"/support/cases/{cid}", headers=customer).json()
    assert [x["sender_type"] for x in seen_by_customer["messages"]] == ["customer"] and "با ایرلاین" not in json.dumps(client.get("/support/cases", headers=customer).json(), ensure_ascii=False)
    ws = client.get(f"/support/cases/{cid}/workspace", headers=agent).json()
    assert [(x["author_kind"], x["is_human"], x["visible_to_customer"]) for x in ws["messages"]] == [("customer", True, True), ("internal_note", True, False)]
    assert ws["customer"]["name"] and ws["customer"]["open_cases"] >= 1 and ws["booking"] is None and ws["sla"]["breached"] is False and ws["history"][-1]["action"] == "internal_note_added"
    assert client.get(f"/support/cases/{cid}/workspace", headers=customer).status_code == 403
    esc = client.post(f"/support/cases/{cid}/escalate", json={"reason": "مشتری در فرودگاه است", "severity": "CRITICAL"}, headers=agent).json()
    assert (esc["priority"], esc["severity"]) == ("urgent", "CRITICAL") and esc["trip_event_id"]
    ws = client.get(f"/support/cases/{cid}/workspace", headers=agent).json()
    assert ws["history"][-1]["action"] == "escalated" and ws["trip_events"][0]["category"] == "support_intervention" and ws["trip_events"][0]["visibility"] == "internal"
    assert client.get(f"/trips/{trip}/changes", headers=customer).json()["changes"] == []   # internal intervention is not shown as a trip change
    other = _token(client, "employee@faraz.test")
    assert client.get(f"/support/cases/{cid}", headers=other).status_code == 404
    assert client.post(f"/support/cases/{cid}/escalate", json={"reason": "تست", "severity": "LOW"}, headers=agent).status_code == 422


def test_finance_and_supplier_read_models_are_scoped_and_factual(client):
    fin = _token(client, "finance@aftab.test")
    uid, tid = _uid("employee@aftab.test"); ouid, otid = _uid("employee@faraz.test")
    with SessionLocal() as db:
        ra, rb = m.Reservation(tenant_id=tid, user_id=uid, service_type="hotel"), m.Reservation(tenant_id=otid, user_id=ouid, service_type="hotel"); db.add_all([ra, rb]); db.flush()
        db.add_all([m.PaymentIntent(tenant_id=tid, reservation_id=ra.id, user_id=uid, command_id="p-" + uuid.uuid4().hex, amount=1500000, status="captured", provider_reference="=HYPERLINK(1)"),
                    m.PaymentIntent(tenant_id=otid, reservation_id=rb.id, user_id=ouid, command_id="p-" + uuid.uuid4().hex, amount=999, status="captured")]); db.commit()
    rows = client.get("/finance/records/payments", params={"status": "captured"}, headers=fin).json()
    assert rows["total"] >= 1 and all(r["amount"] != 999 for r in rows["items"]) and "provider_authority" not in rows["columns"]
    overview = client.get("/finance/overview", headers=fin).json()
    assert overview["derived_balances"] is None and any(p["status"] == "captured" and p["amount"] >= 1500000 for p in overview["payments"])
    csv_response = client.get("/finance/export/payments", headers=fin)
    assert csv_response.status_code == 200 and csv_response.headers["content-type"].startswith("text/csv") and "'=HYPERLINK(1)" in csv_response.text and ",999," not in csv_response.text
    for dataset in ("refunds", "settlements", "invoices", "ledger", "credit-accounts"):
        assert client.get(f"/finance/records/{dataset}", headers=fin).status_code == 200
    assert client.get("/finance/records/users", headers=fin).status_code == 404
    for email in ("employee@aftab.test", "supplier@aftab.test", "agency@aftab.test", "backoffice@aftab.test"):
        h = _token(client, email)
        assert client.get("/finance/overview", headers=h).status_code == 403 and client.get("/finance/export/payments", headers=h).status_code == 403
    assert client.get("/finance/overview").status_code in (401, 403)
    sup = _token(client, "supplier@aftab.test")
    assert client.get("/supplier/settlements", headers=sup).status_code == 200 and set(client.get("/supplier/contracts", headers=sup).json()) == {"suppliers", "contracts"}
    assert client.get("/supplier/settlements", headers=_token(client, "employee@aftab.test")).status_code == 403
