"""Sales desk CRM: intake, round-robin, stage rules, quote, reservation link, SLA sweep, tenant isolation."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app import operations as m
from app.main import SessionLocal, User
from app.sales_desk import SalesCase, SalesDeskAgent, can_move, normalize_mobile, render_template


def _h(client, email):
    return {"Authorization": f"Bearer {client.post('/auth/dev-login', json={'email': email}).json()['access_token']}"}


def _user(email):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        return u.id, u.tenant_id


def _case(client, h, **extra):
    body = {"customer_name": "مشتری آزمون", "mobile": "۰۹۱۲۳۴۵۶۷۸۹", "channel": "whatsapp", "trip": "مشهد ۳ شب", "travellers": 2, **extra}
    r = client.post("/sales-desk/cases", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_pure_helpers():
    assert normalize_mobile("+98 912 345 6789") == "09123456789"
    assert normalize_mobile("۹۱۲۳۴۵۶۷۸۹") == "09123456789"
    for bad in ("0212345678", "abc", ""):
        try:
            normalize_mobile(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    assert can_move("new", "quoted") and not can_move("quoted", "new") and can_move("paid", "lost")
    assert can_move("lost", "new") and not can_move("lost", "paid") and not can_move("new", "new")
    assert render_template("سلام {name} - {unknown}", {"name": "علی"}) == "سلام علی - {unknown}"


def test_permissions_and_tenant_isolation(client):
    emp = _h(client, "employee@aftab.test")
    assert client.get("/sales-desk/cases", headers=emp).status_code == 403
    desk = _h(client, "backoffice@aftab.test")
    case = _case(client, desk)
    assert case["mobile"] == "09123456789" and case["stage"] == "new" and case["code"].startswith("DSK-")
    _, other_tid = _user("employee@faraz.test")
    email = f"desk-{uuid.uuid4().hex[:8]}@faraz.test"
    with SessionLocal() as db:
        db.add(User(tenant_id=other_tid, email=email, name="کارشناس فراز", role="backoffice_expert"))
        db.commit()
    other = _h(client, email)
    assert client.get(f"/sales-desk/cases/{case['id']}", headers=other).status_code == 404
    assert all(i["id"] != case["id"] for i in client.get("/sales-desk/cases", headers=other).json()["items"])
    assert client.post(f"/sales-desk/cases/{case['id']}/stage", json={"stage": "lost", "reason": "x"}, headers=other).status_code == 404
    # backoffice cannot change tenant settings
    assert client.put("/sales-desk/settings", json={"auto_assign": True}, headers=desk).status_code == 403
    bad = client.post("/sales-desk/cases", json={"customer_name": "x", "mobile": "123", "trip": "x"}, headers=desk)
    assert bad.status_code == 422


def test_round_robin_and_complaint_owner(client):
    admin = _h(client, "tenant-admin@aftab.test")
    desk = _h(client, "backoffice@aftab.test")
    desk_id, tid = _user("backoffice@aftab.test")
    admin_id, _ = _user("tenant-admin@aftab.test")
    with SessionLocal() as db:  # isolate from other tests: nobody present
        db.execute(update(SalesDeskAgent).where(SalesDeskAgent.tenant_id == tid).values(present=False))
        db.commit()
    assert client.put("/sales-desk/presence", json={"present": True}, headers=desk).json()["present"] is True
    assert client.put("/sales-desk/presence", json={"present": True}, headers=admin).json()["present"] is True
    got = {_case(client, desk, channel="web_form")["agent_user_id"] for _ in range(2)}
    assert got == {desk_id, admin_id}
    s = client.put("/sales-desk/settings", json={"auto_assign": True, "sla_alert_minutes": 5, "sla_reassign_minutes": 20,
                                                 "complaint_owner_user_id": admin_id, "templates": {"welcome": "درود {name}"}}, headers=admin)
    assert s.status_code == 200, s.text
    assert s.json()["templates"]["welcome"] == "درود {name}" and s.json()["templates"]["quote"]
    complaint = _case(client, desk, channel="complaint")
    assert complaint["is_complaint"] and complaint["agent_user_id"] == admin_id
    assert client.put("/sales-desk/settings", json={"sla_alert_minutes": 30, "sla_reassign_minutes": 10}, headers=admin).status_code == 422
    assert client.put("/sales-desk/settings", json={"templates": {"nope": "x"}}, headers=admin).status_code == 422
    client.put("/sales-desk/settings", json={"auto_assign": True, "complaint_owner_user_id": None}, headers=admin)
    summary = client.get("/sales-desk/summary", headers=desk).json()
    assert summary["present_agents"] >= 2 and summary["requests_today"] >= 3
    team = client.get("/sales-desk/team", headers=desk).json()["items"]
    assert any(r["user_id"] == desk_id and r["present"] for r in team)
    client.put("/sales-desk/presence", json={"present": False}, headers=admin)
    client.put("/sales-desk/presence", json={"present": False}, headers=desk)


def test_stage_quote_reservation_flow(client):
    desk = _h(client, "backoffice@aftab.test")
    desk_id, tid = _user("backoffice@aftab.test")
    case = _case(client, desk, channel="phone")
    cid = case["id"]
    assert case["agent_user_id"] == desk_id  # phone intake with nobody present falls to the creator
    # cannot jump to paid without a reservation; lost needs a reason
    assert client.post(f"/sales-desk/cases/{cid}/stage", json={"stage": "paid"}, headers=desk).status_code == 409
    assert client.post(f"/sales-desk/cases/{cid}/stage", json={"stage": "lost"}, headers=desk).status_code == 422
    call = client.post(f"/sales-desk/cases/{cid}/activities", json={"kind": "call", "body": "تماس اول"}, headers=desk)
    assert call.status_code == 201 and call.json()["stage"] == "contacted" and call.json()["first_response_at"]
    q = client.post(f"/sales-desk/cases/{cid}/quote", json={"amount": 45_000_000, "valid_hours": 12}, headers=desk)
    assert q.status_code == 200 and q.json()["stage"] == "quoted" and "45,000,000" in q.json()["message"]
    assert client.post(f"/sales-desk/cases/{cid}/stage", json={"stage": "contacted"}, headers=desk).status_code == 409
    future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    assert client.post(f"/sales-desk/cases/{cid}/follow-up", json={"at": future}, headers=desk).json()["next_follow_up_at"]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert client.post(f"/sales-desk/cases/{cid}/follow-up", json={"at": past}, headers=desk).status_code == 422
    rendered = client.post(f"/sales-desk/cases/{cid}/render", json={"template": "pay_remind"}, headers=desk).json()
    assert "مشتری آزمون" in rendered["text"] and rendered["mobile"] == "09123456789"

    other_uid, other_tid = _user("employee@faraz.test")
    with SessionLocal() as db:
        own = m.Reservation(tenant_id=tid, user_id=desk_id, service_type="tour", status="reserved", booking_reference="DSK-T-" + uuid.uuid4().hex[:8])
        foreign = m.Reservation(tenant_id=other_tid, user_id=other_uid, service_type="tour", status="reserved")
        db.add_all([own, foreign])
        db.commit()
        own_id, foreign_id = own.id, foreign.id
    assert client.post(f"/sales-desk/cases/{cid}/reservation", json={"reservation_id": foreign_id}, headers=desk).status_code == 404
    linked = client.post(f"/sales-desk/cases/{cid}/reservation", json={"reservation_id": own_id}, headers=desk)
    assert linked.status_code == 200 and linked.json()["stage"] == "awaiting_payment"
    second = _case(client, desk, channel="phone")
    assert client.post(f"/sales-desk/cases/{second['id']}/reservation", json={"reservation_id": own_id}, headers=desk).status_code == 409
    paid = client.post(f"/sales-desk/cases/{cid}/stage", json={"stage": "paid"}, headers=desk)
    assert paid.status_code == 200 and paid.json()["stage"] == "paid"
    detail = client.get(f"/sales-desk/cases/{cid}", headers=desk).json()
    kinds = [a["kind"] for a in detail["activities"]]
    assert {"created", "call", "quote", "reservation", "stage"} <= set(kinds)
    lost = client.post(f"/sales-desk/cases/{second['id']}/stage", json={"stage": "lost", "reason": "قیمت بالا"}, headers=desk)
    assert lost.json()["lost_reason"] == "قیمت بالا"
    assert client.post(f"/sales-desk/cases/{second['id']}/stage", json={"stage": "new"}, headers=desk).json()["lost_reason"] is None
    found = client.get("/sales-desk/cases", params={"q": case["code"]}, headers=desk).json()["items"]
    assert [i["id"] for i in found] == [cid]


def test_sla_sweep_reassigns_unanswered(client):
    admin = _h(client, "tenant-admin@aftab.test")
    desk = _h(client, "backoffice@aftab.test")
    admin_id, tid = _user("tenant-admin@aftab.test")
    with SessionLocal() as db:
        db.execute(update(SalesDeskAgent).where(SalesDeskAgent.tenant_id == tid).values(present=False))
        db.commit()
    client.put("/sales-desk/presence", json={"present": True}, headers=admin)
    case = _case(client, desk, channel="manual", agent_user_id=_user("backoffice@aftab.test")[0])
    with SessionLocal() as db:
        db.execute(update(SalesCase).where(SalesCase.id == case["id"]).values(created_at=datetime.now(timezone.utc) - timedelta(hours=2),
                                                                            sla_due_at=datetime.now(timezone.utc) - timedelta(hours=1)))
        db.commit()
    assert any(i["id"] == case["id"] and i["sla_breached"] for i in client.get("/sales-desk/cases", params={"overdue": True}, headers=desk).json()["items"])
    assert client.post("/sales-desk/sla/sweep", headers=desk).status_code == 403
    swept = client.post("/sales-desk/sla/sweep", headers=admin).json()
    assert swept["reassigned"] >= 1
    assert client.get(f"/sales-desk/cases/{case['id']}", headers=desk).json()["agent_user_id"] == admin_id
    client.put("/sales-desk/presence", json={"present": False}, headers=admin)


def test_public_web_form_intake(client, monkeypatch):
    body = {"customer_name": "بازدیدکننده سایت", "mobile": "09351234567", "trip": "استانبول ۴ شب " + uuid.uuid4().hex[:4], "travellers": 2, "consent": True}
    monkeypatch.delenv("SALES_DESK_PUBLIC_TENANT", raising=False)
    assert client.post("/public/sales-desk/requests", json=body).status_code == 503  # fail closed until configured
    with SessionLocal() as db:
        from app.main import Tenant
        _, tid = _user("backoffice@aftab.test")
        slug = db.scalar(select(Tenant.slug).where(Tenant.id == tid))
    monkeypatch.setenv("SALES_DESK_PUBLIC_TENANT", slug)
    assert client.post("/public/sales-desk/requests", json={**body, "consent": False}).status_code == 422
    assert client.post("/public/sales-desk/requests", json={**body, "mobile": "12"}).status_code == 422
    bot = client.post("/public/sales-desk/requests", json={**body, "website": "http://spam.example"})
    assert bot.status_code == 202
    r = client.post("/public/sales-desk/requests", json=body)
    assert r.status_code == 202 and r.json() == {"received": True}  # nothing about the desk is disclosed
    again = client.post("/public/sales-desk/requests", json={**body, "description": "لطفاً تماس بگیرید"})
    assert again.status_code == 202
    desk = _h(client, "backoffice@aftab.test")
    found = client.get("/sales-desk/cases", params={"q": "09351234567"}, headers=desk).json()["items"]
    mine = [c for c in found if c["trip"] == body["trip"]]
    assert len(mine) == 1 and mine[0]["channel"] == "web_form" and mine[0]["stage"] == "new"  # bot ignored, repeat merged
    detail = client.get(f"/sales-desk/cases/{mine[0]['id']}", headers=desk).json()
    assert any(a["kind"] == "message" and "لطفاً تماس بگیرید" in (a["body"] or "") for a in detail["activities"])
    for i in range(4):  # daily cap per mobile
        client.post("/public/sales-desk/requests", json={**body, "trip": f"سفر دیگر {i} {uuid.uuid4().hex[:4]}"})
    with SessionLocal() as db:
        n = len(db.scalars(select(SalesCase).where(SalesCase.tenant_id == tid, SalesCase.mobile == "09351234567", SalesCase.channel == "web_form")).all())
    assert n <= 3
