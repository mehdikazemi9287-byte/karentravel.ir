"""Voucher QR: only for issued vouchers, owner-only, signed code, public verification shows no personal data."""
import uuid

from sqlalchemy import select

from app import operations as m
from app.main import SessionLocal, User
from app.voucher_verify import make_code, mask_ref, parse_code


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_code_signing():
    rid = str(uuid.uuid4())
    code = make_code("s" * 40, 3, rid)
    assert parse_code("s" * 40, code) == (3, rid)
    assert parse_code("x" * 40, code) is None and parse_code("s" * 40, "4" + code[1:]) is None and parse_code("s" * 40, "junk") is None
    assert mask_ref("KS-TOUR-ABCDEF") == "••••••••••CDEF"


def _res(status, voucher=True):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        r = m.Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="hotel", status=status, booking_reference="VQ-" + uuid.uuid4().hex[:8].upper(),
                          price_snapshot_json='{"total_amount": 1000, "currency": "IRR"}', policy_at_booking_json="{}", current_policy_json="{}")
        db.add(r); db.flush()
        if voucher:
            db.add(m.Voucher(tenant_id=u.tenant_id, reservation_id=r.id, status="issued", revision=1, document_reference="doc"))
        db.commit()
        return r.id, r.booking_reference


def test_voucher_qr_and_public_verify(client):
    h = _h(client, "employee@aftab.test")
    rid, ref = _res("issued")
    q = client.get(f"/me/reservations/{rid}/voucher-qr", headers=h)
    assert q.status_code == 200 and "<svg" in q.json()["qr_svg"] and q.json()["verify_url"].endswith("/v/" + q.json()["code"])
    assert client.get(f"/me/reservations/{rid}/voucher-qr", headers=_h(client, "backoffice@aftab.test")).status_code == 404   # owner only
    pending, _ = _res("reserved", voucher=False)
    assert client.get(f"/me/reservations/{pending}/voucher-qr", headers=h).status_code == 409
    v = client.get(f"/public/vouchers/{q.json()['code']}")
    assert v.status_code == 200
    body = v.json()
    assert body["valid"] is True and body["booking_reference"].endswith(ref[-4:]) and ref not in str(body) and body["service"] == "هتل"
    assert set(body) == {"valid", "booking_reference", "service", "status", "revision"}
    with SessionLocal() as db:
        db.get(m.Reservation, rid).status = "cancelled"
        db.commit()
    assert client.get(f"/public/vouchers/{q.json()['code']}").json()["valid"] is False
    assert client.get("/public/vouchers/1." + str(uuid.uuid4()) + ".AAAAAAAAAAAAAAAA").status_code == 404
