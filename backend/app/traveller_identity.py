"""Traveller identity (هویت مسافر): national code, birth date, gender, nationality and passport.

* Stored 1:1 next to `travellers` in its own tenant-isolated table so the identity numbers never
  travel with the plain traveller list.
* Lists show only a masked number (last 4 digits). The full values are returned to the owning
  account only (`GET /me/travellers/{id}/identity`); staff must give a reason and the read is audited
  (`POST /ops/travellers/{id}/identity/reveal`).
* The national code is checked with the Iranian check-digit rule; an invalid value is rejected with a
  Persian message, never silently dropped.
* `requirement_errors` holds the per-vertical rules enforced at the checkout traveller step:
  flight/train need a national code for Iranians or a passport for foreign nationals; an international
  flight needs a passport that is still valid on the travel date.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Date, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

GENDERS = {"male": "مرد", "female": "زن"}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PASSPORT_RE = re.compile(r"^[A-Z0-9]{6,12}$")
_NATIONALITY_RE = re.compile(r"^[A-Z]{2}$")


class TravellerIdentity(OperationalMixin, Base):
    __tablename__ = "traveller_identities"
    traveller_id: Mapped[str] = mapped_column(ForeignKey("travellers.id"), unique=True, index=True)
    national_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    passport_number: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    passport_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


def normalize_digits(value: Optional[str]) -> str:
    return re.sub(r"[\s\-]", "", (value or "").translate(_DIGITS))


def valid_national_code(value: Optional[str]) -> bool:
    """Iranian national code: 10 digits, not one repeated digit, last digit is the check digit."""
    code = normalize_digits(value)
    if not re.fullmatch(r"\d{10}", code) or len(set(code)) == 1:
        return False
    remainder = sum(int(code[i]) * (10 - i) for i in range(9)) % 11
    check = int(code[9])
    return check == remainder if remainder < 2 else check == 11 - remainder


def mask_last4(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return "•" * max(0, len(value) - 4) + value[-4:]


def _parse_date(value: Optional[str], label: str) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        text = value.strip().translate(_DIGITS)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise ValueError(text)
        return date.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{label} معتبر نیست؛ تاریخ را از تقویم انتخاب کنید")


class IdentityFields(BaseModel):
    """Optional identity fields accepted by POST/PUT /me/travellers. Validation is done in `apply_identity`
    so every rejection carries a Persian message."""
    national_code: Optional[str] = Field(default=None, max_length=20)
    birth_date: Optional[str] = Field(default=None, max_length=20)
    gender: Optional[str] = Field(default=None, max_length=8)
    nationality: Optional[str] = Field(default=None, max_length=2)
    passport_number: Optional[str] = Field(default=None, max_length=20)
    passport_expiry: Optional[str] = Field(default=None, max_length=20)


IDENTITY_KEYS = tuple(IdentityFields.model_fields)


def apply_identity(db: Session, traveller: "m.Traveller", data: BaseModel, *, today: Optional[date] = None) -> Optional[TravellerIdentity]:
    """Validate the identity part of a traveller payload and persist it. Fields not sent keep their value;
    an empty string clears a field."""
    sent = {k: getattr(data, k) for k in IDENTITY_KEYS if k in data.model_fields_set}
    row = db.scalar(select(TravellerIdentity).where(TravellerIdentity.tenant_id == traveller.tenant_id, TravellerIdentity.traveller_id == traveller.id))
    if not sent:
        return row
    today = today or datetime.now(timezone.utc).date()
    values = {k: getattr(row, k) if row else None for k in IDENTITY_KEYS}
    if "national_code" in sent:
        raw = normalize_digits(sent["national_code"])
        if raw and not valid_national_code(raw):
            raise HTTPException(status_code=422, detail="کد ملی معتبر نیست؛ ۱۰ رقم کد ملی را دوباره بررسی کنید")
        values["national_code"] = raw or None
    if "birth_date" in sent:
        born = _parse_date(sent["birth_date"], "تاریخ تولد")
        if born and (born > today or born.year < 1900):
            raise HTTPException(status_code=422, detail="تاریخ تولد معتبر نیست")
        values["birth_date"] = born
    if "gender" in sent:
        if sent["gender"] and sent["gender"] not in GENDERS:
            raise HTTPException(status_code=422, detail="جنسیت را انتخاب کنید")
        values["gender"] = sent["gender"] or None
    if "nationality" in sent:
        nat = (sent["nationality"] or "").upper()
        if nat and not _NATIONALITY_RE.match(nat):
            raise HTTPException(status_code=422, detail="تابعیت معتبر نیست")
        values["nationality"] = nat or None
    if "passport_number" in sent:
        number = normalize_digits(sent["passport_number"]).upper()
        if number and not _PASSPORT_RE.match(number):
            raise HTTPException(status_code=422, detail="شماره گذرنامه معتبر نیست؛ ۶ تا ۱۲ حرف و رقم لاتین وارد کنید")
        values["passport_number"] = number or None
    if "passport_expiry" in sent:
        expiry = _parse_date(sent["passport_expiry"], "تاریخ انقضای گذرنامه")
        if expiry and expiry <= today:
            raise HTTPException(status_code=422, detail="گذرنامه منقضی شده است؛ تاریخ انقضای معتبر وارد کنید")
        values["passport_expiry"] = expiry
    if bool(values["passport_number"]) != bool(values["passport_expiry"]):
        raise HTTPException(status_code=422, detail="شماره و تاریخ انقضای گذرنامه را با هم وارد کنید")
    if values["national_code"] and values["nationality"] and values["nationality"] != "IR":
        raise HTTPException(status_code=422, detail="کد ملی فقط برای مسافر ایرانی ثبت می‌شود؛ برای اتباع خارجی شماره گذرنامه را وارد کنید")
    if values["national_code"] and not values["nationality"]:
        values["nationality"] = "IR"
    if row is None:
        row = TravellerIdentity(tenant_id=traveller.tenant_id, traveller_id=traveller.id)
        db.add(row)
    for k, v in values.items():
        setattr(row, k, v)
    return row


def identities_for(db: Session, tenant_id: int, traveller_ids: list[str]) -> dict[str, TravellerIdentity]:
    if not traveller_ids:
        return {}
    rows = db.scalars(select(TravellerIdentity).where(TravellerIdentity.tenant_id == tenant_id, TravellerIdentity.traveller_id.in_(traveller_ids))).all()
    return {r.traveller_id: r for r in rows}


def masked(row: Optional[TravellerIdentity]) -> dict:
    """List/summary view: never the full national code or passport number."""
    if row is None:
        return {"national_code_masked": None, "passport_number_masked": None, "birth_date": None, "gender": None,
                "nationality": None, "passport_expiry": None, "has_national_code": False, "has_passport": False}
    return {"national_code_masked": mask_last4(row.national_code), "passport_number_masked": mask_last4(row.passport_number),
            "birth_date": row.birth_date.isoformat() if row.birth_date else None, "gender": row.gender, "nationality": row.nationality,
            "passport_expiry": row.passport_expiry.isoformat() if row.passport_expiry else None,
            "has_national_code": bool(row.national_code), "has_passport": bool(row.passport_number)}


def full(row: Optional[TravellerIdentity]) -> dict:
    out = masked(row)
    out.update({"national_code": row.national_code if row else None, "passport_number": row.passport_number if row else None})
    return out


def traveller_output(traveller: "m.Traveller", identity: Optional[TravellerIdentity]) -> dict:
    return {"id": traveller.id, "full_name": traveller.full_name, "profile_reference": traveller.profile_reference, **masked(identity)}


def requirement_errors(service_type: str, travellers: list["m.Traveller"], identities: dict[str, TravellerIdentity], *,
                       international: bool, travel_date: Optional[date] = None) -> list[str]:
    """Per-vertical identity rules for the checkout traveller step (Persian, one line per traveller)."""
    if service_type not in ("flight", "train"):
        return []
    errors = []
    for t in travellers:
        ident = identities.get(t.id)
        nationality = (ident.nationality if ident else None) or "IR"
        passport_ok = bool(ident and ident.passport_number and ident.passport_expiry)
        if international and service_type == "flight":
            if not passport_ok:
                errors.append(f"برای «{t.full_name}» در پرواز خارجی شماره و تاریخ انقضای گذرنامه لازم است")
            elif travel_date and ident.passport_expiry <= travel_date:
                errors.append(f"گذرنامهٔ «{t.full_name}» تا تاریخ سفر معتبر نیست")
        elif nationality == "IR":
            if not (ident and ident.national_code):
                errors.append(f"برای «{t.full_name}» کد ملی لازم است (برای اتباع خارجی، تابعیت و گذرنامه را ثبت کنید)")
        elif not passport_ok:
            errors.append(f"برای «{t.full_name}» (تبعهٔ خارجی) شماره و تاریخ انقضای گذرنامه لازم است")
    return errors


def is_international(attributes: dict) -> bool:
    if not isinstance(attributes, dict):
        return False
    if attributes.get("scope") == "international" or attributes.get("international") is True:
        return True
    countries = [str(attributes.get(k) or "").upper() for k in ("origin_country", "destination_country")]
    return any(c and c != "IR" for c in countries)


class RevealIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


def traveller_identity_router(get_db, current_user, role_has_permission, audit):
    api = APIRouter(tags=["traveller-identity"])

    def staff(user=Depends(current_user)):
        if user.role in ("employee", "customer") or not any(role_has_permission(user.role, p) for p in ("backoffice:read", "support:manage", "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی کارشناس عملیات لازم است")
        return user

    @api.get("/me/travellers/{traveller_id}/identity")
    def my_identity(traveller_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        t = db.scalar(select(m.Traveller).where(m.Traveller.id == traveller_id, m.Traveller.tenant_id == user.tenant_id, m.Traveller.user_id == user.id))
        if t is None:
            raise HTTPException(status_code=404, detail="مسافر در این حساب وجود ندارد")
        return {"id": t.id, "full_name": t.full_name, **full(identities_for(db, user.tenant_id, [t.id]).get(t.id))}

    @api.get("/reservations/{reservation_id}/traveller-requirements")
    def reservation_requirements(reservation_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """Which identity fields the checkout traveller step will require for this reservation."""
        import json
        r = db.scalar(select(m.Reservation).where(m.Reservation.id == reservation_id, m.Reservation.tenant_id == user.tenant_id, m.Reservation.user_id == user.id))
        if r is None:
            raise HTTPException(status_code=404, detail="رزروی با این مشخصات پیدا نشد")
        if r.service_type not in ("flight", "train"):
            return {"requirement": "none", "service_type": r.service_type}
        item = db.scalar(select(m.BookingItem).where(m.BookingItem.reservation_id == r.id, m.BookingItem.tenant_id == user.tenant_id))
        attrs = (json.loads(item.snapshot_json).get("attributes") or {}) if item else {}
        international = r.service_type == "flight" and is_international(attrs)
        return {"requirement": "international" if international else "domestic", "service_type": r.service_type,
                "travel_date": str(attrs.get("departure_time") or "")[:10] or None}

    @api.post("/ops/travellers/{traveller_id}/identity/reveal")
    def reveal(traveller_id: str, data: RevealIn, user=Depends(staff), db: Session = Depends(get_db)) -> dict:
        t = db.scalar(select(m.Traveller).where(m.Traveller.id == traveller_id, m.Traveller.tenant_id == user.tenant_id))
        if t is None:
            raise HTTPException(status_code=404, detail="مسافر وجود ندارد")
        audit(db, user, "traveller_identity.revealed", "traveller", {"traveller_id": t.id, "reason": data.reason})
        db.commit()
        return {"id": t.id, "full_name": t.full_name, **full(identities_for(db, user.tenant_id, [t.id]).get(t.id))}

    return api
