"""Loyalty call schedule (برنامه‌ی تماس حلقه‌ی همسفران).

Call tasks for the customer team, generated from real rows only:
* post_trip — a reservation that reached `completed` recently: ask how the trip went (once per reservation)
* dormant  — a loyalty member whose last reservation is older than N days (at most once per month per member)
* manual   — added by staff, or a follow-up date set when recording a call result
Each task is claimed by one agent and closed with an outcome; nothing is sent to the customer automatically.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

REASON_FA = {"post_trip": "پیگیری بعد از سفر", "dormant": "مشتری کم‌فعال", "manual": "تماس دستی"}
OUTCOME_FA = {"reached": "صحبت شد", "no_answer": "پاسخ نداد", "wrong_number": "شماره اشتباه", "not_interested": "تمایل ندارد", "booked": "به خرید رسید"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LoyaltyCallTask(OperationalMixin, Base):
    __tablename__ = "loyalty_call_tasks"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(16), index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(80))
    due_on: Mapped[str] = mapped_column(String(10), index=True)
    assigned_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)  # open | done | skipped
    outcome: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    done_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "dedupe_key", name="uq_loyalty_call_dedupe"),)


class GenerateIn(BaseModel):
    post_trip_days: int = Field(default=2, ge=0, le=30)
    dormant_days: int = Field(default=180, ge=30, le=730)


class ManualIn(BaseModel):
    user_id: int
    due_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: Optional[str] = Field(default=None, max_length=500)


class ResultIn(BaseModel):
    outcome: str = Field(pattern="^(" + "|".join(OUTCOME_FA) + ")$")
    note: Optional[str] = Field(default=None, max_length=1000)
    next_call_on: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


def loyalty_calls_router(get_db, current_user, role_has_permission, User, audit=None):
    from .loyalty import LoyaltyAccount

    api = APIRouter(tags=["loyalty-calls"])

    def staff(user=Depends(current_user)):
        if user.role in ("employee", "customer") or not any(role_has_permission(user.role, p) for p in ("backoffice:read", "support:manage", "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی تیم مشتریان لازم است")
        return user

    def _add(db: Session, tenant_id: int, user_id: int, reason: str, key: str, due: str, reservation_id: Optional[str] = None, note: Optional[str] = None) -> bool:
        if db.scalar(select(LoyaltyCallTask.id).where(LoyaltyCallTask.tenant_id == tenant_id, LoyaltyCallTask.dedupe_key == key)):
            return False
        db.add(LoyaltyCallTask(tenant_id=tenant_id, user_id=user_id, reason=reason, reservation_id=reservation_id, dedupe_key=key, due_on=due, note=note))
        return True

    @api.post("/loyalty/calls/generate")
    def generate(data: GenerateIn, user=Depends(staff), db: Session = Depends(get_db)):
        t, now, today = user.tenant_id, utcnow(), date.today().isoformat()
        created = {"post_trip": 0, "dormant": 0}
        recent = db.execute(select(m.Reservation.id, m.Reservation.user_id).where(
            m.Reservation.tenant_id == t, m.Reservation.status == "completed",
            m.Reservation.updated_at >= now - timedelta(days=30), m.Reservation.updated_at <= now - timedelta(days=data.post_trip_days))).all()
        for rid, uid in recent:
            created["post_trip"] += _add(db, t, uid, "post_trip", f"post_trip:{rid}", today, reservation_id=rid)
        last = dict(db.execute(select(m.Reservation.user_id, func.max(m.Reservation.created_at)).where(
            m.Reservation.tenant_id == t, m.Reservation.status != "draft").group_by(m.Reservation.user_id)).all())
        cutoff = now - timedelta(days=data.dormant_days)
        month = today[:7]
        for uid in db.scalars(select(LoyaltyAccount.user_id).where(LoyaltyAccount.tenant_id == t)).all():
            seen = last.get(uid)
            if seen is not None and (seen if seen.tzinfo else seen.replace(tzinfo=timezone.utc)) < cutoff:
                created["dormant"] += _add(db, t, uid, "dormant", f"dormant:{uid}:{month}", today)
        if audit:
            audit(db, user, "loyalty.calls.generated", "loyalty_call_task", created)
        db.commit()
        return {"created": created}

    @api.get("/loyalty/calls")
    def list_calls(status: str = Query(default="open", pattern="^(open|done|skipped|all)$"), mine: bool = False, user=Depends(staff), db: Session = Depends(get_db)):
        s = select(LoyaltyCallTask, User.name, User.mobile_e164).join(User, User.id == LoyaltyCallTask.user_id).where(LoyaltyCallTask.tenant_id == user.tenant_id)
        if status != "all":
            s = s.where(LoyaltyCallTask.status == status)
        if mine:
            s = s.where(LoyaltyCallTask.assigned_user_id == user.id)
        rows = db.execute(s.order_by(LoyaltyCallTask.due_on, LoyaltyCallTask.created_at).limit(300)).all()
        agents = {}
        refs = {}
        out = []
        today = date.today().isoformat()
        for task, name, mobile in rows:
            if task.assigned_user_id and task.assigned_user_id not in agents:
                agents[task.assigned_user_id] = db.scalar(select(User.name).where(User.id == task.assigned_user_id))
            if task.reservation_id and task.reservation_id not in refs:
                refs[task.reservation_id] = db.scalar(select(m.Reservation.booking_reference).where(m.Reservation.id == task.reservation_id))
            out.append({"id": task.id, "customer": name, "mobile": mobile, "reason": task.reason, "reason_fa": REASON_FA[task.reason],
                        "booking_reference": refs.get(task.reservation_id), "due_on": task.due_on, "overdue": task.status == "open" and task.due_on < today,
                        "status": task.status, "assigned_to": agents.get(task.assigned_user_id), "mine": task.assigned_user_id == user.id,
                        "outcome": task.outcome, "outcome_fa": OUTCOME_FA.get(task.outcome or ""), "note": task.note})
        counts = dict(db.execute(select(LoyaltyCallTask.status, func.count(LoyaltyCallTask.id)).where(LoyaltyCallTask.tenant_id == user.tenant_id).group_by(LoyaltyCallTask.status)).all())
        return {"items": out, "counts": {k: int(counts.get(k, 0)) for k in ("open", "done", "skipped")}, "outcomes": OUTCOME_FA}

    def _task(db: Session, user, task_id: str) -> LoyaltyCallTask:
        t = db.scalar(select(LoyaltyCallTask).where(LoyaltyCallTask.id == task_id, LoyaltyCallTask.tenant_id == user.tenant_id).with_for_update())
        if t is None:
            raise HTTPException(status_code=404, detail="تماس یافت نشد")
        return t

    @api.post("/loyalty/calls", status_code=201)
    def manual(data: ManualIn, user=Depends(staff), db: Session = Depends(get_db)):
        if db.scalar(select(User.id).where(User.id == data.user_id, User.tenant_id == user.tenant_id)) is None:
            raise HTTPException(status_code=404, detail="مشتری یافت نشد")
        key = f"manual:{data.user_id}:{data.due_on}"
        if not _add(db, user.tenant_id, data.user_id, "manual", key, data.due_on, note=data.note):
            raise HTTPException(status_code=409, detail="برای این مشتری در این روز تماس ثبت شده است")
        db.commit()
        return {"ok": True}

    @api.post("/loyalty/calls/{task_id}/claim")
    def claim(task_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        t = _task(db, user, task_id)
        if t.status != "open":
            raise HTTPException(status_code=409, detail="این تماس بسته شده است")
        if t.assigned_user_id and t.assigned_user_id != user.id:
            raise HTTPException(status_code=409, detail="این تماس را همکار دیگری برداشته است")
        t.assigned_user_id = user.id
        db.commit()
        return {"id": t.id, "assigned": True}

    @api.post("/loyalty/calls/{task_id}/result")
    def result(task_id: str, data: ResultIn, user=Depends(staff), db: Session = Depends(get_db)):
        t = _task(db, user, task_id)
        if t.status != "open":
            raise HTTPException(status_code=409, detail="این تماس قبلاً بسته شده است")
        if t.assigned_user_id and t.assigned_user_id != user.id:
            raise HTTPException(status_code=409, detail="این تماس را همکار دیگری برداشته است")
        if data.next_call_on and data.next_call_on <= date.today().isoformat():
            raise HTTPException(status_code=422, detail="تاریخ تماس بعدی باید بعد از امروز باشد")
        t.status, t.outcome, t.done_at, t.done_by, t.assigned_user_id = "done", data.outcome, utcnow(), user.id, t.assigned_user_id or user.id
        t.note = data.note or t.note
        follow = False
        if data.next_call_on:
            follow = _add(db, user.tenant_id, t.user_id, "manual", f"manual:{t.user_id}:{data.next_call_on}", data.next_call_on, note=f"پیگیری: {data.note or OUTCOME_FA[data.outcome]}")
        db.commit()
        return {"id": t.id, "status": t.status, "outcome": t.outcome, "follow_up_created": follow}

    @api.post("/loyalty/calls/{task_id}/skip")
    def skip(task_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        t = _task(db, user, task_id)
        if t.status != "open":
            raise HTTPException(status_code=409, detail="این تماس قبلاً بسته شده است")
        t.status, t.done_at, t.done_by = "skipped", utcnow(), user.id
        db.commit()
        return {"id": t.id, "status": t.status}

    return api
