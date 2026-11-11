"""Panels Phase 2 — charterer panel (CH-01 list, CH-02 seat-block form, CH-03/04 detail and allocations to agencies) and the
staff review that publishes a block into the normal inventory/checkout path.

* A charterer is an agency (spec §2.7) whose profile is active and that holds a verified, unexpired BAND_ALEF licence.
* A block (`charter_blocks`) records one dated charter flight: route, flight, seats, net fares (ADT/CHD/INF, integer rial),
  release deadline, refund policy, source (manual or an external shared system such as Parto) and its external reference.
* CAO price cap (owner L5): `charter_price_caps` holds the cap per route and period with its legal reference, entered by
  tenant staff from the CAO notice. A block whose ADT net fare is above the applicable cap is refused
  (422 `PRICE_CAP_EXCEEDED`); the agency credit checkout (agency_b2b) and the B2C price check refuse a customer price above it.
  No cap configured = not checked, and every response says `price_cap_status: not_configured` instead of inventing one.
* Publishing (staff `inventory:publish`) creates the route/series/dated instance through `inventory._sync_offer`, so the
  block is sold through the normal search → price check → booking path. Domestic charter sale stays behind the
  `charter_domestic_sale` flag (D8, env `CHARTER_DOMESTIC_SALE=1`), default OFF: a domestic block can be saved and reviewed,
  but publishing or allocating it answers 409 `CHARTER_DOMESTIC_DISABLED`.
* Allocations to other agencies reuse the existing seat quotas (`inv_seat_quotas`): held seats leave public sale, go to the
  agency's own credit booking first, and return automatically at the block's release time.
* External systems (Parto and similar) are behind `CharterSource` adapters. None is contracted yet (supplier rule: no adapter
  before CONTRACTED), so every adapter reports `not_contracted` and makes no network call.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Protocol
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .agency_b2b import AgencyProfile, agency_membership, bps_of, half_up, latin_digits, valid_licence_types, vat_rate_on
from .database import Base
from .operations import OperationalMixin

TEHRAN = ZoneInfo("Asia/Tehran")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def domestic_charter_sale_enabled() -> bool:
    """D8 feature flag `charter_domestic_sale`; OFF unless explicitly enabled for the deployment."""
    return os.getenv("CHARTER_DOMESTIC_SALE", "0").strip() == "1"


# ------------------------------------------------------------------------------------------------ models
class PriceCap(OperationalMixin, Base):
    __tablename__ = "charter_price_caps"
    origin: Mapped[str] = mapped_column(String(3), index=True)
    destination: Mapped[str] = mapped_column(String(3), index=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    cap_unit_irr: Mapped[int] = mapped_column(Integer)  # adult, per passenger
    legal_reference: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class CharterBlock(OperationalMixin, Base):
    __tablename__ = "charter_blocks"
    owner_agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | parto | charter724 | sepehr | other
    external_ref: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    airline_code: Mapped[str] = mapped_column(String(3))
    airline_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    flight_number: Mapped[str] = mapped_column(String(8))
    aircraft: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    origin_city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    destination_city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    route_scope: Mapped[str] = mapped_column(String(16))  # domestic | international
    cabin: Mapped[str] = mapped_column(String(16), default="economy")
    fare_class: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    seats_total: Mapped[int] = mapped_column(Integer)
    net_adult_irr: Mapped[int] = mapped_column(Integer)
    net_child_irr: Mapped[int] = mapped_column(Integer, default=0)
    net_infant_irr: Mapped[int] = mapped_column(Integer, default=0)
    baggage_kg: Mapped[int] = mapped_column(Integer, default=20)
    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    name_change_hours: Mapped[int] = mapped_column(Integer, default=72)
    refund_policy_json: Mapped[str] = mapped_column(Text, default="{}")
    tax_role: Mapped[str] = mapped_column(String(12), default="PRINCIPAL")
    accountant_confirmed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)  # draft | submitted | published | rejected
    review_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    platform_fee_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # per contract; set by staff at approval
    price_cap_unit_irr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_cap_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    instance_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    offer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


TABLES = ("charter_price_caps", "charter_blocks")


# ------------------------------------------------------------------------------------------------ external sources
class CharterSource(Protocol):
    key: str
    label: str

    def status(self) -> str: ...

    def fetch_blocks(self, agency_id: str) -> list[dict]: ...


class NotContracted(RuntimeError):
    pass


class _UncontractedSource:
    """Placeholder adapter: the supplier is UNSELECTED/UNDER_EVALUATION. It never calls the network."""

    def __init__(self, key: str, label: str):
        self.key, self.label = key, label

    def status(self) -> str:
        return "not_contracted"

    def fetch_blocks(self, agency_id: str) -> list[dict]:
        raise NotContracted(f"{self.key}: no contract/credentials; adapter not implemented (supplier rule: no adapter before CONTRACTED)")


SOURCES: dict[str, CharterSource] = {
    "parto": _UncontractedSource("parto", "پرتو (سامانهٔ اشتراکی چارتر)"),
    "charter724": _UncontractedSource("charter724", "چارتر۷۲۴"),
    "sepehr": _UncontractedSource("sepehr", "سپهر"),
}
SOURCE_KEYS = ("manual", "parto", "charter724", "sepehr", "other")


# ------------------------------------------------------------------------------------------------ helpers used by other modules
def applicable_cap(db: Session, tenant_id: int, attrs: dict) -> tuple[Optional[int], Optional[str]]:
    """Lowest active CAO cap for the flight's route and date, or (None, None) when none is configured."""
    origin = str(attrs.get("origin_code") or attrs.get("origin") or "").upper()[:3]
    dest = str(attrs.get("destination_code") or attrs.get("destination") or "").upper()[:3]
    raw = attrs.get("flight_date") or str(attrs.get("departure_time") or "")[:10]
    try:
        day = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None, None
    if not origin or not dest:
        return None, None
    return cap_for(db, tenant_id, origin, dest, day)


