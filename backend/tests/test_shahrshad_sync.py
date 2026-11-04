"""ShahrShad partner places: paged fetch, upsert/deactivate, honest prices, public listing by section."""
from app import shahrshad_sync as ss
from app.main import SessionLocal


def _items(n_rest=3):
    rest = [{"id": f"r-{i}", "slug": f"رستوران-{i}-تهران", "name": f"رستوران آزمون {i}", "category": "restaurant", "city": "تهران", "description": "غذای ایرانی",
             "price_from_irr": 5_000_000, "price_state": "published", "stale": False, "facts_checked_on": "2026-10-01", "facilities": ["parking", "unknown_x"]} for i in range(n_rest)]
    pool = {"id": "p-1", "slug": "پارک-آبی-تهران", "name": "پارک آبی آزمون", "category": "pool", "city": "تهران", "admission": ["men", "women"],
            "price_from_irr": 6_900_000, "price_state": "draft", "stale": False, "image_url": "http://insecure.example/x.jpg"}
    return rest + [pool, {"id": "bad"}]


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_fetch_pages():
    calls = []
    def get(url):
        calls.append(url)
        off = int(url.split("offset=")[1])
        return {"items": [{"id": str(off + i)} for i in range(2 if off < 4 else 1)]}
    assert len(ss.fetch_all(get, page=2)) == 5 and len(calls) == 3


def test_sync_and_public_listing(client, monkeypatch):
    with SessionLocal() as db:
        r = ss.apply(db, _items())
    assert r["fetched"] == 5 and r["created"] + r["updated"] == 4
    page = client.get("/public/partner-venues?section=restaurants&city=تهران").json()
    names = [i["name"] for i in page["items"]]
    assert "رستوران آزمون 0" in names and page["items"][0]["price_from_irr"] == 5_000_000
    assert page["items"][0]["book_url"].startswith("https://shahrshad.ir/venues/") and page["items"][0]["facilities"] == ["پارکینگ"]
    pools = client.get("/public/partner-venues?section=pools-sports").json()["items"]
    p = next(i for i in pools if i["name"] == "پارک آبی آزمون")
    assert p["price_from_irr"] is None and p["image_url"] is None and p["admission"] == ["آقایان", "بانوان"]   # draft price and http image are not shown
    assert client.get("/public/partner-venues?section=restaurants&category=pool").status_code == 422

    with SessionLocal() as db:   # a venue missing from the next sync is hidden, not deleted
        ss.apply(db, _items(n_rest=1))
    names = [i["name"] for i in client.get("/public/partner-venues?section=restaurants&city=تهران").json()["items"]]
    assert "رستوران آزمون 2" not in names and "رستوران آزمون 0" in names

    assert client.post("/admin/shahrshad/sync", headers=_h(client, "employee@aftab.test")).status_code == 403
    monkeypatch.setattr(ss, "fetch_all", lambda: _items())
    s = client.post("/admin/shahrshad/sync", headers=_h(client, "tenant-admin@aftab.test"))
    assert s.status_code == 200, s.text
    assert client.get("/admin/shahrshad/status", headers=_h(client, "tenant-admin@aftab.test")).json()["active"] >= 4
