"""Panels Phase 2b — charter schedule change and cancellation (CH-03 «اعلام اختلال») with impact preview and agency notices.

* Staff with `inventory:publish` (or the tenant admin) record a time/date change (old → new, reason) or a cancellation of a
  published charter block. `POST …/schedule-change/preview` computes the impact without writing anything: allocations per
  agency, bookings and passengers per agency (sold on agency credit), public (B2C) bookings and passengers, and — for a
  cancellation — the amount that would go back to agency credit. `POST …/schedule-change` (Idempotency-Key, request hash)
  records the change (append-only `charter_schedule_changes`) and applies it.
* Change: block, dated flight instance and the public offer get the new times (the offer is re-synced through the normal
  inventory path); held allocations follow the release time. Every affected agency booking gets a notice
  (`charter_change_notices`, status `pending`): the agency accepts it or asks for a refund. The block rule
  «لغو یا تأخیر بیش از ۲ ساعت = استرداد کامل» decides: a shift of more than 2 hours (or another date) allows a full refund to
  agency credit; a smaller shift does not (the normal cancel/refund request path stays open).
* Cancel: the block, instance and offer close; allocations are released; every agency booking gets a notice with a full
  refund to agency credit queued through maker-checker (`agency.credit_refund`, a finance user ≠ the staff user approves);
  every public booking gets a cancel service request in the existing after-sales queue (ops then approve the full refund and
  two finance users pay it). No money moves here.
* Notifications go to the in-app notification table and the outbox only (no SMS is sent).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import approvals
from . import operations as m
from .agency_b2b import AgencyBookingLine, agency_membership
from .agency_settlement import credit_remaining, notify_agency, queue_credit_refund
from .charter_blocks import TEHRAN, CharterBlock
from .database import Base
from .operations import OperationalMixin

FULL_REFUND_SHIFT_MINUTES = 120  # block policy carrier_cancel_or_delay_over_2h = full_refund
ACTIVE_RES = ("reserved", "awaiting_payment", "confirmed", "issued", "changed")
NOTICE_FA = {"pending": "منتظر پاسخ آژانس", "accepted": "پذیرفته شد", "refund_pending": "بازگشت به اعتبار در انتظار تأیید مالی",
             "refunded": "به اعتبار آژانس برگشت", "refund_rejected": "بازگشت به اعتبار رد شد یا منقضی شد", "informed": "اطلاع داده شد", "service_request": "درخواست لغو در صف عملیات"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: Optional[datetime]) -> Optional[datetime]:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def _iso(v) -> Optional[str]:
    return _aw(v).isoformat() if isinstance(v, datetime) else None


class CharterScheduleChange(OperationalMixin, Base):
    """Append-only record of one confirmed change or cancellation of a charter block."""
    __tablename__ = "charter_schedule_changes"
    block_id: Mapped[str] = mapped_column(ForeignKey("charter_blocks.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # change | cancel
    old_departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    old_arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    new_departure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    new_arrival_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    shift_minutes: Mapped[int] = mapped_column(Integer, default=0)
    full_refund_eligible: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text)
    impact_json: Mapped[str] = mapped_column(Text, default="{}")
    idempotency_key: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_charter_change_key"),)


class CharterChangeNotice(OperationalMixin, Base):
    __tablename__ = "charter_change_notices"
    change_id: Mapped[str] = mapped_column(ForeignKey("charter_schedule_changes.id"), index=True)
    block_id: Mapped[str] = mapped_column(ForeignKey("charter_blocks.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    agency_id: Mapped[Optional[str]] = mapped_column(ForeignKey("agencies.id"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    booking_line_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    passengers: Mapped[int] = mapped_column(Integer, default=0)
    seats_held: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    credit_refund_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    service_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    responded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


TABLES = ("charter_schedule_changes", "charter_change_notices")
APPEND_ONLY = ("charter_schedule_changes",)


class Strict(BaseModel):
    model_config = {"extra": "forbid"}


class ChangeIn(Strict):
    kind: str = Field(pattern="^(change|cancel)$")
    new_departure_at: Optional[datetime] = None
    new_arrival_at: Optional[datetime] = None
    new_release_at: Optional[datetime] = None
    reason: str = Field(min_length=5, max_length=1000)


class RespondIn(Strict):
    note: Optional[str] = Field(default=None, max_length=500)


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def charter_changes_router(get_db, current_user, role_has_permission, User, audit: Callable) -> APIRouter:
    from . import after_sales as A
    from .charter_quotas import SeatQuota
    from .inventory import FlightInstance, FlightRoute, FlightSeries, _sync_offer

    api = APIRouter(tags=["charter-changes"])

    def publisher(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("inventory:publish", "tenant:manage")):
            raise HTTPException(status_code=403, detail="مجوز انتشار و تغییر موجودی لازم است")
        return user

    def staff(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("inventory:publish", "tenant:manage", "backoffice:read")):
            raise HTTPException(status_code=403, detail="دسترسی کارکنان لازم است")
        return user

    def block_for(db: Session, user, block_id: str, lock: bool = False) -> CharterBlock:
        q = select(CharterBlock).where(CharterBlock.id == block_id, CharterBlock.tenant_id == user.tenant_id)
        b = db.scalar(q.with_for_update() if lock else q)
        if b is None:
            raise HTTPException(status_code=404, detail="بلوک صندلی یافت نشد")
        return b

    def validate(b: CharterBlock, data: ChangeIn) -> dict:
        if b.status != "published" or not b.instance_id:
            raise HTTPException(status_code=409, detail="تغییر یا لغو فقط برای بلوک منتشرشده ثبت می‌شود")
        if _aw(b.departure_at) <= utcnow():
            raise HTTPException(status_code=409, detail="پرواز انجام شده است")
        if data.kind == "cancel":
            return {"shift_minutes": 0, "full_refund_eligible": True}
        if data.new_departure_at is None or data.new_arrival_at is None:
            raise HTTPException(status_code=422, detail="زمان حرکت و رسیدن تازه لازم است")
        dep, arr = _aw(data.new_departure_at), _aw(data.new_arrival_at)
        if dep <= utcnow():
            raise HTTPException(status_code=422, detail="زمان حرکت تازه گذشته است")
        if arr <= dep or arr - dep > timedelta(hours=20):
            raise HTTPException(status_code=422, detail="زمان رسیدن تازه نامعتبر است")
        if dep == _aw(b.departure_at) and arr == _aw(b.arrival_at):
            raise HTTPException(status_code=422, detail="زمان تازه با زمان فعلی یکسان است")
        release = _aw(data.new_release_at) if data.new_release_at else _aw(b.release_at)
        if release >= dep:
            raise HTTPException(status_code=422, detail="زمان release باید پیش از حرکت تازه باشد؛ release تازه را وارد کنید")
        if data.new_release_at and release <= utcnow():
            raise HTTPException(status_code=422, detail="release تازه گذشته است")
        shift = int(abs((dep - _aw(b.departure_at)).total_seconds()) // 60)
        other_day = dep.astimezone(TEHRAN).date() != _aw(b.departure_at).astimezone(TEHRAN).date()
        return {"shift_minutes": shift, "full_refund_eligible": shift > FULL_REFUND_SHIFT_MINUTES or other_day, "other_day": other_day}

    def impact(db: Session, b: CharterBlock, kind: str) -> dict:
        t = b.tenant_id
        quotas = db.scalars(select(SeatQuota).where(SeatQuota.tenant_id == t, SeatQuota.instance_id == b.instance_id)).all()
        lines = db.scalars(select(AgencyBookingLine).where(AgencyBookingLine.tenant_id == t, AgencyBookingLine.offer_id == b.offer_id,
                                                           AgencyBookingLine.status == "captured")).all()
        res = {r.id: r for r in db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == t, m.Reservation.id.in_({x.reservation_id for x in lines if x.reservation_id})))} if lines else {}
        agency_res = {x.reservation_id for x in lines}
        b2c = db.execute(select(m.Reservation, m.PriceCheck.units).join(m.PriceCheck, m.PriceCheck.id == m.Reservation.price_check_id)
                         .where(m.Reservation.tenant_id == t, m.PriceCheck.tenant_id == t, m.PriceCheck.offer_id == b.offer_id, m.Reservation.status.in_(ACTIVE_RES))).all()
        b2c = [(r, u) for r, u in b2c if r.id not in agency_res]
        agencies: dict[str, dict] = {}
        ids = {q.agency_id for q in quotas} | {x.agency_id for x in lines}
        names = dict(db.execute(select(m.Agency.id, m.Agency.display_name).where(m.Agency.tenant_id == t, m.Agency.id.in_(ids))).all()) if ids else {}
        for aid in ids:
            agencies[aid] = {"agency_id": aid, "agency_name": names.get(aid), "allocation_held": 0, "allocation_initial": 0, "bookings": 0, "passengers": 0,
                             "net_irr": 0, "refundable_to_credit_irr": 0, "booking_refs": []}
        for q in quotas:
            a = agencies[q.agency_id]
            a["allocation_held"] += q.seats if q.status == "held" else 0
            a["allocation_initial"] += q.seats_initial
        active_lines = []
        for x in lines:
            r = res.get(x.reservation_id)
            if r is None or r.status not in ACTIVE_RES:
                continue
            active_lines.append(x)
            a = agencies[x.agency_id]
            a["bookings"] += 1
            a["passengers"] += x.units
            a["net_irr"] += x.net_irr
            a["refundable_to_credit_irr"] += credit_remaining(db, x)
            a["booking_refs"].append(r.booking_reference)
        owner = names.get(b.owner_agency_id) or db.scalar(select(m.Agency.display_name).where(m.Agency.id == b.owner_agency_id))
        items = sorted(agencies.values(), key=lambda a: -(a["passengers"] + a["allocation_held"]))
        return {"block_id": b.id, "kind": kind, "flight": f"{b.airline_code}{b.flight_number}", "route": f"{b.origin}-{b.destination}", "owner_agency": owner,
                "agencies": items, "agency_bookings": len(active_lines), "agency_passengers": sum(x.units for x in active_lines),
                "public_bookings": len(b2c), "public_passengers": sum(int(u or 1) for _, u in b2c),
                "passengers_total": sum(x.units for x in active_lines) + sum(int(u or 1) for _, u in b2c),
                "allocations_held": sum(a["allocation_held"] for a in items),
                "refund_to_agency_credit_irr": sum(a["refundable_to_credit_irr"] for a in items) if kind == "cancel" else 0,
                "_lines": active_lines, "_b2c": b2c, "_quotas": quotas}

    def public(i: dict) -> dict:
        return {k: v for k, v in i.items() if not k.startswith("_")}

    @api.post("/staff/charter/blocks/{block_id}/schedule-change/preview")
    def preview(block_id: str, data: ChangeIn, user=Depends(publisher), db: Session = Depends(get_db)) -> dict:
        b = block_for(db, user, block_id)
        rule = validate(b, data)
        out = {**public(impact(db, b, data.kind)), **rule, "old_departure_at": _iso(b.departure_at), "old_arrival_at": _iso(b.arrival_at),
               "new_departure_at": _iso(_aw(data.new_departure_at)) if data.new_departure_at else None, "new_arrival_at": _iso(_aw(data.new_arrival_at)) if data.new_arrival_at else None,
               "money_moves": False, "note": "پیش‌نمایش است و چیزی ثبت نمی‌شود. هیچ مبلغی بدون تأیید کارشناس مالی دوم جابه‌جا نمی‌شود."}
        db.rollback()
        return out

    def can_apply(actor, _payload) -> bool:
        return any(role_has_permission(actor.role, p) for p in ("inventory:publish", "tenant:manage"))

    def _execute(db: Session, request, payload: dict, checker) -> dict:
        data = ChangeIn.model_validate(payload["change"])
        try:
            ch = apply_change(db, checker, payload["block_id"], data, f"mc:{request.id}", payload["request_hash"], request.maker_user_id)
        except HTTPException as exc:
            d = exc.detail
            raise ValueError(d.get("message") if isinstance(d, dict) else str(d)) from exc
        return {"change_id": ch.id, "kind": ch.kind}

    approvals.register("charter.schedule_change", can_check=can_apply, execute=_execute, label="تغییر یا لغو پرواز چارتر")

    @api.post("/staff/charter/blocks/{block_id}/schedule-change", status_code=202)
    def confirm(block_id: str, data: ChangeIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                user=Depends(publisher), db: Session = Depends(get_db)) -> dict:
        """Maker: validates and records a maker-checker request. Nothing changes until a second staff user approves it."""
        h = _hash({"block_id": block_id, **data.model_dump(mode="json")})
        b = block_for(db, user, block_id)
        validate(b, data)
        pending = [r for r in db.scalars(select(approvals.MakerCheckerRequest).where(approvals.MakerCheckerRequest.tenant_id == user.tenant_id,
                                                                                        approvals.MakerCheckerRequest.kind == "charter.schedule_change",
                                                                                        approvals.MakerCheckerRequest.target_ref == f"charter_block:{b.id}",
                                                                                        approvals.MakerCheckerRequest.status == "pending"))
                   if _aw(r.expires_at) > utcnow() and r.idempotency_key != idempotency_key]
        if pending:
            raise HTTPException(status_code=409, detail="برای این پرواز یک تغییر یا لغو در انتظار تأیید نفر دوم است")
        flight = f"{b.airline_code}{b.flight_number} {b.origin}-{b.destination}"
        try:
            r = approvals.create_request(db, user=user, kind="charter.schedule_change", idempotency_key=idempotency_key,
                                         payload={"block_id": b.id, "change": data.model_dump(mode="json"), "request_hash": h},
                                         summary=f"{'لغو' if data.kind == 'cancel' else 'تغییر زمان'} پرواز چارتر {flight}", target_ref=f"charter_block:{b.id}", audit=audit)
        except approvals.MakerCheckerError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        audit(db, user, "charter.block.change_requested", "charter_block", {"block_id": b.id, "kind": data.kind, "mc_request_id": r.id})
        db.commit()
        return {"request_id": r.id, "status": r.status, "kind": data.kind, "message": "درخواست ثبت شد و پس از تأیید کارشناس دوم اعمال می‌شود."}

    def apply_change(db: Session, user, block_id: str, data: ChangeIn, idempotency_key: str, h: str, maker_id: int) -> CharterScheduleChange:
        """Runs inside the checker's approval: re-validates against the block as it is now, then records and applies the change."""
        b = block_for(db, user, block_id, lock=True)
        rule = validate(b, data)
        imp = impact(db, b, data.kind)
        now = utcnow()
        ch = CharterScheduleChange(tenant_id=user.tenant_id, block_id=b.id, kind=data.kind, old_departure_at=_aw(b.departure_at), old_arrival_at=_aw(b.arrival_at),
                                   new_departure_at=_aw(data.new_departure_at) if data.kind == "change" else None,
                                   new_arrival_at=_aw(data.new_arrival_at) if data.kind == "change" else None, shift_minutes=rule["shift_minutes"],
                                   full_refund_eligible=1 if rule["full_refund_eligible"] else 0, reason=data.reason.strip(),
                                   impact_json=json.dumps(public(imp), ensure_ascii=False, default=str), idempotency_key=idempotency_key, request_hash=h, created_by_user_id=maker_id)
        db.add(ch)
        db.flush()
        inst = db.get(FlightInstance, b.instance_id)
        offer = db.scalar(select(m.Offer).where(m.Offer.id == b.offer_id, m.Offer.tenant_id == user.tenant_id).with_for_update())
        series = db.get(FlightSeries, inst.series_id)
        route = db.get(FlightRoute, series.route_id)
        flight = f"{b.airline_code}{b.flight_number} {b.origin}-{b.destination}"
        if data.kind == "change":
            dep, arr = _aw(data.new_departure_at), _aw(data.new_arrival_at)
            b.departure_at, b.arrival_at = dep, arr
            if data.new_release_at:
                b.release_at = _aw(data.new_release_at)
            local = dep.astimezone(TEHRAN)
            inst.departure_at, inst.arrival_at, inst.flight_date = dep, arr, local.date().isoformat()
            series.date_from = series.date_to = local.date().isoformat()
            series.schedule_json = json.dumps({str(local.weekday()): {"time": local.strftime("%H:%M"), "duration": int((arr - dep).total_seconds() // 60)}})
            series.stop_sale_minutes = series.stop_quota_minutes = max(0, int((dep - _aw(b.release_at)).total_seconds() // 60))
            _sync_offer(db, user.tenant_id, series, route, inst, now)
            attrs = json.loads(offer.attributes_json or "{}")
            attrs.update({"charter_block_id": b.id, "route_scope": b.route_scope, "refund_policy": json.loads(b.refund_policy_json or "{}"), "schedule_changed_at": now.isoformat()})
            offer.attributes_json = json.dumps(attrs, ensure_ascii=False, sort_keys=True)
            for q in imp["_quotas"]:
                if q.status == "held":
                    q.release_at = _aw(b.release_at)
            when = dep.astimezone(TEHRAN).strftime("%Y-%m-%d %H:%M")
            msg = f"زمان پرواز {flight} به {when} (به وقت تهران) تغییر کرد. دلیل: {ch.reason}"
        else:
            b.status = "cancelled"
            inst.status = "cancelled"
            if offer is not None:
                offer.status, offer.available_units = "inactive", 0
            for q in imp["_quotas"]:
                if q.status == "held":
                    q.seats, q.status, q.released_reason = 0, "released", "charter_cancelled"
            msg = f"پرواز {flight} لغو شد. دلیل: {ch.reason}"
        notices = []
        booked_agencies = set()
        for line in imp["_lines"]:
            booked_agencies.add(line.agency_id)
            n = CharterChangeNotice(tenant_id=user.tenant_id, change_id=ch.id, block_id=b.id, kind=data.kind, agency_id=line.agency_id, user_id=line.booked_by_user_id,
                                    reservation_id=line.reservation_id, booking_line_id=line.id, passengers=line.units, status="pending")
            db.add(n)
            db.flush()
            if data.kind == "cancel":
                amount = credit_remaining(db, line)
                if amount > 0:
                    row = queue_credit_refund(db, user=user, line=line, amount=amount, penalty=0, source="charter_cancel", key=f"charter-cancel:{n.id}", audit=audit,
                                              charter_notice_id=n.id, note=f"لغو پرواز چارتر {flight}")
                    n.status, n.credit_refund_id = "refund_pending", row.id
                else:
                    n.status = "informed"
            notices.append(n)
            db.add(m.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="charter_change_notice", aggregate_id=n.id, event_type=f"charter.{data.kind}.notice",
                                 payload_json=json.dumps({"agency_id": line.agency_id, "reservation_id": line.reservation_id, "change_id": ch.id}),
                                 correlation_id=str(uuid.uuid4()), idempotency_key=f"ccn:{n.id}"))
        for a in imp["agencies"]:  # allocation-only agencies are informed too
            if a["agency_id"] not in booked_agencies and a["allocation_initial"]:
                db.add(CharterChangeNotice(tenant_id=user.tenant_id, change_id=ch.id, block_id=b.id, kind=data.kind, agency_id=a["agency_id"],
                                           seats_held=a["allocation_held"], status="informed"))
        for aid in {a["agency_id"] for a in imp["agencies"]} | {b.owner_agency_id}:
            notify_agency(db, user.tenant_id, aid, title="تغییر در پرواز چارتر" if data.kind == "change" else "لغو پرواز چارتر", message=msg,
                          link="/agency/inventory/notices", event_type=f"charter.{data.kind}", aggregate_type="charter_schedule_change", aggregate_id=ch.id,
                          key=f"csc:{ch.id}:{aid[:8]}", payload={"block_id": b.id})
        for r, units in imp["_b2c"]:
            n = CharterChangeNotice(tenant_id=user.tenant_id, change_id=ch.id, block_id=b.id, kind=data.kind, user_id=r.user_id, reservation_id=r.id,
                                    passengers=int(units or 1), status="informed")
            db.add(n)
            db.flush()
            if data.kind == "cancel" and r.status in ("reserved", "awaiting_payment", "confirmed", "issued") and not db.scalar(
                    select(m.BookingServiceRequest.id).where(m.BookingServiceRequest.tenant_id == user.tenant_id, m.BookingServiceRequest.reservation_id == r.id,
                                                             m.BookingServiceRequest.status.in_(A.OPEN_STATUSES))):
                n.service_request_id, n.status = _cancel_request(db, user, r, ch, flight), "service_request"
            db.add(m.NotificationRecord(tenant_id=user.tenant_id, user_id=r.user_id, topic="trip_change", title="تغییر در پرواز شما" if data.kind == "change" else "لغو پرواز شما",
                                        message=msg + ("" if data.kind == "change" else " درخواست استرداد کامل برای شما ثبت شد و کارشناس پیگیری می‌کند."),
                                        deep_link=f"/account/refunds/{n.service_request_id}" if n.service_request_id else "/account/bookings"))
            db.add(m.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="charter_change_notice", aggregate_id=n.id, event_type=f"charter.{data.kind}.customer_notice",
                                 payload_json=json.dumps({"reservation_id": r.id, "change_id": ch.id}), correlation_id=str(uuid.uuid4()), idempotency_key=f"ccn:{n.id}"))
        audit(db, user, f"charter.block.{'schedule_changed' if data.kind == 'change' else 'cancelled'}", "charter_block",
              {"block_id": b.id, "change_id": ch.id, "shift_minutes": ch.shift_minutes, "notices": len(notices), "public_bookings": len(imp["_b2c"]), "maker_user_id": maker_id})
        return ch

    def _cancel_request(db: Session, user, r: m.Reservation, ch: CharterScheduleChange, flight: str) -> str:
        """Cancel request in the existing after-sales queue on the customer's behalf (carrier cancellation → full refund by ops + two finance users)."""
        req = m.BookingServiceRequest(tenant_id=r.tenant_id, reservation_id=r.id, request_type="cancel", status="submitted",
                                      quote_snapshot_json=json.dumps({"status": "carrier_cancelled", "charter_change_id": ch.id}), reason=f"لغو پرواز چارتر {flight}: {ch.reason}"[:1000])
        db.add(req)
        db.flush()
        prior = r.status
        m.transition_reservation(db, r, "cancel_requested", user.id, f"csc:{ch.id}:{r.id}:cancel_requested")
        db.add(A.ServiceRequestHandling(tenant_id=r.tenant_id, request_id=req.id, reservation_id=r.id, customer_user_id=r.user_id, prior_reservation_status=prior,
                                        refund_destination="wallet", destination_json="{}"))
        A.record_event(db, req=req, event_type="submitted", actor_kind="system", actor_id=user.id, to_status="submitted", note=req.reason,
                       payload={"request_type": "cancel", "carrier_cancel": True, "charter_change_id": ch.id}, command_id=f"csc-sr:{ch.id}:{r.id}")
        return req.id

    def change_out(db: Session, ch: CharterScheduleChange) -> dict:
        notices = db.scalars(select(CharterChangeNotice).where(CharterChangeNotice.tenant_id == ch.tenant_id, CharterChangeNotice.change_id == ch.id)).all()
        return {"id": ch.id, "block_id": ch.block_id, "kind": ch.kind, "old_departure_at": _iso(ch.old_departure_at), "old_arrival_at": _iso(ch.old_arrival_at),
                "new_departure_at": _iso(ch.new_departure_at), "new_arrival_at": _iso(ch.new_arrival_at), "shift_minutes": ch.shift_minutes,
                "full_refund_eligible": bool(ch.full_refund_eligible), "reason": ch.reason, "impact": json.loads(ch.impact_json or "{}"), "created_at": _iso(ch.created_at),
                "notices": [notice_out(db, n) for n in notices]}

    def notice_out(db: Session, n: CharterChangeNotice) -> dict:
        from .agency_settlement import AgencyCreditRefund, refund_out
        b = db.get(CharterBlock, n.block_id)
        ch = db.get(CharterScheduleChange, n.change_id)
        res = db.get(m.Reservation, n.reservation_id) if n.reservation_id else None
        refund = db.get(AgencyCreditRefund, n.credit_refund_id) if n.credit_refund_id else None
        status = n.status
        if refund is not None:
            r = refund_out(db, refund)
            status = {"executed": "refunded", "pending_approval": "refund_pending"}.get(r["status"], "refund_rejected")
        return {"id": n.id, "change_id": n.change_id, "block_id": n.block_id, "kind": n.kind, "agency_id": n.agency_id, "reservation_id": n.reservation_id,
                "booking_reference": res.booking_reference if res else None, "passengers": n.passengers,
                "amount_irr": (db.get(AgencyBookingLine, n.booking_line_id).net_irr if n.booking_line_id else None), "seats_held": n.seats_held, "status": status,
                "status_label": NOTICE_FA.get(status, status), "flight": f"{b.airline_code}{b.flight_number}" if b else None, "route": f"{b.origin}-{b.destination}" if b else None,
                "old_departure_at": _iso(ch.old_departure_at) if ch else None, "new_departure_at": _iso(ch.new_departure_at) if ch else None,
                "shift_minutes": ch.shift_minutes if ch else None, "full_refund_eligible": bool(ch.full_refund_eligible) if ch else False, "reason": ch.reason if ch else None,
                "credit_refund": refund_out(db, refund) if refund else None, "service_request_id": n.service_request_id,
                "can_respond": n.status == "pending" and n.kind == "change" and n.booking_line_id is not None,
                "can_request_refund": n.status == "pending" and n.kind == "change" and n.booking_line_id is not None and bool(ch and ch.full_refund_eligible),
                "responded_at": _iso(n.responded_at), "response_note": n.response_note, "created_at": _iso(n.created_at)}

    @api.get("/staff/charter/blocks/{block_id}/schedule-changes")
    def staff_changes(block_id: str, user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        b = block_for(db, user, block_id)
        rows = db.scalars(select(CharterScheduleChange).where(CharterScheduleChange.tenant_id == user.tenant_id, CharterScheduleChange.block_id == b.id)
                          .order_by(CharterScheduleChange.created_at.desc())).all()
        reqs = [approvals.output(r) for r in db.scalars(select(approvals.MakerCheckerRequest).where(
            approvals.MakerCheckerRequest.tenant_id == user.tenant_id, approvals.MakerCheckerRequest.kind == "charter.schedule_change",
            approvals.MakerCheckerRequest.target_ref == f"charter_block:{b.id}").order_by(approvals.MakerCheckerRequest.created_at.desc()))]
        for r in reqs:
            if r["status"] == "pending" and r["expires_at"] and datetime.fromisoformat(r["expires_at"]) <= utcnow():
                r["status"] = "expired"
            r["can_decide"] = r["status"] == "pending" and r["maker_user_id"] != user.id and can_apply(user, {})
            r["mine"] = r["maker_user_id"] == user.id
        out = {"items": [change_out(db, c) for c in rows], "block_status": b.status, "requests": reqs, "me": user.id,
               "can_change": any(role_has_permission(user.role, p) for p in ("inventory:publish", "tenant:manage"))}
        db.commit()
        return out

    @api.get("/agency/{agency_id}/charter/blocks/{block_id}/schedule-changes")
    def owner_changes(agency_id: str, block_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = agency_membership(db, agency_id, user, role_has_permission)
        b = db.scalar(select(CharterBlock).where(CharterBlock.id == block_id, CharterBlock.tenant_id == user.tenant_id, CharterBlock.owner_agency_id == agency.id))
        if b is None:
            raise HTTPException(status_code=404, detail="بلوک صندلی یافت نشد")
        rows = db.scalars(select(CharterScheduleChange).where(CharterScheduleChange.tenant_id == user.tenant_id, CharterScheduleChange.block_id == b.id)
                          .order_by(CharterScheduleChange.created_at.desc())).all()
        items = [{k: v for k, v in change_out(db, c).items() if k != "notices"} for c in rows]
        db.commit()
        return {"items": items}

    @api.get("/agency/{agency_id}/charter/notices")
    def agency_notices(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = agency_membership(db, agency_id, user, role_has_permission)
        rows = db.scalars(select(CharterChangeNotice).where(CharterChangeNotice.tenant_id == user.tenant_id, CharterChangeNotice.agency_id == agency.id)
                          .order_by(CharterChangeNotice.created_at.desc()).limit(300)).all()
        items = [notice_out(db, n) for n in rows]
        db.commit()
        return {"items": items, "member_role": role, "pending": sum(1 for i in items if i["can_respond"])}

    def own_notice(db: Session, user, agency_id: str, nid: str) -> CharterChangeNotice:
        agency, role = agency_membership(db, agency_id, user, role_has_permission)
        if role == "staff":
            raise HTTPException(status_code=403, detail="پاسخ به اطلاعیه با اعضای آژانس است")
        n = db.scalar(select(CharterChangeNotice).where(CharterChangeNotice.id == nid, CharterChangeNotice.tenant_id == user.tenant_id,
                                                        CharterChangeNotice.agency_id == agency.id).with_for_update())
        if n is None:
            raise HTTPException(status_code=404, detail="اطلاعیه یافت نشد")
        return n

    @api.post("/agency/{agency_id}/charter/notices/{nid}/accept")
    def accept(agency_id: str, nid: str, data: RespondIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        n = own_notice(db, user, agency_id, nid)
        if n.status == "accepted":
            return notice_out(db, n)
        if n.status != "pending" or n.kind != "change" or n.booking_line_id is None:
            raise HTTPException(status_code=409, detail="این اطلاعیه منتظر پاسخ نیست")
        n.status, n.responded_by_user_id, n.responded_at, n.response_note = "accepted", user.id, utcnow(), data.note
        db.add(m.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="charter_change_notice", aggregate_id=n.id, event_type="charter.change.accepted",
                             payload_json=json.dumps({"agency_id": n.agency_id, "reservation_id": n.reservation_id}), correlation_id=str(uuid.uuid4()), idempotency_key=f"ccn-acc:{n.id}"))
        audit(db, user, "charter.notice.accepted", "charter_block", {"block_id": n.block_id, "notice_id": n.id, "agency_id": n.agency_id})
        db.commit()
        return notice_out(db, n)

    @api.post("/agency/{agency_id}/charter/notices/{nid}/refund-request", status_code=202)
    def refund_request(agency_id: str, nid: str, data: RespondIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                       user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        n = own_notice(db, user, agency_id, nid)
        if n.status == "refund_pending" and n.credit_refund_id:
            return notice_out(db, n)
        if n.status != "pending" or n.kind != "change" or n.booking_line_id is None:
            raise HTTPException(status_code=409, detail="این اطلاعیه منتظر پاسخ نیست")
        ch = db.get(CharterScheduleChange, n.change_id)
        if not ch.full_refund_eligible:
            raise HTTPException(status_code=409, detail={"code": "SHIFT_BELOW_POLICY", "message": "طبق قاعدهٔ بلوک فقط تغییر بیش از ۲ ساعت (یا تغییر روز) استرداد کامل دارد؛ "
                                                                                                   "برای استرداد عادی از مسیر لغو و استرداد رزرو اقدام کنید."})
        line = db.get(AgencyBookingLine, n.booking_line_id)
        amount = credit_remaining(db, line)
        if amount <= 0:
            raise HTTPException(status_code=409, detail="مبلغی برای بازگشت به اعتبار باقی نمانده است")
        try:
            row = queue_credit_refund(db, user=user, line=line, amount=amount, penalty=0, source="charter_change", key=f"charter-change:{n.id}", audit=audit,
                                      charter_notice_id=n.id, note=data.note or "درخواست استرداد پس از تغییر زمان پرواز")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        n.status, n.credit_refund_id, n.responded_by_user_id, n.responded_at, n.response_note = "refund_pending", row.id, user.id, utcnow(), data.note
        audit(db, user, "charter.notice.refund_requested", "charter_block", {"block_id": n.block_id, "notice_id": n.id, "credit_refund_id": row.id, "amount_irr": amount})
        db.commit()
        return notice_out(db, n)

    return api


__all__ = ["CharterScheduleChange", "CharterChangeNotice", "TABLES", "APPEND_ONLY", "charter_changes_router", "FULL_REFUND_SHIFT_MINUTES"]
