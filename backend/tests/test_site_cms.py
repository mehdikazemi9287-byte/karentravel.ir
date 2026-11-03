"""Site CMS: schema-checked slots, draft → publish, public read, revisions, media library guards."""
import io
import struct
import zlib


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _png() -> bytes:
    raw = b"\x00\xff\x00\x00"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


TRIPS = {"title": "سفرهای پیشنهادی پاییز", "items": [{"title": "کویر", "title2": "مصر", "meta": "۲ شب", "href": "/destinations/isfahan", "image": "/images/approved-figma/refTripNorth.jpg"}]}


def test_cms_flow(client):
    admin = _h(client, "tenant-admin@aftab.test")
    assert client.get("/cms/blocks", headers=_h(client, "employee@aftab.test")).status_code == 403
    keys = [b["key"] for b in client.get("/cms/blocks", headers=admin).json()["items"]]
    assert {"hero", "trips", "footer", "announcement"} <= set(keys)

    # schema guards: unknown field, external non-https link, price text
    assert client.put("/cms/blocks/trips", json={**TRIPS, "price": 1}, headers=admin).status_code == 422
    bad = {"title": "x", "items": [{**TRIPS["items"][0], "href": "javascript:alert(1)"}]}
    assert client.put("/cms/blocks/trips", json=bad, headers=admin).status_code == 422
    priced = {"title": "تور کیش فقط ۹۹۰۰۰۰۰ تومان", "items": TRIPS["items"]}
    assert client.put("/cms/blocks/trips", json=priced, headers=admin).status_code == 422
    assert client.put("/cms/blocks/nope", json={}, headers=admin).status_code == 404

    r = client.put("/cms/blocks/trips", json=TRIPS, headers=admin).json()
    assert r["has_unpublished_changes"] and r["published"] is None
    assert "trips" not in client.get("/public/tenants/aftab-bank/site-content").json()   # draft is not public
    p = client.post("/cms/blocks/trips/publish", headers=admin).json()
    assert p["version"] >= 1 and not p["has_unpublished_changes"]
    assert client.get("/public/tenants/aftab-bank/site-content").json()["trips"]["title"] == "سفرهای پیشنهادی پاییز"
    assert "trips" not in client.get("/public/tenants/faraz-industries/site-content").json()   # tenant isolation

    # media: wrong type refused, png accepted, duplicate detected, in-use cannot be deleted
    assert client.post("/cms/media", files={"file": ("x.svg", io.BytesIO(b"<svg onload=alert(1)>"), "image/svg+xml")}, headers=admin).status_code == 415
    png = _png()
    up = client.post("/cms/media", files={"file": ("tile.png", io.BytesIO(png), "image/png")}, data={"alt": "کاشی"}, headers=admin).json()
    again = client.post("/cms/media", files={"file": ("tile2.png", io.BytesIO(png), "image/png")}, headers=admin).json()
    assert again["id"] == up["id"] and again.get("duplicate")
    img = client.get(f"/public/tenants/aftab-bank/media/{up['id']}")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content == png
    assert client.get(f"/public/tenants/faraz-industries/media/{up['id']}").status_code == 404
    with_img = {"title": "سفرهای پیشنهادی", "items": [{**TRIPS["items"][0], "image": up["ref"]}]}
    assert client.put("/cms/blocks/trips", json=with_img, headers=admin).status_code == 200
    assert client.delete(f"/cms/media/{up['id']}", headers=admin).status_code == 409
    missing = {"title": "x", "items": [{**TRIPS["items"][0], "image": "media:00000000-0000-0000-0000-000000000000"}]}
    assert client.put("/cms/blocks/trips", json=missing, headers=admin).status_code == 422

    # history: restore the first published version back into the draft
    revs = client.get("/cms/blocks/trips/revisions", headers=admin).json()["items"]
    first = revs[-1]
    restored = client.post(f"/cms/blocks/trips/revisions/{first['id']}/restore", headers=admin).json()
    assert restored["draft"]["title"] == first["data"]["title"]
    assert client.delete(f"/cms/media/{up['id']}", headers=admin).status_code in (200, 409)
    assert client.post("/cms/blocks/trips/unpublish", headers=admin).status_code == 200
    assert "trips" not in client.get("/public/tenants/aftab-bank/site-content").json()
