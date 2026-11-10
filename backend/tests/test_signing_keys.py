"""M-5: per-purpose signing keys with HKDF fallback and a legacy-acceptance window."""
import jwt
import pytest

from app import signing_keys as sk
from app.voucher_verify import make_code, parse_code

MASTER = "m" * 48


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (*sk.PURPOSES.values(), "SIGNING_LEGACY_FALLBACK"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)


def test_derived_keys_are_distinct_stable_and_not_the_master():
    keys = {p: sk.signing_key(p, MASTER) for p in sk.PURPOSES}
    assert keys["access_token"] == MASTER  # live sessions survive the upgrade
    others = [keys[p] for p in ("mfa_ticket", "payment_state", "voucher_qr")]
    assert len(set(others)) == 3 and MASTER not in others
    assert sk.signing_key("payment_state", MASTER) == keys["payment_state"]
    assert sk.signing_key("payment_state", "n" * 48) != keys["payment_state"]


def test_explicit_env_overrides_derivation(monkeypatch):
    monkeypatch.setenv("PAYMENT_STATE_SECRET", "p" * 40)
    monkeypatch.setenv("ACCESS_TOKEN_SECRET", "a" * 40)
    assert sk.signing_key("payment_state", MASTER) == "p" * 40
    assert sk.signing_key("access_token", MASTER) == "a" * 40


def test_legacy_key_accepted_only_during_transition(monkeypatch):
    legacy = jwt.encode({"aud": "x"}, MASTER, algorithm="HS256")
    assert MASTER in sk.verification_keys("payment_state", MASTER)
    monkeypatch.setenv("SIGNING_LEGACY_FALLBACK", "0")
    assert sk.verification_keys("payment_state", MASTER) == [sk.signing_key("payment_state", MASTER)]
    for key in sk.verification_keys("payment_state", MASTER):
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(legacy, key, algorithms=["HS256"], audience="x")


def test_voucher_codes_old_and_new(monkeypatch):
    rid = "0" * 8 + "-0000-4000-8000-" + "0" * 12
    new = make_code(sk.signing_key("voucher_qr", MASTER), 3, rid)
    old = make_code(MASTER, 3, rid)
    assert parse_code(sk.verification_keys("voucher_qr", MASTER), new) == (3, rid)
    assert parse_code(sk.verification_keys("voucher_qr", MASTER), old) == (3, rid)
    monkeypatch.setenv("SIGNING_LEGACY_FALLBACK", "0")
    assert parse_code(sk.verification_keys("voucher_qr", MASTER), old) is None
    # an explicit VOUCHER_QR_SECRET was the signer before too: no legacy widening
    monkeypatch.setenv("SIGNING_LEGACY_FALLBACK", "1")
    monkeypatch.setenv("VOUCHER_QR_SECRET", "v" * 40)
    assert sk.verification_keys("voucher_qr", MASTER) == ["v" * 40]


def test_hkdf_matches_rfc5869_case_1():
    ikm = bytes.fromhex("0b" * 22)
    okm = sk._hkdf_sha256(ikm, bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"), 42, salt=bytes.fromhex("000102030405060708090a0b0c"))
    assert okm.hex() == "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
