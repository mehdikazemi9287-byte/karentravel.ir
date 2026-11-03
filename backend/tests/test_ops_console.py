"""Ops dashboard and contract file: real-row KPIs, contract file sections, Moadian readiness, RBAC and tenant isolation."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import operations as m
from app.main import SessionLocal, User
from app.ops_console import MoadianRecord, mask_ref, snapshot_total, tehran_day_bounds, tehran_today


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_helpers():
    a, b = tehran_day_bounds(date(2026, 11, 3))
    assert a == datetime(2026, 11, 2, 20, 30, tzinfo=timezone.utc) and b - a == timedelta(days=1)
    assert tehran_today(datetime(2026, 11, 2, 21, 0, tzinfo=timezone.utc)) == date(2026, 11, 3)
    assert snapshot_total('{"total_amount": 12}') == 12 and snapshot_total("{}") is None and snapshot_total("x") is None
    assert mask_ref("A12345678") == "•••••5678" and mask_ref(None) is None


def _contract(status="confirmed", invoice=True, paid=True):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        ref = "OPS-" + uuid.uuid4().hex[:8].upper()
        now = datetime.now(timezone.utc)
        res = m.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status=status, booking_reference=ref,
                            price_snapshot_json=json.dumps({"total_amount": 5_000_000, "currency": "IRR", "units": 1}),
                            policy_at_booking_json=json.dumps({"free_cancellation_until": "2026-12-01"}), current_policy_json="{}",
                            confirmed_at=now if status == "confirmed" else None)
        db.add(res); db.flush()
        db.add(m.BookingStatusHistory(tenant_id=user.tenant_id, reservation_id=res.id, from_status="awaiting_payment", to_status=status,
                                      actor_id=user.id, command_id="h-" + ref))
        tr = m.Traveller(tenant_id=user.tenant_id, user_id=user.id, full_name="مسافر آزمایشی", profile_reference="P12345678")
        db.add(tr); db.flush()
        db.add(m.ReservationTraveller(reservation_id=res.id, traveller_id=tr.id))
        if invoice:
            db.add(m.Invoice(tenant_id=user.tenant_id, user_id=user.id, reservation_id=res.id, invoice_number="INV-" + ref, command_id="inv-" + ref,
                             subtotal_amount=4_587_156, tax_amount=412_844, total_amount=5_000_000, currency="IRR"))
        if paid:
            db.add(m.PaymentIntent(tenant_id=user.tenant_id, reservation_id=res.id, user_id=user.id, command_id="pay-" + ref, amount=5_000_000,
                                   status="captured", captured_amount=5_000_000, provider_capture_reference="RRN998877"))
        db.commit()
        return res.id, ref


def test_dashboard_counts_real_rows(client):
    bo = _h(client, "backoffice@aftab.test")
    assert client.get("/ops/dashboard", headers=_h(client, "employee@aftab.test")).status_code == 403
    before = client.get("/ops/dashboard", headers=bo).json()
    rid, ref = _contract()
    _contract(status="awaiting_payment", invoice=False, paid=True)  # paid but not confirmed -> data alert
    d = client.get("/ops/dashboard", headers=bo).json()
    k = {i["key"]: i["value"] for i in d["kpis"]}
    kb = {i["key"]: i["value"] for i in before["kpis"]}
    assert k["confirmed"] == kb["confirmed"] + 1 and k["confirmed_value"] == kb["confirmed_value"] + 5_000_000
    assert k["captured"] >= kb["captured"] + 10_000_000
    assert len(d["chart"]) == 30 and d["chart"][-1]["day"] == d["today"] and d["chart"][-1]["count"] >= 1
    assert any(r["id"] == rid and r["amount"] == 5_000_000 and r["status_fa"] == "تأیید شد" for r in d["latest"])
    alerts = {a["key"]: a["count"] for a in d["alerts"]}
    assert alerts.get("paid_unconfirmed", 0) >= 1 and alerts.get("moadian_pending", 0) >= 1
    tasks = {t["key"]: t["count"] for t in d["tasks"]}
    assert tasks["awaiting_payment"] >= 1
    found = client.get("/ops/contracts", params={"q": ref}, headers=bo).json()["items"]
    assert [i["id"] for i in found] == [rid]


def test_contract_file_and_moadian(client):
    bo = _h(client, "backoffice@aftab.test")
    admin = _h(client, "tenant-admin@aftab.test")
    rid, ref = _contract()
    f = client.get(f"/ops/contracts/{rid}", headers=bo)
    assert f.status_code == 200, f.text
    f = f.json()
    assert f["booking_reference"] == ref and f["services"]["sell"] == 5_000_000 and f["services"]["tax"] == 412_844
    assert f["finance"]["paid_gateway"] == 5_000_000 and f["finance"]["balance"] == 0 and f["finance"]["invoice"]["number"] == "INV-" + ref
    assert f["travellers"][0]["document"] == "•••••5678" and any(p["kind"] == "status" for p in f["path"])
    assert f["payments"][0]["reference"] == "•••••8877"
    assert f["cancellation"]["policy_at_booking"]["free_cancellation_until"] == "2026-12-01"
    assert f["moadian"]["status"] in ("not_ready", "ready")

    # settings: only tenant admin; codes validated
    assert client.put("/ops/moadian/settings", json={"economic_code": "14001234567", "memory_id": "A1B2C3"}, headers=bo).status_code == 403
    assert client.put("/ops/moadian/settings", json={"economic_code": "14001234567", "memory_id": "A1B2C3", "service_codes": {"hotel": "123"}}, headers=admin).status_code == 422
    client.put("/ops/moadian/settings", json={"economic_code": None, "memory_id": None, "service_codes": {}}, headers=admin)
    r = client.post(f"/ops/contracts/{rid}/moadian", headers=bo)
    assert r.status_code == 409 and "کد اقتصادی" in r.json()["detail"]
    s = client.put("/ops/moadian/settings", json={"economic_code": "14001234567", "memory_id": "A1B2C3", "service_codes": {"hotel": "2720000114542"}}, headers=admin)
    assert s.status_code == 200 and s.json()["provider_connected"] is False
    assert client.get(f"/ops/contracts/{rid}", headers=bo).json()["moadian"]["status"] == "ready"

    assert client.post(f"/ops/contracts/{rid}/moadian", headers=_h(client, "employee@aftab.test")).status_code == 403
    p = client.post(f"/ops/contracts/{rid}/moadian", headers=bo)
    assert p.status_code == 201, p.text
    body = p.json()
    assert body["status"] == "waiting_for_provider" and body["payload"]["header"]["tbill"] == 5_000_000
    assert body["payload"]["header"]["tins"] == "14001234567" and body["payload"]["body"][0]["sstid"] == "2720000114542"
    assert "taxid" not in body["payload"]["header"]  # never invented
    assert client.post(f"/ops/contracts/{rid}/moadian", headers=bo).status_code == 201  # re-prepare keeps one record
    with SessionLocal() as db:
        recs = db.scalars(select(MoadianRecord).where(MoadianRecord.reservation_id == rid)).all()
        assert len(recs) == 1 and recs[0].attempts == 2
    assert client.get(f"/ops/contracts/{rid}", headers=bo).json()["moadian"]["status"] == "waiting_for_provider"

    # contract without invoice cannot be prepared
    rid2, _ = _contract(invoice=False)
    assert client.post(f"/ops/contracts/{rid2}/moadian", headers=bo).status_code == 409

    # tenant isolation
    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"ops-adm-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="مدیر فراز", role="tenant_admin"))
        db.commit()
    other = _h(client, oemail)
    assert client.get(f"/ops/contracts/{rid}", headers=other).status_code == 404
    assert client.post(f"/ops/contracts/{rid}/moadian", headers=other).status_code == 404
    assert all(i["id"] != rid for i in client.get("/ops/contracts", params={"q": ref}, headers=other).json()["items"])
