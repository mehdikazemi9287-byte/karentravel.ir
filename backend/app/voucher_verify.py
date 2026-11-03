"""Voucher QR (کد QR واچر) and public verification.

The QR carries an opaque, signed code (tenant + reservation + HMAC). Anyone scanning it — a hotel desk, a tour
leader — sees only whether the voucher is valid, the masked booking reference, the service and status. No name,
price or contact detail is exposed. The QR exists only for a reservation whose voucher is actually issued.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import operations as m

STATUS_FA = {"issued": "صادرشده و معتبر", "completed": "سفر انجام شده", "cancelled": "لغو شده", "refunded": "مسترد شده",
             "changed": "تغییر کرده", "change_requested": "در حال تغییر", "cancel_requested": "در حال لغو", "refund_requested": "در حال استرداد"}
VALID = ("issued", "changed", "change_requested")
SERVICE_FA = {"flight": "پرواز", "hotel": "هتل", "tour": "تور", "train": "قطار", "bus": "اتوبوس", "visa": "ویزا", "vacation_rental": "اقامتگاه", "car_rental": "خودرو"}


def _sig(secret: str, tenant_id: int, reservation_id: str) -> str:
    d = hmac.new(secret.encode("utf-8"), f"voucher:{tenant_id}:{reservation_id}".encode("utf-8"), hashlib.sha256).digest()[:12]
    return base64.urlsafe_b64encode(d).decode("ascii").rstrip("=")


def make_code(secret: str, tenant_id: int, reservation_id: str) -> str:
    return f"{tenant_id}.{reservation_id}.{_sig(secret, tenant_id, reservation_id)}"


def parse_code(secret: str, code: str) -> Optional[tuple[int, str]]:
    parts = (code or "").split(".")
    if len(parts) != 3 or not parts[0].isdigit() or len(parts[1]) != 36:
        return None
    tid, rid, sig = int(parts[0]), parts[1], parts[2]
    return (tid, rid) if hmac.compare_digest(sig, _sig(secret, tid, rid)) else None


def mask_ref(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    return ref if len(ref) <= 4 else "•" * (len(ref) - 4) + ref[-4:]


def voucher_verify_router(get_db, current_user, jwt_secret: str, set_tenant_context: Callable):
    from .account_security import qr_svg

    secret = os.environ.get("VOUCHER_QR_SECRET") or jwt_secret
    site = (os.environ.get("PUBLIC_SITE_URL") or "https://karentravel.ir").rstrip("/")
    api = APIRouter(tags=["voucher-verify"])

    @api.get("/me/reservations/{reservation_id}/voucher-qr")
    def voucher_qr(reservation_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
        r = db.scalar(select(m.Reservation).where(m.Reservation.id == reservation_id, m.Reservation.tenant_id == user.tenant_id, m.Reservation.user_id == user.id))
        if r is None:
            raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
        voucher = db.scalar(select(m.Voucher).where(m.Voucher.reservation_id == r.id, m.Voucher.tenant_id == user.tenant_id).order_by(m.Voucher.revision.desc()))
        if r.status not in VALID or voucher is None or voucher.status != "issued":
            raise HTTPException(status_code=409, detail="واچر این رزرو هنوز صادر نشده است")
        code = make_code(secret, user.tenant_id, r.id)
        url = f"{site}/v/{code}"
        return {"code": code, "verify_url": url, "qr_svg": qr_svg(url), "voucher_link": f"/reservations/{r.id}/voucher"}

    @api.get("/public/vouchers/{code}")
    def verify(code: str, db: Session = Depends(get_db)):
        parsed = parse_code(secret, code)
        if parsed is None:
            raise HTTPException(status_code=404, detail="این کد واچر معتبر نیست")
        tid, rid = parsed
        set_tenant_context(db, tid)
        r = db.scalar(select(m.Reservation).where(m.Reservation.id == rid, m.Reservation.tenant_id == tid))
        if r is None:
            raise HTTPException(status_code=404, detail="این کد واچر معتبر نیست")
        voucher = db.scalar(select(m.Voucher).where(m.Voucher.reservation_id == r.id, m.Voucher.tenant_id == tid).order_by(m.Voucher.revision.desc()))
        valid = r.status in VALID and voucher is not None and voucher.status == "issued"
        return {"valid": valid, "booking_reference": mask_ref(r.booking_reference), "service": SERVICE_FA.get(r.service_type, r.service_type),
                "status": STATUS_FA.get(r.status, "نامعتبر"), "revision": voucher.revision if voucher else None}

    return api
