"""Charter seat quotas (سهمیه‌ی صندلی همکاران) on the tenant's own flights.

A quota holds a number of seats of one dated flight for one partner agency. Held seats are taken out of the
public offer (`available_units`), so they cannot be sold to others; they are not counted as sold. Seats go back
to public sale when the quota is released — by staff (fully or partly, e.g. right before booking the agency's
passengers) or automatically once the series' stop-quota time before departure has passed. Every change is
row-locked on the offer and audited.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class SeatQuota(OperationalMixin, Base):
    __tablename__ = "inv_seat_quotas"
    instance_id: Mapped[str] = mapped_column(ForeignKey("inv_flight_instances.id"), index=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    seats: Mapped[int] = mapped_column(Integer)           # currently held
    seats_initial: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="held", index=True)  # held | released
    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)  # stop-quota time
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    released_reason: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


def held_seats(db: Session, tenant_id: int, instance_id: str) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(SeatQuota.seats), 0)).where(
        SeatQuota.tenant_id == tenant_id, SeatQuota.instance_id == instance_id, SeatQuota.status == "held")) or 0)


class QuotaIn(BaseModel):
    instance_id: str = Field(min_length=36, max_length=36)
    agency_id: str = Field(min_length=36, max_length=36)
    seats: int = Field(ge=1, le=1000)
    note: Optional[str] = Field(default=None, max_length=500)


class ReleaseIn(BaseModel):
    seats: Optional[int] = Field(default=None, ge=1, le=1000)  # None = all
    reason: str = Field(default="manual", pattern="^(manual|agency_booking)$")


def charter_quotas_router(get_db, current_user, role_has_permission, User, audit=None):
    from .inventory import FlightInstance, FlightRoute, FlightSeries  # tables owned by the inventory module

    api = APIRouter(tags=["charter-quotas"])

    def admin(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("platform:manage", "tenant:manage", "inventory:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیریت موجودی لازم است")
        return user

    def _a(db, user, action, detail):
        if audit:
            audit(db, user, action, "inv_seat_quota", detail)

    def _flight(db: Session, tenant_id: int, instance_id: str, lock: bool = False):
        row = db.execute(select(FlightInstance, FlightSeries, FlightRoute).join(FlightSeries, FlightSeries.id == FlightInstance.series_id)
                         .join(FlightRoute, FlightRoute.id == FlightSeries.route_id)
                         .where(FlightInstance.id == instance_id, FlightInstance.tenant_id == tenant_id)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="پرواز یافت نشد")
        inst = row[0]
        offer = None
        if inst.offer_id:
            q = select(m.Offer).where(m.Offer.id == inst.offer_id, m.Offer.tenant_id == tenant_id)
            offer = db.scalar(q.with_for_update() if lock else q)
        return inst, row[1], row[2], offer

    def _release(db: Session, q: SeatQuota, seats: int, reason: str) -> int:
        inst = db.get(FlightInstance, q.instance_id)
        offer = db.scalar(select(m.Offer).where(m.Offer.id == inst.offer_id, m.Offer.tenant_id == q.tenant_id).with_for_update()) if inst and inst.offer_id else None
        seats = min(seats, q.seats)
        q.seats -= seats
        if offer is not None:
            offer.available_units += seats
        if q.seats == 0:
            q.status, q.released_reason = "released", reason
        return seats

    def _sweep(db: Session, tenant_id: int) -> int:
        now = utcnow()
        moved = 0
        for q in db.scalars(select(SeatQuota).where(SeatQuota.tenant_id == tenant_id, SeatQuota.status == "held", SeatQuota.release_at <= now)).all():
            moved += _release(db, q, q.seats, "stop_quota")
        return moved

    def _out(db: Session, q: SeatQuota, names: dict) -> dict:
        return {"id": q.id, "instance_id": q.instance_id, "agency_id": q.agency_id, "agency": names.get(q.agency_id), "seats": q.seats,
                "seats_initial": q.seats_initial, "status": q.status, "release_at": _aw(q.release_at).isoformat(), "released_reason": q.released_reason, "note": q.note}

    @api.get("/charter-quotas/agencies")
    def agencies(user=Depends(admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id).order_by(m.Agency.display_name)).all()
        return {"items": [{"id": a.id, "name": a.display_name, "status": a.status} for a in rows]}

    @api.get("/charter-quotas")
    def list_quotas(instance_id: Optional[str] = None, status: Optional[str] = Query(default=None, pattern="^(held|released)$"),
                    user=Depends(admin), db: Session = Depends(get_db)):
        released = _sweep(db, user.tenant_id)
        if released:
            db.commit()
        s = select(SeatQuota).where(SeatQuota.tenant_id == user.tenant_id)
        if instance_id:
            s = s.where(SeatQuota.instance_id == instance_id)
        if status:
            s = s.where(SeatQuota.status == status)
        rows = db.scalars(s.order_by(SeatQuota.release_at).limit(500)).all()
        names = dict(db.execute(select(m.Agency.id, m.Agency.display_name).where(m.Agency.tenant_id == user.tenant_id)).all())
        return {"items": [_out(db, q, names) for q in rows], "auto_released_seats": released}

    @api.get("/charter-quotas/flights/{instance_id}")
    def flight_availability(instance_id: str, user=Depends(admin), db: Session = Depends(get_db)):
        if _sweep(db, user.tenant_id):
            db.commit()
        inst, s, r, offer = _flight(db, user.tenant_id, instance_id)
        held = held_seats(db, user.tenant_id, inst.id)
        available = offer.available_units if offer else 0
        return {"instance_id": inst.id, "flight": f"{s.airline_code}{s.flight_number}", "route": f"{r.origin}-{r.destination}", "flight_date": inst.flight_date,
                "capacity": inst.capacity, "public_available": available, "held_quota": held, "sold": max(0, inst.capacity - available - held),
                "stop_quota_at": (_aw(inst.departure_at) - timedelta(minutes=s.stop_quota_minutes)).isoformat()}

    @api.post("/charter-quotas", status_code=201)
    def hold(data: QuotaIn, user=Depends(admin), db: Session = Depends(get_db)):
        inst, s, r, offer = _flight(db, user.tenant_id, data.instance_id, lock=True)
        agency = db.scalar(select(m.Agency).where(m.Agency.id == data.agency_id, m.Agency.tenant_id == user.tenant_id))
        if agency is None:
            raise HTTPException(status_code=404, detail="آژانس همکار یافت نشد")
        if offer is None or inst.status != "open":
            raise HTTPException(status_code=409, detail="این پرواز هنوز برای فروش منتشر نشده یا بسته است")
        release_at = _aw(inst.departure_at) - timedelta(minutes=s.stop_quota_minutes)
        if release_at <= utcnow():
            raise HTTPException(status_code=409, detail="زمان سهمیه‌دهی این پرواز گذشته است")
        if offer.available_units < data.seats:
            raise HTTPException(status_code=409, detail=f"فقط {offer.available_units} صندلی آزاد برای سهمیه باقی است")
        offer.available_units -= data.seats
        q = SeatQuota(tenant_id=user.tenant_id, instance_id=inst.id, agency_id=agency.id, seats=data.seats, seats_initial=data.seats,
                      status="held", release_at=release_at, note=data.note, created_by=user.id)
        db.add(q)
        db.flush()
        _a(db, user, "charter.quota.held", {"quota_id": q.id, "instance_id": inst.id, "agency_id": agency.id, "seats": data.seats})
        db.commit()
        return _out(db, q, {agency.id: agency.display_name})

    @api.post("/charter-quotas/{quota_id}/release")
    def release(quota_id: str, data: ReleaseIn, user=Depends(admin), db: Session = Depends(get_db)):
        q = db.scalar(select(SeatQuota).where(SeatQuota.id == quota_id, SeatQuota.tenant_id == user.tenant_id).with_for_update())
        if q is None:
            raise HTTPException(status_code=404, detail="سهمیه یافت نشد")
        if q.status != "held":
            raise HTTPException(status_code=409, detail="این سهمیه قبلاً آزاد شده است")
        n = _release(db, q, data.seats or q.seats, data.reason)
        _a(db, user, "charter.quota.released", {"quota_id": q.id, "seats": n, "reason": data.reason})
        db.commit()
        names = dict(db.execute(select(m.Agency.id, m.Agency.display_name).where(m.Agency.id == q.agency_id)).all())
        return {**_out(db, q, names), "released_now": n}

    return api
