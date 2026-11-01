"""Own inventory (KarenSeir design): charter/block flight declaration, contract templates, sales report.

Flight series -> dated flight instances -> one bookable Offer per instance (manual_supplier),
so declared flights appear in normal search and go through the normal price-check/booking path
(markup rules from the commerce module apply there). Capacity = Offer.available_units.
Sales stop `stop_sale_minutes` before departure (Offer.valid_until).
"""
from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

TEHRAN = ZoneInfo("Asia/Tehran")
WEEKDAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]  # python weekday() order


class FlightRoute(OperationalMixin, Base):
    __tablename__ = "inv_flight_routes"
    origin: Mapped[str] = mapped_column(String(4))
    destination: Mapped[str] = mapped_column(String(4))
    origin_city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    destination_city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    scope: Mapped[str] = mapped_column(String(16), default="domestic")
    status: Mapped[str] = mapped_column(String(16), default="active")
    __table_args__ = (UniqueConstraint("tenant_id", "origin", "destination", name="uq_inv_route"),)


class FlightSeries(OperationalMixin, Base):
    __tablename__ = "inv_flight_series"
    route_id: Mapped[str] = mapped_column(ForeignKey("inv_flight_routes.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    airline_code: Mapped[str] = mapped_column(String(4))
    airline_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    flight_number: Mapped[str] = mapped_column(String(10))
    aircraft: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    flight_type: Mapped[str] = mapped_column(String(16), default="charter")
    cabin: Mapped[str] = mapped_column(String(16), default="economy")
    fare_class: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    date_from: Mapped[str] = mapped_column(String(10))
    date_to: Mapped[str] = mapped_column(String(10))
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")   # {"0": {"time": "08:30", "duration": 75}, ...} python weekday keys
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    adult_fare: Mapped[int] = mapped_column(Integer, default=0)
    child_fare: Mapped[int] = mapped_column(Integer, default=0)
    infant_fare: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    baggage_kg: Mapped[int] = mapped_column(Integer, default=20)
    stop_sale_minutes: Mapped[int] = mapped_column(Integer, default=120)
    send_list_minutes: Mapped[int] = mapped_column(Integer, default=360)
    stop_quota_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    penalty_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    refundable: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class FlightInstance(OperationalMixin, Base):
    __tablename__ = "inv_flight_instances"
    series_id: Mapped[str] = mapped_column(ForeignKey("inv_flight_series.id"), index=True)
    flight_date: Mapped[str] = mapped_column(String(10), index=True)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    offer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("offers.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)   # open | closed | cancelled
    list_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "series_id", "flight_date", name="uq_inv_instance_day"),)


class ContractTemplate(OperationalMixin, Base):
    __tablename__ = "inv_contract_templates"
    service_type: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")


TABLES = ("inv_flight_routes", "inv_flight_series", "inv_flight_instances", "inv_contract_templates")
PLACEHOLDERS = ("customer_name", "booking_reference", "service", "title", "amount", "currency", "booking_date", "travellers", "company_name", "policy")
SERVICE_FA = {"flight": "بلیت هواپیما", "hotel": "اقامت هتل", "tour": "تور", "train": "بلیت قطار", "bus": "بلیت اتوبوس", "visa": "ویزا", "insurance": "بیمه مسافرتی", "package": "پرواز + هتل", "any": "همه خدمات"}


# ---------------------------------------------------------------- schemas
class RouteIn(BaseModel):
    origin: str = Field(pattern=r"^[A-Za-z]{3}$")
    destination: str = Field(pattern=r"^[A-Za-z]{3}$")
    origin_city: Optional[str] = Field(default=None, max_length=80)
    destination_city: Optional[str] = Field(default=None, max_length=80)
    scope: str = Field(default="domestic", pattern="^(domestic|international)$")
    status: str = Field(default="active", pattern="^(active|disabled)$")


class DaySlot(BaseModel):
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    duration: int = Field(ge=10, le=1500)


class SeriesIn(BaseModel):
    route_id: str
    supplier_id: str
    airline_code: str = Field(pattern=r"^[A-Za-z0-9]{2,3}$")
    airline_name: Optional[str] = Field(default=None, max_length=80)
    flight_number: str = Field(pattern=r"^[A-Za-z0-9]{1,8}$")
    aircraft: Optional[str] = Field(default=None, max_length=40)
    flight_type: str = Field(default="charter", pattern="^(charter|system)$")
    cabin: str = Field(default="economy", pattern="^(economy|premium|business|first)$")
    fare_class: Optional[str] = Field(default=None, max_length=8)
    date_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    schedule: dict[str, DaySlot]
    capacity: int = Field(ge=0, le=1000)
    adult_fare: int = Field(gt=0)
    child_fare: int = Field(ge=0)
    infant_fare: int = Field(ge=0)
    currency: str = Field(default="IRR", pattern="^[A-Z]{3}$")
    baggage_kg: int = Field(default=20, ge=0, le=100)
    stop_sale_minutes: int = Field(default=120, ge=0, le=10080)
    send_list_minutes: int = Field(default=360, ge=0, le=10080)
    stop_quota_minutes: int = Field(default=1440, ge=0, le=43200)
    penalty_code: Optional[str] = Field(default=None, max_length=40)
    refundable: bool = True
    description: Optional[str] = Field(default=None, max_length=2000)
    status: str = Field(default="active", pattern="^(active|disabled)$")

    @field_validator("schedule")
    @classmethod
    def _days(cls, v):
        if not v or any(k not in {"0", "1", "2", "3", "4", "5", "6"} for k in v):
            raise ValueError("حداقل یک روز هفته با ساعت پرواز لازم است")
        return v


class InstanceUpdateIn(BaseModel):
    capacity: Optional[int] = Field(default=None, ge=0, le=1000)
    status: Optional[str] = Field(default=None, pattern="^(open|closed|cancelled)$")
    mark_list_sent: bool = False


class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    supplier_type: str = Field(default="airline", pattern="^(airline|charterer|hotel|tour_operator|transport|other)$")


class TemplateIn(BaseModel):
    service_type: str = Field(max_length=24)
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(min_length=10, max_length=40000)
    status: str = Field(default="active", pattern="^(active|disabled)$")


# ---------------------------------------------------------------- helpers
def _days(date_from: str, date_to: str):
    d, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
    while d <= end:
        yield d
        d += timedelta(days=1)


def _aw(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _sold(db: Session, inst: FlightInstance) -> int:
    if not inst.offer_id:
        return 0
    offer = db.get(m.Offer, inst.offer_id)
    return max(0, inst.capacity - (offer.available_units if offer else inst.capacity))


def _sync_offer(db: Session, tenant_id: int, s: FlightSeries, r: FlightRoute, inst: FlightInstance, now: datetime, sold: Optional[int] = None) -> None:
    attrs = {"origin": r.origin, "destination": r.destination, "origin_code": r.origin, "destination_code": r.destination,
             "origin_city": r.origin_city, "destination_city": r.destination_city, "city": r.destination_city or r.destination,
             "departure_time": _aw(inst.departure_at).isoformat(), "arrival_time": _aw(inst.arrival_at).isoformat(), "flight_date": inst.flight_date,
             "airline": s.airline_name or s.airline_code, "airline_code": s.airline_code, "flight_number": f"{s.airline_code}{s.flight_number}",
             "duration": int((_aw(inst.arrival_at) - _aw(inst.departure_at)).total_seconds() // 60), "stops": 0, "cabin": s.cabin, "cabin_class": s.cabin,
             "fare_class": s.fare_class, "fare_type": s.flight_type, "flight_type": s.flight_type, "scope": r.scope, "aircraft": s.aircraft,
             "baggage": f"{s.baggage_kg} کیلوگرم", "baggage_kg": s.baggage_kg, "child_fare": s.child_fare, "infant_fare": s.infant_fare,
             "supplier_net_rate": s.adult_fare, "supplier_currency": s.currency, "price_source": "CHR" if s.flight_type == "charter" else "CTR",
             "inventory": "inv_flight", "inventory_instance_id": inst.id, "authoritative_inventory": True, "instant_booking": True,
             "observed_at": now.isoformat(), "penalty_code": s.penalty_code}
    policy = {"verified": True, "cancellation": {"refundable": bool(s.refundable), "penalty_code": s.penalty_code}}
    stop = _aw(inst.departure_at) - timedelta(minutes=s.stop_sale_minutes)
    status = "active" if inst.status == "open" and s.status == "active" and stop > now else "inactive"
    title = f"پرواز {s.airline_name or s.airline_code} {s.airline_code}{s.flight_number} · {r.origin_city or r.origin} به {r.destination_city or r.destination}"
    if inst.offer_id:
        offer = db.scalar(select(m.Offer).where(m.Offer.id == inst.offer_id, m.Offer.tenant_id == tenant_id).with_for_update())
    else:
        offer = None
    if offer is None:
        offer = m.Offer(tenant_id=tenant_id, supplier_id=s.supplier_id, service_type="flight", title=title, amount=s.adult_fare, currency=s.currency,
                        available_units=inst.capacity, status=status, provider_key="karenseir_inventory", fulfillment_mode="manual_supplier",
                        attributes_json=json.dumps(attrs, ensure_ascii=False, sort_keys=True), policy_json=json.dumps(policy, ensure_ascii=False, sort_keys=True), valid_until=stop)
        db.add(offer)
        db.flush()
        inst.offer_id = offer.id
        return
    offer.title, offer.amount, offer.currency, offer.supplier_id = title, s.adult_fare, s.currency, s.supplier_id
    if sold is not None:
        offer.available_units = max(0, inst.capacity - sold)
    offer.status, offer.valid_until = status, stop
    offer.attributes_json = json.dumps(attrs, ensure_ascii=False, sort_keys=True)
    offer.policy_json = json.dumps(policy, ensure_ascii=False, sort_keys=True)


def _series_dict(s: FlightSeries) -> dict:
    d = {k: getattr(s, k) for k in ("id", "route_id", "supplier_id", "airline_code", "airline_name", "flight_number", "aircraft", "flight_type", "cabin", "fare_class",
                                     "date_from", "date_to", "capacity", "adult_fare", "child_fare", "infant_fare", "currency", "baggage_kg", "stop_sale_minutes",
                                     "send_list_minutes", "stop_quota_minutes", "penalty_code", "description", "status")}
    d["refundable"] = bool(s.refundable)
    d["schedule"] = json.loads(s.schedule_json or "{}")
    return d


def render_contract(body: str, values: dict) -> str:
    """Placeholders {{name}} are replaced with escaped values; unknown placeholders stay visible as —."""
    def rep(mt):
        key = mt.group(1)
        return html.escape(str(values.get(key, "—")))
    return re.sub(r"\{\{\s*([a-z_]+)\s*\}\}", rep, html.escape(body, quote=False))


# ---------------------------------------------------------------- router
def inventory_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["inventory"])

    def admin(user=Depends(current_user)):
        if not (role_has_permission(user.role, "platform:manage") or role_has_permission(user.role, "tenant:manage") or role_has_permission(user.role, "inventory:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیریت موجودی لازم است")
        return user

    def staff(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("platform:manage", "tenant:manage", "backoffice:read", "ledger:read", "inventory:manage")):
            raise HTTPException(status_code=403, detail="دسترسی کارمند لازم است")
        return user

    def _a(db, user, action, ref, detail=None):
        if audit:
            try:
                audit(db, user, action, ref, detail or {})
            except Exception:
                pass

    def _get(db, model, tenant_id, row_id, lock=False):
        q = select(model).where(model.id == row_id, model.tenant_id == tenant_id)
        row = db.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise HTTPException(status_code=404, detail="یافت نشد")
        return row

    # ---- routes
    @api.get("/inventory/routes")
    def routes(user=Depends(staff), db: Session = Depends(get_db)):
        rows = db.scalars(select(FlightRoute).where(FlightRoute.tenant_id == user.tenant_id).order_by(FlightRoute.origin, FlightRoute.destination)).all()
        return {"items": [{k: getattr(r, k) for k in ("id", "origin", "destination", "origin_city", "destination_city", "scope", "status")} for r in rows]}

    def _save_route(db, user, row, data):
        o, d = data.origin.upper(), data.destination.upper()
        if o == d:
            raise HTTPException(status_code=422, detail="مبدأ و مقصد یکسان است")
        dup = db.scalar(select(FlightRoute.id).where(FlightRoute.tenant_id == user.tenant_id, FlightRoute.origin == o, FlightRoute.destination == d, FlightRoute.id != (row.id or "")))
        if dup:
            raise HTTPException(status_code=409, detail="این مسیر قبلاً تعریف شده است")
        row.origin, row.destination, row.origin_city, row.destination_city, row.scope, row.status = o, d, data.origin_city, data.destination_city, data.scope, data.status
        db.flush()
        db.commit()
        return {k: getattr(row, k) for k in ("id", "origin", "destination", "origin_city", "destination_city", "scope", "status")}

    @api.post("/inventory/routes", status_code=201)
    def create_route(data: RouteIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = FlightRoute(tenant_id=user.tenant_id)
        db.add(row)
        return _save_route(db, user, row, data)

    @api.put("/inventory/routes/{route_id}")
    def update_route(route_id: str, data: RouteIn, user=Depends(admin), db: Session = Depends(get_db)):
        return _save_route(db, user, _get(db, FlightRoute, user.tenant_id, route_id), data)

    @api.get("/inventory/suppliers")
    def suppliers(user=Depends(staff), db: Session = Depends(get_db)):
        rows = db.scalars(select(m.Supplier).where(m.Supplier.tenant_id == user.tenant_id).order_by(m.Supplier.display_name)).all()
        return {"items": [{"id": s.id, "name": s.display_name, "type": s.supplier_type, "status": s.status} for s in rows]}

    @api.post("/inventory/suppliers", status_code=201)
    def create_supplier(data: SupplierIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = m.Supplier(tenant_id=user.tenant_id, supplier_type=data.supplier_type, display_name=data.name.strip(), status="active", lifecycle_status="ACTIVE")
        db.add(row)
        db.flush()
        _a(db, user, "inventory.supplier.created", row.id)
        db.commit()
        return {"id": row.id, "name": row.display_name, "type": row.supplier_type, "status": row.status}

    # ---- series
    @api.get("/inventory/flight-series")
    def list_series(user=Depends(staff), db: Session = Depends(get_db)):
        return {"items": [_series_dict(s) for s in db.scalars(select(FlightSeries).where(FlightSeries.tenant_id == user.tenant_id).order_by(FlightSeries.date_from.desc()))]}

    def _save_series(db, user, row, data):
        _get(db, FlightRoute, user.tenant_id, data.route_id)
        sup = db.scalar(select(m.Supplier).where(m.Supplier.id == data.supplier_id, m.Supplier.tenant_id == user.tenant_id))
        if sup is None:
            raise HTTPException(status_code=422, detail="تأمین‌کننده معتبر نیست")
        if data.date_to < data.date_from:
            raise HTTPException(status_code=422, detail="تاریخ پایان قبل از تاریخ شروع است")
        if (date.fromisoformat(data.date_to) - date.fromisoformat(data.date_from)).days > 400:
            raise HTTPException(status_code=422, detail="بازه‌ی تعریف پرواز حداکثر ۴۰۰ روز است")
        for f in ("route_id", "supplier_id", "airline_name", "aircraft", "flight_type", "cabin", "fare_class", "date_from", "date_to", "capacity", "adult_fare", "child_fare",
                  "infant_fare", "currency", "baggage_kg", "stop_sale_minutes", "send_list_minutes", "stop_quota_minutes", "penalty_code", "description", "status"):
            setattr(row, f, getattr(data, f))
        row.airline_code, row.flight_number = data.airline_code.upper(), data.flight_number.upper()
        row.refundable = 1 if data.refundable else 0
        row.schedule_json = json.dumps({k: v.model_dump() for k, v in sorted(data.schedule.items())})
        db.flush()
        _a(db, user, "inventory.series.saved", row.id)
        db.commit()
        return _series_dict(row)

    @api.post("/inventory/flight-series", status_code=201)
    def create_series(data: SeriesIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = FlightSeries(tenant_id=user.tenant_id)
        db.add(row)
        return _save_series(db, user, row, data)

    @api.put("/inventory/flight-series/{series_id}")
    def update_series(series_id: str, data: SeriesIn, user=Depends(admin), db: Session = Depends(get_db)):
        return _save_series(db, user, _get(db, FlightSeries, user.tenant_id, series_id), data)

    @api.post("/inventory/flight-series/{series_id}/generate")
    def generate(series_id: str, user=Depends(admin), db: Session = Depends(get_db)):
        """Create the dated flights of a series (idempotent) and publish each as a bookable offer.
        Existing flights keep their sold seats; their schedule/price follow the series."""
        s = _get(db, FlightSeries, user.tenant_id, series_id, lock=True)
        r = _get(db, FlightRoute, user.tenant_id, s.route_id)
        sched = json.loads(s.schedule_json or "{}")
        now = datetime.now(timezone.utc)
        created = updated = skipped = 0
        for day in _days(s.date_from, s.date_to):
            slot = sched.get(str(day.weekday()))
            if not slot:
                continue
            hh, mm = map(int, slot["time"].split(":"))
            dep = datetime(day.year, day.month, day.day, hh, mm, tzinfo=TEHRAN).astimezone(timezone.utc)
            if dep <= now:
                skipped += 1
                continue
            arr = dep + timedelta(minutes=int(slot["duration"]))
            inst = db.scalar(select(FlightInstance).where(FlightInstance.tenant_id == user.tenant_id, FlightInstance.series_id == s.id, FlightInstance.flight_date == day.isoformat()).with_for_update())
            if inst is None:
                inst = FlightInstance(tenant_id=user.tenant_id, series_id=s.id, flight_date=day.isoformat(), departure_at=dep, arrival_at=arr, capacity=s.capacity, status="open")
                db.add(inst)
                db.flush()
                _sync_offer(db, user.tenant_id, s, r, inst, now)
                created += 1
            else:
                inst.departure_at, inst.arrival_at = dep, arr
                _sync_offer(db, user.tenant_id, s, r, inst, now)
                updated += 1
        _a(db, user, "inventory.series.generated", s.id, {"created": created, "updated": updated})
        db.commit()
        return {"created": created, "updated": updated, "skipped_past": skipped}

    # ---- flights (dated instances)
    def _inst_dict(db, i: FlightInstance, s: FlightSeries, r: FlightRoute) -> dict:
        sold = _sold(db, i)
        now = datetime.now(timezone.utc)
        dep = i.departure_at if i.departure_at.tzinfo else i.departure_at.replace(tzinfo=timezone.utc)
        mins = int((dep - now).total_seconds() // 60)
        return {"id": i.id, "series_id": s.id, "flight_date": i.flight_date, "departure_at": dep.isoformat(), "arrival_at": i.arrival_at.isoformat(),
                "route": f"{r.origin}-{r.destination}", "route_name": f"{r.origin_city or r.origin} ← {r.destination_city or r.destination}",
                "flight": f"{s.airline_code}{s.flight_number}", "airline": s.airline_name or s.airline_code, "capacity": i.capacity, "sold": sold,
                "remaining": max(0, i.capacity - sold), "status": i.status, "offer_id": i.offer_id, "adult_fare": s.adult_fare, "currency": s.currency,
                "minutes_to_departure": mins, "sale_open": i.status == "open" and mins > s.stop_sale_minutes,
                "quota_open": mins > s.stop_quota_minutes, "list_due": mins <= s.send_list_minutes and i.list_sent_at is None and i.status != "cancelled",
                "list_sent_at": i.list_sent_at.isoformat() if i.list_sent_at else None}

    @api.get("/inventory/flights")
    def flights(date_from: Optional[str] = None, date_to: Optional[str] = None, route_id: Optional[str] = None, series_id: Optional[str] = None,
                limit: int = Query(default=200, ge=1, le=1000), user=Depends(staff), db: Session = Depends(get_db)):
        q = (select(FlightInstance, FlightSeries, FlightRoute).join(FlightSeries, FlightSeries.id == FlightInstance.series_id)
             .join(FlightRoute, FlightRoute.id == FlightSeries.route_id).where(FlightInstance.tenant_id == user.tenant_id))
        if date_from: q = q.where(FlightInstance.flight_date >= date_from)
        if date_to: q = q.where(FlightInstance.flight_date <= date_to)
        if route_id: q = q.where(FlightSeries.route_id == route_id)
        if series_id: q = q.where(FlightInstance.series_id == series_id)
        rows = db.execute(q.order_by(FlightInstance.departure_at).limit(limit)).all()
        items = [_inst_dict(db, i, s, r) for i, s, r in rows]
        return {"items": items, "totals": {"capacity": sum(x["capacity"] for x in items), "sold": sum(x["sold"] for x in items)}}

    @api.put("/inventory/flights/{instance_id}")
    def update_flight(instance_id: str, data: InstanceUpdateIn, user=Depends(admin), db: Session = Depends(get_db)):
        i = _get(db, FlightInstance, user.tenant_id, instance_id, lock=True)
        s = _get(db, FlightSeries, user.tenant_id, i.series_id)
        r = _get(db, FlightRoute, user.tenant_id, s.route_id)
        sold = _sold(db, i)
        if data.capacity is not None:
            if data.capacity < sold:
                raise HTTPException(status_code=409, detail=f"ظرفیت نمی‌تواند کمتر از {sold} صندلی فروخته‌شده باشد")
            i.capacity = data.capacity
        if data.status:
            if data.status == "cancelled" and sold:
                raise HTTPException(status_code=409, detail="این پرواز مسافر دارد؛ ابتدا رزروها را تعیین تکلیف کنید")
            i.status = data.status
        if data.mark_list_sent:
            i.list_sent_at = datetime.now(timezone.utc)
        _sync_offer(db, user.tenant_id, s, r, i, datetime.now(timezone.utc), sold=sold)
        _a(db, user, "inventory.flight.updated", i.id, data.model_dump())
        db.commit()
        return _inst_dict(db, i, s, r)

    @api.get("/inventory/flights/{instance_id}/manifest")
    def manifest(instance_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        i = _get(db, FlightInstance, user.tenant_id, instance_id)
        s = _get(db, FlightSeries, user.tenant_id, i.series_id)
        r = _get(db, FlightRoute, user.tenant_id, s.route_id)
        out = []
        if i.offer_id:
            rows = db.execute(select(m.Reservation, User.name, User.email).join(m.PriceCheck, m.PriceCheck.id == m.Reservation.price_check_id)
                              .join(User, User.id == m.Reservation.user_id)
                              .where(m.Reservation.tenant_id == user.tenant_id, m.PriceCheck.offer_id == i.offer_id)).all()
            for res, buyer, email in rows:
                names = db.scalars(select(m.Traveller.full_name).join(m.ReservationTraveller, m.ReservationTraveller.traveller_id == m.Traveller.id)
                                   .where(m.ReservationTraveller.reservation_id == res.id)).all()
                units = json.loads(res.price_snapshot_json or "{}").get("units", 1)
                out.append({"reservation_id": res.id, "booking_reference": res.booking_reference, "status": res.status, "buyer": buyer, "buyer_email": email,
                            "seats": units, "travellers": names})
        return {"flight": _inst_dict(db, i, s, r), "passengers": out, "seats_booked": sum(p["seats"] for p in out if p["status"] not in ("cancelled", "expired"))}

    # ---- contract templates
    def _tpl(t):
        return {"id": t.id, "service_type": t.service_type, "title": t.title, "body": t.body, "version": t.version, "status": t.status}

    @api.get("/inventory/contract-templates")
    def templates(user=Depends(admin), db: Session = Depends(get_db)):
        return {"items": [_tpl(t) for t in db.scalars(select(ContractTemplate).where(ContractTemplate.tenant_id == user.tenant_id).order_by(ContractTemplate.service_type))],
                "placeholders": list(PLACEHOLDERS)}

    @api.post("/inventory/contract-templates", status_code=201)
    def create_template(data: TemplateIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = ContractTemplate(tenant_id=user.tenant_id, **data.model_dump())
        db.add(row)
        db.commit()
        return _tpl(row)

    @api.put("/inventory/contract-templates/{template_id}")
    def update_template(template_id: str, data: TemplateIn, user=Depends(admin), db: Session = Depends(get_db)):
        t = _get(db, ContractTemplate, user.tenant_id, template_id)
        changed = t.body != data.body
        for k, v in data.model_dump().items():
            setattr(t, k, v)
        if changed:
            t.version += 1
        db.commit()
        return _tpl(t)

    @api.get("/reservations/{reservation_id}/contract")
    def contract(reservation_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
        res = db.scalar(select(m.Reservation).where(m.Reservation.id == reservation_id, m.Reservation.tenant_id == user.tenant_id))
        is_staff = any(role_has_permission(user.role, p) for p in ("platform:manage", "tenant:manage", "backoffice:read", "ledger:read"))
        if res is None or (res.user_id != user.id and not is_staff):
            raise HTTPException(status_code=404, detail="رزرو یافت نشد")
        tpl = db.scalar(select(ContractTemplate).where(ContractTemplate.tenant_id == user.tenant_id, ContractTemplate.status == "active",
                                                       ContractTemplate.service_type.in_((res.service_type, "any"))).order_by((ContractTemplate.service_type == "any").asc()))
        if tpl is None:
            raise HTTPException(status_code=404, detail="متن قرارداد برای این خدمت تعریف نشده است")
        buyer = db.get(User, res.user_id)
        price = json.loads(res.price_snapshot_json or "{}")
        names = db.scalars(select(m.Traveller.full_name).join(m.ReservationTraveller, m.ReservationTraveller.traveller_id == m.Traveller.id).where(m.ReservationTraveller.reservation_id == res.id)).all()
        item = db.scalar(select(m.BookingItem).where(m.BookingItem.reservation_id == res.id, m.BookingItem.tenant_id == user.tenant_id))
        title = json.loads(item.snapshot_json).get("title") if item else SERVICE_FA.get(res.service_type, res.service_type)
        policy = json.loads(res.policy_at_booking_json or "{}")
        values = {"customer_name": buyer.name if buyer else "—", "booking_reference": res.booking_reference or res.id, "service": SERVICE_FA.get(res.service_type, res.service_type),
                  "title": title, "amount": f"{int(price.get('total_amount') or 0):,}", "currency": "ریال" if price.get("currency", "IRR") == "IRR" else price.get("currency"),
                  "booking_date": (res.created_at or datetime.now(timezone.utc)).astimezone(TEHRAN).strftime("%Y-%m-%d"), "travellers": "، ".join(names) or "—",
                  "company_name": "کارن‌سیر", "policy": json.dumps(policy.get("cancellation", {}), ensure_ascii=False) if policy.get("cancellation") else "طبق قوانین خدمت"}
        return {"template_id": tpl.id, "version": tpl.version, "title": tpl.title, "html": render_contract(tpl.body, values).replace("\n", "<br>")}

    # ---- sales report
    @api.get("/commerce/reports/sales")
    def sales(date_from: Optional[str] = None, date_to: Optional[str] = None, service_type: Optional[str] = None, status: Optional[str] = None,
              limit: int = Query(default=200, ge=1, le=2000), user=Depends(staff), db: Session = Depends(get_db)):
        q = select(m.Reservation, User.name).join(User, User.id == m.Reservation.user_id).where(m.Reservation.tenant_id == user.tenant_id)
        if date_from: q = q.where(m.Reservation.created_at >= datetime.fromisoformat(date_from).replace(tzinfo=TEHRAN))
        if date_to: q = q.where(m.Reservation.created_at < (datetime.fromisoformat(date_to) + timedelta(days=1)).replace(tzinfo=TEHRAN))
        if service_type: q = q.where(m.Reservation.service_type == service_type)
        if status: q = q.where(m.Reservation.status == status)
        rows = db.execute(q.order_by(m.Reservation.created_at.desc()).limit(limit)).all()
        items, by_service, total = [], {}, 0
        for res, buyer in rows:
            p = json.loads(res.price_snapshot_json or "{}")
            amount = int(p.get("total_amount") or 0)
            items.append({"id": res.id, "booking_reference": res.booking_reference, "service_type": res.service_type, "status": res.status, "buyer": buyer,
                          "amount": amount, "currency": p.get("currency", "IRR"), "units": p.get("units"), "created_at": res.created_at.isoformat() if res.created_at else None})
            if res.status not in ("cancelled", "expired", "draft"):
                b = by_service.setdefault(res.service_type, {"count": 0, "amount": 0})
                b["count"] += 1
                b["amount"] += amount
                total += amount
        return {"items": items, "by_service": by_service, "total_amount": total}

    return api
