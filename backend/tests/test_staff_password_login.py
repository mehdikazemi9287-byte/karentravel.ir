"""Staff password login (/auth/password/login) and the server-console tool scripts/set_staff_password.py.

TEST FIXTURES ONLY: synthetic accounts created per test; every password is random and generated at runtime."""
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.main import PASSWORD_LOGIN_FAILED_DETAIL, SessionLocal, Tenant, User
from app.operations import AuthenticationAudit, AuthenticationState
from app.security import hash_password
from scripts import set_staff_password as tool

TENANT = "aftab-bank"


def _pw() -> str:
    return secrets.token_urlsafe(18)


def _user(role="backoffice_expert", password=None, tenant=TENANT, mobile=None, disabled=False) -> dict:
    email = f"pw-{uuid.uuid4().hex[:10]}@{tenant}.test"
    with SessionLocal() as db:
        t = db.scalar(select(Tenant).where(Tenant.slug == tenant))
        user = User(tenant_id=t.id, email=email, name="کارمند آزمون", role=role, mobile_e164=mobile,
                    password_hash=hash_password(password) if password else None,
                    disabled_at=datetime.now(timezone.utc) if disabled else None)
        db.add(user); db.commit()
        return {"id": user.id, "email": email, "tenant_id": t.id}


def _login(client, identifier, password, tenant=TENANT):
    return client.post("/auth/password/login", json={"tenant_slug": tenant, "identifier": identifier, "password": password, "device_id": "password-device-01"})


def _assert_generic(response):
    assert response.status_code == 401
    assert response.json()["detail"] == PASSWORD_LOGIN_FAILED_DETAIL


def _actions(user_id):
    with SessionLocal() as db:
        return [a.action for a in db.scalars(select(AuthenticationAudit).where(AuthenticationAudit.user_id == user_id).order_by(AuthenticationAudit.created_at)).all()]


def test_password_login_issues_the_same_session_as_otp(client):
    password = _pw()
    u = _user(password=password)
    response = _login(client, u["email"].upper(), password)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "refresh_token", "token_type", "user"}
    assert body["user"]["role"] == "backoffice_expert"
    # the refresh session is real and bound to the login device
    refreshed = client.post("/auth/refresh", json={"refresh_token": body["refresh_token"], "device_id": "password-device-01"})
    assert refreshed.status_code == 200
    assert "password.login_succeeded" in _actions(u["id"])


def test_mobile_identifier_works(client):
    password = _pw()
    mobile = "+98912" + str(secrets.randbelow(10**7)).zfill(7)
    _user(password=password, mobile=mobile)
    assert _login(client, "0" + mobile[3:], password).status_code == 200


def test_wrong_password_unknown_user_no_password_and_other_tenant_answer_identically(client):
    password = _pw()
    u = _user(password=password)
    no_pw = _user()
    responses = [
        _login(client, u["email"], _pw()),                               # wrong password
        _login(client, f"missing-{uuid.uuid4().hex}@x.test", password),  # unknown account
        _login(client, no_pw["email"], password),                        # account without a password
        _login(client, u["email"], password, tenant="faraz-industries"),  # right password, other tenant
        _login(client, u["email"], password, tenant="no-such-tenant"),    # unknown tenant
        _login(client, u["email"], secrets.token_hex(1)),               # short password: 401, not 422
    ]
    for r in responses:
        _assert_generic(r)
    assert len({json.dumps(r.json(), sort_keys=True) for r in responses}) == 1


def test_lockout_after_repeated_failures_blocks_even_the_right_password(client):
    password = _pw()
    u = _user(password=password)
    for _ in range(5):
        _assert_generic(_login(client, u["email"], _pw()))
    _assert_generic(_login(client, u["email"], password))  # locked: same generic answer
    with SessionLocal() as db:
        state = db.scalar(select(AuthenticationState).where(AuthenticationState.user_id == u["id"]))
        assert state.failed_attempts >= 5 and state.locked_until is not None
        state.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1); db.commit()
    assert _login(client, u["email"], password).status_code == 200  # lock expired: success resets the counter
    with SessionLocal() as db:
        assert db.scalar(select(AuthenticationState).where(AuthenticationState.user_id == u["id"])).failed_attempts == 0
    assert "password.login_locked" in _actions(u["id"]) and "password.login_failed" in _actions(u["id"])


def test_account_without_password_never_gets_its_otp_lock_counted(client):
    u = _user(role="customer")
    for _ in range(7):
        _assert_generic(_login(client, u["email"], _pw()))
    with SessionLocal() as db:
        assert db.scalar(select(AuthenticationState).where(AuthenticationState.user_id == u["id"])) is None


