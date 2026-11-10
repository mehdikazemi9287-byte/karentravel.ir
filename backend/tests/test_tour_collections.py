"""Themed tour pages (last-minute, Nowruz, special) and the FAQ slot: only real, bookable departures are listed."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from app import operations as m
from sqlalchemy import select

from app.main import SessionLocal, User, _nowruz_window, tour_collection
from test_search_v2_public import _seed_public_tenant

TEHRAN = timezone(timedelta(hours=3, minutes=30))


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _tour(db, tenant, supplier_id, title, starts, *, remaining=5, status="published", deadline=None):
    t = m.TourProduct(tenant_id=tenant, supplier_id=supplier_id, title=title, slug=uuid.uuid4().hex, origin="تهران", destination="کیش",
                      tour_type="leisure", status=status, details_json=json.dumps({"description": "Mock QA", "private_contract": "hidden"}))
    db.add(t)
    db.flush()
    db.add(m.TourDeparture(tenant_id=tenant, tour_id=t.id, starts_at=starts, ends_at=starts + timedelta(days=3),
                           booking_deadline=deadline or starts - timedelta(days=1), capacity=10, remaining=remaining, base_price=1000000))
    return t.id


def test_nowruz_window_moves_to_next_year():
    a, b = _nowruz_window(datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert a.astimezone(TEHRAN).date().isoformat() == "2027-03-14" and b.astimezone(TEHRAN).date().isoformat() == "2027-04-04"
    a, _ = _nowruz_window(datetime(2027, 3, 25, tzinfo=timezone.utc))
    assert a.astimezone(TEHRAN).year == 2027
    a, _ = _nowruz_window(datetime(2027, 4, 10, tzinfo=timezone.utc))
    assert a.astimezone(TEHRAN).year == 2028


def test_tour_collections(client):
    tenant = _seed_public_tenant()
    now = datetime.now(timezone.utc)
    nowruz_start, _ = _nowruz_window(now)
    with SessionLocal() as db:
        s = m.Supplier(tenant_id=tenant, supplier_type="tour", display_name="Mock QA collections", status="active")
        db.add(s)
        db.flush()
        soon = _tour(db, tenant, s.id, "Mock QA soon", now + timedelta(days=5), remaining=3)
        later = _tour(db, tenant, s.id, "Mock QA later", now + timedelta(days=40))
        full = _tour(db, tenant, s.id, "Mock QA full", now + timedelta(days=4), remaining=0)
        closed = _tour(db, tenant, s.id, "Mock QA closed", now + timedelta(days=3), deadline=now - timedelta(hours=1))
        draft = _tour(db, tenant, s.id, "Mock QA draft", now + timedelta(days=6), status="draft")
        nowruz = _tour(db, tenant, s.id, "Mock QA nowruz", nowruz_start + timedelta(days=7))
        db.commit()

    lm = client.get("/public/tenants/aftab-bank/tour-collections/last-minute").json()
    ids = [i["id"] for i in lm["items"]]
    assert soon in ids and later not in ids and full not in ids and closed not in ids and draft not in ids
    item = next(i for i in lm["items"] if i["id"] == soon)
    assert item["nights"] == 3 and item["departure_count"] == 1
    assert item["departures"][0]["seats_left"] is True and "base_price" not in str(lm) and "private" not in str(lm)
    assert lm["window"]["from"] < lm["window"]["to"] and "rating" not in item

    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).limit(1))
        for i, (r, state) in enumerate([(5, "approved"), (4, "approved"), (1, "pending")]):
            db.add(m.Review(tenant_id=tenant, user_id=user_id, service_type="tour", service_reference=soon, rating=r, title="Mock QA", body="Mock QA review body",
                            moderation_state=state, command_id=f"mockqa-{soon}-{i}"))
        db.commit()
    item = next(i for i in client.get("/public/tenants/aftab-bank/tour-collections/last-minute").json()["items"] if i["id"] == soon)
    assert item["rating"] == {"average": 4.5, "count": 2}

    nr = [i["id"] for i in client.get("/public/tenants/aftab-bank/tour-collections/nowruz").json()["items"]]
    assert nowruz in nr and soon not in nr

    assert client.get("/public/tenants/aftab-bank/tour-collections/cheap").status_code == 404
    assert client.get("/public/tenants/aftab-bank/tour-collections/special").json()["items"] == []

    admin = _h(client, "tenant-admin@aftab.test")
    body = {"title": "تورهای ویژه", "intro": "انتخاب کارشناسان", "tour_ids": [later, draft, soon]}
    assert client.put("/cms/blocks/special_tours", json={**body, "tour_ids": ["bad id!"]}, headers=admin).status_code == 422
    assert client.put("/cms/blocks/special_tours", json=body, headers=admin).status_code == 200
    # a draft is not public yet
    assert client.get("/public/tenants/aftab-bank/tour-collections/special").json()["items"] == []
    assert client.post("/cms/blocks/special_tours/publish", headers=admin).status_code == 200
    special = [i["id"] for i in client.get("/public/tenants/aftab-bank/tour-collections/special").json()["items"]]
    assert special == [later, soon]  # editor's order; the unpublished tour drops off

    with SessionLocal() as db:
        assert tour_collection(db, tenant, "special", []) == {"key": "special", "items": []}


def test_faq_slot(client):
    admin = _h(client, "tenant-admin@aftab.test")
    faq = {"title": "سؤالات متداول", "intro": "", "items": [{"question": "چطور رزرو کنم؟", "answer": "از جست‌وجوی سایت مقصد و تاریخ را انتخاب کنید."}]}
    assert client.put("/cms/blocks/faq", json={**faq, "items": []}, headers=admin).status_code == 422
    bad = {**faq, "items": [{"question": "قیمت تور کیش؟", "answer": "از ۵ میلیون تومان"}]}
    assert client.put("/cms/blocks/faq", json=bad, headers=admin).status_code == 422
    assert client.put("/cms/blocks/faq", json=faq, headers=admin).status_code == 200
    assert client.post("/cms/blocks/faq/publish", headers=admin).status_code == 200
    assert client.get("/public/tenants/aftab-bank/site-content").json()["faq"]["items"][0]["question"] == "چطور رزرو کنم؟"


def test_festival_window_and_activation(client):
    tenant = _seed_public_tenant()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        s = m.Supplier(tenant_id=tenant, supplier_type="tour", display_name="Mock QA festival", status="active")
        db.add(s)
        db.flush()
        tid = _tour(db, tenant, s.id, "Mock QA festival tour", now + timedelta(days=20))
        db.commit()
    admin = _h(client, "tenant-admin@aftab.test")
    today = now.astimezone(TEHRAN).date()
    base = {"active": True, "title": "جشنواره‌ی پاییز", "intro": "تورهای منتخب پاییز", "image": "", "terms": "", "tour_ids": [tid],
            "starts_on": (today - timedelta(days=1)).isoformat(), "ends_on": (today + timedelta(days=5)).isoformat()}
    assert client.put("/cms/blocks/festival", json={**base, "ends_on": (today - timedelta(days=3)).isoformat()}, headers=admin).status_code == 422
    assert client.put("/cms/blocks/festival", json={**base, "title": "جشنواره با ۳۰٪ تخفیف"}, headers=admin).status_code == 422
    url = "/public/tenants/aftab-bank/tour-collections/festival"
    assert client.get(url).json() == {"key": "festival", "items": [], "festival": None}

    assert client.put("/cms/blocks/festival", json=base, headers=admin).status_code == 200
    assert client.post("/cms/blocks/festival/publish", headers=admin).status_code == 200
    live = client.get(url).json()
    assert live["festival"]["title"] == "جشنواره‌ی پاییز" and [i["id"] for i in live["items"]] == [tid]

    # not started yet → nothing public
    later = {**base, "starts_on": (today + timedelta(days=2)).isoformat()}
    assert client.put("/cms/blocks/festival", json=later, headers=admin).status_code == 200
    assert client.post("/cms/blocks/festival/publish", headers=admin).status_code == 200
    assert client.get(url).json()["festival"] is None
    # switched off
    assert client.put("/cms/blocks/festival", json={**base, "active": False}, headers=admin).status_code == 200
    assert client.post("/cms/blocks/festival/publish", headers=admin).status_code == 200
    assert client.get(url).json() == {"key": "festival", "items": [], "festival": None}
