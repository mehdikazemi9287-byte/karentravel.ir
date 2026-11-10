"""Generic maker-checker (four-eyes) primitive.

Used for money-creating finance operations (security review H-1: wallet
funding, credit-account creation, credit-limit changes) and meant to be
reused by any other operation that must not be executed by one person alone
(e.g. refunds).

Flow
----
1. At import time the owning module registers a *kind*::

       approvals.register(
           "wallet.fund",
           can_check=lambda user, payload: role_has_permission(user.role, "credit:fund"),
           execute=lambda db, request, payload, checker: {...result dict...},
           label="شارژ کیف پول",
       )

   ``execute`` runs inside the approving transaction, must be idempotent
   (derive every ledger command id from ``request.id``, e.g. ``f"mc:{request.id}"``)
   and raises ``MakerCheckerError`` (or ``ValueError``) to refuse; the request
   then stays pending and nothing is written.

2. The maker calls ``create_request(db, user=..., kind=..., payload=..., idempotency_key=...)``
   from their endpoint instead of moving money. Same key + same payload returns
   the same request; same key + different payload is a 409. Nothing moves yet.

3. A DIFFERENT user for whom ``can_check(user, payload)`` is true calls
   ``approve(db, request_id=..., user=...)``; the row is locked, expiry and
   status re-checked, ``execute`` runs, and the request becomes ``executed``
   with ``result_json``. Approving an already-executed request returns it
   unchanged (idempotent replay); it never executes twice.
   ``reject(...)`` closes it without executing. Pending requests older than
   ``expires_at`` become ``expired`` lazily (on list/approve) and can no longer
   be approved.

4. Every step (requested / approved+executed / rejected / expired) is passed
   to the ``audit(db, user, action, entity, detail)`` callback given to
   ``maker_checker_router`` / the functions (main.py's ``_platform_audit``).

HTTP (mounted by main.py)
-------------------------
GET  /maker-checker/requests?status=pending&kind=wallet.fund   kinds the caller may check (+ their own requests)
POST /maker-checker/requests/{id}/approve   {"note": "..."}
POST /maker-checker/requests/{id}/reject    {"note": "..."}

The caller may not approve or reject their own request (they may see it).
The calling commit is the caller's: the functions flush, the router commits.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin

DEFAULT_TTL = timedelta(hours=72)
STATUSES = ("pending", "executed", "rejected", "expired")


class MakerCheckerRequest(OperationalMixin, Base):
    __tablename__ = "maker_checker_requests"
    kind: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(String(300), default="")
    amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    maker_user_id: Mapped[int] = mapped_column(Integer, index=True)
    checker_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "kind", "idempotency_key", name="uq_maker_checker_idempotency"),)


class MakerCheckerError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class Kind:
    name: str
    can_check: Callable[[Any, dict], bool]
    execute: Callable[[Session, MakerCheckerRequest, dict, Any], dict]
    label: str = ""


_KINDS: dict[str, Kind] = {}


def register(name: str, *, can_check: Callable[[Any, dict], bool], execute: Callable[[Session, MakerCheckerRequest, dict, Any], dict], label: str = "") -> None:
    """Idempotent registration (re-registering the same name replaces it)."""
    _KINDS[name] = Kind(name, can_check, execute, label or name)


def kinds() -> dict[str, Kind]:
    return dict(_KINDS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _hash(kind: str, payload: dict) -> str:
    return hashlib.sha256(f"{kind}:{json.dumps(payload, sort_keys=True, ensure_ascii=False)}".encode("utf-8")).hexdigest()


def _noop_audit(*_args, **_kwargs) -> None:
    return None


def output(row: MakerCheckerRequest) -> dict:
    kind = _KINDS.get(row.kind)
    return {"id": row.id, "kind": row.kind, "kind_label": kind.label if kind else row.kind, "status": row.status,
            "summary": row.summary, "amount": row.amount, "target_ref": row.target_ref,
            "payload": json.loads(row.payload_json), "maker_user_id": row.maker_user_id,
            "checker_user_id": row.checker_user_id, "decision_note": row.decision_note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "expires_at": _aware(row.expires_at).isoformat() if row.expires_at else None,
            "result": json.loads(row.result_json) if row.result_json else None}


def create_request(db: Session, *, user, kind: str, payload: dict, idempotency_key: str, summary: str = "",
                   amount: Optional[int] = None, target_ref: Optional[str] = None, ttl: timedelta = DEFAULT_TTL,
                   audit: Callable = _noop_audit) -> MakerCheckerRequest:
    if kind not in _KINDS:
        raise MakerCheckerError(500, f"unknown maker-checker kind {kind}")
    request_hash = _hash(kind, payload)
    prior = db.scalar(select(MakerCheckerRequest).where(MakerCheckerRequest.tenant_id == user.tenant_id, MakerCheckerRequest.kind == kind, MakerCheckerRequest.idempotency_key == idempotency_key))
    if prior is not None:
        if prior.request_hash != request_hash or prior.maker_user_id != user.id:
            raise MakerCheckerError(409, "این شناسهٔ درخواست قبلاً با محتوای دیگری ثبت شده است")
        return prior
    row = MakerCheckerRequest(tenant_id=user.tenant_id, kind=kind, status="pending", payload_json=json.dumps(payload, sort_keys=True, ensure_ascii=False),
                              request_hash=request_hash, idempotency_key=idempotency_key, summary=summary[:300], amount=amount,
                              target_ref=target_ref, maker_user_id=user.id, expires_at=_now() + ttl)
    db.add(row)
    db.flush()
    audit(db, user, f"maker_checker.{kind}.requested", "maker_checker_request", {"request_id": row.id, "kind": kind, "amount": amount, "target_ref": target_ref})
    return row


def _expire_if_stale(db: Session, row: MakerCheckerRequest, user, audit: Callable) -> bool:
    if row.status == "pending" and _aware(row.expires_at) <= _now():
        row.status, row.decided_at = "expired", _now()
        audit(db, user, f"maker_checker.{row.kind}.expired", "maker_checker_request", {"request_id": row.id})
        return True
    return False


def _locked(db: Session, tenant_id: int, request_id: str) -> MakerCheckerRequest:
    row = db.scalar(select(MakerCheckerRequest).where(MakerCheckerRequest.id == request_id, MakerCheckerRequest.tenant_id == tenant_id).with_for_update())
    if row is None:
        raise MakerCheckerError(404, "درخواست یافت نشد")
    return row


def _checker_guard(row: MakerCheckerRequest, user) -> Kind:
    kind = _KINDS.get(row.kind)
    if kind is None:
        raise MakerCheckerError(409, "نوع این درخواست دیگر پشتیبانی نمی‌شود")
    if row.maker_user_id == user.id:
        raise MakerCheckerError(403, "ثبت‌کنندهٔ درخواست نمی‌تواند خودش آن را تأیید یا رد کند")
    if not kind.can_check(user, json.loads(row.payload_json)):
        raise MakerCheckerError(403, "مجوز تأیید این درخواست وجود ندارد")
    return kind


def approve(db: Session, *, request_id: str, user, note: Optional[str] = None, audit: Callable = _noop_audit) -> MakerCheckerRequest:
    row = _locked(db, user.tenant_id, request_id)
    if row.status == "executed":
        if row.checker_user_id == user.id:
            return row  # idempotent replay of the same approval
        raise MakerCheckerError(409, "این درخواست قبلاً تأیید و اجرا شده است")
    kind = _checker_guard(row, user)
    if _expire_if_stale(db, row, user, audit):
        db.flush()
        raise MakerCheckerError(409, "مهلت این درخواست تمام شده است؛ درخواست تازه ثبت کنید")
    if row.status != "pending":
        raise MakerCheckerError(409, "این درخواست دیگر در انتظار تأیید نیست")
    try:
        with db.begin_nested():
            result = kind.execute(db, row, json.loads(row.payload_json), user)
    except ValueError as exc:
        raise MakerCheckerError(409, str(exc)) from exc
    row.status, row.checker_user_id, row.decided_at = "executed", user.id, _now()
    row.decision_note = (note or None) and note[:500]
    row.result_json = json.dumps(result or {}, sort_keys=True, ensure_ascii=False, default=str)
    db.flush()
    audit(db, user, f"maker_checker.{row.kind}.approved", "maker_checker_request", {"request_id": row.id, "kind": row.kind, "maker_user_id": row.maker_user_id, "amount": row.amount, "target_ref": row.target_ref})
    return row


def reject(db: Session, *, request_id: str, user, note: Optional[str] = None, audit: Callable = _noop_audit) -> MakerCheckerRequest:
    row = _locked(db, user.tenant_id, request_id)
    if row.status == "rejected" and row.checker_user_id == user.id:
        return row
    _checker_guard(row, user)
    if _expire_if_stale(db, row, user, audit):
        db.flush()
        raise MakerCheckerError(409, "مهلت این درخواست تمام شده است")
    if row.status != "pending":
        raise MakerCheckerError(409, "این درخواست دیگر در انتظار تأیید نیست")
    row.status, row.checker_user_id, row.decided_at = "rejected", user.id, _now()
    row.decision_note = (note or None) and note[:500]
    db.flush()
    audit(db, user, f"maker_checker.{row.kind}.rejected", "maker_checker_request", {"request_id": row.id, "kind": row.kind, "maker_user_id": row.maker_user_id})
    return row


def list_requests(db: Session, *, user, status: Optional[str] = "pending", kind: Optional[str] = None, audit: Callable = _noop_audit, limit: int = 200) -> list[dict]:
    q = select(MakerCheckerRequest).where(MakerCheckerRequest.tenant_id == user.tenant_id)
    if kind:
        q = q.where(MakerCheckerRequest.kind == kind)
    rows = db.scalars(q.order_by(MakerCheckerRequest.created_at.desc()).limit(limit)).all()
    out = []
    for row in rows:
        _expire_if_stale(db, row, user, audit)
        if status and row.status != status:
            continue
        own = row.maker_user_id == user.id
        k = _KINDS.get(row.kind)
        can_check = (not own) and k is not None and k.can_check(user, json.loads(row.payload_json))
        if own or can_check:
            out.append({**output(row), "mine": own, "can_decide": can_check and row.status == "pending"})
    return out


class DecisionNoteIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


def maker_checker_router(get_db, current_user, audit: Callable = _noop_audit) -> APIRouter:
    api = APIRouter(tags=["maker-checker"])

    @api.get("/maker-checker/requests")
    def list_route(status: Optional[str] = "pending", kind: Optional[str] = None, user=Depends(current_user), db: Session = Depends(get_db)):
        if status and status not in STATUSES:
            raise HTTPException(status_code=422, detail="وضعیت نامعتبر است")
        items = list_requests(db, user=user, status=status or None, kind=kind, audit=audit)
        db.commit()
        return {"items": items}

    @api.post("/maker-checker/requests/{request_id}/approve")
    def approve_route(request_id: str, data: DecisionNoteIn, user=Depends(current_user), db: Session = Depends(get_db)):
        try:
            row = approve(db, request_id=request_id, user=user, note=data.note, audit=audit)
        except MakerCheckerError as exc:
            db.commit()  # keep a lazy expiry; nothing else was written
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        db.commit()
        return output(row)

    @api.post("/maker-checker/requests/{request_id}/reject")
    def reject_route(request_id: str, data: DecisionNoteIn, user=Depends(current_user), db: Session = Depends(get_db)):
        try:
            row = reject(db, request_id=request_id, user=user, note=data.note, audit=audit)
        except MakerCheckerError as exc:
            db.commit()
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        db.commit()
        return output(row)

    return api