def test_disabled_account_and_non_staff_hash_are_refused(client):
    password = _pw()
    disabled = _user(password=password, disabled=True)
    _assert_generic(_login(client, disabled["email"], password))
    stale = _user(role="customer", password=password)  # a hash on a customer (should never happen) is ignored
    _assert_generic(_login(client, stale["email"], password))


def test_mfa_account_still_needs_the_second_step(client, monkeypatch):
    import app.main as main
    password = _pw()
    u = _user(password=password)
    monkeypatch.setattr(main, "_mfa_enabled", lambda db, tenant_id, user_id: user_id == u["id"])
    _assert_generic(_login(client, u["email"], _pw()))  # one failure on record
    body = _login(client, u["email"], password).json()
    assert body.get("mfa_required") is True and body.get("mfa_ticket") and "access_token" not in body
    with SessionLocal() as db:  # the right password alone does not wipe the failure counter of an MFA account
        assert db.scalar(select(AuthenticationState).where(AuthenticationState.user_id == u["id"])).failed_attempts == 1


def test_password_is_never_loaded_with_ordinary_user_queries():
    from sqlalchemy import inspect as sa_inspect
    assert "password_hash" in {c.key for c in sa_inspect(User).column_attrs if c.deferred}


# ------------------------------------------------------------------ server-console tool
def _prompt(*answers):
    it = iter(answers)
    return lambda _label: next(it)


def test_tool_sets_password_for_staff_and_writes_audit(client):
    u = _user(role="tenant_admin")
    password = _pw()
    printed = []
    code = tool.main(["--tenant", TENANT, "--email", u["email"]], prompt=_prompt(password, password), require_tty=False, out=printed.append)
    assert code == 0
    assert all(password not in line for line in printed)
    assert _login(client, u["email"], password).status_code == 200
    assert "password.set" in _actions(u["id"])


def test_tool_refuses_customer_mismatch_short_and_non_tty():
    customer = _user(role="customer")
    password = _pw()
    assert tool.main(["--tenant", TENANT, "--email", customer["email"]], prompt=_prompt(password, password), require_tty=False, out=lambda *_: None) == 3
    staff = _user(role="finance_operator")
    assert tool.main(["--tenant", TENANT, "--email", staff["email"]], prompt=_prompt(password, _pw()), require_tty=False, out=lambda *_: None) == 4
    short = secrets.token_hex(3)
    assert tool.main(["--tenant", TENANT, "--email", staff["email"]], prompt=_prompt(short, short), require_tty=False, out=lambda *_: None) == 4
    assert tool.main(["--tenant", TENANT, "--email", staff["email"]], prompt=_prompt(password, password), out=lambda *_: None) == 5  # pytest stdin is not a TTY
    with SessionLocal() as db:
        for uid in (customer["id"], staff["id"]):
            assert db.get(User, uid).password_hash is None


def test_tool_list_masks_contacts():
    _user(role="platform_admin", mobile="+98912" + str(secrets.randbelow(10**7)).zfill(7))
    printed = []
    assert tool.main(["--list"], out=printed.append) == 0
    assert printed and all("password_set=" in line for line in printed)
    assert not any("+98912" in line and "****" not in line for line in printed)


# ------------------------------------------------------------------ migration 82
def test_migration_82_is_additive_idempotent_and_refuses_downgrade(tmp_path):
    import importlib.util
    from pathlib import Path

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261128_82_staff_password_hash.py"
    spec = importlib.util.spec_from_file_location("mig82", path)
    mig = importlib.util.module_from_spec(spec); spec.loader.exec_module(mig)
    assert (mig.revision, mig.down_revision) == ("20261128_82", "20261128_81")
    engine = sa.create_engine(f"sqlite:///{tmp_path}/m.db")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(160))"))
        conn.execute(sa.text("INSERT INTO users VALUES (1, 'a@b.test')"))
    for _ in range(2):
        with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            mig.upgrade()
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT id, email, password_hash FROM users")).all() == [(1, "a@b.test", None)]
    with pytest.raises(RuntimeError):
        mig.downgrade()


def test_cookie_mode_treats_password_login_like_otp_login(client, monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_MODE", "1")
    client.cookies.clear()
    password = _pw()
    u = _user(password=password)
    r = _login(client, u["email"], password)
    assert r.status_code == 200 and r.json()["token_type"] == "cookie" and "access_token" not in r.json()
    names = {v.split("=", 1)[0] for k, v in r.headers.multi_items() if k.lower() == "set-cookie"}
    assert {"karenseir_at", "karenseir_rt", "karenseir_csrf"} <= names
    client.cookies.clear()