def cap_for(db: Session, tenant_id: int, origin: str, destination: str, day: date) -> tuple[Optional[int], Optional[str]]:
    row = db.scalar(select(PriceCap).where(PriceCap.tenant_id == tenant_id, PriceCap.status == "active", PriceCap.origin == origin, PriceCap.destination == destination,
                                           PriceCap.valid_from <= day, PriceCap.valid_to >= day).order_by(PriceCap.cap_unit_irr).limit(1))
    return (row.cap_unit_irr, row.legal_reference) if row else (None, None)


def take_agency_quota(db: Session, tenant_id: int, agency_id: str, attrs: dict, units: int) -> Optional[str]:
    """Move up to `units` seats of this agency's held quota on the flight back to the offer, for its own booking that follows."""
    from .charter_quotas import SeatQuota
    instance_id = attrs.get("inventory_instance_id")
    if not instance_id:
        return None
    q = db.scalar(select(SeatQuota).where(SeatQuota.tenant_id == tenant_id, SeatQuota.instance_id == instance_id, SeatQuota.agency_id == agency_id,
                                          SeatQuota.status == "held", SeatQuota.release_at > utcnow()).with_for_update().limit(1))
    if q is None:
        return None
    from .inventory import FlightInstance
    inst = db.get(FlightInstance, instance_id)
    offer = db.scalar(select(m.Offer).where(m.Offer.id == inst.offer_id, m.Offer.tenant_id == tenant_id).with_for_update()) if inst and inst.offer_id else None
    n = min(units, q.seats)
    q.seats -= n
    if offer is not None:
        offer.available_units += n
    if q.seats == 0:
        q.status, q.released_reason = "released", "agency_booking"
    return q.id


# ------------------------------------------------------------------------------------------------ schemas
class Strict(BaseModel):
    model_config = {"extra": "forbid"}


class RefundTier(Strict):
    hours_before: int = Field(ge=0, le=24 * 60)
    penalty_bps: int = Field(ge=0, le=10_000)


class BlockIn(Strict):
    source: str = Field(default="manual", pattern="^(manual|parto|charter724|sepehr|other)$")
    external_ref: Optional[str] = Field(default=None, max_length=80)
    airline_code: str = Field(pattern=r"^[A-Za-z0-9]{2,3}$")
    airline_name: Optional[str] = Field(default=None, max_length=80)
    flight_number: str = Field(pattern=r"^[A-Za-z0-9]{1,8}$")
    aircraft: Optional[str] = Field(default=None, max_length=40)
    origin: str = Field(pattern=r"^[A-Za-z]{3}$")
    destination: str = Field(pattern=r"^[A-Za-z]{3}$")
    origin_city: Optional[str] = Field(default=None, max_length=80)
    destination_city: Optional[str] = Field(default=None, max_length=80)
    route_scope: str = Field(pattern="^(domestic|international)$")
    cabin: str = Field(default="economy", pattern="^(economy|premium|business|first)$")
    fare_class: Optional[str] = Field(default=None, max_length=8)
    departure_at: datetime
    arrival_at: datetime
    seats_total: int = Field(ge=1, le=1000)
    net_adult_irr: int = Field(gt=0, le=10**11)
    net_child_irr: int = Field(default=0, ge=0, le=10**11)
    net_infant_irr: int = Field(default=0, ge=0, le=10**11)
    baggage_kg: int = Field(default=20, ge=0, le=100)
    release_at: datetime
    name_change_hours: int = Field(default=72, ge=0, le=720)
    refund_tiers: list[RefundTier] = Field(default_factory=list, max_length=8)
    non_refundable: bool = False
    submit: bool = False

    @field_validator("external_ref", "flight_number", mode="before")
    @classmethod
    def _d(cls, v):
        return latin_digits(v)


