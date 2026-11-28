"""PR-9: /admin user management — search + paging, invite by mobile (no password; OTP login), reversible deactivation,
price group. TEST FIXTURES ONLY: synthetic names and 0912-000-xxxx style numbers; users are disabled, never deleted."""
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.commerce import CustomerGroup
from app.main import SessionLocal, User


def _h(client, email):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"email": email}).json()["access_token"]}


def _mobile():
    return "0912" + str(random.randint(1000000, 9999999))


def test_invite_search_disable_and_price_group(client):
    admin = _h(client, "tenant-admin@aftab.test")
    assert client.post("/admin/users", headers=_h(client, "employee@aftab.test"), json={"name": "x y", "mobile": _mobile()}).status_code == 403
    mobile = _mobile()
    tag = "دعوتی " + uuid.uuid4().hex[:6]
    created = client.post("/admin/users", headers=admin, json={"name": tag, "mobile": "۰" + mobile[1:].translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")), "role": "employee"})
    assert created.status_code == 201, created.text
    u = created.json()
    assert u["mobile"] == "+98" + mobile[1:] and u["email"] is None and u["active"] and u["role"] == "employee"
    assert client.post("/admin/users", headers=admin, json={"name": tag, "mobile": mobile}).status_code == 409
    assert client.post("/admin/users", headers=admin, json={"name": tag, "mobile": "12345"}).status_code == 422
    assert client.post("/admin/users", headers=admin, json={"name": tag, "mobile": _mobile(), "role": "platform_admin"}).status_code == 422

    found = client.get("/admin/users/search", headers=admin, params={"q": tag}).json()
    assert found["total"] == 1 and found["items"][0]["id"] == u["id"]
    assert client.get("/admin/users/search", headers=admin, params={"q": mobile}).json()["items"][0]["id"] == u["id"]
    page = client.get("/admin/users/search", headers=admin, params={"page_size": 5}).json()
    assert len(page["items"]) <= 5 and page["total"] >= len(page["items"])
    assert all(i["role"] != "public_search_identity" for i in page["items"])

    reason = {"reason": "آزمون غیرفعال‌سازی"}
    off = client.put(f"/admin/users/{u['id']}/status", headers=admin, json={"active": False, **reason}).json()
    assert off["active"] is False and off["disabled_at"]
    assert client.get("/admin/users/search", headers=admin, params={"q": tag, "status": "disabled"}).json()["total"] == 1
    assert client.get("/admin/users/search", headers=admin, params={"q": tag, "status": "active"}).json()["total"] == 0
    assert client.put(f"/admin/users/{u['id']}/status", headers=admin, json={"active": True, **reason}).json()["active"] is True
    with SessionLocal() as db:
        me = db.scalar(select(User).where(User.email == "tenant-admin@aftab.test"))
        assert db.get(User, u["id"]) is not None                               # never deleted
        group = CustomerGroup(tenant_id=me.tenant_id, code="adm-" + uuid.uuid4().hex[:8], name="گروه آزمون کاربران")
        db.add(group); db.commit(); gid, my_id = group.id, me.id
    assert client.put(f"/admin/users/{my_id}/status", headers=admin, json={"active": False, **reason}).status_code == 409   # not yourself
    try:
        g = client.put(f"/admin/users/{u['id']}/price-group", headers=admin, json={"group_id": gid}).json()
        assert g["price_group"] == {"id": gid, "name": "گروه آزمون کاربران"}
        assert client.put(f"/admin/users/{u['id']}/price-group", headers=admin, json={"group_id": "no-such-group"}).status_code == 422
        listed = client.get("/admin/users/search", headers=admin, params={"q": tag}).json()["items"][0]
        assert listed["price_group"]["id"] == gid
    finally:
        with SessionLocal() as db:
            db.get(CustomerGroup, gid).status = "disabled"
            db.get(User, u["id"]).disabled_at = datetime.now(timezone.utc)
            db.commit()


def test_old_list_shape_is_kept_and_search_is_admin_only(client):
    admin = _h(client, "tenant-admin@aftab.test")
    legacy = client.get("/admin/users", headers=admin).json()
    assert isinstance(legacy, list) and {"id", "name", "email", "role", "mutable"} <= set(legacy[0])
    assert client.get("/admin/users/search", headers=_h(client, "employee@aftab.test")).status_code == 403


def test_invited_user_gets_an_otp_challenge_in_the_admin_tenant(client, monkeypatch):
    """The login page sends the organization's slug to /auth/otp/request; the invited mobile must resolve there.
    The SMS adapter is replaced by a stub that accepts; nothing is sent."""
    from types import SimpleNamespace
    from app import providers
    from app.main import Tenant
    from app.operations import OTPChallenge
    monkeypatch.setitem(providers.ADAPTERS, "otp", SimpleNamespace(execute=lambda *a, **k: {"ok": True, "reference": "test-stub"}))
    admin = _h(client, "tenant-admin@aftab.test")
    mobile = _mobile()
    u = client.post("/admin/users", headers=admin, json={"name": "ورود آزمون " + uuid.uuid4().hex[:5], "mobile": mobile}).json()
    with SessionLocal() as db:
        slug = db.get(Tenant, db.get(User, u["id"]).tenant_id).slug
    assert client.post("/auth/otp/request", json={"tenant_slug": slug, "identifier": mobile}).status_code == 202
    with SessionLocal() as db:
        assert db.scalar(select(OTPChallenge.id).where(OTPChallenge.user_id == u["id"])) is not None
        db.get(User, u["id"]).disabled_at = datetime.now(timezone.utc)
        db.commit()
