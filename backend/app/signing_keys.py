"""Per-purpose signing secrets (security review M-5).

One leaked secret must not let an attacker forge every kind of signed value,
so each purpose has its own key:

  purpose          optional env (or <NAME>_FILE)   used for
  ---------------  ------------------------------  -----------------------------------
  access_token     ACCESS_TOKEN_SECRET             access JWTs (default: JWT_SECRET itself,
                                                   so live sessions survive the upgrade)
  mfa_ticket       MFA_TICKET_SECRET               short-lived 2FA login ticket
  payment_state    PAYMENT_STATE_SECRET            Zarinpal callback state token
  voucher_qr       VOUCHER_QR_SECRET               signed voucher QR codes (env existed before)

When the env var is not set the key is derived from the main JWT_SECRET with
HKDF-SHA256 (RFC 5869, info = "karenseir:<purpose>:v1"), so an existing
deployment keeps working with no new configuration and still gets separated
keys.

Transition: values signed before this change used JWT_SECRET directly. While
SIGNING_LEGACY_FALLBACK is "1" (default) verification also accepts the legacy
key for mfa_ticket / payment_state / voucher_qr, so in-flight payments and
printed vouchers keep verifying. Set SIGNING_LEGACY_FALLBACK=0 once vouchers
issued before the upgrade have expired.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from .config import read_secret

DEV_DEFAULT = "development-only-change-before-production"
PURPOSES = {
    "access_token": "ACCESS_TOKEN_SECRET",
    "mfa_ticket": "MFA_TICKET_SECRET",
    "payment_state": "PAYMENT_STATE_SECRET",
    "voucher_qr": "VOUCHER_QR_SECRET",
}


def _hkdf_sha256(master: bytes, info: bytes, length: int = 32, salt: bytes = b"karenseir-signing-keys") -> bytes:
    prk = hmac.new(salt, master, hashlib.sha256).digest()
    out, block, counter = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def master_secret() -> str:
    return read_secret("JWT_SECRET", DEV_DEFAULT)


def signing_key(purpose: str, master: str | None = None) -> str:
    """The key to SIGN values of `purpose` with."""
    env = PURPOSES[purpose]
    explicit = read_secret(env, "")
    if explicit:
        return explicit
    master = master if master is not None else master_secret()
    if purpose == "access_token":
        return master
    return _hkdf_sha256(master.encode("utf-8"), f"karenseir:{purpose}:v1".encode("utf-8")).hex()


def legacy_fallback_enabled() -> bool:
    return os.getenv("SIGNING_LEGACY_FALLBACK", "1").strip().lower() not in {"0", "false", "no", "off"}


def verification_keys(purpose: str, master: str | None = None) -> list[str]:
    """Keys accepted when VERIFYING `purpose`: the current key first, then the
    legacy shared key during the transition window."""
    master = master if master is not None else master_secret()
    keys = [signing_key(purpose, master)]
    # voucher_qr honoured VOUCHER_QR_SECRET before this change, so the shared
    # key was never its signer when that env is set.
    explicit_voucher = purpose == "voucher_qr" and bool(read_secret(PURPOSES[purpose], ""))
    if purpose != "access_token" and not explicit_voucher and legacy_fallback_enabled() and master not in keys:
        keys.append(master)
    return keys
