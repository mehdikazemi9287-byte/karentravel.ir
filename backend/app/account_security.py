"""Two-step login with an authenticator app (Google Authenticator and compatible: TOTP, RFC 6238).

* Opt-in per user: setup creates a pending secret (QR + manual key); it is enabled only after a valid code.
* Login: after the SMS/OTP step succeeds, a user with 2FA enabled receives a short-lived signed ticket instead of
  tokens; `/auth/2fa/verify` with a 6-digit app code or a one-time recovery code completes the login.
* Lockout shares the existing `authentication_states` counter: 5 wrong codes lock the account for 15 minutes.
* Replay: an app code that was already used (same 30-second step or older) is rejected.
* The secret is sealed at rest (HMAC-SHA256 keystream + encrypt-then-MAC, key from MFA_SECRET_KEY or JWT_SECRET).
  Recovery codes are stored only as salted hashes and shown once.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import struct
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from urllib.parse import quote

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin
from .signing_keys import signing_key, verification_keys

STEP = 30
DIGITS = 6
MAX_FAILED = 5
LOCK_MINUTES = 15
TICKET_MINUTES = 5
RECOVERY_COUNT = 10
ISSUER = "KarenSeir"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ TOTP (RFC 4226 / 6238)
def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _b32(secret: str) -> bytes:
    s = secret.upper().replace(" ", "")
    return base64.b32decode(s + "=" * (-len(s) % 8))


def hotp(secret: str, counter: int) -> str:
    digest = hmac.new(_b32(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    o = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return str(code).zfill(DIGITS)


def totp(secret: str, at: Optional[float] = None) -> str:
    return hotp(secret, int((time.time() if at is None else at) // STEP))


def match_step(secret: str, code: str, at: Optional[float] = None, window: int = 1) -> Optional[int]:
    """Returns the matched time step (for replay protection) or None."""
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    now = int((time.time() if at is None else at) // STEP)
    for step in range(now - window, now + window + 1):
        if hmac.compare_digest(hotp(secret, step), code):
            return step
    return None


def otpauth_uri(secret: str, account: str, issuer: str = ISSUER) -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP}"


# ------------------------------------------------------------------ sealing at rest
def _keys(master: str) -> tuple[bytes, bytes]:
    base = hmac.new(master.encode("utf-8"), b"karenseir-mfa-v1", hashlib.sha256).digest()
    return hmac.new(base, b"enc", hashlib.sha256).digest(), hmac.new(base, b"mac", hashlib.sha256).digest()


def _stream(key: bytes, nonce: bytes, n: int) -> bytes:
    out, counter = b"", 0
    while len(out) < n:
        out += hmac.new(key, nonce + struct.pack(">I", counter), hashlib.sha256).digest()
        counter += 1
    return out[:n]


def seal(plain: str, master: str) -> str:
    k_enc, k_mac = _keys(master)
    nonce = secrets.token_bytes(16)
    data = plain.encode("utf-8")
    ct = bytes(a ^ b for a, b in zip(data, _stream(k_enc, nonce, len(data))))
    tag = hmac.new(k_mac, nonce + ct, hashlib.sha256).digest()[:16]
    return "v1:" + base64.urlsafe_b64encode(nonce + ct + tag).decode("ascii")


def unseal(sealed: str, master: str) -> str:
    if not sealed.startswith("v1:"):
        raise ValueError("unknown seal version")
    raw = base64.urlsafe_b64decode(sealed[3:].encode("ascii"))
    nonce, ct, tag = raw[:16], raw[16:-16], raw[-16:]
    k_enc, k_mac = _keys(master)
    if not hmac.compare_digest(tag, hmac.new(k_mac, nonce + ct, hashlib.sha256).digest()[:16]):
        raise ValueError("sealed secret was tampered with")
    return bytes(a ^ b for a, b in zip(ct, _stream(k_enc, nonce, len(ct)))).decode("utf-8")


def _recovery_hash(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code.replace('-', '').upper()}".encode("utf-8")).hexdigest()


def new_recovery_codes() -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["".join(secrets.choice(alphabet) for _ in range(4)) + "-" + "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(RECOVERY_COUNT)]


def qr_svg(data: str) -> str:
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


class UserMfa(OperationalMixin, Base):
    __tablename__ = "auth_user_mfa"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | enabled
    secret_sealed: Mapped[str] = mapped_column(String(200))
    last_step: Mapped[int] = mapped_column(Integer, default=0)
    recovery_salt: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recovery_hashes_json: Mapped[str] = mapped_column(Text, default="[]")
    enabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_auth_user_mfa"),)


def mfa_enabled(db: Session, tenant_id: int, user_id: int) -> bool:
    row = db.scalar(select(UserMfa).where(UserMfa.tenant_id == tenant_id, UserMfa.user_id == user_id))
    return bool(row and row.status == "enabled")


class CodeIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class DisableIn(BaseModel):
    code: Optional[str] = Field(default=None, pattern=r"^\d{6}$")
    recovery_code: Optional[str] = Field(default=None, min_length=8, max_length=12)


class MfaVerifyIn(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=64)
    mfa_ticket: str = Field(min_length=20, max_length=2000)
    code: Optional[str] = Field(default=None, pattern=r"^\d{6}$")
    recovery_code: Optional[str] = Field(default=None, min_length=8, max_length=12)
    device_id: str = Field(min_length=8, max_length=200)


def account_security_router(get_db, current_user, User, Tenant, jwt_secret: str, issue_session: Callable, fingerprints: Callable, set_tenant_context: Callable):
    master = os.environ.get("MFA_SECRET_KEY") or jwt_secret
    api = APIRouter(tags=["account-security"])
    TICKET_AUD = "karenseir-mfa"

    def _row(db: Session, user) -> Optional[UserMfa]:
        return db.scalar(select(UserMfa).where(UserMfa.tenant_id == user.tenant_id, UserMfa.user_id == user.id))

    def _audit(db: Session, tenant_id: int, user_id: int, action: str, request: Optional[Request] = None, device_id: Optional[str] = None):
        dh, ih = fingerprints(request, device_id) if request is not None else (None, None)
        db.add(m.AuthenticationAudit(tenant_id=tenant_id, user_id=user_id, action=action, device_hash=dh, ip_hash=ih))

    def _check(row: UserMfa, code: Optional[str], recovery: Optional[str]) -> Optional[str]:
        """Returns 'app' / 'recovery' on success (and consumes it), None on failure."""
        if code:
            step = match_step(unseal(row.secret_sealed, master), code)
            if step is not None and step > (row.last_step or 0):
                row.last_step = step
                return "app"
            return None
        if recovery and row.recovery_salt:
            hashes = json.loads(row.recovery_hashes_json or "[]")
            h = _recovery_hash(recovery, row.recovery_salt)
            for i, stored in enumerate(hashes):
                if hmac.compare_digest(stored, h):
                    hashes.pop(i)
                    row.recovery_hashes_json = json.dumps(hashes)
                    return "recovery"
        return None

    def _issue_recovery(row: UserMfa) -> list[str]:
        codes = new_recovery_codes()
        row.recovery_salt = secrets.token_hex(8)
        row.recovery_hashes_json = json.dumps([_recovery_hash(c, row.recovery_salt) for c in codes])
        return codes

    # ------------------------------------------------------------ self service
    @api.get("/me/2fa")
    def status(user=Depends(current_user), db: Session = Depends(get_db)):
        row = _row(db, user)
        return {"enabled": bool(row and row.status == "enabled"), "pending": bool(row and row.status == "pending"),
                "enabled_at": row.enabled_at.isoformat() if row and row.enabled_at else None,
                "recovery_codes_left": len(json.loads(row.recovery_hashes_json or "[]")) if row and row.status == "enabled" else 0}

    @api.post("/me/2fa/setup")
    def setup(user=Depends(current_user), db: Session = Depends(get_db)):
        row = _row(db, user)
        if row and row.status == "enabled":
            raise HTTPException(status_code=409, detail="ورود دومرحله‌ای از قبل فعال است")
        secret = new_secret()
        if row is None:
            row = UserMfa(tenant_id=user.tenant_id, user_id=user.id)
            db.add(row)
        row.status, row.secret_sealed, row.last_step = "pending", seal(secret, master), 0
        account = user.mobile_e164 or user.email
        uri = otpauth_uri(secret, account)
        db.commit()
        return {"secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "otpauth_uri": uri, "qr_svg": qr_svg(uri), "account": account}

    @api.post("/me/2fa/enable")
    def enable(data: CodeIn, request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
        row = _row(db, user)
        if row is None or row.status != "pending":
            raise HTTPException(status_code=409, detail="ابتدا راه‌اندازی را شروع کنید")
        if _check(row, data.code, None) is None:
            raise HTTPException(status_code=400, detail="کد برنامه درست نیست؛ ساعت گوشی را بررسی کنید")
        row.status, row.enabled_at = "enabled", utcnow()
        codes = _issue_recovery(row)
        _audit(db, user.tenant_id, user.id, "mfa.enabled", request)
        db.commit()
        return {"enabled": True, "recovery_codes": codes}

    @api.post("/me/2fa/recovery-codes")
    def regenerate(data: CodeIn, request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
        row = _row(db, user)
        if row is None or row.status != "enabled":
            raise HTTPException(status_code=409, detail="ورود دومرحله‌ای فعال نیست")
        if _check(row, data.code, None) is None:
            raise HTTPException(status_code=400, detail="کد برنامه درست نیست")
        codes = _issue_recovery(row)
        _audit(db, user.tenant_id, user.id, "mfa.recovery_regenerated", request)
        db.commit()
        return {"recovery_codes": codes}

    @api.post("/me/2fa/disable")
    def disable(data: DisableIn, request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
        row = _row(db, user)
        if row is None:
            raise HTTPException(status_code=409, detail="ورود دومرحله‌ای فعال نیست")
        if row.status == "enabled" and _check(row, data.code, data.recovery_code) is None:
            raise HTTPException(status_code=400, detail="کد برنامه یا کد بازیابی درست نیست")
        db.delete(row)
        _audit(db, user.tenant_id, user.id, "mfa.disabled", request)
        db.commit()
        return {"enabled": False}

    # ------------------------------------------------------------ login step 2
    def ticket_for(user, tenant, challenge_id: Optional[str]) -> str:
        now = utcnow()
        return jwt.encode({"aud": TICKET_AUD, "sub": str(user.id), "tenant": tenant.id, "chl": challenge_id, "iat": now,
                           "exp": now + timedelta(minutes=TICKET_MINUTES), "jti": str(uuid.uuid4())}, signing_key("mfa_ticket", jwt_secret), algorithm="HS256")

    def decode_ticket(token: str) -> dict:
        """Own per-purpose key (M-5); the legacy shared key only while SIGNING_LEGACY_FALLBACK is on."""
        last: Exception = jwt.InvalidTokenError("no key")
        for key in verification_keys("mfa_ticket", jwt_secret):
            try:
                return jwt.decode(token, key, algorithms=["HS256"], audience=TICKET_AUD, options={"require": ["exp", "sub", "tenant"]})
            except jwt.InvalidSignatureError as exc:
                last = exc
        raise last

    @api.post("/auth/2fa/verify")
    def verify(data: MfaVerifyIn, request: Request, db: Session = Depends(get_db)):
        if not data.code and not data.recovery_code:
            raise HTTPException(status_code=422, detail="کد برنامه یا کد بازیابی لازم است")
        tenant = db.scalar(select(Tenant).where(Tenant.slug == data.tenant_slug))
        try:
            claims = decode_ticket(data.mfa_ticket)
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="مهلت ورود تمام شده است؛ دوباره کد پیامکی بگیرید")
        if tenant is None or claims["tenant"] != tenant.id:
            raise HTTPException(status_code=401, detail="مهلت ورود تمام شده است؛ دوباره کد پیامکی بگیرید")
        set_tenant_context(db, tenant.id)
        user = db.scalar(select(User).where(User.id == int(claims["sub"]), User.tenant_id == tenant.id))
        row = db.scalar(select(UserMfa).where(UserMfa.tenant_id == tenant.id, UserMfa.user_id == int(claims["sub"])).with_for_update()) if user else None
        if user is None or row is None or row.status != "enabled":
            raise HTTPException(status_code=401, detail="مهلت ورود تمام شده است؛ دوباره کد پیامکی بگیرید")
        now = utcnow()
        state = db.scalar(select(m.AuthenticationState).where(m.AuthenticationState.tenant_id == tenant.id, m.AuthenticationState.user_id == user.id).with_for_update())
        if state is None:
            state = m.AuthenticationState(tenant_id=tenant.id, user_id=user.id, failed_attempts=0)
            db.add(state)
            db.flush()
        locked = state.locked_until if state.locked_until is None or state.locked_until.tzinfo else state.locked_until.replace(tzinfo=timezone.utc)
        if locked and locked > now:
            raise HTTPException(status_code=423, detail="به‌خاطر کدهای اشتباه، حساب تا ۱۵ دقیقه قفل است")
        how = _check(row, data.code, data.recovery_code)
        if how is None:
            state.failed_attempts = (state.failed_attempts or 0) + 1
            if state.failed_attempts >= MAX_FAILED:
                state.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            _audit(db, tenant.id, user.id, "mfa.verify_failed", request, data.device_id)
            db.commit()
            if state.locked_until and state.failed_attempts >= MAX_FAILED:
                raise HTTPException(status_code=423, detail="به‌خاطر کدهای اشتباه، حساب تا ۱۵ دقیقه قفل است")
            raise HTTPException(status_code=401, detail="کد درست نیست")
        state.failed_attempts, state.locked_until = 0, None
        _audit(db, tenant.id, user.id, "mfa.verified" if how == "app" else "mfa.recovery_used", request, data.device_id)
        return issue_session(db, tenant, user, request, data.device_id)

    api.ticket_for = ticket_for  # used by the SMS/OTP step in main.py
    return api
