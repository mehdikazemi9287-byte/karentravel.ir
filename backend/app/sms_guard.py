"""Cross-tenant SMS budget per destination mobile (security review 1405-08-17, M-6 follow-up).

The per-account throttle (`_otp_throttled`) and the per-tenant daily budget (`SMS_DAILY_CAP_PER_TENANT`) in main.py are
both tenant-scoped: the rows they count live behind tenant RLS. Neither bounds how many SMS one *phone number* receives
from the platform as a whole. This module adds that bound: a global counter per destination for the current clock hour
and the current UTC day, shared by every tenant and every SMS path that calls `reserve_sms`.

* The table holds only a keyed hash of the destination (HMAC-SHA256 with the server secret), never the number itself,
  and no tenant id, so it is deliberately outside tenant RLS (it is not a tenant table).
* `reserve_sms` increments both buckets with one atomic upsert each (INSERT .. ON CONFLICT DO UPDATE .. RETURNING), so
  two concurrent requests can never both take the last slot. It runs in the caller's transaction: if the send then
  fails and the caller rolls back, the slot is given back as well (a failed send costs nothing).
* Callers answer exactly as they do for any other throttle (the same generic 202 "accepted"), so the cap never tells
  an outsider whether a number exists or how many messages it already received (enumeration-safe).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base

SMS_DEST_MAX_PER_HOUR = int(os.getenv("SMS_DEST_MAX_PER_HOUR", "8"))
SMS_DEST_MAX_PER_DAY = int(os.getenv("SMS_DEST_MAX_PER_DAY", "20"))
WINDOWS = (("h", 3600), ("d", 86400))


class SmsDestinationCounter(Base):
    """Global (all tenants) SMS count per destination hash and time bucket. Not tenant data: no tenant_id, no RLS."""
    __tablename__ = "sms_destination_counters"
    destination_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[str] = mapped_column(String(1), primary_key=True)
    bucket: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def _secret() -> bytes:
    from .main import JWT_SECRET  # same server secret as the other keyed hashes; never stored with the counter
    return JWT_SECRET.encode("utf-8")


def destination_hash(destination: str) -> str:
    digits = "".join(ch for ch in (destination or "") if ch.isdigit())
    return hmac.new(_secret(), f"sms-dest:{digits}".encode("utf-8"), hashlib.sha256).hexdigest()


def _limits() -> dict[str, int]:
    return {"h": SMS_DEST_MAX_PER_HOUR, "d": SMS_DEST_MAX_PER_DAY}


def _increment(db: Session, key: str, window: str, bucket: int) -> int:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    now = datetime.now(timezone.utc)
    stmt = insert(SmsDestinationCounter).values(destination_hash=key, window=window, bucket=bucket, count=1, updated_at=now)
    stmt = stmt.on_conflict_do_update(index_elements=["destination_hash", "window", "bucket"],
                                      set_={"count": SmsDestinationCounter.count + 1, "updated_at": now}).returning(SmsDestinationCounter.count)
    return int(db.execute(stmt).scalar_one())


def reserve_sms(db: Session, destination: str, *, now: float | None = None) -> bool:
    """Take one SMS slot for `destination` in the hour and day buckets. False = over the global cap (send nothing).

    A refused attempt still counts inside its bucket, which only makes the cap stricter for a flood; the caller should
    roll back anyway (it answers with the generic response and writes nothing)."""
    if not destination:
        return True  # nothing will be sent; the caller's own path handles the missing number
    limits = _limits()
    if min(limits.values()) <= 0:
        return False
    key = destination_hash(destination)
    ts = int(now if now is not None else time.time())
    allowed = True
    for window, seconds in WINDOWS:
        if _increment(db, key, window, ts // seconds) > limits[window]:
            allowed = False
    if not allowed:
        logging.getLogger("karenseir.security").warning("sms_destination_cap_reached", extra={"status": 202})
    return allowed


def prune(db: Session, *, now: float | None = None) -> int:
    """Delete buckets older than two days (housekeeping; safe to run any time)."""
    ts = int(now if now is not None else time.time())
    old_hour, old_day = ts // 3600 - 48, ts // 86400 - 2
    q = db.query(SmsDestinationCounter)
    n = q.filter(SmsDestinationCounter.window == "h", SmsDestinationCounter.bucket < old_hour).delete(synchronize_session=False)
    n += q.filter(SmsDestinationCounter.window == "d", SmsDestinationCounter.bucket < old_day).delete(synchronize_session=False)
    return n
