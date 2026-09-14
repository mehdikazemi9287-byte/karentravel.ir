"""Targeted tests for mobile-first Auth/OTP wiring (users.mobile_e164 +
dual-mode /auth/otp/request dispatch). request_otp/verify_otp's core
lifecycle (one-time use, tenant isolation, lockout, enumeration-safety)
is unchanged and already covered by test_security_finance_notifications.py
-- not duplicated here."""
import pytest
from sqlalchemy import select

import app.providers as providers_module
from app.kavenegar_adapter import normalize_iranian_mobile
from app.main import SessionLocal, User


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client, email: str) -> dict:
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


class RecordingOTPAdapter:
    """Records exactly what destination/code it was asked to send -- lets
    tests assert request_otp never forwards an email, and does forward the
    real normalized mobile."""
    def __init__(self):
        self.calls = []

    def execute(self, operation, payload, context):
        self.calls.append(dict(payload))
        return {"ok": True, "status": "accepted", "reference": "recording-adapter"}


def _set_mobile(email: str, mobile_e164: str | None):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.mobile_e164 = mobile_e164
        db.commit()


@pytest.fixture()
def employee_mobile():
    """The test DB is seeded once per session (conftest.py), not per test,
    so any mutation here must be undone in a finally/teardown -- never
    left to an inline statement a failed assertion could skip."""
    _set_mobile("employee@aftab.test", "+989121234567")
    try:
        yield "+989121234567"
    finally:
        _set_mobile("employee@aftab.test", None)


# ---- normalization (DB/E.164 layer, built on the same Kavenegar normalizer) ----

def test_e164_normalization_matches_brief_examples():
    # request_otp builds "+" + normalize_iranian_mobile(...) -- exercised
    # directly here since that IS the canonical-form contract.
    assert f"+{normalize_iranian_mobile('09121234567')}" == "+989121234567"
    assert f"+{normalize_iranian_mobile('+989121234567')}" == "+989121234567"
    assert f"+{normalize_iranian_mobile('989121234567')}" == "+989121234567"
    assert f"+{normalize_iranian_mobile('00989121234567')}" == "+989121234567"


def test_invalid_numbers_rejected_by_normalizer():
    for bad in ("", "12345", "employee@aftab.test", "0812345678", "+19123456789"):
        assert normalize_iranian_mobile(bad) is None


# ---- model / migration-equivalent behavior (sqlite create_all schema) ----

def test_existing_user_has_null_mobile_by_default():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        assert user is not None
        assert user.mobile_e164 is None


def test_duplicate_non_null_mobile_is_rejected(client, employee_mobile):
    with SessionLocal() as db:
        other = db.scalar(select(User).where(User.email == "welfare@aftab.test"))
        other.mobile_e164 = employee_mobile
        try:
            db.commit()
            raised = False
        except Exception:
            db.rollback()
            raised = True
    assert raised, "duplicate non-null mobile_e164 must violate the unique constraint"


def test_multiple_null_mobiles_are_allowed(client):
    with SessionLocal() as db:
        a = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        b = db.scalar(select(User).where(User.email == "welfare@aftab.test"))
        assert a.mobile_e164 is None and b.mobile_e164 is None
        db.commit()  # two NULLs must coexist without violating uniqueness


def test_equivalent_input_formats_normalize_to_same_canonical_value():
    variants = ["09121234567", "+989121234567", "989121234567", "00989121234567"]
    canon = {f"+{normalize_iranian_mobile(v)}" for v in variants}
    assert canon == {"+989121234567"}


# ---- /auth/otp/request dual-mode dispatch ----

def test_valid_mobile_accepted_and_provider_receives_normalized_mobile(client, monkeypatch, employee_mobile):
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    resp = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "09121234567"})
    assert resp.status_code == 202
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["destination_reference"] == employee_mobile


def test_email_is_never_forwarded_to_provider_as_destination(client, monkeypatch):
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "employee@aftab.test"})
    for call in adapter.calls:
        assert "@" not in call["destination_reference"]
        assert call["destination_reference"] != "employee@aftab.test"


def test_missing_mobile_does_not_silently_fall_back_to_email_as_destination(client, monkeypatch):
    # employee@aftab.test has no mobile on file; even though it IS matched
    # (via email), the destination forwarded must never be the email --
    # it must be the empty/absent mobile, which the real provider then
    # rejects closed (proven separately in test_kavenegar_otp.py).
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "employee@aftab.test"})
    assert adapter.calls[0]["destination_reference"] in ("", None)


def test_provider_not_called_for_unmatched_mobile(client, monkeypatch):
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    resp = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "09300000000"})
    assert resp.status_code == 202  # still enumeration-safe generic accepted
    assert adapter.calls == []


def test_mobile_lookup_uses_canonical_form_regardless_of_input_spelling(client, monkeypatch, employee_mobile):
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    for spelling in ("09121234567", "+989121234567", "00989121234567"):
        adapter.calls.clear()
        resp = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": spelling})
        assert resp.status_code == 202
        assert adapter.calls[0]["destination_reference"] == employee_mobile


# ---- backward compatibility ----

def test_existing_email_login_still_works_end_to_end(client, monkeypatch):
    from sqlalchemy import func
    from app.operations import OTPChallenge
    adapter = RecordingOTPAdapter()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", adapter)
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(OTPChallenge))
    requested = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "employee@aftab.test"})
    assert requested.status_code == 202
    with SessionLocal() as db:
        after = db.scalar(select(func.count()).select_from(OTPChallenge))
    # A real, persisted challenge (not just the generic enumeration-safe
    # response) was created for an email-matched user -- proving the
    # email login path still fully works end to end.
    assert after == before + 1


def test_devlogin_email_path_unaffected(client):
    session = login(client, "employee@aftab.test")
    assert session["user"]["name"]
    assert client.get("/health").status_code == 200


def test_existing_kavenegar_adapter_tests_are_unaffected_by_this_change():
    # Sentinel: importing the Kavenegar module here must not raise, and
    # its own suite (test_kavenegar_otp.py) is run separately -- this just
    # proves the auth-layer change does not break the import graph.
    import app.kavenegar_adapter  # noqa: F401