class DecisionIn(Strict):
    decision: str = Field(pattern="^(approve|reject)$")
    reason: Optional[str] = Field(default=None, max_length=500)
    platform_fee_bps: Optional[int] = Field(default=None, ge=0, le=5000)


class AllocationIn(Strict):
    agency_id: str = Field(min_length=36, max_length=36)
    seats: int = Field(ge=1, le=1000)
    note: Optional[str] = Field(default=None, max_length=300)


class ReleaseIn(Strict):
    seats: Optional[int] = Field(default=None, ge=1, le=1000)


class CapIn(Strict):
    origin: str = Field(pattern=r"^[A-Za-z]{3}$")
    destination: str = Field(pattern=r"^[A-Za-z]{3}$")
    valid_from: date
    valid_to: date
    cap_unit_irr: int = Field(gt=0, le=10**11)
    legal_reference: str = Field(min_length=4, max_length=200)


# ------------------------------------------------------------------------------------------------ outputs
def _iso(v) -> Optional[str]:
    return _aw(v).isoformat() if isinstance(v, datetime) else (v.isoformat() if v is not None else None)


def seller_view(b: CharterBlock, sold: int) -> dict:
    """agency_seller MoneyBreakdown: the charterer's own rate, the platform fee and its VAT, net payable. No customer price."""
    gross = b.net_adult_irr * sold
    out = {"view": "agency_seller", "sold_seats": sold, "agency_rate_unit_irr": b.net_adult_irr, "gross_at_agency_rate_irr": gross,
           "platform_fee_bps": b.platform_fee_bps, "basis": "adult_rate_x_sold_seats"}
    if b.platform_fee_bps is None:
        out.update({"platform_fee_irr": None, "vat_on_fee_irr": None, "net_payable_irr": None, "fee_status": "not_set"})
        return out
    fee = bps_of(gross, b.platform_fee_bps)
    from sqlalchemy.orm import object_session
    v = vat_rate_on(utcnow().date(), object_session(b), b.tenant_id)
    vat = bps_of(fee, v.rate_bps)
    out.update({"platform_fee_irr": fee, "vat_rate_bps": v.rate_bps, "vat_rate_id": v.id, "vat_on_fee_irr": vat, "net_payable_irr": gross - fee - vat, "fee_status": "contract"})
    return out


