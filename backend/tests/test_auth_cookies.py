"""M-3: httpOnly cookie session transport + double-submit CSRF behind AUTH_COOKIE_MODE."""
import uuid

import pytest
from sqlalchemy import select

from app.main import SessionLocal, User

EMAIL = "cookie-mode@aftab.test"  # own account: the wallets created here must not collide with other tests'


@pytest.fixture(autouse=True)
def _cookie_user():
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == EMAIL)) is None:
            base = db.scalar(select(User).where(User.email == "employee@aftab.test"))
            db.add(User(tenant_id=base.tenant_id, email=EMAIL, name="[TEST] cookie", role="employee"))
            db.commit()


@pytest.fixture()
def cookie_mode(monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_MODE", "1")
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)


def _set_cookies(response):
    return [v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"]


def test_flag_off_keeps_bearer_tokens_in_body(client, monkeypatch):
    monkeypatch.delenv("AUTH_COOKIE_MODE", raising=False)
    r = client.post("/auth/dev-login", json={"email": EMAIL})
    assert r.status_code == 200 and r.json()["access_token"] and not _set_cookies(r)


def test_cookie_login_hides_tokens_and_authenticates(client, cookie_mode):
    client.cookies.clear()
    r = client.post("/auth/dev-login", json={"email": EMAIL})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" not in body and "refresh_token" not in body
    assert body["token_type"] == "cookie" and body["subject"]["sub"] and body["user"]["role"] == "employee"
    cookies = _set_cookies(r)
    at = next(c for c in cookies if c.startswith("karenseir_at="))
    rt = next(c for c in cookies if c.startswith("karenseir_rt="))
    csrf = next(c for c in cookies if c.startswith("karenseir_csrf="))
    assert "HttpOnly" in at and "HttpOnly" in rt and "HttpOnly" not in csrf
    assert all("SameSite=Lax" in c for c in (at, rt, csrf)) and not any("Secure" in c for c in (at, rt, csrf))  # plain HTTP
    assert client.get("/me/wallets").status_code == 200
    # synthetic placeholder header from the browser client is ignored, cookie wins
    assert client.get("/me/wallets", headers={"Authorization": "Bearer cookie.e30=."}).status_code == 200


def test_state_changing_cookie_request_needs_csrf_header(client, cookie_mode):
    client.cookies.clear()
    client.post("/auth/dev-login", json={"email": EMAIL})
    key = {"Idempotency-Key": f"csrf-{uuid.uuid4().hex}"}
    assert client.post("/me/wallets", headers=key, json={"currency": "IRR"}).status_code == 403
    assert client.post("/me/wallets", headers={**key, "X-CSRF-Token": "wrong"}, json={"currency": "IRR"}).status_code == 403
    ok = client.post("/me/wallets", headers={**key, "X-CSRF-Token": client.cookies["karenseir_csrf"]}, json={"currency": "IRR"})
    assert ok.status_code == 201


def test_bearer_clients_keep_working_with_cookie_mode_on(client, cookie_mode):
    client.cookies.clear()
    r = client.post("/auth/dev-login", headers={"X-Auth-Transport": "bearer"}, json={"email": EMAIL})
    assert r.status_code == 200 and r.json()["access_token"] and not _set_cookies(r)
    bearer = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/me/wallets", headers={**bearer, "Idempotency-Key": f"b-{uuid.uuid4().hex}"}, json={"currency": "IRR"}).status_code == 201  # no CSRF for header auth
    refreshed = client.post("/auth/refresh", json={"refresh_token": r.json()["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.json()["access_token"]


def test_cookie_refresh_rotates_and_logout_clears(client, cookie_mode):
    client.cookies.clear()
    client.post("/auth/dev-login", json={"email": EMAIL})
    old_rt = client.cookies["karenseir_rt"]
    assert client.post("/auth/refresh", json={}).status_code == 403  # CSRF required
    r = client.post("/auth/refresh", headers={"X-CSRF-Token": client.cookies["karenseir_csrf"]}, json={})
    assert r.status_code == 200 and r.json()["token_type"] == "cookie" and "access_token" not in r.json()
    assert client.cookies["karenseir_rt"] != old_rt
    out = client.post("/auth/logout", headers={"X-CSRF-Token": client.cookies["karenseir_csrf"]}, json={})
    assert out.status_code == 204
    assert all("Max-Age=0" in c for c in _set_cookies(out)) and len(_set_cookies(out)) == 3
    client.cookies.clear()
    assert client.get("/me/wallets").status_code == 401


def test_secure_flag_follows_https(client, cookie_mode, monkeypatch):
    client.cookies.clear()
    r = client.post("/auth/dev-login", headers={"X-Forwarded-Proto": "https"}, json={"email": EMAIL})
    assert all("Secure" in c for c in _set_cookies(r))
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "1")
    r = client.post("/auth/dev-login", json={"email": EMAIL})
    assert all("Secure" in c for c in _set_cookies(r))
    client.cookies.clear()
