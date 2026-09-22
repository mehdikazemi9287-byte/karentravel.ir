from sqlalchemy import func, select

import app.providers as providers_module
from app.main import SessionLocal, Tenant, User
from app.operations import OTPChallenge


class _OkAdapter:
    def execute(self, operation, payload, context):
        return {"ok": True, "status": "accepted", "reference": "test-adapter"}


def test_new_mobile_registers_and_gets_customer_role_in_consumer_tenant(client, monkeypatch):
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", _OkAdapter())
    r = client.post("/auth/register/request", json={"mobile": "09121230001", "name": "کاربر تست"})
    assert r.status_code == 202
    body = r.json()
    assert body["tenant_slug"] == "karenseir-consumer"

    with SessionLocal() as db:
        challenge = db.get(OTPChallenge, body["challenge_id"])
        assert challenge is not None
        user = db.get(User, challenge.user_id)
        assert user.role == "customer"
        assert user.mobile_e164 == "+989121230001"
        tenant = db.get(Tenant, user.tenant_id)
        assert tenant.slug == "karenseir-consumer"


def test_duplicate_mobile_does_not_create_a_second_account(client, monkeypatch):
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", _OkAdapter())
    r1 = client.post("/auth/register/request", json={"mobile": "09121230002"})
    assert r1.status_code == 202
    r2 = client.post("/auth/register/request", json={"mobile": "09121230002"})
    assert r2.status_code == 202

    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(User).where(User.mobile_e164 == "+989121230002"))
        assert count == 1


def test_mobile_already_used_by_another_tenant_user_is_not_duplicated(client, monkeypatch):
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", _OkAdapter())
    with SessionLocal() as db:
        other_tenant = db.scalar(select(Tenant).where(Tenant.slug == "aftab-bank"))
        assert other_tenant is not None
        db.add(User(tenant_id=other_tenant.id, email="staff-mobile-collision@aftab.test", name="staff", role="employee", mobile_e164="+989121230003"))
        db.commit()

    r = client.post("/auth/register/request", json={"mobile": "09121230003"})
    assert r.status_code == 202

    with SessionLocal() as db:
        after = db.scalar(select(func.count()).select_from(User).where(User.mobile_e164 == "+989121230003"))
        assert after == 1  # still exactly one -- no duplicate created, and no customer-role account either
        rows = db.scalars(select(User).where(User.mobile_e164 == "+989121230003")).all()
        assert rows[0].role == "employee"  # the original staff account, untouched


def test_invalid_mobile_is_rejected(client):
    r = client.post("/auth/register/request", json={"mobile": "not-a-number"})
    assert r.status_code == 422


def test_register_then_otp_verify_end_to_end_issues_real_tokens(client, monkeypatch):
    captured = {}

    class _CapturingAdapter:
        def execute(self, operation, payload, context):
            captured["code"] = payload["code"]
            return {"ok": True, "status": "accepted", "reference": "test-adapter"}

    monkeypatch.setitem(providers_module.ADAPTERS, "otp", _CapturingAdapter())
    r = client.post("/auth/register/request", json={"mobile": "09121230004", "name": "کاربر انتها به انتها"})
    assert r.status_code == 202
    challenge_id = r.json()["challenge_id"]
    tenant_slug = r.json()["tenant_slug"]

    verify = client.post("/auth/otp/verify", json={
        "tenant_slug": tenant_slug, "challenge_id": challenge_id,
        "code": captured["code"], "device_id": "test-device-0001",
    })
    assert verify.status_code == 200
    tokens = verify.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    with SessionLocal() as db:
        challenge = db.get(OTPChallenge, challenge_id)
        user = db.get(User, challenge.user_id)
        assert user.role == "customer"
