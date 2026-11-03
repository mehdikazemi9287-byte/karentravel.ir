"""Authenticator-app two-step login: RFC vectors, sealing, setup/enable, login ticket, replay, recovery codes, lockout."""
import time
import uuid

import pytest
from sqlalchemy import select

import app.providers as providers
from app.account_security import UserMfa, hotp, match_step, seal, totp, unseal
from app.main import SessionLocal, User
from app.operations import AuthenticationState

RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32("12345678901234567890")


def test_rfc_vectors_and_window():
    # RFC 4226 appendix D (6 digits) and RFC 6238 appendix B (T=59 -> 94287082, last 6 digits)
    assert [hotp(RFC_SECRET, i) for i in (0, 1, 9)] == ["755224", "287082", "520489"]
    assert totp(RFC_SECRET, 59) == "287082" and totp(RFC_SECRET, 1111111109) == "081804"
    assert match_step(RFC_SECRET, "287082", at=59 + 30) == 1 and match_step(RFC_SECRET, "287082", at=59 + 90) is None
    assert match_step(RFC_SECRET, "abc") is None


def test_seal_roundtrip_and_tamper():
    s = seal("SECRETVALUE", "master-key-for-tests-0123456789abcdef")
    assert "SECRETVALUE" not in s and unseal(s, "master-key-for-tests-0123456789abcdef") == "SECRETVALUE"
    with pytest.raises(ValueError):
        unseal(s, "other-master-key-0123456789abcdefghij")
    broken = s[:-4] + ("AAAA" if s[-4:] != "AAAA" else "BBBB")
    with pytest.raises(ValueError):
        unseal(broken, "master-key-for-tests-0123456789abcdef")


class _Capture:
    code = None

    def execute(self, operation, payload, context):
        _Capture.code = payload["code"]
        return {"ok": True, "status": "accepted", "reference": "mfa-test"}


def _user():
    email = f"mfa-{uuid.uuid4().hex[:8]}@aftab.test"
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == "employee@aftab.test"))
        db.add(User(tenant_id=tid, email=email, name="کارشناس امنیت", role="backoffice_expert"))
        db.commit()
    return email


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _otp_step(client, monkeypatch, email):
    monkeypatch.setitem(providers.ADAPTERS, "otp", _Capture())
    r = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": email})
    assert r.status_code == 202, r.text
    return client.post("/auth/otp/verify", json={"tenant_slug": "aftab-bank", "challenge_id": r.json()["challenge_id"], "code": _Capture.code, "device_id": "mfa-device-0001"})


def _mfa(client, ticket, **kw):
    return client.post("/auth/2fa/verify", json={"tenant_slug": "aftab-bank", "mfa_ticket": ticket, "device_id": "mfa-device-0001", **kw})


def test_setup_enable_login_recovery_and_lockout(client, monkeypatch):
    email = _user()
    h = _h(client, email)
    assert client.get("/me/2fa", headers=h).json() == {"enabled": False, "pending": False, "enabled_at": None, "recovery_codes_left": 0}
    # without 2FA the SMS step still returns tokens directly
    plain = _otp_step(client, monkeypatch, email)
    assert plain.status_code == 200 and "access_token" in plain.json()

    s = client.post("/me/2fa/setup", headers=h)
    assert s.status_code == 200
    body = s.json()
    secret = body["secret"].replace(" ", "")
    assert body["otpauth_uri"].startswith("otpauth://totp/KarenSeir:") and "<svg" in body["qr_svg"]
    with SessionLocal() as db:
        row = db.scalar(select(UserMfa).where(UserMfa.user_id == db.scalar(select(User.id).where(User.email == email))))
        assert row.status == "pending" and secret not in row.secret_sealed
    assert client.post("/me/2fa/enable", json={"code": "000000" if totp(secret) != "000000" else "111111"}, headers=h).status_code == 400
    en = client.post("/me/2fa/enable", json={"code": totp(secret)}, headers=h)
    assert en.status_code == 200 and len(en.json()["recovery_codes"]) == 10
    recovery = en.json()["recovery_codes"]
    assert client.post("/me/2fa/setup", headers=h).status_code == 409

    # login: SMS step now yields a ticket, not tokens
    step1 = _otp_step(client, monkeypatch, email)
    assert step1.status_code == 200 and step1.json()["mfa_required"] is True and "access_token" not in step1.json()
    ticket = step1.json()["mfa_ticket"]
    assert _mfa(client, ticket, code=totp(secret)).status_code == 401           # same step as enable -> replay rejected
    ok = _mfa(client, ticket, code=totp(secret, time.time() + 30))              # next step, inside the window
    assert ok.status_code == 200 and "access_token" in ok.json() and ok.json()["user"]["role"] == "backoffice_expert"
    assert _mfa(client, "x" * 40, code=totp(secret)).status_code == 401
    assert client.post("/auth/2fa/verify", json={"tenant_slug": "faraz-industries", "mfa_ticket": ticket, "code": "123456", "device_id": "mfa-device-0001"}).status_code == 401

    # recovery code: one-time
    t2 = _otp_step(client, monkeypatch, email).json()["mfa_ticket"]
    assert _mfa(client, t2, recovery_code=recovery[0].lower()).status_code == 200
    assert _mfa(client, t2, recovery_code=recovery[0]).status_code == 401
    assert client.get("/me/2fa", headers=h).json()["recovery_codes_left"] == 9

    # lockout after 5 wrong codes, even a right code is then refused
    t3 = _otp_step(client, monkeypatch, email).json()["mfa_ticket"]
    wrong = [_mfa(client, t3, code="000001").status_code for _ in range(5)]
    assert wrong[:4] == [401] * 4 and wrong[4] == 423
    assert _mfa(client, t3, recovery_code=recovery[1]).status_code == 423
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        st = db.scalar(select(AuthenticationState).where(AuthenticationState.user_id == uid))
        st.locked_until, st.failed_attempts = None, 0
        db.commit()

    # disable needs a valid factor
    assert client.post("/me/2fa/disable", json={"code": "000002"}, headers=h).status_code == 400
    assert client.post("/me/2fa/disable", json={"recovery_code": recovery[2]}, headers=h).json() == {"enabled": False}
    assert client.get("/me/2fa", headers=h).json()["enabled"] is False
    final = _otp_step(client, monkeypatch, email)
    assert final.status_code == 200 and "access_token" in final.json()
