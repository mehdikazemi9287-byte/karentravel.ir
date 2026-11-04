"""Train ticket requests (درخواست بلیت قطار) — for a rail supplier that gives a sales panel but no web service.

The customer sends route, date, travellers and preferences (coupe, passenger kind, car transport). An agent checks
capacity in the supplier's panel during office hours and sends one or more real offers (train, time, wagon, price).
The customer accepts one: a normal reservation is created and paid through the existing checkout, so card, wallet,
organisation credit and approval flows all work unchanged. After payment the agent issues the ticket in the supplier
panel and records the ticket numbers here; the reservation becomes `issued`. A request can also be handed to the sales
desk when the customer wants a whole tour. Nothing is issued or priced automatically.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

TEHRAN = timezone(timedelta(hours=3, minutes=30))
STATUS_FA = {"submitted": "در انتظار بررسی", "offered": "پیشنهاد ارسال شد", "accepted": "در انتظار پرداخت", "issued": "بلیت صادر شد",
             "unavailable": "ظرفیت نبود", "cancelled": "لغو شد", "referred": "ارجاع به کارشناس تور"}
WAGON_FA = {"any": "فرقی ندارد", "coupe4": "کوپه‌ی ۴ تخته", "coupe6": "کوپه‌ی ۶ تخته", "seat": "سالنی (صندلی)"}
KIND_FA = {"normal": "مسافران عادی", "brothers": "ویژه‌ی برادران", "sisters": "ویژه‌ی خواهران"}
DAYS_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
DEFAULT_HOURS = {"days": [0, 1, 2, 3, 4], "start": "08:00", "end": "17:00", "thursday_end": "13:00"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(v: Optional[datetime]) -> Optional[datetime]:
    return v if v is None or v.tzinfo else v.replace(tzinfo=timezone.utc)


class TrainRequest(OperationalMixin, Base):
    __tablename__ = "train_requests"
    code: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    origin: Mapped[str] = mapped_column(String(80))
    destination: Mapped[str] = mapped_column(String(80))
    depart_on: Mapped[str] = mapped_column(String(10), index=True)
    return_on: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)
    infants: Mapped[int] = mapped_column(Integer, default=0)
    wagon: Mapped[str] = mapped_column(String(12), default="any")
    passenger_kind: Mapped[str] = mapped_column(String(12), default="normal")
    exclusive_coupe: Mapped[bool] = mapped_column(Boolean, default=False)
    car_transport: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="submitted", index=True)
    assigned_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    offers_json: Mapped[str] = mapped_column(Text, default="[]")
    offer_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_offer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    ticket_numbers: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    staff_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sales_case_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_train_request_code"),)


class TrainDeskSettings(OperationalMixin, Base):
    __tablename__ = "train_desk_settings"
    hours_json: Mapped[str] = mapped_column(Text, default=json.dumps(DEFAULT_HOURS))
    offer_valid_minutes: Mapped[int] = mapped_column(Integer, default=60)
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_train_desk_settings_tenant"),)


_DATE = r"^\d{4}-\d{2}-\d{2}$"


class RequestIn(BaseModel):
    origin: str = Field(min_length=2, max_length=80)
    destination: str = Field(min_length=2, max_length=80)
    depart_on: str = Field(pattern=_DATE)
    return_on: Optional[str] = Field(default=None, pattern=_DATE)
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=9)
    infants: int = Field(default=0, ge=0, le=9)
    wagon: str = Field(default="any", pattern="^(" + "|".join(WAGON_FA) + ")$")
    passenger_kind: str = Field(default="normal", pattern="^(" + "|".join(KIND_FA) + ")$")
    exclusive_coupe: bool = False
    car_transport: bool = False
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check(self):
        today = datetime.now(TEHRAN).date().isoformat()
        if self.depart_on < today:
            raise ValueError("تاریخ رفت گذشته است")
        if self.return_on and self.return_on < self.depart_on:
            raise ValueError("تاریخ برگشت نمی‌تواند قبل از رفت باشد")
        if self.origin.strip() == self.destination.strip():
            raise ValueError("مبدأ و مقصد باید متفاوت باشند")
        if self.adults + self.children + self.infants > 9:
            raise ValueError("در هر درخواست حداکثر ۹ مسافر ثبت می‌شود")
        return self


class OfferIn(BaseModel):
    train_name: str = Field(min_length=2, max_length=80)
    train_number: Optional[str] = Field(default=None, max_length=20)
    company: Optional[str] = Field(default=None, max_length=80)
    leg: str = Field(default="depart", pattern="^(depart|return)$")
    departs_at: datetime
    arrives_at: Optional[datetime] = None
    wagon: str = Field(min_length=2, max_length=60)
    price_adult: int = Field(gt=0, le=2_000_000_000)
    price_child: int = Field(default=0, ge=0, le=2_000_000_000)
    price_infant: int = Field(default=0, ge=0, le=2_000_000_000)


class OffersIn(BaseModel):
    offers: list[OfferIn] = Field(min_length=1, max_length=8)
    valid_minutes: Optional[int] = Field(default=None, ge=10, le=1440)
    staff_note: Optional[str] = Field(default=None, max_length=500)


class AcceptIn(BaseModel):
    offer_ids: list[str] = Field(min_length=1, max_length=2)


class NoteIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


class IssueIn(BaseModel):
    ticket_numbers: str = Field(min_length=3, max_length=400)


class HoursIn(BaseModel):
    days: list[int] = Field(min_length=1, max_length=7)
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    thursday_end: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    offer_valid_minutes: int = Field(default=60, ge=10, le=1440)

    @field_validator("days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("روز هفته نامعتبر است")
        return sorted(set(v))


def office_state(hours: dict, now: Optional[datetime] = None) -> dict:
    """Whether the desk is open now (Tehran time, Saturday = 0) and when it next opens."""
    local = (now or utcnow()).astimezone(TEHRAN)

    def window(d: datetime):
        wd = (d.weekday() + 2) % 7
        if wd not in hours.get("days", []):
            return None
        end = hours.get("thursday_end") if wd == 5 and hours.get("thursday_end") else hours["end"]
        s = d.replace(hour=int(hours["start"][:2]), minute=int(hours["start"][3:]), second=0, microsecond=0)
        e = d.replace(hour=int(end[:2]), minute=int(end[3:]), second=0, microsecond=0)
        return (s, e) if e > s else None

    w = window(local)
    if w and w[0] <= local < w[1]:
        return {"open": True, "next_open": None}
    for i in range(0, 8):
        d = local + timedelta(days=i)
        w = window(d)
        if w and w[0] > local:
            return {"open": False, "next_open": w[0].isoformat(), "next_open_fa": f"{DAYS_FA[(w[0].weekday() + 2) % 7]} ساعت {hours['start']}"}
    return {"open": False, "next_open": None}


def train_requests_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["train-requests"])

    def agent(user=Depends(current_user)):
        if user.role in ("customer", "employee", "supplier", "agency_partner") or not any(role_has_permission(user.role, p) for p in ("support:manage", "reservation:manage", "tenant:manage")):
            raise HTTPException(status_code=403, detail="این بخش برای کارشناسان فروش است")
        return user

    def admin(user=Depends(current_user)):
        if not role_has_permission(user.role, "tenant:manage"):
            raise HTTPException(status_code=403, detail="تنظیم ساعت کاری با مدیر مجموعه است")
        return user

    def _a(db, user, action, ref, detail=None):
        if audit:
            audit(db, user, action, "train_request", {"ref": ref, **(detail or {})})

    def _settings(db, tenant_id: int) -> TrainDeskSettings:
        s = db.scalar(select(TrainDeskSettings).where(TrainDeskSettings.tenant_id == tenant_id))
        if s is None:
            s = TrainDeskSettings(tenant_id=tenant_id, hours_json=json.dumps(DEFAULT_HOURS), offer_valid_minutes=60)
            db.add(s)
            db.flush()
        return s

    def _notify(db, r: TrainRequest, title: str, message: str, link: str = "/account/train-requests"):
        """In-app notification for the customer (shown in حساب من › اعلان‌ها); SMS waits for an SMS provider."""
        db.add(m.NotificationRecord(tenant_id=r.tenant_id, user_id=r.user_id, topic="train_request", title=title, message=message, deep_link=link))

    def _offers(r: TrainRequest) -> list[dict]:
        return json.loads(r.offers_json or "[]")

    def _out(r: TrainRequest, staff: bool = False, names: Optional[dict] = None, customer: Optional[dict] = None) -> dict:
        now = utcnow()
        expired = r.status == "offered" and r.offer_expires_at is not None and _aware(r.offer_expires_at) <= now
        o = {"id": r.id, "code": r.code, "origin": r.origin, "destination": r.destination, "depart_on": r.depart_on, "return_on": r.return_on,
             "adults": r.adults, "children": r.children, "infants": r.infants, "wagon": r.wagon, "wagon_fa": WAGON_FA.get(r.wagon),
             "passenger_kind": r.passenger_kind, "passenger_kind_fa": KIND_FA.get(r.passenger_kind), "exclusive_coupe": r.exclusive_coupe,
             "car_transport": r.car_transport, "note": r.note, "status": r.status, "status_fa": STATUS_FA.get(r.status), "offers": _offers(r),
             "offer_expires_at": _aware(r.offer_expires_at).isoformat() if r.offer_expires_at else None, "offer_expired": expired,
             "accepted_offer_id": r.accepted_offer_id, "reservation_id": r.reservation_id,
             "checkout_url": f"/checkout/{r.reservation_id}" if r.reservation_id and r.status == "accepted" else None,
             "ticket_numbers": r.ticket_numbers, "staff_note": r.staff_note, "created_at": _aware(r.created_at).isoformat()}
        if staff:
            o |= {"assigned_to": (names or {}).get(r.assigned_user_id), "assigned_user_id": r.assigned_user_id, "customer": customer, "sales_case_id": r.sales_case_id}
        return o

    def _get(db, tenant_id: int, rid: str, lock: bool = False, user_id: Optional[int] = None) -> TrainRequest:
        s = select(TrainRequest).where(TrainRequest.id == rid, TrainRequest.tenant_id == tenant_id)
        if user_id is not None:
            s = s.where(TrainRequest.user_id == user_id)
        r = db.scalar(s.with_for_update() if lock else s)
        if r is None:
            raise HTTPException(status_code=404, detail="درخواست یافت نشد")
        return r

    # ---- customer ----
    @api.get("/train-requests/desk")
    def desk(user=Depends(current_user), db: Session = Depends(get_db)):
        s = _settings(db, user.tenant_id)
        hours = json.loads(s.hours_json)
        db.commit()
        return {"hours": hours, "days_fa": [DAYS_FA[d] for d in hours["days"]], **office_state(hours), "wagons": WAGON_FA, "kinds": KIND_FA}

    @api.post("/train-requests", status_code=201)
    def create(data: RequestIn, user=Depends(current_user), db: Session = Depends(get_db)):
        open_count = db.scalar(select(func.count(TrainRequest.id)).where(TrainRequest.tenant_id == user.tenant_id, TrainRequest.user_id == user.id, TrainRequest.status.in_(("submitted", "offered"))))
        if (open_count or 0) >= 5:
            raise HTTPException(status_code=429, detail="پنج درخواست باز دارید؛ برای درخواست تازه، یکی را لغو کنید یا منتظر پاسخ بمانید")
        n = (db.scalar(select(func.count(TrainRequest.id)).where(TrainRequest.tenant_id == user.tenant_id)) or 0) + 1
        r = TrainRequest(tenant_id=user.tenant_id, user_id=user.id, code=f"TR-{n:05d}-{uuid.uuid4().hex[:3].upper()}", origin=data.origin.strip(), destination=data.destination.strip(),
                         depart_on=data.depart_on, return_on=data.return_on, adults=data.adults, children=data.children, infants=data.infants, wagon=data.wagon,
                         passenger_kind=data.passenger_kind, exclusive_coupe=data.exclusive_coupe, car_transport=data.car_transport, note=data.note, status="submitted")
        db.add(r)
        hours = json.loads(_settings(db, user.tenant_id).hours_json)
        db.commit()
        return _out(r) | {"desk": office_state(hours)}

    @api.get("/me/train-requests")
    def mine(user=Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(TrainRequest).where(TrainRequest.tenant_id == user.tenant_id, TrainRequest.user_id == user.id).order_by(TrainRequest.created_at.desc()).limit(50)).all()
        return {"items": [_out(r) for r in rows]}

    @api.post("/me/train-requests/{rid}/cancel")
    def cancel(rid: str, user=Depends(current_user), db: Session = Depends(get_db)):
        r = _get(db, user.tenant_id, rid, lock=True, user_id=user.id)
        if r.status not in ("submitted", "offered"):
            raise HTTPException(status_code=409, detail="این درخواست دیگر قابل لغو نیست")
        r.status = "cancelled"
        db.commit()
        return _out(r)

    @api.post("/me/train-requests/{rid}/accept")
    def accept(rid: str, data: AcceptIn, user=Depends(current_user), db: Session = Depends(get_db)):
        r = _get(db, user.tenant_id, rid, lock=True, user_id=user.id)
        if r.status != "offered":
            raise HTTPException(status_code=409, detail="پیشنهادی برای پذیرش وجود ندارد")
        if r.offer_expires_at and _aware(r.offer_expires_at) <= utcnow():
            raise HTTPException(status_code=409, detail="مهلت این پیشنهاد گذشته است؛ کارشناس ظرفیت را دوباره بررسی می‌کند")
        offers = {o["id"]: o for o in _offers(r)}
        chosen = [offers.get(i) for i in data.offer_ids]
        if any(o is None for o in chosen):
            raise HTTPException(status_code=422, detail="پیشنهاد انتخاب‌شده معتبر نیست")
        legs = [o["leg"] for o in chosen]
        if len(set(legs)) != len(legs) or (r.return_on and "return" not in legs and any(o["leg"] == "return" for o in offers.values())):
            raise HTTPException(status_code=422, detail="برای هر مسیر (رفت و برگشت) یک قطار انتخاب کنید")
        total = sum(o["total"] for o in chosen)
        travellers = r.adults + r.children + r.infants
        first = min(chosen, key=lambda o: o["departs_at"])
        res = m.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="train", status="reserved", booking_reference=f"KS-TRAIN-{uuid.uuid4().hex[:10].upper()}",
                            price_snapshot_json=json.dumps({"total_amount": total, "currency": "IRR", "travellers": travellers, "units": travellers, "adults": r.adults,
                                                            "children": r.children, "infants": r.infants, "train_request_id": r.id, "offers": chosen}, sort_keys=True, ensure_ascii=False),
                            policy_at_booking_json="{}", current_policy_json="{}")
        db.add(res)
        db.flush()
        for o in chosen:
            db.add(m.BookingItem(tenant_id=user.tenant_id, reservation_id=res.id, item_type="train", snapshot_json=json.dumps({
                "title": f"قطار {o['train_name']}", "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier",
                "attributes": {"origin": r.origin if o["leg"] == "depart" else r.destination, "destination": r.destination if o["leg"] == "depart" else r.origin,
                               "departure_time": o["departs_at"], "arrival_time": o.get("arrives_at"), "train_number": o.get("train_number"), "wagon": o["wagon"], "travellers": travellers}},
                sort_keys=True, ensure_ascii=False)))
        last = max(chosen, key=lambda o: o.get("arrives_at") or o["departs_at"])
        trip = m.ensure_trip_for_reservation(db, res, title=f"قطار {r.origin} به {r.destination}", destination=r.destination, origin=r.origin,
                                             starts_at=datetime.fromisoformat(first["departs_at"]), ends_at=datetime.fromisoformat(last.get("arrives_at") or last["departs_at"]))
        m.record_trip_event(db, tenant_id=user.tenant_id, trip_id=trip.id, reservation_id=res.id, event_key=f"train-accepted:{r.id}", event_type="booking.created", source="system",
                            title="قطار انتخاب شد", message="پس از پرداخت، کارشناس بلیت را صادر می‌کند و در همین سفر می‌گذارد.", requires_action=True, deep_link=f"/checkout/{res.id}")
        r.status, r.accepted_offer_id, r.reservation_id = "accepted", ",".join(data.offer_ids), res.id
        db.commit()
        return _out(r)

    # ---- agents ----
    @api.get("/train-desk/requests")
    def queue(status: str = Query(default="open", pattern="^(open|submitted|offered|accepted|issued|unavailable|cancelled|referred|all)$"), mine_only: bool = False,
              user=Depends(agent), db: Session = Depends(get_db)):
        s = select(TrainRequest, User.name, User.mobile_e164).join(User, User.id == TrainRequest.user_id).where(TrainRequest.tenant_id == user.tenant_id)
        if status == "open":
            s = s.where(TrainRequest.status.in_(("submitted", "offered", "accepted")))
        elif status != "all":
            s = s.where(TrainRequest.status == status)
        if mine_only:
            s = s.where(TrainRequest.assigned_user_id == user.id)
        rows = db.execute(s.order_by(TrainRequest.depart_on, TrainRequest.created_at).limit(200)).all()
        ids = {r.assigned_user_id for r, _, _ in rows if r.assigned_user_id}
        names = dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all()) if ids else {}
        paid: dict[str, str] = {}
        res_ids = [r.reservation_id for r, _, _ in rows if r.reservation_id]
        if res_ids:
            paid = dict(db.execute(select(m.Reservation.id, m.Reservation.status).where(m.Reservation.id.in_(res_ids))).all())
        counts = dict(db.execute(select(TrainRequest.status, func.count(TrainRequest.id)).where(TrainRequest.tenant_id == user.tenant_id).group_by(TrainRequest.status)).all())
        hours = json.loads(_settings(db, user.tenant_id).hours_json)
        db.commit()
        return {"items": [_out(r, True, names, {"name": n, "mobile": mob}) | {"reservation_status": paid.get(r.reservation_id)} for r, n, mob in rows],
                "counts": {k: int(v) for k, v in counts.items()}, "desk": office_state(hours), "hours": hours}

    @api.post("/train-desk/requests/{rid}/claim")
    def claim(rid: str, user=Depends(agent), db: Session = Depends(get_db)):
        r = _get(db, user.tenant_id, rid, lock=True)
        if r.assigned_user_id and r.assigned_user_id != user.id:
            raise HTTPException(status_code=409, detail="این درخواست را همکار دیگری برداشته است")
        r.assigned_user_id = user.id
        db.commit()
        return {"id": r.id, "assigned": True}

    def _mine(r: TrainRequest, user):
        if r.assigned_user_id and r.assigned_user_id != user.id:
            raise HTTPException(status_code=409, detail="این درخواست را همکار دیگری برداشته است")
        r.assigned_user_id = r.assigned_user_id or user.id

    @api.post("/train-desk/requests/{rid}/offers")
    def offer(rid: str, data: OffersIn, user=Depends(agent), db: Session = Depends(get_db)):
        r = _get(db, user.tenant_id, rid, lock=True)
        if r.status not in ("submitted", "offered"):
            raise HTTPException(status_code=409, detail="برای این درخواست دیگر پیشنهاد فرستاده نمی‌شود")
        _mine(r, user)
        if not r.return_on and any(o.leg == "return" for o in data.offers):
            raise HTTPException(status_code=422, detail="این درخواست برگشت ندارد")
        if r.children and any(o.price_child == 0 for o in data.offers) or r.infants and any(o.price_infant == 0 for o in data.offers):
            raise HTTPException(status_code=422, detail="نرخ کودک یا نوزاد را وارد کنید")
        out = []
        for o in data.offers:
            if _aware(o.departs_at) <= utcnow():
                raise HTTPException(status_code=422, detail="ساعت حرکت قطار گذشته است")
            if o.arrives_at and _aware(o.arrives_at) <= _aware(o.departs_at):
                raise HTTPException(status_code=422, detail="ساعت رسیدن باید بعد از حرکت باشد")
            total = o.price_adult * r.adults + o.price_child * r.children + o.price_infant * r.infants
            out.append({"id": str(uuid.uuid4()), "leg": o.leg, "train_name": o.train_name, "train_number": o.train_number, "company": o.company,
                        "departs_at": _aware(o.departs_at).isoformat(), "arrives_at": _aware(o.arrives_at).isoformat() if o.arrives_at else None, "wagon": o.wagon,
                        "price_adult": o.price_adult, "price_child": o.price_child, "price_infant": o.price_infant, "total": total})
        minutes = data.valid_minutes or _settings(db, user.tenant_id).offer_valid_minutes
        r.offers_json, r.status, r.offer_expires_at = json.dumps(out, ensure_ascii=False), "offered", utcnow() + timedelta(minutes=minutes)
        r.staff_note = data.staff_note or r.staff_note
        _notify(db, r, "پیشنهاد قطار آماده است", f"برای {r.origin} به {r.destination}، {len(out)} قطار پیشنهاد شده است؛ تا {minutes} دقیقه برای انتخاب و پرداخت فرصت دارید.")
        _a(db, user, "train.offered", r.id, {"count": len(out)})
        db.commit()
        return _out(r, True)

    @api.post("/train-desk/requests/{rid}/unavailable")
    def unavailable(rid: str, data: NoteIn, user=Depends(agent), db: Session = Depends(get_db)):
        r = _get(db, user.tenant_id, rid, lock=True)
        if r.status not in ("submitted", "offered"):
            raise HTTPException(status_code=409, detail="وضعیت درخواست اجازه‌ی این کار را نمی‌دهد")
        _mine(r, user)
        r.status, r.staff_note = "unavailable", data.note or "برای این تاریخ ظرفیت پیدا نشد."
        _notify(db, r, "ظرفیت قطار پیدا نشد", f"برای {r.origin} به {r.destination} در تاریخ درخواستی ظرفیتی پیدا نشد. می‌توانید تاریخ دیگری درخواست کنید.")
        _a(db, user, "train.unavailable", r.id)
        db.commit()
        return _out(r, True)

    @api.post("/train-desk/requests/{rid}/issue")
    def issue(rid: str, data: IssueIn, user=Depends(agent), db: Session = Depends(get_db)):
        r = _get(db, user.tenant_id, rid, lock=True)
        if r.status != "accepted" or not r.reservation_id:
            raise HTTPException(status_code=409, detail="مشتری هنوز قطاری انتخاب نکرده است")
        res = db.scalar(select(m.Reservation).where(m.Reservation.id == r.reservation_id, m.Reservation.tenant_id == user.tenant_id).with_for_update())
        if res is None or res.status != "confirmed":
            raise HTTPException(status_code=409, detail="پرداخت این رزرو هنوز تأیید نشده است؛ پیش از پرداخت بلیت صادر نکنید")
        _mine(r, user)
        m.transition_reservation(db, res, "issued", user.id, f"train-issue:{r.id}")
        r.status, r.ticket_numbers = "issued", data.ticket_numbers.strip()
        _notify(db, r, "بلیت قطار صادر شد", f"شماره‌ی بلیت: {r.ticket_numbers}", f"/manage-booking/{res.id}")
        if res.trip_id:
            m.record_trip_event(db, tenant_id=user.tenant_id, trip_id=res.trip_id, reservation_id=res.id, event_key=f"train-issued:{r.id}", event_type="booking.issued", source="human_agent",
                                title="بلیت قطار صادر شد", message=f"شماره‌ی بلیت: {r.ticket_numbers}", requires_action=False, deep_link=f"/manage-booking/{res.id}")
        _a(db, user, "train.issued", r.id)
        db.commit()
        return _out(r, True)

    @api.post("/train-desk/requests/{rid}/refer")
    def refer(rid: str, data: NoteIn, user=Depends(agent), db: Session = Depends(get_db)):
        """Hand the request to the sales desk when the customer wants a whole tour (hotel, transfer, ...)."""
        from .sales_desk import SalesCase, _new_code, _log, normalize_mobile
        r = _get(db, user.tenant_id, rid, lock=True)
        if r.status in ("issued", "cancelled", "referred"):
            raise HTTPException(status_code=409, detail="این درخواست بسته شده است")
        cust = db.scalar(select(User).where(User.id == r.user_id))
        try:
            mobile = normalize_mobile(cust.mobile_e164 or "") if cust is not None else ""
        except Exception:  # noqa: BLE001 — customer without a valid mobile
            mobile = ""
        if not mobile:
            raise HTTPException(status_code=422, detail="شماره‌ی موبایل مشتری ثبت نشده است؛ برای ارجاع، با مشتری تماس بگیرید")
        case = SalesCase(tenant_id=user.tenant_id, code=_new_code(db, user.tenant_id), customer_name=cust.name or "مشتری", mobile=mobile, customer_user_id=cust.id,
                         channel="trip_request", trip=f"تور با قطار {r.origin} به {r.destination}", travel_date=r.depart_on, travellers=r.adults + r.children + r.infants,
                         stage="new", description=(data.note or "") + f"\nاز درخواست قطار {r.code}", created_by_user_id=user.id, agent_user_id=user.id)
        db.add(case)
        db.flush()
        _log(db, case, user.id, "created", None, {"channel": "trip_request", "from_train_request": r.code})
        r.status, r.sales_case_id = "referred", case.id
        _notify(db, r, "درخواست شما به کارشناس تور سپرده شد", "کارشناس تور برای برنامه‌ی کامل سفر با شما تماس می‌گیرد.")
        _a(db, user, "train.referred", r.id, {"case": case.code})
        db.commit()
        return _out(r, True) | {"sales_case_code": case.code}

    @api.get("/train-desk/settings")
    def get_settings(user=Depends(agent), db: Session = Depends(get_db)):
        s = _settings(db, user.tenant_id)
        db.commit()
        return {"hours": json.loads(s.hours_json), "offer_valid_minutes": s.offer_valid_minutes, "days_fa": DAYS_FA}

    @api.put("/train-desk/settings")
    def put_settings(data: HoursIn, user=Depends(admin), db: Session = Depends(get_db)):
        if data.end <= data.start or (data.thursday_end and data.thursday_end <= data.start):
            raise HTTPException(status_code=422, detail="پایان ساعت کاری باید بعد از شروع باشد")
        s = _settings(db, user.tenant_id)
        s.hours_json = json.dumps({"days": data.days, "start": data.start, "end": data.end, "thursday_end": data.thursday_end})
        s.offer_valid_minutes = data.offer_valid_minutes
        _a(db, user, "train.settings", s.id)
        db.commit()
        return get_settings(user, db)

    return api


__all__ = ["train_requests_router", "office_state", "TrainRequest", "TrainDeskSettings", "date"]
