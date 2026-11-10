"""Reversible deactivation (users.disabled_at / tenants.disabled_at) is enforced at login, refresh and on every token."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.main import SessionLocal, Tenant, User


def _set(model, column_filter, value):
    with SessionLocal() as db:
        row = db.scalar(select(model).where(column_filter))
        row.disabled_at = value
        db.commit()


@pytest.fixture()
def restore():
    yield
    with SessionLocal() as db:
        for row in db.scalars(select(User).where(User.disabled_at.isnot(None), User.email.in_(["welfare@aftab.test"]))):
            row.disabled_at = None
        for row in db.scalars(select(Tenant).where(Tenant.disabled_at.isnot(None), Tenant.slug == "faraz-industries")):
            row.disabled_at = None
        db.commit()


def test_disabled_user_cannot_log_in_refresh_or_use_token(client, restore):
    session = client.post("/auth/dev-login", json={"email": "welfare@aftab.test"}).json()
    bearer = {"Authorization": f"Bearer {session['access_token']}"}
    assert client.get("/me/wallets", headers=bearer).status_code == 200
    _set(User, User.email == "welfare@aftab.test", datetime.now(timezone.utc))
    assert client.get("/me/wallets", headers=bearer).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code == 401
    assert client.post("/auth/dev-login", json={"email": "welfare@aftab.test"}).status_code == 401
    otp = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "welfare@aftab.test"})
    assert otp.status_code == 202 and otp.json()["status"] == "accepted"  # enumeration-safe, nothing sent
    _set(User, User.email == "welfare@aftab.test", None)  # reversible
    assert client.post("/auth/dev-login", json={"email": "welfare@aftab.test"}).status_code == 200


def test_disabled_tenant_blocks_its_users(client, restore):
    session = client.post("/auth/dev-login", json={"email": "employee@faraz.test"}).json()
    _set(Tenant, Tenant.slug == "faraz-industries", datetime.now(timezone.utc))
    assert client.get("/me/wallets", headers={"Authorization": f"Bearer {session['access_token']}"}).status_code == 401
    assert client.post("/auth/dev-login", json={"email": "employee@faraz.test"}).status_code == 401
    assert client.post("/auth/dev-login", json={"email": "employee@aftab.test"}).status_code == 200  # other tenants unaffected
