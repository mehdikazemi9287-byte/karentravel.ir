"""Requests to Padvira (public request API) and Gift Asan (WooCommerce order) on the customer's behalf."""
import pytest
from fastapi import HTTPException

from app import partner_requests as pr


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_padvira_payload_and_errors():
    seen = {}
    def ok(body, key):
        seen.update(body=body, key=key)
        return 201, {"id": "cmvvabc1234567"}
    data = pr.PadviraIn(full_name="مریم آزمون", contact="۰۹۱۲۱۲۳۴۵۶۷", service="بوت‌کمپ طبیعت", message="برای دو نفر در آذر", category="family")
    assert pr.padvira_create(data, "k" * 20, post=ok) == "cmvvabc1234567"
    assert seen["body"]["contact"] == "09121234567" and seen["body"]["message"].startswith("[از کارن‌سیر] بوت‌کمپ طبیعت") and seen["key"] == "k" * 20
    with pytest.raises(HTTPException) as e:
        pr.padvira_create(data, "k" * 20, post=lambda b, k: (422, {"fieldErrors": {"message": "کوتاه"}}))
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:
        pr.padvira_create(data, "k" * 20, post=lambda b, k: (500, {}))
    assert e.value.status_code == 502


def test_giftasan_order_payload(monkeypatch):
    monkeypatch.delenv("GIFTASAN_WC_KEY", raising=False)
    data = pr.SouvenirIn(full_name="علی آزمون", contact="09121234567", city="یزد", items="باقلوا و قطاب ۲ جعبه", deliver_to="تهران، ونک")
    with pytest.raises(HTTPException) as e:
        pr.giftasan_create(data, "ref-1")
    assert e.value.status_code == 503   # no key configured
    seen = {}
    def post(body):
        seen.update(body)
        return 201, {"id": 9876}
    assert pr.giftasan_create(data, "ref-1", post=post) == "9876"
    assert seen["status"] == "on-hold" and seen["set_paid"] is False and "line_items" not in seen
    assert "سوغات یزد: باقلوا" in seen["customer_note"] and seen["billing"]["phone"] == "09121234567"


def test_endpoints_and_status_refresh(client, monkeypatch):
    cust = _h(client, "employee@aftab.test")
    monkeypatch.setattr(pr, "padvira_create", lambda data, key: "cmvvpadvira0001")
    r = client.post("/partners/padvira/requests", json={"full_name": "مریم آزمون", "contact": "09121234567", "service": "اردو", "message": "اردوی خانوادگی دو روزه"}, headers=cust)
    assert r.status_code == 201, r.text
    assert r.json()["reference"] == "cmvvpadvira0001" and r.json()["status_fa"] == "ثبت شد"
    assert client.post("/partners/padvira/requests", json={"full_name": "م", "contact": "1", "service": "x", "message": "x"}, headers=cust).status_code == 422
    monkeypatch.setattr(pr, "giftasan_create", lambda data, ref: "5555")
    g = client.post("/partners/giftasan/souvenir-requests", json={"full_name": "علی آزمون", "contact": "09121234567", "city": "شیراز", "items": "مسقطی", "deliver_to": "تهران"}, headers=cust)
    assert g.status_code == 201 and g.json()["service"] == "سوغات شیراز"
    # status refresh from the partner (only when older than 10 minutes)
    from datetime import timedelta
    from app.main import SessionLocal
    with SessionLocal() as db:
        for row in db.query(pr.PartnerRequest).filter(pr.PartnerRequest.reference.in_(["cmvvpadvira0001", "5555"])).all():
            row.checked_at = row.checked_at - timedelta(minutes=30)
        db.commit()
    monkeypatch.setattr(pr, "padvira_track", lambda ref, contact: {"status": "review", "publicNote": "کارشناس تماس می‌گیرد"})
    monkeypatch.setattr(pr, "giftasan_status", lambda ref: {"status": "processing"})
    items = {i["reference"]: i for i in client.get("/me/partner-requests", headers=cust).json()["items"]}
    assert items["cmvvpadvira0001"]["status_fa"] == "در حال بررسی" and items["cmvvpadvira0001"]["public_note"] == "کارشناس تماس می‌گیرد"
    assert items["5555"]["status_fa"] == "در حال آماده‌سازی"
    assert all(i["reference"] not in ("cmvvpadvira0001",) for i in client.get("/me/partner-requests", headers=_h(client, "backoffice@aftab.test")).json()["items"])


def test_shahrshad_place_request_and_desk(client):
    from app import shahrshad_sync as ss
    from app.main import SessionLocal
    with SessionLocal() as db:
        ss.apply(db, [{"id": "sh-place-1", "slug": "کافه-آزمون", "name": "کافه آزمون", "category": "restaurant", "city": "تهران"}])
    d = client.get("/public/partner-venues/sh-place-1").json()
    assert d["name"] == "کافه آزمون" and "book_url" not in d
    assert client.get("/public/partner-venues/nope").status_code == 404
    cust = _h(client, "employee@aftab.test")
    r = client.post("/partners/shahrshad/requests", json={"venue_id": "sh-place-1", "full_name": "سارا آزمون", "contact": "09121234567", "people": 4, "date": "2026-12-01"}, headers=cust)
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["partner_fa"] == "شهرشاد" and req["reference"].startswith("SH-") and req["status_fa"] == "ثبت شد"
    agent = _h(client, "backoffice@aftab.test")
    assert client.get("/partner-desk/requests", headers=cust).status_code == 403
    items = client.get("/partner-desk/requests?partner=shahrshad", headers=agent).json()["items"]
    assert any(i["id"] == req["id"] and i["contact"] == "09121234567" for i in items)
    u = client.post(f"/partner-desk/requests/{req['id']}/status", json={"status": "done", "public_note": "میز ساعت ۲۰ رزرو شد"}, headers=agent)
    assert u.status_code == 200 and u.json()["status_fa"] == "رسیدگی شد"
    mine = {i["id"]: i for i in client.get("/me/partner-requests", headers=cust).json()["items"]}
    assert mine[req["id"]]["public_note"] == "میز ساعت ۲۰ رزرو شد"
