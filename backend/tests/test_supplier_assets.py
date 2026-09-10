"""Supplier asset uploads: RBAC, tenant + supplier ownership, content validation,
persistence metadata, safe storage keys."""
import base64
import uuid

from app.main import SessionLocal
from app import operations as om

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAFhAJ/wlseKgAAAABJRU5ErkJggg=="
)


def login(client, email):
    resp = client.post("/auth/dev-login", json={"email": email})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def onboard(client, headers, kind="multi_service"):
    key = f"onb-{uuid.uuid4().hex}"
    resp = client.post("/supplier/onboarding", headers={**headers, "Idempotency-Key": key},
                       json={"supplier_type": kind, "display_name": f"تأمین‌کننده {kind}"})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _upload(client, headers, supplier_id, *, filename="logo.png", content=PNG_1X1,
            entity_type="supplier_profile", kind="image", visibility="private", ctype="image/png"):
    return client.post(
        f"/supplier/{supplier_id}/assets",
        headers=headers,
        data={"entity_type": entity_type, "kind": kind, "visibility": visibility},
        files={"file": (filename, content, ctype)},
    )


def test_happy_path_upload_list_download(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    up = _upload(client, sup, sid)
    assert up.status_code == 201, up.text
    body = up.json()
    assert body["byte_size"] == len(PNG_1X1)
    assert body["checksum_sha256"]
    assert ".." not in body["download_url"]

    listed = client.get(f"/supplier/{sid}/assets", headers=sup)
    assert listed.status_code == 200
    assert len(listed.json()["assets"]) == 1

    content = client.get(body["download_url"], headers=sup)
    assert content.status_code == 200
    assert content.content == PNG_1X1
    assert content.headers["content-type"].startswith("image/png")

    # storage key is tenant-scoped and traversal-free
    with SessionLocal() as db:
        row = db.get(om.SupplierAsset, body["id"])
        assert row.storage_key.startswith("tenant/")
        assert "/supplier/" in row.storage_key and ".." not in row.storage_key
        assert row.created_by is not None


def test_unauthenticated_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    resp = client.post(f"/supplier/{sid}/assets",
                       data={"entity_type": "supplier_profile", "kind": "image"},
                       files={"file": ("x.png", PNG_1X1, "image/png")})
    assert resp.status_code == 401


def test_customer_role_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    customer = login(client, "employee@aftab.test")
    assert _upload(client, customer, sid).status_code == 403


def test_cross_supplier_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    up = _upload(client, sup, sid).json()

    # a second supplier in the same tenant that this user has no membership for
    with SessionLocal() as db:
        other = om.Supplier(tenant_id=1, supplier_type="hotel", display_name="تأمین‌کننده دیگر", status="active")
        db.add(other); db.flush()
        other_asset = om.SupplierAsset(
            tenant_id=1, supplier_id=other.id, entity_type="license", kind="document",
            visibility="private", status="active", storage_key=f"tenant/1/supplier/{other.id}/license/{other.id}/{uuid.uuid4().hex}.pdf",
            original_filename="x.pdf", content_type="application/pdf", byte_size=10,
            checksum_sha256="0" * 64, created_by=1)
        db.add(other_asset); db.commit()
        other_id, other_asset_id = other.id, other_asset.id

    assert _upload(client, sup, other_id).status_code == 403
    assert client.get(f"/supplier/{other_id}/assets", headers=sup).status_code == 403
    assert client.get(f"/supplier/assets/{other_asset_id}/content", headers=sup).status_code == 403
    assert client.request("DELETE", f"/supplier/assets/{other_asset_id}", headers=sup).status_code == 403


def test_cross_tenant_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    up = _upload(client, sup, sid).json()
    faraz = login(client, "employee@faraz.test")
    assert client.get(f"/supplier/assets/{up['id']}/content", headers=faraz).status_code in (403, 404)
    assert client.get(f"/supplier/{sid}/assets", headers=faraz).status_code in (403, 404)


def test_invalid_extension_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    assert _upload(client, sup, sid, filename="evil.exe", ctype="application/octet-stream").status_code == 422
    assert _upload(client, sup, sid, filename="evil.php", ctype="text/plain").status_code == 422


def test_content_type_mismatch_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    # .png extension but not a real PNG
    assert _upload(client, sup, sid, filename="fake.png", content=b"\x89PNG\r\n\x1a\nnot-real").status_code == 422
    # executable payload masquerading as png
    assert _upload(client, sup, sid, filename="x.png", content=b"MZ\x90\x00" + b"\x00" * 64).status_code == 422


def test_oversized_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    big = b"%PDF-1.4\n" + b"0" * (16 * 1024 * 1024)
    resp = _upload(client, sup, sid, filename="big.pdf", content=big, kind="document", ctype="application/pdf")
    assert resp.status_code == 413


def test_path_traversal_filename_denied(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    assert _upload(client, sup, sid, filename="../../../../etc/passwd").status_code == 422
    assert _upload(client, sup, sid, filename="..\\..\\win.png").status_code == 422


def test_replace_and_delete(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    up = _upload(client, sup, sid).json()

    rep = client.put(f"/supplier/assets/{up['id']}/content", headers=sup,
                     files={"file": ("logo2.png", PNG_1X1, "image/png")})
    assert rep.status_code == 200
    assert rep.json()["original_filename"] == "logo2.png"

    dele = client.request("DELETE", f"/supplier/assets/{up['id']}", headers=sup)
    assert dele.status_code == 204
    assert client.get(f"/supplier/assets/{up['id']}/content", headers=sup).status_code == 404
    assert client.get(f"/supplier/{sid}/assets", headers=sup).json()["assets"] == []


def test_audit_event_written(client):
    sup = login(client, "supplier@aftab.test")
    sid = onboard(client, sup)
    up = _upload(client, sup, sid).json()
    with SessionLocal() as db:
        events = db.query(om.OutboxEvent).filter(
            om.OutboxEvent.aggregate_type == "supplier_asset",
            om.OutboxEvent.aggregate_id == up["id"]).all()
        assert any("upload" in e.payload_json for e in events)
