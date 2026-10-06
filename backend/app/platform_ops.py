"""Trip Operations Center, unified trip change log, support workspace and finance/supplier read models.

One source of truth: `trip_events`. Customers, support and operations read the same rows through the same
serializer (staff additionally see internal events and the acting user). Nothing here infers a change: an
event exists only because a person or an integration recorded it, with its old and new value.
Every query is tenant-scoped; customer routes are additionally owner-scoped.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Callable, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import operations as m

CATEGORIES = {"schedule_change": "تغییر زمان‌بندی", "cancellation": "لغو", "hotel_change": "تغییر هتل", "room_change": "تغییر اتاق", "transfer_change": "تغییر ترانسفر", "tour_change": "تغییر تور",
              "document_change": "تغییر مدارک", "payment_issue": "مشکل پرداخت", "supplier_issue": "مشکل تأمین‌کننده", "support_intervention": "اقدام پشتیبانی"}
NEEDS_BOTH = {"schedule_change", "hotel_change", "room_change", "transfer_change", "tour_change", "document_change"}
SEVERITIES = ("info", "warning", "critical")
SOURCES = ("human_agent", "supplier", "provider", "system", "support")
STAFF_READ = ("trip:event:create", "support:manage", "backoffice:read")
Values = Optional[dict[str, str]]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TripEventIn(Strict):
    command_id: str = Field(min_length=8, max_length=80)
    category: Literal[tuple(CATEGORIES)]  # type: ignore[valid-type]
    severity: Literal[SEVERITIES] = "warning"  # type: ignore[valid-type]
    source: Literal[SOURCES] = "human_agent"  # type: ignore[valid-type]
    reservation_id: Optional[str] = Field(default=None, max_length=36)
    old_value: Values = None
    new_value: Values = None
    reason: str = Field(min_length=3, max_length=500)
    requires_action: bool = False
    visibility: Literal["customer", "internal"] = "customer"
    effective_at: Optional[datetime] = None

    @field_validator("old_value", "new_value")
    @classmethod
    def bounded(cls, v: Values) -> Values:
        if v is None: return None
        if not v or len(v) > 12 or any(not k.strip() or len(k) > 60 or not str(x).strip() or len(str(x)) > 300 for k, x in v.items()): raise ValueError("مقادیر تغییر باید ۱ تا ۱۲ فیلد متنی کوتاه باشند")
        return {k.strip(): str(x).strip() for k, x in v.items()}


class NoteIn(Strict):
    body: str = Field(min_length=2, max_length=4000)


class AgencyMemberIn(Strict):
    user_id: int = Field(gt=0)


class AgencyChannelIn(Strict):
    sales_channel_id: Optional[str] = Field(default=None, min_length=36, max_length=36)


class EscalateIn(Strict):
    reason: str = Field(min_length=3, max_length=500)
    severity: Literal["HIGH", "CRITICAL"] = "HIGH"


def _load(text: Optional[str]) -> Optional[dict]:
    return json.loads(text) if text else None


def event_out(e: m.TripEventRecord, staff: bool, actors: Optional[dict] = None) -> dict:
    data = {"id": e.id, "trip_id": e.trip_id, "reservation_id": e.reservation_id, "type": e.event_type, "category": e.change_category, "category_fa": CATEGORIES.get(e.change_category or ""),
            "severity": e.severity, "source": e.source, "title": e.title, "message": e.message, "old_value": _load(e.old_value_json), "new_value": _load(e.new_value_json),
            "affected_reference": e.affected_reference, "requires_action": e.requires_action, "deep_link": e.deep_link, "created_at": e.created_at.isoformat(),
            "effective_at": e.effective_at.isoformat() if e.effective_at else None, "acknowledged": e.acknowledged_at is not None, "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else None}
    if staff:
        data.update({"visibility": e.visibility, "actor": (actors or {}).get(e.actor_user_id) if e.actor_user_id else None, "acknowledged_by_user_id": e.acknowledged_by_user_id})
    return data


def platform_ops_router(get_db, current_user, require_permission, role_has_permission, supplier_scope: Callable, audit: Callable, User) -> APIRouter:
    router = APIRouter(tags=["platform-ops"])

    def staff(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in STAFF_READ): raise HTTPException(status_code=403, detail="مجوز لازم برای این اقدام وجود ندارد")
        return user

    def actors_for(db: Session, events) -> dict:
        ids = {e.actor_user_id for e in events if e.actor_user_id}
        return {u.id: {"id": u.id, "name": u.name, "role": u.role} for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}

    def own_trip(db: Session, trip_id: str, user) -> m.Trip:
        trip = db.scalar(select(m.Trip).where(m.Trip.id == trip_id, m.Trip.tenant_id == user.tenant_id, m.Trip.user_id == user.id))
        if trip is None: raise HTTPException(status_code=404, detail="سفر در این حساب وجود ندارد")
        return trip

    def tenant_trip(db: Session, trip_id: str, user, lock: bool = False) -> m.Trip:
        stmt = select(m.Trip).where(m.Trip.id == trip_id, m.Trip.tenant_id == user.tenant_id)
        trip = db.scalar(stmt.with_for_update() if lock else stmt)
        if trip is None: raise HTTPException(status_code=404, detail="سفر در این مجموعه وجود ندارد")
        return trip

    is_change = or_(m.TripEventRecord.change_category.is_not(None), m.TripEventRecord.old_value_json.is_not(None), m.TripEventRecord.new_value_json.is_not(None))

    # ---- Trip Operations Center -------------------------------------------------------------------------------
    @router.post("/operations/trips/{trip_id}/events", status_code=201)
    def record_event(trip_id: str, data: TripEventIn, user=Depends(require_permission("trip:event:create")), db: Session = Depends(get_db)) -> dict:
        trip = tenant_trip(db, trip_id, user, lock=True)
        if data.category in NEEDS_BOTH and (not data.old_value or not data.new_value or data.old_value == data.new_value): raise HTTPException(status_code=422, detail="مقدار قبلی و جدید باید هر دو ثبت شوند و متفاوت باشند")
        if data.category == "cancellation" and not data.old_value: raise HTTPException(status_code=422, detail="برای لغو، مورد لغوشده را در مقدار قبلی ثبت کنید")
        reservation = None
        if data.reservation_id:
            reservation = db.scalar(select(m.Reservation).where(m.Reservation.id == data.reservation_id, m.Reservation.tenant_id == user.tenant_id))
            if reservation is None or (reservation.trip_id != trip.id and reservation.user_id != trip.user_id): raise HTTPException(status_code=422, detail="رزرو به این سفر تعلق ندارد")
        key = "ops-event:" + data.command_id
        prior = db.scalar(select(m.TripEventRecord).where(m.TripEventRecord.tenant_id == user.tenant_id, m.TripEventRecord.event_key == key))
        if prior is not None:
            if prior.trip_id != trip.id or prior.change_category != data.category or _load(prior.new_value_json) != data.new_value or _load(prior.old_value_json) != data.old_value: raise HTTPException(status_code=409, detail="این شناسه برای تغییر دیگری استفاده شده است")
            return event_out(prior, True, actors_for(db, [prior]))
        lines = [f"{k}: {(data.old_value or {}).get(k, '—')} ← {(data.new_value or {}).get(k, '—')}" for k in dict.fromkeys([*(data.old_value or {}), *(data.new_value or {})])]
        event = m.ingest_trip_event(db, m.TripEventRecord(
            tenant_id=user.tenant_id, trip_id=trip.id, reservation_id=reservation.id if reservation else None, event_key=key, event_type=f"ops.{data.category}", severity=data.severity, source=data.source,
            title=CATEGORIES[data.category], message="\n".join([*lines, f"دلیل: {data.reason.strip()}"]), effective_at=data.effective_at, requires_action=data.requires_action, visibility=data.visibility,
            deep_link=f"/trips/{trip.id}", change_category=data.category, actor_user_id=user.id, old_value_json=json.dumps(data.old_value, ensure_ascii=False) if data.old_value else None,
            new_value_json=json.dumps(data.new_value, ensure_ascii=False) if data.new_value else None, affected_reference=(reservation.booking_reference or reservation.id) if reservation else None))
        audit(db, user, "trip_event.recorded", "trip_event", {"trip_event_id": event.id, "trip_id": trip.id, "category": data.category, "severity": data.severity, "source": data.source, "visibility": data.visibility})
        db.commit()
        return event_out(event, True, actors_for(db, [event]))

    @router.get("/operations/trip-events")
    def ops_center(category: Optional[str] = None, severity: Optional[str] = None, unacknowledged: bool = False, requires_action: bool = False, trip_id: Optional[str] = None,
                   offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        base = select(m.TripEventRecord).where(m.TripEventRecord.tenant_id == user.tenant_id, is_change)
        stmt = base
        if category: stmt = stmt.where(m.TripEventRecord.change_category == category)
        if severity: stmt = stmt.where(m.TripEventRecord.severity == severity)
        if unacknowledged: stmt = stmt.where(m.TripEventRecord.acknowledged_at.is_(None), m.TripEventRecord.visibility == "customer")
        if requires_action: stmt = stmt.where(m.TripEventRecord.requires_action.is_(True))
        if trip_id: stmt = stmt.where(m.TripEventRecord.trip_id == trip_id)
        count = lambda s: db.scalar(select(func.count()).select_from(s.subquery()))  # noqa: E731
        rows = db.scalars(stmt.order_by(m.TripEventRecord.created_at.desc()).offset(offset).limit(limit)).all()
        open_customer = base.where(m.TripEventRecord.acknowledged_at.is_(None), m.TripEventRecord.visibility == "customer")
        return {"total": count(stmt), "summary": {"all": count(base), "unacknowledged": count(open_customer), "critical_unacknowledged": count(open_customer.where(m.TripEventRecord.severity == "critical"))},
                "categories": CATEGORIES, "items": [event_out(e, True, actors_for(db, rows)) for e in rows]}

    @router.get("/operations/trips/{trip_id}/timeline")
    def staff_timeline(trip_id: str, user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        trip = tenant_trip(db, trip_id, user)
        rows = db.scalars(select(m.TripEventRecord).where(m.TripEventRecord.tenant_id == user.tenant_id, m.TripEventRecord.trip_id == trip.id).order_by(m.TripEventRecord.created_at.desc())).all()
        return {"trip": {"id": trip.id, "title": trip.title, "destination": trip.destination, "status": trip.status, "customer_id": trip.user_id}, "events": [event_out(e, True, actors_for(db, rows)) for e in rows]}

    # ---- Customer: «چه چیزی در سفر من تغییر کرده؟» ---------------------------------------------------------------
    @router.get("/trips/{trip_id}/changes")
    def my_trip_changes(trip_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        trip = own_trip(db, trip_id, user)
        rows = db.scalars(select(m.TripEventRecord).where(m.TripEventRecord.tenant_id == user.tenant_id, m.TripEventRecord.trip_id == trip.id, m.TripEventRecord.visibility == "customer", is_change)
                          .order_by(m.TripEventRecord.created_at.desc())).all()
        return {"trip": {"id": trip.id, "title": trip.title, "destination": trip.destination, "status": trip.status}, "recorded_only": True, "unacknowledged": sum(1 for e in rows if e.acknowledged_at is None),
                "changes": [event_out(e, False) for e in rows]}

    @router.post("/trips/{trip_id}/events/{event_id}/acknowledge")
    def acknowledge(trip_id: str, event_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        trip = own_trip(db, trip_id, user)
        event = db.scalar(select(m.TripEventRecord).where(m.TripEventRecord.id == event_id, m.TripEventRecord.trip_id == trip.id, m.TripEventRecord.tenant_id == user.tenant_id, m.TripEventRecord.visibility == "customer").with_for_update())
        if event is None: raise HTTPException(status_code=404, detail="رویداد قابل نمایش نیست")
        if event.acknowledged_at is None:
            event.acknowledged_at, event.acknowledged_by_user_id = datetime.now(timezone.utc), user.id
            for n in db.scalars(select(m.NotificationRecord).where(m.NotificationRecord.tenant_id == user.tenant_id, m.NotificationRecord.trip_event_id == event.id, m.NotificationRecord.user_id == user.id)): n.status = "read"
            audit(db, user, "trip_event.acknowledged", "trip_event", {"trip_event_id": event.id, "trip_id": trip.id})
            db.commit()
        return event_out(event, False)

    @router.get("/ai/trip-changes-context")
    def ai_changes_context(trip_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """Grounding for the assistant: recorded events only. An empty list means 'no recorded change', never a guess."""
        data = my_trip_changes(trip_id, user, db)
        return {"generated_transactional_data": False, "authoritative": True, "trip": data["trip"], "recorded_changes": data["changes"],
                "answer_policy": "explain_only_recorded_events_cite_event_id" if data["changes"] else "state_no_recorded_change"}

    # ---- Notifications: delivery observability ------------------------------------------------------------------
    @router.get("/operations/notification-deliveries")
    def deliveries(status: Optional[str] = None, channel: Optional[str] = None, trip_event_id: Optional[str] = None, limit: int = Query(default=50, ge=1, le=200), user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        stmt = select(m.NotificationDeliveryAttempt, m.NotificationRecord).join(m.NotificationRecord, m.NotificationRecord.id == m.NotificationDeliveryAttempt.notification_id).where(
            m.NotificationDeliveryAttempt.tenant_id == user.tenant_id, m.NotificationRecord.tenant_id == user.tenant_id)
        if status: stmt = stmt.where(m.NotificationDeliveryAttempt.status == status)
        if channel: stmt = stmt.where(m.NotificationDeliveryAttempt.channel == channel)
        if trip_event_id: stmt = stmt.where(m.NotificationRecord.trip_event_id == trip_event_id)
        rows = db.execute(stmt.order_by(m.NotificationDeliveryAttempt.created_at.desc()).limit(limit)).all()
        return {"items": [{"id": a.id, "notification_id": n.id, "event_id": n.trip_event_id, "recipient_user_id": n.user_id, "channel": a.channel, "template": n.topic, "delivery_status": a.status, "attempt": a.attempt,
                           "error_code": a.error_code, "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None, "delivered_at": a.delivered_at.isoformat() if a.delivered_at else None,
                           "deep_link": n.deep_link, "read": n.status == "read"} for a, n in rows]}

    # ---- Support workspace --------------------------------------------------------------------------------------
    def case_for_agent(db: Session, case_id: str, user, lock: bool = False) -> m.SupportCase:
        stmt = select(m.SupportCase).where(m.SupportCase.id == case_id, m.SupportCase.tenant_id == user.tenant_id)
        row = db.scalar(stmt.with_for_update() if lock else stmt)
        if row is None: raise HTTPException(status_code=404, detail="پرونده در این مجموعه وجود ندارد")
        return row

    def trail(row: m.SupportCase, user, action: str, **extra) -> None:
        row.audit_trail_json = json.dumps([*json.loads(row.audit_trail_json or "[]"), {"at": datetime.now(timezone.utc).isoformat(), "actor_user_id": user.id, "action": action, **extra}], ensure_ascii=False)

    @router.get("/support/cases/{case_id}/workspace")
    def workspace(case_id: str, user=Depends(require_permission("support:manage")), db: Session = Depends(get_db)) -> dict:
        row = case_for_agent(db, case_id, user)
        messages = db.scalars(select(m.SupportThreadMessage).where(m.SupportThreadMessage.tenant_id == user.tenant_id, m.SupportThreadMessage.case_id == row.id).order_by(m.SupportThreadMessage.created_at)).all()
        customer = db.scalar(select(User).where(User.id == row.user_id, User.tenant_id == user.tenant_id))
        reservation = db.scalar(select(m.Reservation).where(m.Reservation.id == row.reservation_id, m.Reservation.tenant_id == user.tenant_id)) if row.reservation_id else None
        events = db.scalars(select(m.TripEventRecord).where(m.TripEventRecord.tenant_id == user.tenant_id, m.TripEventRecord.trip_id == row.trip_id).order_by(m.TripEventRecord.created_at.desc()).limit(50)).all() if row.trip_id else []
        now = datetime.now(timezone.utc)
        due = row.sla_due_at.replace(tzinfo=timezone.utc) if row.sla_due_at and row.sla_due_at.tzinfo is None else row.sla_due_at
        kinds = {"customer": "customer", "human_agent": "human_support", "internal_note": "internal_note", "ai_assistant": "ai_assistant"}
        return {"case": {"id": row.id, "subject": row.subject, "status": row.status, "priority": row.priority, "case_type": row.case_type, "severity": row.severity, "assigned_to_user_id": row.assigned_to_user_id,
                         "resolution_type": row.resolution_type, "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None},
                "sla": {"due_at": due.isoformat() if due else None, "breached": bool(due and row.status not in ("resolved", "closed") and now > due)},
                "messages": [{"id": x.id, "author_kind": kinds.get(x.sender_type, x.sender_type), "is_human": x.sender_type in ("customer", "human_agent", "internal_note"), "visible_to_customer": x.sender_type != "internal_note",
                              "sender_user_id": x.sender_user_id, "body": x.body, "created_at": x.created_at.isoformat()} for x in messages],
                "customer": None if customer is None else {"id": customer.id, "name": customer.name, "role": customer.role,
                                                           "reservations": db.scalar(select(func.count()).select_from(m.Reservation).where(m.Reservation.tenant_id == user.tenant_id, m.Reservation.user_id == customer.id)),
                                                           "open_cases": db.scalar(select(func.count()).select_from(m.SupportCase).where(m.SupportCase.tenant_id == user.tenant_id, m.SupportCase.user_id == customer.id, m.SupportCase.status.notin_(("resolved", "closed"))))},
                "booking": None if reservation is None else {"id": reservation.id, "service_type": reservation.service_type, "status": reservation.status, "booking_reference": reservation.booking_reference, "trip_id": reservation.trip_id,
                                                             "confirmed_at": reservation.confirmed_at.isoformat() if reservation.confirmed_at else None},
                "trip_events": [event_out(e, True, actors_for(db, events)) for e in events], "history": json.loads(row.audit_trail_json or "[]")}

    @router.post("/support/cases/{case_id}/internal-notes", status_code=201)
    def internal_note(case_id: str, data: NoteIn, user=Depends(require_permission("support:manage")), db: Session = Depends(get_db)) -> dict:
        row = case_for_agent(db, case_id, user, lock=True)
        note = m.SupportThreadMessage(tenant_id=user.tenant_id, case_id=row.id, sender_type="internal_note", sender_user_id=user.id, body=data.body.strip())
        db.add(note); trail(row, user, "internal_note_added"); db.commit()
        return {"id": note.id, "author_kind": "internal_note", "visible_to_customer": False, "body": note.body}

    @router.post("/support/cases/{case_id}/escalate")
    def escalate(case_id: str, data: EscalateIn, user=Depends(require_permission("support:manage")), db: Session = Depends(get_db)) -> dict:
        row = case_for_agent(db, case_id, user, lock=True)
        if row.status in ("resolved", "closed"): raise HTTPException(status_code=409, detail="پروندهٔ بسته‌شده قابل ارجاع نیست")
        previous = {"priority": row.priority, "severity": row.severity}
        row.priority, row.severity = "urgent", data.severity
        trail(row, user, "escalated", reason=data.reason.strip(), previous=previous, severity=data.severity)
        event_id = None
        if row.trip_id:
            event = m.ingest_trip_event(db, m.TripEventRecord(tenant_id=user.tenant_id, trip_id=row.trip_id, reservation_id=row.reservation_id, event_key=f"case-escalation:{row.id}:{len(json.loads(row.audit_trail_json))}",
                                                             event_type="ops.support_intervention", severity="critical" if data.severity == "CRITICAL" else "warning", source="support", title=CATEGORIES["support_intervention"],
                                                             message=f"ارجاع پرونده: {data.reason.strip()}", visibility="internal", change_category="support_intervention", actor_user_id=user.id,
                                                             new_value_json=json.dumps({"case": row.id, "severity": data.severity}), old_value_json=json.dumps({"severity": previous["severity"]})))
            event_id = event.id
        audit(db, user, "support_case.escalated", "support_case", {"case_id": row.id, "severity": data.severity, "trip_event_id": event_id})
        db.commit()
        return {"id": row.id, "priority": row.priority, "severity": row.severity, "trip_event_id": event_id}

    # ---- Finance read models (tenant-scoped, real rows only) -----------------------------------------------------
    DATASETS = {
        "payments": (m.PaymentIntent, ("id", "reservation_id", "user_id", "amount", "currency", "status", "provider_key", "provider_reference", "captured_amount", "refunded_amount", "created_at")),
        "refunds": (m.RefundRecord, ("id", "payment_intent_id", "amount", "status", "provider_reference", "created_at")),
        "settlements": (m.SettlementRecord, ("id", "supplier_id", "reservation_id", "amount", "currency", "status", "external_reference", "created_at")),
        "invoices": (m.Invoice, ("id", "invoice_number", "reservation_id", "user_id", "subtotal_amount", "tax_amount", "total_amount", "currency", "status", "issued_at")),
        "ledger": (m.FinancialLedgerEntry, ("id", "wallet_id", "credit_account_id", "reservation_id", "entry_type", "amount", "reversal_of_id", "created_at")),
        "credit-accounts": (m.CreditAccount, ("id", "organization_id", "user_id", "currency", "limit_amount", "created_at")),
    }

    def cell(value):
        return value.isoformat() if isinstance(value, datetime) else value

    def dataset_rows(db: Session, name: str, user, status: Optional[str], offset: int, limit: int):
        if name not in DATASETS: raise HTTPException(status_code=404, detail="مجموعه‌دادهٔ مالی ناشناخته است")
        model, columns = DATASETS[name]
        stmt = select(model).where(model.tenant_id == user.tenant_id)
        if status and hasattr(model, "status"): stmt = stmt.where(model.status == status)
        total = db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db.scalars(stmt.order_by(model.created_at.desc()).offset(offset).limit(limit)).all()
        return total, columns, [{c: cell(getattr(r, c)) for c in columns} for r in rows]

    @router.get("/finance/overview")
    def finance_overview(user=Depends(require_permission("ledger:read")), db: Session = Depends(get_db)) -> dict:
        def by_status(model, amount):
            cols = [model.status, func.count(), func.coalesce(func.sum(amount), 0)] + ([model.currency] if hasattr(model, "currency") else [])
            rows = db.execute(select(*cols).where(model.tenant_id == user.tenant_id).group_by(model.status, *([model.currency] if hasattr(model, "currency") else []))).all()
            return [{"status": r[0], "count": r[1], "amount": int(r[2]), "currency": r[3] if len(r) > 3 else None} for r in rows]
        return {"payments": by_status(m.PaymentIntent, m.PaymentIntent.amount), "refunds": by_status(m.RefundRecord, m.RefundRecord.amount), "settlements": by_status(m.SettlementRecord, m.SettlementRecord.amount),
                "invoices": by_status(m.Invoice, m.Invoice.total_amount), "credit_accounts": db.scalar(select(func.count()).select_from(m.CreditAccount).where(m.CreditAccount.tenant_id == user.tenant_id)),
                "derived_balances": None, "note": "ارقام فقط جمع ردیف‌های ثبت‌شده به تفکیک وضعیت است؛ مانده یا مطالبات محاسبه‌شده نمایش داده نمی‌شود."}

    @router.get("/finance/records/{dataset}")
    def finance_records(dataset: str, status: Optional[str] = None, offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), user=Depends(require_permission("ledger:read")), db: Session = Depends(get_db)) -> dict:
        total, columns, rows = dataset_rows(db, dataset, user, status, offset, limit)
        return {"dataset": dataset, "total": total, "columns": columns, "items": rows}

    @router.get("/finance/export/{dataset}")
    def finance_export(dataset: str, status: Optional[str] = None, user=Depends(require_permission("ledger:read")), db: Session = Depends(get_db)) -> Response:
        total, columns, rows = dataset_rows(db, dataset, user, status, 0, 5000)
        buffer = io.StringIO(); writer = csv.writer(buffer); writer.writerow(columns)
        for r in rows: writer.writerow(["'" + v if isinstance(v, str) and v[:1] in "=+-@" else v for v in (r[c] for c in columns)])  # neutralise spreadsheet formulas
        audit(db, user, "finance.exported", "finance_export", {"dataset": dataset, "rows": len(rows), "status": status}); db.commit()
        return Response(content="﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{dataset}.csv"', "Cache-Control": "no-store"})

    # ---- Supplier: own settlements and contracts ------------------------------------------------------------------
    @router.get("/supplier/settlements")
    def supplier_settlements(user=Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
        scope = supplier_scope(db, user)
        rows = db.scalars(select(m.SettlementRecord).where(m.SettlementRecord.tenant_id == user.tenant_id, m.SettlementRecord.supplier_id.in_(scope)).order_by(m.SettlementRecord.created_at.desc()).limit(200)).all() if scope else []
        return {"items": [{"id": r.id, "supplier_id": r.supplier_id, "reservation_id": r.reservation_id, "amount": r.amount, "currency": r.currency, "status": r.status, "external_reference": r.external_reference, "created_at": r.created_at.isoformat()} for r in rows]}

    @router.get("/supplier/contracts")
    def supplier_contracts(user=Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
        scope = supplier_scope(db, user)
        suppliers = db.scalars(select(m.Supplier).where(m.Supplier.tenant_id == user.tenant_id, m.Supplier.id.in_(scope))).all() if scope else []
        contracts = db.scalars(select(m.ProviderContract).where(m.ProviderContract.tenant_id == user.tenant_id, m.ProviderContract.supplier_id.in_(scope))).all() if scope else []
        return {"suppliers": [{"id": s.id, "name": s.display_name, "type": s.supplier_type, "status": s.status, "lifecycle_status": s.lifecycle_status} for s in suppliers],
                "contracts": [{"id": c.id, "supplier_id": c.supplier_id, "provider_key": c.provider_key, "mode": c.mode, "configured": bool(c.config_reference)} for c in contracts]}

    # ---- Notifications: manual requeue of a dead-lettered delivery (uses the existing outbox retry machinery) -----
    @router.post("/operations/notification-deliveries/{attempt_id}/requeue")
    def requeue(attempt_id: str, user=Depends(require_permission("trip:event:create")), db: Session = Depends(get_db)) -> dict:
        attempt = db.scalar(select(m.NotificationDeliveryAttempt).where(m.NotificationDeliveryAttempt.id == attempt_id, m.NotificationDeliveryAttempt.tenant_id == user.tenant_id).with_for_update())
        if attempt is None: raise HTTPException(status_code=404, detail="تلاش تحویل پیدا نشد")
        if attempt.status not in ("dead_letter", "failed"): raise HTTPException(status_code=409, detail="فقط تحویل ناموفقِ متوقف‌شده دوباره در صف قرار می‌گیرد")
        notification = db.scalar(select(m.NotificationRecord).where(m.NotificationRecord.id == attempt.notification_id, m.NotificationRecord.tenant_id == user.tenant_id))
        event = db.scalar(select(m.TripEventRecord).where(m.TripEventRecord.id == notification.trip_event_id, m.TripEventRecord.tenant_id == user.tenant_id)) if notification and notification.trip_event_id else None
        outbox = db.scalar(select(m.OutboxEvent).where(m.OutboxEvent.tenant_id == user.tenant_id, m.OutboxEvent.idempotency_key == event.event_key, m.OutboxEvent.event_type == "trip.event.recorded").with_for_update()) if event else None
        if outbox is None: raise HTTPException(status_code=409, detail="رویداد ارسال مرتبط پیدا نشد")
        outbox.status, outbox.available_at, outbox.attempts, outbox.last_error = "retry", datetime.now(timezone.utc), 0, None
        attempt.status, attempt.error_code = "retry", None
        audit(db, user, "notification.requeued", "notification_delivery", {"attempt_id": attempt.id, "notification_id": attempt.notification_id, "channel": attempt.channel})
        db.commit()
        return {"id": attempt.id, "delivery_status": attempt.status, "channel": attempt.channel}

    # ---- Agency workspace: attribution only through the agency's sales channel --------------------------------------
    def can_admin_agencies(user) -> bool:
        return role_has_permission(user.role, "tenant:manage")

    def my_agency(db: Session, agency_id: str, user) -> m.Agency:
        row = db.scalar(select(m.Agency).where(m.Agency.id == agency_id, m.Agency.tenant_id == user.tenant_id))
        member = row is not None and (can_admin_agencies(user) or db.scalar(select(m.AgencyMembership.id).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.user_id == user.id, m.AgencyMembership.agency_id == agency_id)))
        if not member: raise HTTPException(status_code=404, detail="آژانس در دسترس این حساب نیست")
        return row

    def agency_reservations(db: Session, agency: m.Agency, user):
        if not agency.sales_channel_id: return []
        return db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == user.tenant_id, m.Reservation.sales_channel_id == agency.sales_channel_id).order_by(m.Reservation.created_at.desc()).limit(500)).all()

    def total_of(r: m.Reservation):
        snap = json.loads(r.price_snapshot_json or "{}")
        amount = snap.get("total_amount")
        return (amount, snap.get("currency") or "IRR") if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0 else (None, None)

    agency_user = require_permission("agency:manage")

    @router.get("/agency/workspace")
    def agency_workspace(user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        stmt = select(m.Agency).where(m.Agency.tenant_id == user.tenant_id)
        if not can_admin_agencies(user): stmt = stmt.where(m.Agency.id.in_(select(m.AgencyMembership.agency_id).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.user_id == user.id)))
        rows = db.scalars(stmt.order_by(m.Agency.created_at.desc())).all()
        return {"agencies": [{"id": a.id, "name": a.display_name, "status": a.status, "markup_bps": a.markup_bps, "commission_bps": a.commission_bps, "sales_channel_linked": bool(a.sales_channel_id)} for a in rows], "can_administer": can_admin_agencies(user)}

    @router.get("/agency/{agency_id}/bookings")
    def agency_bookings(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = my_agency(db, agency_id, user)
        rows = agency_reservations(db, agency, user)
        return {"sales_channel_linked": bool(agency.sales_channel_id), "items": [{"id": r.id, "booking_reference": r.booking_reference, "service_type": r.service_type, "status": r.status, "customer_id": r.user_id,
                                                                                 "total_amount": total_of(r)[0], "currency": total_of(r)[1], "created_at": r.created_at.isoformat(), "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None} for r in rows]}

    @router.get("/agency/{agency_id}/customers")
    def agency_customers(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        rows = agency_reservations(db, my_agency(db, agency_id, user), user)
        counts: dict[int, int] = {}
        for r in rows: counts[r.user_id] = counts.get(r.user_id, 0) + 1
        names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(set(counts)), User.tenant_id == user.tenant_id))} if counts else {}
        return {"items": [{"customer_id": uid, "name": names.get(uid), "bookings": n} for uid, n in sorted(counts.items(), key=lambda x: -x[1])]}

    @router.get("/agency/{agency_id}/commissions")
    def agency_commissions(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = my_agency(db, agency_id, user)
        items, totals = [], {}
        for r in agency_reservations(db, agency, user):
            amount, currency = total_of(r)
            if r.confirmed_at is None or amount is None: continue
            commission = amount * agency.commission_bps // 10000
            items.append({"reservation_id": r.id, "booking_reference": r.booking_reference, "confirmed_at": r.confirmed_at.isoformat(), "base_amount": amount, "currency": currency, "commission_bps": agency.commission_bps, "commission_amount": commission})
            totals[currency] = totals.get(currency, 0) + commission
        return {"basis": "configured_rate_on_confirmed_reservations", "settled": False, "commission_bps": agency.commission_bps, "items": items, "totals": [{"currency": c, "commission_amount": v} for c, v in totals.items()],
                "note": "محاسبه بر اساس نرخ کمیسیون ثبت‌شده و مبلغ رزروهای تأییدشده است؛ پرداخت‌شده بودن آن فقط در بخش تسویه مشخص می‌شود."}

    @router.get("/agency/{agency_id}/settlements")
    def agency_settlements(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        ids = [r.id for r in agency_reservations(db, my_agency(db, agency_id, user), user)]
        rows = db.scalars(select(m.SettlementRecord).where(m.SettlementRecord.tenant_id == user.tenant_id, m.SettlementRecord.reservation_id.in_(ids)).order_by(m.SettlementRecord.created_at.desc())).all() if ids else []
        return {"items": [{"id": s.id, "reservation_id": s.reservation_id, "amount": s.amount, "currency": s.currency, "status": s.status, "external_reference": s.external_reference, "created_at": s.created_at.isoformat()} for s in rows]}

    @router.get("/agency/{agency_id}/report")
    def agency_report(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        rows = agency_reservations(db, my_agency(db, agency_id, user), user)
        by_status, by_service, confirmed = {}, {}, {}
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1; by_service[r.service_type] = by_service.get(r.service_type, 0) + 1
            amount, currency = total_of(r)
            if r.confirmed_at is not None and amount is not None: confirmed[currency] = confirmed.get(currency, 0) + amount
        return {"bookings": len(rows), "by_status": by_status, "by_service_type": by_service, "confirmed_sales": [{"currency": c, "amount": v} for c, v in confirmed.items()]}

    @router.post("/agency/{agency_id}/members", status_code=201)
    def add_agency_member(agency_id: str, data: AgencyMemberIn, user=Depends(require_permission("tenant:manage")), db: Session = Depends(get_db)) -> dict:
        agency = my_agency(db, agency_id, user)
        target = db.scalar(select(User).where(User.id == data.user_id, User.tenant_id == user.tenant_id))
        if target is None or not role_has_permission(target.role, "agency:manage"): raise HTTPException(status_code=422, detail="کاربر باید در همین مجموعه و با نقش آژانس باشد")
        if db.scalar(select(m.AgencyMembership.id).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.user_id == target.id, m.AgencyMembership.agency_id == agency.id)) is None:
            db.add(m.AgencyMembership(tenant_id=user.tenant_id, user_id=target.id, agency_id=agency.id))
            audit(db, user, "agency.member_added", "agency", {"agency_id": agency.id, "user_id": target.id}); db.commit()
        return {"agency_id": agency.id, "user_id": target.id}

    @router.put("/agency/{agency_id}/sales-channel")
    def link_agency_channel(agency_id: str, data: AgencyChannelIn, user=Depends(require_permission("tenant:manage")), db: Session = Depends(get_db)) -> dict:
        agency = my_agency(db, agency_id, user)
        if data.sales_channel_id:
            channel = db.scalar(select(m.SalesChannel).where(m.SalesChannel.id == data.sales_channel_id, m.SalesChannel.tenant_id == user.tenant_id))
            if channel is None: raise HTTPException(status_code=422, detail="کانال فروش در این مجموعه وجود ندارد")
            if db.scalar(select(m.Agency.id).where(m.Agency.tenant_id == user.tenant_id, m.Agency.sales_channel_id == channel.id, m.Agency.id != agency.id)): raise HTTPException(status_code=409, detail="این کانال فروش به آژانس دیگری متصل است")
        previous, agency.sales_channel_id = agency.sales_channel_id, data.sales_channel_id
        audit(db, user, "agency.sales_channel_linked", "agency", {"agency_id": agency.id, "from": previous, "to": data.sales_channel_id}); db.commit()
        return {"agency_id": agency.id, "sales_channel_id": agency.sales_channel_id}

    return router
