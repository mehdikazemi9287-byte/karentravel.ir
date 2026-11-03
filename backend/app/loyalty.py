"""Loyalty circle (حلقه‌ی همسفران): levels, points from completed trips, referral codes.

- Off by default per tenant; while off nothing is earned and customers see "not active".
- Points are earned only when a reservation reaches `completed` (the trip actually happened),
  from the amount recorded at booking time: floor(total / irr_per_point). Idempotent per reservation.
- A customer may enter one referral code (not their own, same tenant) before their first completed trip;
  the referrer gets the configured bonus when that first trip completes. Idempotent.
- Levels and their benefit text are set by the tenant admin. Nothing here changes prices: a benefit is
  only what the admin writes, so no discount is promised that the pricing engine does not apply.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin

DEFAULT_LEVELS = [
    {"key": "bronze", "name": "برنزی", "min_points": 0, "benefits": ""},
    {"key": "silver", "name": "نقره‌ای", "min_points": 500, "benefits": ""},
    {"key": "gold", "name": "طلایی", "min_points": 2000, "benefits": ""},
    {"key": "diamond", "name": "الماس", "min_points": 5000, "benefits": ""},
]
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class LoyaltySettings(OperationalMixin, Base):
    __tablename__ = "loyalty_settings"
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    irr_per_point: Mapped[int] = mapped_column(Integer, default=100_000)
    referral_bonus_points: Mapped[int] = mapped_column(Integer, default=0)
    levels_json: Mapped[str] = mapped_column(Text, default="[]")
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_loyalty_settings_tenant"),)


class LoyaltyAccount(OperationalMixin, Base):
    __tablename__ = "loyalty_accounts"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)   # lifetime, decides the level
    points_balance: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[str] = mapped_column(String(12))
    referred_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_loyalty_account_user"),
                      UniqueConstraint("tenant_id", "referral_code", name="uq_loyalty_referral_code"))


class LoyaltyEntry(OperationalMixin, Base):
    __tablename__ = "loyalty_entries"
    account_id: Mapped[str] = mapped_column(ForeignKey("loyalty_accounts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # trip | referral | adjust
    points: Mapped[int] = mapped_column(Integer)
    ref: Mapped[str] = mapped_column(String(80))   # idempotency: trip:<reservation>, referral:<user>, adjust:<uuid>
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "ref", name="uq_loyalty_entry_ref"),)


# ---------------------------------------------------------------- helpers
def _settings(db: Session, tenant_id: int, create: bool = True) -> Optional[LoyaltySettings]:
    row = db.scalar(select(LoyaltySettings).where(LoyaltySettings.tenant_id == tenant_id))
    if row is None and create:
        row = LoyaltySettings(tenant_id=tenant_id, enabled=False, levels_json=json.dumps(DEFAULT_LEVELS, ensure_ascii=False))
        db.add(row)
        db.flush()
    return row


def levels_of(row: Optional[LoyaltySettings]) -> list[dict]:
    try:
        levels = json.loads(row.levels_json) if row and row.levels_json else []
    except ValueError:
        levels = []
    return sorted(levels or DEFAULT_LEVELS, key=lambda lv: lv["min_points"])


def level_for(levels: list[dict], earned: int) -> tuple[dict, Optional[dict]]:
    current = levels[0]
    nxt = None
    for lv in levels:
        if earned >= lv["min_points"]:
            current = lv
        elif nxt is None:
            nxt = lv
    return current, nxt


def _new_code(db: Session, tenant_id: int) -> str:
    for _ in range(10):
        code = "KS" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not db.scalar(select(LoyaltyAccount.id).where(LoyaltyAccount.tenant_id == tenant_id, LoyaltyAccount.referral_code == code)):
            return code
    raise RuntimeError("could not allocate a referral code")


def account_for(db: Session, tenant_id: int, user_id: int) -> LoyaltyAccount:
    acc = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.tenant_id == tenant_id, LoyaltyAccount.user_id == user_id))
    if acc is None:
        acc = LoyaltyAccount(tenant_id=tenant_id, user_id=user_id, referral_code=_new_code(db, tenant_id))
        db.add(acc)
        db.flush()
    return acc


def _credit(db: Session, acc: LoyaltyAccount, kind: str, points: int, ref: str, note: Optional[str] = None, actor: Optional[int] = None) -> bool:
    if db.scalar(select(LoyaltyEntry.id).where(LoyaltyEntry.tenant_id == acc.tenant_id, LoyaltyEntry.ref == ref)):
        return False
    db.add(LoyaltyEntry(tenant_id=acc.tenant_id, account_id=acc.id, kind=kind, points=points, ref=ref, note=note, actor_user_id=actor))
    acc.points_balance += points
    if points > 0 and kind in ("trip", "referral"):
        acc.points_earned += points
    elif kind == "adjust":
        acc.points_earned = max(0, acc.points_earned + points)
    return True


def sync_level_group(db: Session, tenant_id: int, user_id: int, earned: int, levels: list[dict]) -> Optional[str]:
    """Put the member in the customer group of their level so the existing sales rules (markup/discount per group)
    price their bookings. A member already in a group that no level uses (e.g. an organization group) is left alone."""
    from .commerce import CustomerGroup, CustomerGroupMember

    codes = {lv.get("group_code") for lv in levels if lv.get("group_code")}
    if not codes:
        return None
    groups = {g.code: g.id for g in db.scalars(select(CustomerGroup).where(CustomerGroup.tenant_id == tenant_id, CustomerGroup.code.in_(codes))).all()}
    target = groups.get(level_for(levels, earned)[0].get("group_code") or "")
    member = db.scalar(select(CustomerGroupMember).where(CustomerGroupMember.tenant_id == tenant_id, CustomerGroupMember.user_id == user_id))
    if member is not None and member.group_id not in set(groups.values()):
        return None
    if target is None:
        if member is not None:
            db.delete(member)
        return None
    if member is None:
        db.add(CustomerGroupMember(tenant_id=tenant_id, user_id=user_id, group_id=target))
    else:
        member.group_id = target
    return target


def award_trip(db: Session, reservation) -> None:
    """Called when a reservation becomes `completed`. Never raises."""
    try:
        with db.begin_nested():
            st = _settings(db, reservation.tenant_id, create=False)
            if st is None or not st.enabled or st.irr_per_point <= 0:
                return
            try:
                snap = json.loads(reservation.price_snapshot_json or "{}")
            except ValueError:
                snap = {}
            total = int(snap.get("total_amount") or 0)
            if snap.get("currency", "IRR") != "IRR" or total <= 0:
                return
            acc = account_for(db, reservation.tenant_id, reservation.user_id)
            points = total // st.irr_per_point
            if points > 0:
                _credit(db, acc, "trip", points, f"trip:{reservation.id}", f"سفر {reservation.booking_reference or reservation.id}")
            if acc.referred_by_user_id and not acc.referral_rewarded and st.referral_bonus_points > 0:
                ref_acc = account_for(db, reservation.tenant_id, acc.referred_by_user_id)
                if _credit(db, ref_acc, "referral", st.referral_bonus_points, f"referral:{acc.user_id}", "اولین سفر دوست معرفی‌شده"):
                    acc.referral_rewarded = True
                    sync_level_group(db, reservation.tenant_id, ref_acc.user_id, ref_acc.points_earned, levels_of(st))
            sync_level_group(db, reservation.tenant_id, acc.user_id, acc.points_earned, levels_of(st))
    except Exception:  # pragma: no cover - loyalty must never block a status change
        return


# ---------------------------------------------------------------- schemas
class LevelIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_-]{2,24}$")
    name: str = Field(min_length=1, max_length=40)
    min_points: int = Field(ge=0, le=10_000_000)
    benefits: str = Field(default="", max_length=300)
    group_code: Optional[str] = Field(default=None, max_length=40)  # commerce customer group whose sales rules (e.g. a discount) apply to this level


class SettingsIn(BaseModel):
    enabled: bool
    irr_per_point: int = Field(ge=1_000, le=1_000_000_000)
    referral_bonus_points: int = Field(ge=0, le=1_000_000)
    levels: list[LevelIn] = Field(min_length=1, max_length=8)

    @field_validator("levels")
    @classmethod
    def _levels(cls, v: list[LevelIn]) -> list[LevelIn]:
        if len({lv.key for lv in v}) != len(v) or len({lv.min_points for lv in v}) != len(v):
            raise ValueError("کلید و حداقل امتیاز هر سطح باید یکتا باشد")
        if min(lv.min_points for lv in v) != 0:
            raise ValueError("سطح اول باید از امتیاز صفر شروع شود")
        return sorted(v, key=lambda lv: lv.min_points)


class ReferralIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class AdjustIn(BaseModel):
    user_id: int
    points: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=3, max_length=300)

    @field_validator("points")
    @classmethod
    def _nz(cls, v: int) -> int:
        if v == 0:
            raise ValueError("امتیاز صفر است")
        return v


# ---------------------------------------------------------------- router
def loyalty_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["loyalty"])

    def manager(user=Depends(current_user)):
        if not (role_has_permission(user.role, "tenant:manage") or role_has_permission(user.role, "platform:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیریت لازم است")
        return user

    def _out_settings(st: LoyaltySettings) -> dict:
        return {"enabled": st.enabled, "irr_per_point": st.irr_per_point, "referral_bonus_points": st.referral_bonus_points, "levels": levels_of(st)}

    @api.get("/me/loyalty")
    def me(user=Depends(current_user), db: Session = Depends(get_db)):
        st = _settings(db, user.tenant_id, create=False)
        if st is None or not st.enabled:
            return {"enabled": False}
        acc = account_for(db, user.tenant_id, user.id)
        levels = levels_of(st)
        cur, nxt = level_for(levels, acc.points_earned)
        rows = db.scalars(select(LoyaltyEntry).where(LoyaltyEntry.tenant_id == user.tenant_id, LoyaltyEntry.account_id == acc.id)
                          .order_by(LoyaltyEntry.created_at.desc()).limit(20)).all()
        has_trip = db.scalar(select(func.count()).select_from(LoyaltyEntry).where(LoyaltyEntry.tenant_id == user.tenant_id, LoyaltyEntry.account_id == acc.id, LoyaltyEntry.kind == "trip")) or 0
        db.commit()
        return {"enabled": True, "points_earned": acc.points_earned, "points_balance": acc.points_balance, "level": cur, "next_level": nxt,
                "to_next": (nxt["min_points"] - acc.points_earned) if nxt else 0, "levels": levels, "referral_code": acc.referral_code,
                "referred": acc.referred_by_user_id is not None, "can_enter_referral": acc.referred_by_user_id is None and has_trip == 0,
                "irr_per_point": st.irr_per_point, "referral_bonus_points": st.referral_bonus_points,
                "history": [{"kind": e.kind, "points": e.points, "note": e.note, "at": e.created_at.isoformat() if e.created_at else None} for e in rows]}

    @api.post("/me/loyalty/referral")
    def enter_referral(data: ReferralIn, user=Depends(current_user), db: Session = Depends(get_db)):
        st = _settings(db, user.tenant_id, create=False)
        if st is None or not st.enabled:
            raise HTTPException(status_code=409, detail="حلقه‌ی همسفران فعال نیست")
        acc = account_for(db, user.tenant_id, user.id)
        if acc.referred_by_user_id is not None:
            raise HTTPException(status_code=409, detail="کد معرف قبلاً ثبت شده است")
        if db.scalar(select(LoyaltyEntry.id).where(LoyaltyEntry.tenant_id == user.tenant_id, LoyaltyEntry.account_id == acc.id, LoyaltyEntry.kind == "trip")):
            raise HTTPException(status_code=409, detail="کد معرف فقط پیش از اولین سفر ثبت می‌شود")
        ref = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.tenant_id == user.tenant_id, LoyaltyAccount.referral_code == data.code.strip().upper()))
        if ref is None:
            raise HTTPException(status_code=404, detail="کد معرف پیدا نشد")
        if ref.user_id == user.id:
            raise HTTPException(status_code=422, detail="کد خودتان را نمی‌توانید وارد کنید")
        acc.referred_by_user_id = ref.user_id
        db.commit()
        return {"referred": True}

    @api.get("/loyalty/settings")
    def get_settings(user=Depends(manager), db: Session = Depends(get_db)):
        st = _settings(db, user.tenant_id)
        db.commit()
        return _out_settings(st)

    @api.put("/loyalty/settings")
    def put_settings(data: SettingsIn, user=Depends(manager), db: Session = Depends(get_db)):
        st = _settings(db, user.tenant_id)
        st.enabled, st.irr_per_point, st.referral_bonus_points = data.enabled, data.irr_per_point, data.referral_bonus_points
        from .commerce import CustomerGroup
        codes = {lv.group_code for lv in data.levels if lv.group_code}
        found = set(db.scalars(select(CustomerGroup.code).where(CustomerGroup.tenant_id == user.tenant_id, CustomerGroup.code.in_(codes))).all()) if codes else set()
        if codes - found:
            raise HTTPException(status_code=422, detail="گروه مشتری یافت نشد: " + "، ".join(sorted(codes - found)))
        st.levels_json = json.dumps([lv.model_dump() for lv in data.levels], ensure_ascii=False)
        levels = levels_of(st)
        for acc in db.scalars(select(LoyaltyAccount).where(LoyaltyAccount.tenant_id == user.tenant_id)).all():
            sync_level_group(db, user.tenant_id, acc.user_id, acc.points_earned, levels)
        if audit:
            audit(db, user, "loyalty.settings.saved", "loyalty_settings", {"enabled": data.enabled, "irr_per_point": data.irr_per_point})
        db.commit()
        return _out_settings(st)

    @api.get("/loyalty/members")
    def members(limit: int = Query(default=50, ge=1, le=500), user=Depends(manager), db: Session = Depends(get_db)):
        st = _settings(db, user.tenant_id)
        levels = levels_of(st)
        rows = db.execute(select(LoyaltyAccount, User.name).join(User, User.id == LoyaltyAccount.user_id)
                          .where(LoyaltyAccount.tenant_id == user.tenant_id).order_by(LoyaltyAccount.points_earned.desc()).limit(limit)).all()
        per_level: dict[str, int] = {lv["key"]: 0 for lv in levels}
        for acc, _ in db.execute(select(LoyaltyAccount, User.id).join(User, User.id == LoyaltyAccount.user_id).where(LoyaltyAccount.tenant_id == user.tenant_id)).all():
            per_level[level_for(levels, acc.points_earned)[0]["key"]] += 1
        db.commit()
        return {"enabled": st.enabled, "levels": [{**lv, "members": per_level.get(lv["key"], 0)} for lv in levels],
                "items": [{"user_id": a.user_id, "name": n, "points_earned": a.points_earned, "points_balance": a.points_balance,
                           "level": level_for(levels, a.points_earned)[0]["name"], "referral_code": a.referral_code, "referred": a.referred_by_user_id is not None} for a, n in rows]}

    @api.post("/loyalty/adjust", status_code=201)
    def adjust(data: AdjustIn, user=Depends(manager), db: Session = Depends(get_db)):
        if db.scalar(select(User.id).where(User.id == data.user_id, User.tenant_id == user.tenant_id)) is None:
            raise HTTPException(status_code=404, detail="کاربر در این مستأجر نیست")
        acc = account_for(db, user.tenant_id, data.user_id)
        if acc.points_balance + data.points < 0:
            raise HTTPException(status_code=409, detail="موجودی امتیاز کافی نیست")
        _credit(db, acc, "adjust", data.points, f"adjust:{secrets.token_hex(8)}", data.reason.strip(), user.id)
        sync_level_group(db, user.tenant_id, acc.user_id, acc.points_earned, levels_of(_settings(db, user.tenant_id)))
        if audit:
            audit(db, user, "loyalty.adjusted", "loyalty_account", {"user_id": data.user_id, "points": data.points, "reason": data.reason})
        db.commit()
        return {"user_id": data.user_id, "points_balance": acc.points_balance, "points_earned": acc.points_earned}

    return api