# ------------------------------------------------------------------------------------------------ router
def charter_blocks_router(get_db, current_user, role_has_permission, User, audit: Callable) -> APIRouter:
    from .charter_quotas import SeatQuota
    from .inventory import FlightInstance, FlightRoute, FlightSeries, _sync_offer

    api = APIRouter(tags=["charter-blocks"])

    def a(db, user, action: str, detail: dict) -> None:
        audit(db, user, action, "charter_block", detail)

    def charterer(db: Session, agency_id: str, user, *, write: bool = False):
        agency, role = agency_membership(db, agency_id, user, role_has_permission, owner=write)
        return agency, role

    def require_band_alef(db: Session, tenant_id: int, agency_id: str) -> None:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.tenant_id == tenant_id, AgencyProfile.agency_id == agency_id))
        if p is None or p.kyc_status != "active":
            raise HTTPException(status_code=422, detail={"code": "AGENCY_NOT_ACTIVE", "message": "آژانس هنوز احراز و فعال نشده است"})
        if "BAND_ALEF" not in valid_licence_types(db, tenant_id, agency_id):
            raise HTTPException(status_code=422, detail={"code": "LICENCE_REQUIRED", "message": "برای ثبت پرواز و چارتر مجوز معتبر و احرازشدهٔ بند الف لازم است"})

    def block_for(db: Session, user, block_id: str, owner_agency_id: Optional[str] = None, lock: bool = False) -> CharterBlock:
        q = select(CharterBlock).where(CharterBlock.id == block_id, CharterBlock.tenant_id == user.tenant_id)
        if owner_agency_id is not None:
            q = q.where(CharterBlock.owner_agency_id == owner_agency_id)
        row = db.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise HTTPException(status_code=404, detail="بلوک صندلی یافت نشد")
        return row

    def seats(db: Session, b: CharterBlock) -> dict:
        held = sold = 0
        public = b.seats_total if b.status != "published" else 0
        if b.instance_id:
            from .charter_quotas import held_seats
            held = held_seats(db, b.tenant_id, b.instance_id)
            offer = db.get(m.Offer, b.offer_id) if b.offer_id else None
            public = offer.available_units if offer else 0
            sold = max(0, b.seats_total - public - held)
        return {"seats_total": b.seats_total, "sold": sold, "allocated_held": held, "public_available": public, "remaining": b.seats_total - sold}

    def out(db: Session, b: CharterBlock, *, staff: bool = False) -> dict:
        s = seats(db, b)
        domestic_off = b.route_scope == "domestic" and not domestic_charter_sale_enabled()
        d = {k: getattr(b, k) for k in ("id", "owner_agency_id", "source", "external_ref", "airline_code", "airline_name", "flight_number", "aircraft", "origin", "destination",
                                        "origin_city", "destination_city", "route_scope", "cabin", "fare_class", "seats_total", "net_adult_irr", "net_child_irr", "net_infant_irr",
                                        "baggage_kg", "name_change_hours", "tax_role", "status", "review_note", "platform_fee_bps", "price_cap_unit_irr", "price_cap_reference",
                                        "instance_id")}
        d.update({"departure_at": _iso(b.departure_at), "arrival_at": _iso(b.arrival_at), "release_at": _iso(b.release_at), "reviewed_at": _iso(b.reviewed_at),
                  "created_at": _iso(b.created_at), "refund_policy": json.loads(b.refund_policy_json or "{}"), "accountant_confirmed": bool(b.accountant_confirmed),
                  "seats": s, "domestic_sale_disabled": domestic_off, "price_cap_status": "not_configured" if b.price_cap_unit_irr is None else "within",
                  "money": seller_view(b, s["sold"])})
        if staff:
            names = db.scalar(select(m.Agency.display_name).where(m.Agency.id == b.owner_agency_id))
            d["owner_agency_name"] = names
        return d

    def validate(data: BlockIn) -> None:
        if data.origin.upper() == data.destination.upper():
            raise HTTPException(status_code=422, detail="مبدأ و مقصد یکسان است")
        dep, arr, rel = _aw(data.departure_at), _aw(data.arrival_at), _aw(data.release_at)
        if dep <= utcnow():
            raise HTTPException(status_code=422, detail="زمان حرکت گذشته است")
        if arr <= dep or arr - dep > timedelta(hours=20):
            raise HTTPException(status_code=422, detail="زمان رسیدن نامعتبر است")
        if not utcnow() < rel < dep:
            raise HTTPException(status_code=422, detail="زمان release باید بین اکنون و زمان حرکت باشد")
        if data.source != "manual" and not (data.external_ref or "").strip():
            raise HTTPException(status_code=422, detail="برای منبع بیرونی، شناسهٔ مرجع آن سامانه لازم است")
        for t in data.refund_tiers:
            if data.non_refundable:
                raise HTTPException(status_code=422, detail="بلیت غیرقابل استرداد پلهٔ جریمه ندارد")

    def check_cap(db: Session, tenant_id: int, data_origin: str, data_dest: str, dep: datetime, net_adult: int) -> tuple[Optional[int], Optional[str]]:
        day = _aw(dep).astimezone(TEHRAN).date()
        cap, ref = cap_for(db, tenant_id, data_origin.upper(), data_dest.upper(), day)
        if cap is not None and net_adult > cap:
            raise HTTPException(status_code=422, detail={"code": "PRICE_CAP_EXCEEDED", "message": "نرخ بزرگسال از سقف اعلامی سازمان هواپیمایی برای این مسیر و تاریخ بیشتر است",
                                                         "price_cap_unit_irr": cap, "price_cap_reference": ref, "net_adult_irr": net_adult})
        return cap, ref

    # ---- sources / flag -------------------------------------------------------------------------------------------
    @api.get("/charter/sources")
    def sources(user=Depends(current_user)) -> dict:
        return {"items": [{"key": "manual", "label": "ورود دستی (همین پنل)", "status": "active"}] +
                         [{"key": k, "label": s.label, "status": s.status()} for k, s in SOURCES.items()],
                "domestic_charter_sale": domestic_charter_sale_enabled()}

    @api.get("/charter/price-cap")
    def price_cap(origin: str, destination: str, day: date, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        cap, ref = cap_for(db, user.tenant_id, origin.upper()[:3], destination.upper()[:3], day)
        return {"origin": origin.upper()[:3], "destination": destination.upper()[:3], "date": day.isoformat(), "cap_unit_irr": cap, "legal_reference": ref,
                "status": "not_configured" if cap is None else "configured"}

    # ---- charterer side -------------------------------------------------------------------------------------------
    @api.get("/agency/{agency_id}/charter/blocks")
    def list_blocks(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = charterer(db, agency_id, user)
        rows = db.scalars(select(CharterBlock).where(CharterBlock.tenant_id == user.tenant_id, CharterBlock.owner_agency_id == agency.id).order_by(CharterBlock.departure_at)).all()
        items = [out(db, b) for b in rows]
        lic = "BAND_ALEF" in valid_licence_types(db, user.tenant_id, agency.id)
        return {"items": items, "member_role": role, "band_alef_valid": lic, "domestic_charter_sale": domestic_charter_sale_enabled(),
                "summary": {"seats_total": sum(i["seats_total"] for i in items), "sold": sum(i["seats"]["sold"] for i in items),
                            "allocated_held": sum(i["seats"]["allocated_held"] for i in items),
                            "next_release_at": min((i["release_at"] for i in items if i["status"] == "published" and i["release_at"] > utcnow().isoformat()), default=None)}}

    @api.post("/agency/{agency_id}/charter/blocks", status_code=201)
    def create_block(agency_id: str, data: BlockIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = charterer(db, agency_id, user, write=True)
        require_band_alef(db, user.tenant_id, agency.id)
        validate(data)
        cap, ref = check_cap(db, user.tenant_id, data.origin, data.destination, data.departure_at, data.net_adult_irr)
        policy = {"non_refundable": data.non_refundable, "tiers": [t.model_dump() for t in sorted(data.refund_tiers, key=lambda t: -t.hours_before)],
                  "carrier_cancel_or_delay_over_2h": "full_refund"}
        b = CharterBlock(tenant_id=user.tenant_id, owner_agency_id=agency.id, source=data.source, external_ref=(data.external_ref or "").strip() or None,
                         airline_code=data.airline_code.upper(), airline_name=data.airline_name, flight_number=data.flight_number.upper(), aircraft=data.aircraft,
                         origin=data.origin.upper(), destination=data.destination.upper(), origin_city=data.origin_city, destination_city=data.destination_city,
                         route_scope=data.route_scope, cabin=data.cabin, fare_class=data.fare_class, departure_at=_aw(data.departure_at), arrival_at=_aw(data.arrival_at),
                         seats_total=data.seats_total, net_adult_irr=data.net_adult_irr, net_child_irr=data.net_child_irr, net_infant_irr=data.net_infant_irr,
                         baggage_kg=data.baggage_kg, release_at=_aw(data.release_at), name_change_hours=data.name_change_hours, refund_policy_json=json.dumps(policy, ensure_ascii=False),
                         tax_role="PRINCIPAL", accountant_confirmed=0, status="submitted" if data.submit else "draft", price_cap_unit_irr=cap, price_cap_reference=ref,
                         created_by_user_id=user.id)
        db.add(b)
        db.flush()
        a(db, user, "charter.block.created", {"block_id": b.id, "agency_id": agency.id, "status": b.status, "seats": b.seats_total, "net_adult_irr": b.net_adult_irr, "source": b.source})
        db.commit()
        return out(db, b)

    @api.get("/agency/{agency_id}/charter/blocks/{block_id}")
    def get_block(agency_id: str, block_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = charterer(db, agency_id, user)
        b = block_for(db, user, block_id, agency.id)
        quotas = db.scalars(select(SeatQuota).where(SeatQuota.tenant_id == user.tenant_id, SeatQuota.instance_id == b.instance_id).order_by(SeatQuota.created_at)).all() if b.instance_id else []
        names = dict(db.execute(select(m.Agency.id, m.Agency.display_name).where(m.Agency.tenant_id == user.tenant_id, m.Agency.id.in_({q.agency_id for q in quotas}))).all()) if quotas else {}
        return {**out(db, b), "member_role": role,
                "allocations": [{"id": q.id, "agency_id": q.agency_id, "agency": names.get(q.agency_id), "seats": q.seats, "seats_initial": q.seats_initial, "status": q.status,
                                 "release_at": _iso(q.release_at), "released_reason": q.released_reason, "note": q.note} for q in quotas]}

    @api.post("/agency/{agency_id}/charter/blocks/{block_id}/submit")
    def submit_block(agency_id: str, block_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = charterer(db, agency_id, user, write=True)
        b = block_for(db, user, block_id, agency.id, lock=True)
        if b.status not in ("draft", "rejected"):
            raise HTTPException(status_code=409, detail="این بلوک در وضعیت قابل ارسال نیست")
        require_band_alef(db, user.tenant_id, agency.id)
        b.status, b.review_note = "submitted", None
        a(db, user, "charter.block.submitted", {"block_id": b.id, "agency_id": agency.id})
        db.commit()
        return out(db, b)

    @api.get("/agency/{agency_id}/charter/partners")
    def partners(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = charterer(db, agency_id, user, write=True)
        active = select(AgencyProfile.agency_id).where(AgencyProfile.tenant_id == user.tenant_id, AgencyProfile.kyc_status == "active")
        rows = db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id, m.Agency.id != agency.id, m.Agency.id.in_(active)).order_by(m.Agency.display_name)).all()
        return {"items": [{"id": x.id, "name": x.display_name} for x in rows]}

    @api.post("/agency/{agency_id}/charter/blocks/{block_id}/allocations", status_code=201)
    def allocate(agency_id: str, block_id: str, data: AllocationIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = charterer(db, agency_id, user, write=True)
        b = block_for(db, user, block_id, agency.id, lock=True)
        if b.status != "published" or not b.instance_id:
            raise HTTPException(status_code=409, detail="سهمیه فقط روی بلوک منتشرشده تعریف می‌شود")
        if b.route_scope == "domestic" and not domestic_charter_sale_enabled():
            raise HTTPException(status_code=409, detail={"code": "CHARTER_DOMESTIC_DISABLED", "message": "فروش چارتر داخلی تا تأیید قانونی غیرفعال است"})
        if data.agency_id == agency.id:
            raise HTTPException(status_code=422, detail="به آژانس خودتان سهمیه نمی‌دهید")
        target = db.scalar(select(m.Agency).where(m.Agency.id == data.agency_id, m.Agency.tenant_id == user.tenant_id))
        tp = db.scalar(select(AgencyProfile).where(AgencyProfile.tenant_id == user.tenant_id, AgencyProfile.agency_id == data.agency_id))
        if target is None or tp is None or tp.kyc_status != "active":
            raise HTTPException(status_code=422, detail="آژانس گیرنده فعال نیست")
        inst = db.get(FlightInstance, b.instance_id)
        offer = db.scalar(select(m.Offer).where(m.Offer.id == b.offer_id, m.Offer.tenant_id == user.tenant_id).with_for_update())
        release_at = _aw(b.release_at)
        if release_at <= utcnow():
            raise HTTPException(status_code=409, detail="زمان release این بلوک گذشته است")
        if offer is None or offer.available_units < data.seats:
            raise HTTPException(status_code=409, detail=f"فقط {offer.available_units if offer else 0} صندلی آزاد باقی است")
        offer.available_units -= data.seats
        q = SeatQuota(tenant_id=user.tenant_id, instance_id=inst.id, agency_id=target.id, seats=data.seats, seats_initial=data.seats, status="held",
                      release_at=release_at, note=data.note, created_by=user.id)
        db.add(q)
        db.flush()
        a(db, user, "charter.block.allocated", {"block_id": b.id, "quota_id": q.id, "to_agency_id": target.id, "seats": data.seats})
        db.commit()
        return {"id": q.id, "agency_id": target.id, "agency": target.display_name, "seats": q.seats, "status": q.status, "release_at": _iso(q.release_at)}

    @api.post("/agency/{agency_id}/charter/blocks/{block_id}/allocations/{quota_id}/release")
    def release_allocation(agency_id: str, block_id: str, quota_id: str, data: ReleaseIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = charterer(db, agency_id, user, write=True)
        b = block_for(db, user, block_id, agency.id, lock=True)
        q = db.scalar(select(SeatQuota).where(SeatQuota.id == quota_id, SeatQuota.tenant_id == user.tenant_id, SeatQuota.instance_id == b.instance_id).with_for_update())
        if q is None or not b.instance_id:
            raise HTTPException(status_code=404, detail="سهمیه یافت نشد")
        if q.status != "held":
            raise HTTPException(status_code=409, detail="این سهمیه قبلاً آزاد شده است")
        offer = db.scalar(select(m.Offer).where(m.Offer.id == b.offer_id, m.Offer.tenant_id == user.tenant_id).with_for_update())
        n = min(data.seats or q.seats, q.seats)
        q.seats -= n
        if offer is not None:
            offer.available_units += n
        if q.seats == 0:
            q.status, q.released_reason = "released", "manual"
        a(db, user, "charter.block.allocation_released", {"block_id": b.id, "quota_id": q.id, "seats": n})
        db.commit()
        return {"id": q.id, "seats": q.seats, "status": q.status, "released_now": n}

    @api.get("/agency/{agency_id}/charter/allocations-received")
    def received(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = charterer(db, agency_id, user)
        rows = db.execute(select(SeatQuota, CharterBlock).join(CharterBlock, CharterBlock.instance_id == SeatQuota.instance_id)
                          .where(SeatQuota.tenant_id == user.tenant_id, SeatQuota.agency_id == agency.id).order_by(SeatQuota.release_at)).all()
        return {"items": [{"quota_id": q.id, "flight": f"{b.airline_code}{b.flight_number}", "route": f"{b.origin}-{b.destination}", "departure_at": _iso(b.departure_at),
                           "seats": q.seats, "seats_initial": q.seats_initial, "status": q.status, "release_at": _iso(q.release_at), "offer_id": b.offer_id} for q, b in rows]}

    # ---- staff side -----------------------------------------------------------------------------------------------
    def staff(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("inventory:publish", "tenant:manage", "backoffice:read")):
            raise HTTPException(status_code=403, detail="دسترسی کارکنان لازم است")
        return user

    def publisher(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("inventory:publish", "tenant:manage")):
            raise HTTPException(status_code=403, detail="مجوز انتشار موجودی لازم است")
        return user

    @api.get("/staff/charter/blocks")
    def staff_blocks(status: Optional[str] = None, user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        q = select(CharterBlock).where(CharterBlock.tenant_id == user.tenant_id)
        if status:
            q = q.where(CharterBlock.status == status)
        rows = db.scalars(q.order_by(CharterBlock.created_at.desc()).limit(300)).all()
        return {"items": [out(db, b, staff=True) for b in rows], "domestic_charter_sale": domestic_charter_sale_enabled(),
                "can_publish": any(role_has_permission(user.role, p) for p in ("inventory:publish", "tenant:manage"))}

    @api.get("/staff/charter/blocks/{block_id}/audit")
    def block_audit(block_id: str, user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        from .main import AuditEvent
        block_for(db, user, block_id)
        rows = db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == user.tenant_id, AuditEvent.entity == "charter_block", AuditEvent.detail.contains(block_id))
                          .order_by(AuditEvent.created_at)).all()
        names = {u.id: u.name for u in db.scalars(select(User).where(User.tenant_id == user.tenant_id, User.id.in_({r.actor_id for r in rows})))} if rows else {}
        return {"items": [{"action": r.action, "actor": names.get(r.actor_id), "at": _iso(r.created_at), "detail": json.loads(r.detail or "{}")} for r in rows]}

    @api.post("/staff/charter/blocks/{block_id}/decision")
    def decide(block_id: str, data: DecisionIn, user=Depends(publisher), db: Session = Depends(get_db)) -> dict:
        b = block_for(db, user, block_id, lock=True)
        if b.status != "submitted":
            raise HTTPException(status_code=409, detail="فقط بلوک ارسال‌شده برای بازبینی قابل تصمیم است")
        if b.created_by_user_id == user.id:
            raise HTTPException(status_code=403, detail="ثبت‌کنندهٔ بلوک نمی‌تواند آن را بازبینی کند")
        if data.decision == "reject":
            if not (data.reason or "").strip():
                raise HTTPException(status_code=422, detail="دلیل رد لازم است")
            b.status, b.review_note, b.reviewed_by_user_id, b.reviewed_at = "rejected", data.reason, user.id, utcnow()
            a(db, user, "charter.block.rejected", {"block_id": b.id, "reason": data.reason})
            db.commit()
            return out(db, b, staff=True)
        if b.route_scope == "domestic" and not domestic_charter_sale_enabled():
            raise HTTPException(status_code=409, detail={"code": "CHARTER_DOMESTIC_DISABLED", "message": "فروش چارتر داخلی تا تأیید قانونی غیرفعال است؛ بلوک ثبت می‌ماند ولی منتشر نمی‌شود"})
        require_band_alef(db, user.tenant_id, b.owner_agency_id)
        if _aw(b.release_at) <= utcnow():
            raise HTTPException(status_code=409, detail="زمان release این بلوک گذشته است")
        cap, ref = check_cap(db, user.tenant_id, b.origin, b.destination, b.departure_at, b.net_adult_irr)
        agency = db.scalar(select(m.Agency).where(m.Agency.id == b.owner_agency_id, m.Agency.tenant_id == user.tenant_id).with_for_update())
        supplier = db.scalar(select(m.Supplier).where(m.Supplier.id == agency.supplier_id, m.Supplier.tenant_id == user.tenant_id)) if agency.supplier_id else None
        if supplier is None:
            # Neutral name: the public offer never carries the agency's identity (R-PUB-1).
            supplier = m.Supplier(tenant_id=user.tenant_id, supplier_type="charterer", display_name=f"چارتر همکار {agency.id[:6].upper()}", status="active", lifecycle_status="CONTRACTED")
            db.add(supplier)
            db.flush()
            agency.supplier_id = supplier.id
        route = db.scalar(select(FlightRoute).where(FlightRoute.tenant_id == user.tenant_id, FlightRoute.origin == b.origin, FlightRoute.destination == b.destination))
        if route is None:
            route = FlightRoute(tenant_id=user.tenant_id, origin=b.origin, destination=b.destination, origin_city=b.origin_city, destination_city=b.destination_city, scope=b.route_scope, status="active")
            db.add(route)
            db.flush()
        local = _aw(b.departure_at).astimezone(TEHRAN)
        minutes_before = max(0, int((_aw(b.departure_at) - _aw(b.release_at)).total_seconds() // 60))
        policy = json.loads(b.refund_policy_json or "{}")
        series = FlightSeries(tenant_id=user.tenant_id, route_id=route.id, supplier_id=supplier.id, airline_code=b.airline_code, airline_name=b.airline_name,
                              flight_number=b.flight_number, aircraft=b.aircraft, flight_type="charter", cabin=b.cabin, fare_class=b.fare_class,
                              date_from=local.date().isoformat(), date_to=local.date().isoformat(),
                              schedule_json=json.dumps({str(local.weekday()): {"time": local.strftime("%H:%M"), "duration": int((_aw(b.arrival_at) - _aw(b.departure_at)).total_seconds() // 60)}}),
                              capacity=b.seats_total, adult_fare=b.net_adult_irr, child_fare=b.net_child_irr, infant_fare=b.net_infant_irr, currency="IRR",
                              baggage_kg=b.baggage_kg, stop_sale_minutes=minutes_before, send_list_minutes=360, stop_quota_minutes=minutes_before,
                              refundable=0 if policy.get("non_refundable") else 1, description="بلوک چارتر همکار", status="active")
        db.add(series)
        db.flush()
        inst = FlightInstance(tenant_id=user.tenant_id, series_id=series.id, flight_date=local.date().isoformat(), departure_at=_aw(b.departure_at), arrival_at=_aw(b.arrival_at),
                              capacity=b.seats_total, status="open")
        db.add(inst)
        db.flush()
        _sync_offer(db, user.tenant_id, series, route, inst, utcnow())
        offer = db.get(m.Offer, inst.offer_id)
        attrs = json.loads(offer.attributes_json)
        attrs.update({"charter_block_id": b.id, "route_scope": b.route_scope, "refund_policy": policy})
        offer.attributes_json = json.dumps(attrs, ensure_ascii=False, sort_keys=True)
        b.status, b.review_note, b.reviewed_by_user_id, b.reviewed_at = "published", data.reason, user.id, utcnow()
        b.platform_fee_bps, b.price_cap_unit_irr, b.price_cap_reference = data.platform_fee_bps, cap, ref
        b.instance_id, b.offer_id = inst.id, offer.id
        a(db, user, "charter.block.published", {"block_id": b.id, "instance_id": inst.id, "offer_id": offer.id, "platform_fee_bps": data.platform_fee_bps})
        db.commit()
        return out(db, b, staff=True)

    @api.get("/staff/charter/price-caps")
    def caps(user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        rows = db.scalars(select(PriceCap).where(PriceCap.tenant_id == user.tenant_id).order_by(PriceCap.valid_from.desc())).all()
        return {"items": [{"id": r.id, "origin": r.origin, "destination": r.destination, "valid_from": r.valid_from.isoformat(), "valid_to": r.valid_to.isoformat(),
                           "cap_unit_irr": r.cap_unit_irr, "legal_reference": r.legal_reference, "status": r.status} for r in rows],
                "can_edit": role_has_permission(user.role, "tenant:manage")}

    @api.post("/staff/charter/price-caps", status_code=201)
    def add_cap(data: CapIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        if not role_has_permission(user.role, "tenant:manage"):
            raise HTTPException(status_code=403, detail="ثبت سقف قیمت با مدیر مجموعه است")
        if data.valid_from > data.valid_to:
            raise HTTPException(status_code=422, detail="بازهٔ تاریخ نامعتبر است")
        r = PriceCap(tenant_id=user.tenant_id, origin=data.origin.upper(), destination=data.destination.upper(), valid_from=data.valid_from, valid_to=data.valid_to,
                     cap_unit_irr=data.cap_unit_irr, legal_reference=data.legal_reference.strip(), status="active", created_by_user_id=user.id)
        db.add(r)
        db.flush()
        a(db, user, "charter.price_cap.created", {"cap_id": r.id, "route": f"{r.origin}-{r.destination}", "cap_unit_irr": r.cap_unit_irr, "reference": r.legal_reference})
        db.commit()
        return {"id": r.id}

    return api


__all__ = ["CharterBlock", "PriceCap", "applicable_cap", "cap_for", "take_agency_quota", "charter_blocks_router", "domestic_charter_sale_enabled", "SOURCES", "half_up"]
