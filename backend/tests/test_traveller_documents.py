"""Traveller documents: ownership on upload, masked number, blurred preview, audited reveal, review, retention sweep, isolation."""
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

from PIL import Image
from sqlalchemy import select

from app import operations as m
from app.main import AuditEvent, SessionLocal, User
from app.traveller_documents import TravellerDocument, mask_number


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _png(color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (600, 400), color).save(buf, "PNG")
    return buf.getvalue()


def _reservation(email, status="confirmed"):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        r = m.Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="tour", status=status, booking_reference="DOC-" + uuid.uuid4().hex[:8],
                          price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
        db.add(r)
        db.commit()
        return r.id


def test_mask_number():
    assert mask_number("K 1234 5678") == "••••••678" and mask_number(None) is None


def test_upload_review_reveal_and_retention(client, monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(tmp_path))
    cust = _h(client, "employee@aftab.test")
    bo = _h(client, "backoffice@aftab.test")
    rid = _reservation("employee@aftab.test")
    other_rid = _reservation("backoffice@aftab.test")

    files = {"file": ("passport.png", _png(), "image/png")}
    assert client.post("/me/documents", data={"doc_type": "passport", "reservation_id": other_rid}, files=files, headers=cust).status_code == 404
    assert client.post("/me/documents", data={"doc_type": "passport"}, files={"file": ("x.png", b"not an image", "image/png")}, headers=cust).status_code == 422
    assert client.post("/me/documents", data={"doc_type": "tattoo"}, files=files, headers=cust).status_code == 422
    up = client.post("/me/documents", data={"doc_type": "passport", "number": "K12345678", "holder_name": "مسافر آزمون", "expires_on": "2030-01-01",
                                            "reservation_id": rid}, files={"file": ("passport.png", _png(), "image/png")}, headers=cust)
    assert up.status_code == 201, up.text
    doc = up.json()
    assert doc["number"] == "••••••678" and doc["status"] == "submitted" and doc["has_file"] and "storage_key" not in doc
    assert any(d["id"] == doc["id"] for d in client.get("/me/documents", headers=cust).json()["items"])

    # staff queue: customers cannot read it; no file in the listing
    assert client.get("/ops/documents", headers=cust).status_code == 403
    q = client.get("/ops/documents", headers=bo).json()
    item = next(i for i in q["items"] if i["id"] == doc["id"])
    assert item["owner"] and item["booking_reference"].startswith("DOC-") and q["counts"]["submitted"] >= 1

    pv = client.get(f"/ops/documents/{doc['id']}/preview", headers=bo)
    assert pv.status_code == 200 and pv.headers["content-type"] == "image/jpeg" and pv.headers["cache-control"] == "no-store"
    with Image.open(io.BytesIO(pv.content)) as im:
        assert max(im.size) <= 360
    assert client.post(f"/ops/documents/{doc['id']}/reveal", json={"reason": "x"}, headers=bo).status_code == 422
    rv = client.post(f"/ops/documents/{doc['id']}/reveal", json={"reason": "تطبیق نام با بلیت"}, headers=bo)
    assert rv.status_code == 200 and rv.content.startswith(b"\x89PNG")
    with SessionLocal() as db:
        ev = db.scalars(select(AuditEvent).where(AuditEvent.action == "traveller_document.revealed").order_by(AuditEvent.id.desc())).first()
        assert json.loads(ev.detail)["document_id"] == doc["id"]

    assert client.post(f"/ops/documents/{doc['id']}/review", json={"decision": "reject"}, headers=bo).status_code == 422
    assert client.post(f"/ops/documents/{doc['id']}/review", json={"decision": "reject", "note": "عکس صفحه‌ی اول واضح نیست"}, headers=bo).json()["status"] == "rejected"
    assert client.post(f"/ops/documents/{doc['id']}/review", json={"decision": "approve"}, headers=bo).json()["status"] == "approved"

    # retention: past delete_after but reservation active -> kept; reservation completed -> file removed, row kept
    with SessionLocal() as db:
        d = db.get(TravellerDocument, doc["id"])
        d.delete_after = datetime.now(timezone.utc) - timedelta(days=1)
        key = d.storage_key
        db.commit()
    assert (tmp_path / key).exists()
    assert client.post("/ops/documents/purge", headers=bo).json()["purged"] == 0
    with SessionLocal() as db:
        db.get(m.Reservation, rid).status = "completed"
        db.commit()
    assert client.post("/ops/documents/purge", headers=bo).json()["purged"] >= 1
    assert not (tmp_path / key).exists()
    after = next(d for d in client.get("/me/documents", headers=cust).json()["items"] if d["id"] == doc["id"])
    assert after["status"] == "deleted" and after["deleted_reason"] == "retention" and not after["has_file"] and after["number"] == "••••••678"
    assert client.get(f"/ops/documents/{doc['id']}/preview", headers=bo).status_code == 410

    # owner deletion and retention settings
    up2 = client.post("/me/documents", data={"doc_type": "national_id"}, files={"file": ("id.png", _png((10, 10, 10)), "image/png")}, headers=cust).json()
    assert client.delete(f"/me/documents/{up2['id']}", headers=cust).json()["deleted_reason"] == "owner"
    assert client.put("/ops/documents/settings", json={"retention_days": 30}, headers=bo).status_code == 403
    assert client.put("/ops/documents/settings", json={"retention_days": 30}, headers=_h(client, "tenant-admin@aftab.test")).status_code == 200

    # isolation
    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"doc-bo-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="عملیات فراز", role="backoffice_expert"))
        db.commit()
    other = _h(client, oemail)
    assert client.get(f"/ops/documents/{up2['id']}/preview", headers=other).status_code == 404
    assert all(i["id"] != doc["id"] for i in client.get("/ops/documents?status=all", headers=other).json()["items"])
