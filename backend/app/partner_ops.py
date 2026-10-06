"""Partner management, agency quotes, commission ledger and accounting views.

Rules that keep this honest:
- an agency quote always points at a real, currently valid supplier offer and carries that offer's price unchanged;
- a booking counts for an agency only on the agency's own sales channel, and a customer may use that channel only
  with an accepted quote from that agency (see main._resolve_transaction_provenance);
- a commission entry is posted by finance for a confirmed, priced reservation, once, and moves
  accrued -> approved -> settled (or reversed); nothing is posted automatically;
- accounting figures are sums over stored rows with the formula stated in the response.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from . import operations as m
from .catalog import CatalogHotel, CatalogHotelProviderMapping, normalize_text

QUOTE_OPEN = ("sent",)
COMMISSION_FLOW = {"accrued": {"approved", "reversed"}, "approved": {"settled", "reversed"}, "settled": set(), "reversed": set()}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgencyIn(Strict):
    display_name: str = Field(min_length=2, max_length=180)
    commission_bps: int = Field(default=0, ge=0, le=5000)
    markup_bps: int = Field(default=0, ge=0, le=5000)


class SupplierIn(Strict):
    display_name: str = Field(min_length=2, max_length=180)
    supplier_type: Literal["hotel", "tour", "transport", "experience", "flight", "other"]


class NameIn(Strict):
    name: str = Field(min_length=3, max_length=160)


class UserIn(Strict):
    user_id: int = Field(gt=0)


class HotelIn(Strict):
    hotel_id: str = Field(min_length=1, max_length=40)


class CreditLinkIn(Strict):
    credit_account_id: Optional[str] = Field(default=None, min_length=36, max_length=36)


class MappingIn(Strict):
    provider: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    provider_hotel_id: str = Field(min_length=1, max_length=120)


class QuoteIn(Strict):
    offer_id: str = Field(min_length=36, max_length=36)
    customer_user_id: int = Field(gt=0)
    note: Optional[str] = Field(default=None, max_length=1000)


class DecisionIn(Strict):
    decision: Literal["accept", "decline"]


class LinkBookingIn(Strict):
    reservation_id: str = Field(min_length=36, max_length=36)


class AccrueIn(Strict):
    reservation_id: str = Field(min_length=36, max_length=36)


class SettleIn(Strict):
    external_reference: str = Field(min_length=3, max_length=160)


class ReasonIn(Strict):
    reason: str = Field(min_length=3, max_length=500)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _total(r: m.Reservation):
    snap = json.loads(r.price_snapshot_json or "{}")
    amount = snap.get("total_amount")
    return (amount, snap.get("currency") or "IRR") if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0 else (None, None)


def agency_channel_allowed(db: Session, user, channel: m.SalesChannel) -> bool:
    """Used by the booking provenance check: an AGENCY channel is usable only by a customer holding an accepted quote of the agency that owns it."""
    if channel.channel_type != "AGENCY":
        return True
    agency_ids = select(m.Agency.id).where(m.Agency.tenant_id == user.tenant_id, m.Agency.sales_channel_id == channel.id)
    return db.scalar(select(m.AgencyQuote.id).where(m.AgencyQuote.tenant_id == user.tenant_id, m.AgencyQuote.customer_user_id == user.id, m.AgencyQuote.agency_id.in_(agency_ids),
                                                    m.AgencyQuote.status.in_(("accepted", "booked"))).limit(1)) is not None


def partner_ops_router(get_db, current_user, require_permission, role_has_permission, supplier_scope: Callable, audit: Callable, User) -> APIRouter:
    router = APIRouter(tags=["partner-ops"])
    admin = require_permission("tenant:manage")
    agency_user = require_permission("agency:manage")
    now = lambda: datetime.now(timezone.utc)  # noqa: E731

    def agency_for(db: Session, agency_id: str, user, lock: bool = False) -> m.Agency:
        stmt = select(m.Agency).where(m.Agency.id == agency_id, m.Agency.tenant_id == user.tenant_id)
        row = db.scalar(stmt.with_for_update() if lock else stmt)
        ok = row is not None and (role_has_permission(user.role, "tenant:manage") or db.scalar(select(m.AgencyMembership.id).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.user_id == user.id, m.AgencyMembership.agency_id == agency_id)))
        if not ok: raise HTTPException(status_code=404, detail="آژانس در دسترس این حساب نیست")
        return row

    def supplier_for_admin(db: Session, supplier_id: str, user) -> m.Supplier:
        row = db.scalar(select(m.Supplier).where(m.Supplier.id == supplier_id, m.Supplier.tenant_id == user.tenant_id))
        if row is None: raise HTTPException(status_code=404, detail="تأمین‌کننده در این مجموعه وجود ندارد")
        return row

    def tenant_user(db: Session, user_id: int, user, permission: str) -> object:
        target = db.scalar(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
        if target is None or not role_has_permission(target.role, permission) or role_has_permission(target.role, "platform:manage"): raise HTTPException(status_code=422, detail="کاربر باید در همین مجموعه و با نقش متناسب باشد")
        return target

    # ---- Supplier / agency management (tenant administration) ----------------------------------------------------
    @router.get("/admin/partners")
    def partners(user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        t = user.tenant_id
        users = {u.id: u for u in db.scalars(select(User).where(User.tenant_id == t))}
        brief = lambda uid: {"user_id": uid, "name": users[uid].name if uid in users else None}  # noqa: E731
        channels = db.scalars(select(m.SalesChannel).where(m.SalesChannel.tenant_id == t).order_by(m.SalesChannel.name)).all()
        agencies = db.scalars(select(m.Agency).where(m.Agency.tenant_id == t).order_by(m.Agency.created_at.desc())).all()
        a_members, s_members, s_hotels = {}, {}, {}
        for x in db.scalars(select(m.AgencyMembership).where(m.AgencyMembership.tenant_id == t)): a_members.setdefault(x.agency_id, []).append(brief(x.user_id))
        for x in db.scalars(select(m.SupplierMembership).where(m.SupplierMembership.tenant_id == t)): s_members.setdefault(x.supplier_id, []).append(brief(x.user_id))
        links = db.scalars(select(m.SupplierCatalogHotel).where(m.SupplierCatalogHotel.tenant_id == t)).all()
        names = {h.id: h.name_fa or h.name_en or h.name_local for h in db.scalars(select(CatalogHotel).where(CatalogHotel.id.in_({x.hotel_id for x in links})))} if links else {}
        for x in links: s_hotels.setdefault(x.supplier_id, []).append({"hotel_id": x.hotel_id, "name": names.get(x.hotel_id)})
        by_channel = {a.sales_channel_id: a.id for a in agencies if a.sales_channel_id}
        return {"suppliers": [{"id": s.id, "name": s.display_name, "type": s.supplier_type, "status": s.status, "lifecycle_status": s.lifecycle_status, "members": s_members.get(s.id, []), "hotels": s_hotels.get(s.id, [])}
                              for s in db.scalars(select(m.Supplier).where(m.Supplier.tenant_id == t).order_by(m.Supplier.created_at.desc()))],
                "agencies": [{"id": a.id, "name": a.display_name, "status": a.status, "commission_bps": a.commission_bps, "markup_bps": a.markup_bps, "sales_channel_id": a.sales_channel_id, "credit_account_id": a.credit_account_id, "members": a_members.get(a.id, [])} for a in agencies],
                "sales_channels": [{"id": c.id, "name": c.name, "type": c.channel_type, "status": c.status, "agency_id": by_channel.get(c.id)} for c in channels],
                "credit_accounts": [{"id": c.id, "currency": c.currency, "limit_amount": c.limit_amount} for c in db.scalars(select(m.CreditAccount).where(m.CreditAccount.tenant_id == t))],
                "agency_users": [brief(u.id) for u in users.values() if u.role == "agency_partner"], "supplier_users": [brief(u.id) for u in users.values() if u.role == "supplier"]}

    @router.post("/admin/partners/agencies", status_code=201)
    def create_agency(data: AgencyIn, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        if db.scalar(select(m.Agency.id).where(m.Agency.tenant_id == user.tenant_id, m.Agency.display_name == data.display_name.strip())): raise HTTPException(status_code=409, detail="آژانسی با این نام وجود دارد")
        row = m.Agency(tenant_id=user.tenant_id, display_name=data.display_name.strip(), status="active", commission_bps=data.commission_bps, markup_bps=data.markup_bps); db.add(row); db.flush()
        audit(db, user, "agency.created", "agency", {"agency_id": row.id, "commission_bps": row.commission_bps}); db.commit()
        return {"id": row.id, "name": row.display_name}

    @router.post("/admin/partners/agencies/{agency_id}/sales-channel", status_code=201)
    def create_agency_channel(agency_id: str, data: NameIn, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user, lock=True)
        if agency.sales_channel_id: raise HTTPException(status_code=409, detail="این آژانس کانال فروش دارد")
        entity = db.scalar(select(m.LicensedEntity).where(m.LicensedEntity.tenant_id == user.tenant_id, m.LicensedEntity.status == "active").order_by(m.LicensedEntity.created_at))
        if entity is None: raise HTTPException(status_code=409, detail="ابتدا نهاد دارای مجوز فروش برای این مجموعه ثبت شود")
        if db.scalar(select(m.SalesChannel.id).where(m.SalesChannel.tenant_id == user.tenant_id, m.SalesChannel.name == data.name.strip())): raise HTTPException(status_code=409, detail="کانال فروشی با این نام وجود دارد")
        channel = m.SalesChannel(tenant_id=user.tenant_id, name=data.name.strip(), channel_type="AGENCY", licensed_entity_id=entity.id, status="active"); db.add(channel); db.flush()
        agency.sales_channel_id = channel.id
        audit(db, user, "agency.sales_channel_created", "agency", {"agency_id": agency.id, "sales_channel_id": channel.id}); db.commit()
        return {"agency_id": agency.id, "sales_channel_id": channel.id}

    @router.delete("/admin/partners/agencies/{agency_id}/members/{user_id}")
    def remove_agency_member(agency_id: str, user_id: int, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user)
        removed = db.execute(delete(m.AgencyMembership).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.agency_id == agency.id, m.AgencyMembership.user_id == user_id)).rowcount
        if removed: audit(db, user, "agency.member_removed", "agency", {"agency_id": agency.id, "user_id": user_id}); db.commit()
        return {"removed": bool(removed)}

    @router.put("/admin/partners/agencies/{agency_id}/credit-account")
    def link_agency_credit(agency_id: str, data: CreditLinkIn, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user, lock=True)
        if data.credit_account_id:
            if db.scalar(select(m.CreditAccount.id).where(m.CreditAccount.id == data.credit_account_id, m.CreditAccount.tenant_id == user.tenant_id)) is None: raise HTTPException(status_code=422, detail="حساب اعتباری در این مجموعه وجود ندارد")
            if db.scalar(select(m.Agency.id).where(m.Agency.tenant_id == user.tenant_id, m.Agency.credit_account_id == data.credit_account_id, m.Agency.id != agency.id)): raise HTTPException(status_code=409, detail="این حساب اعتباری به آژانس دیگری متصل است")
        previous, agency.credit_account_id = agency.credit_account_id, data.credit_account_id
        audit(db, user, "agency.credit_account_linked", "agency", {"agency_id": agency.id, "from": previous, "to": data.credit_account_id}); db.commit()
        return {"agency_id": agency.id, "credit_account_id": agency.credit_account_id}

    @router.post("/admin/partners/suppliers", status_code=201)
    def create_supplier(data: SupplierIn, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        if db.scalar(select(m.Supplier.id).where(m.Supplier.tenant_id == user.tenant_id, m.Supplier.display_name == data.display_name.strip())): raise HTTPException(status_code=409, detail="تأمین‌کننده‌ای با این نام وجود دارد")
        row = m.Supplier(tenant_id=user.tenant_id, display_name=data.display_name.strip(), supplier_type=data.supplier_type, status="active"); db.add(row); db.flush()
        audit(db, user, "supplier.created", "supplier", {"supplier_id": row.id, "type": row.supplier_type}); db.commit()
        return {"id": row.id, "name": row.display_name}

    @router.post("/admin/partners/suppliers/{supplier_id}/members", status_code=201)
    def add_supplier_member(supplier_id: str, data: UserIn, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        supplier, target = supplier_for_admin(db, supplier_id, user), tenant_user(db, data.user_id, user, "inventory:manage")
        if db.scalar(select(m.SupplierMembership.id).where(m.SupplierMembership.tenant_id == user.tenant_id, m.SupplierMembership.supplier_id == supplier.id, m.SupplierMembership.user_id == target.id)) is None:
            db.add(m.SupplierMembership(tenant_id=user.tenant_id, supplier_id=supplier.id, user_id=target.id, role="owner"))
            audit(db, user, "supplier.member_added", "supplier", {"supplier_id": supplier.id, "user_id": target.id}); db.commit()
        return {"supplier_id": supplier.id, "user_id": target.id}

    @router.delete("/admin/partners/suppliers/{supplier_id}/members/{user_id}")
    def remove_supplier_member(supplier_id: str, user_id: int, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        supplier = supplier_for_admin(db, supplier_id, user)
        removed = db.execute(delete(m.SupplierMembership).where(m.SupplierMembership.tenant_id == user.tenant_id, m.SupplierMembership.supplier_id == supplier.id, m.SupplierMembership.user_id == user_id)).rowcount
        if removed: audit(db, user, "supplier.member_removed", "supplier", {"supplier_id": supplier.id, "user_id": user_id}); db.commit()
        return {"removed": bool(removed)}

    @router.post("/admin/partners/suppliers/{supplier_id}/hotels", status_code=201)
    def add_supplier_hotel(supplier_id: str, data: HotelIn, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        supplier = supplier_for_admin(db, supplier_id, user)
        hotel = db.get(CatalogHotel, data.hotel_id)
        if hotel is None or hotel.duplicate_of: raise HTTPException(status_code=422, detail="هتل در فهرست مرجع نیست یا رکورد تکراری است")
        if db.scalar(select(m.SupplierCatalogHotel.id).where(m.SupplierCatalogHotel.tenant_id == user.tenant_id, m.SupplierCatalogHotel.supplier_id == supplier.id, m.SupplierCatalogHotel.hotel_id == hotel.id)) is None:
            db.add(m.SupplierCatalogHotel(tenant_id=user.tenant_id, supplier_id=supplier.id, hotel_id=hotel.id))
            audit(db, user, "supplier.hotel_assigned", "supplier", {"supplier_id": supplier.id, "hotel_id": hotel.id}); db.commit()
        return {"supplier_id": supplier.id, "hotel_id": hotel.id}

    @router.delete("/admin/partners/suppliers/{supplier_id}/hotels/{hotel_id}")
    def remove_supplier_hotel(supplier_id: str, hotel_id: str, user=Depends(admin), db: Session = Depends(get_db)) -> dict:
        supplier = supplier_for_admin(db, supplier_id, user)
        removed = db.execute(delete(m.SupplierCatalogHotel).where(m.SupplierCatalogHotel.tenant_id == user.tenant_id, m.SupplierCatalogHotel.supplier_id == supplier.id, m.SupplierCatalogHotel.hotel_id == hotel_id)).rowcount
        if removed: audit(db, user, "supplier.hotel_unassigned", "supplier", {"supplier_id": supplier.id, "hotel_id": hotel_id}); db.commit()
        return {"removed": bool(removed)}

    # ---- Supplier self-service: hotels assigned to me and my provider ids (verification stays with KarenSeir) -----
    def my_hotel_ids(db: Session, user) -> set[str]:
        scope = supplier_scope(db, user)
        return set(db.scalars(select(m.SupplierCatalogHotel.hotel_id).where(m.SupplierCatalogHotel.tenant_id == user.tenant_id, m.SupplierCatalogHotel.supplier_id.in_(scope)))) if scope else set()

    @router.get("/supplier/hotels")
    def supplier_hotels(user=Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
        ids = my_hotel_ids(db, user)
        hotels = db.scalars(select(CatalogHotel).where(CatalogHotel.id.in_(ids)).order_by(CatalogHotel.id)).all() if ids else []
        maps: dict[str, list] = {}
        for x in (db.scalars(select(CatalogHotelProviderMapping).where(CatalogHotelProviderMapping.hotel_id.in_(ids))) if ids else []):
            maps.setdefault(x.hotel_id, []).append({"id": x.id, "provider": x.provider, "provider_hotel_id": x.provider_hotel_id, "status": x.status})
        return {"items": [{"hotel_id": h.id, "name": h.name_fa or h.name_en or h.name_local, "name_en": h.name_en, "status": h.status, "content_complete": bool(h.content_complete), "rate_available": False, "mappings": maps.get(h.id, [])} for h in hotels]}

    @router.post("/supplier/hotels/{hotel_id}/provider-mappings", status_code=201)
    def supplier_propose_mapping(hotel_id: str, data: MappingIn, user=Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
        if hotel_id not in my_hotel_ids(db, user): raise HTTPException(status_code=404, detail="این هتل به تأمین‌کنندهٔ شما واگذار نشده است")
        if db.scalar(select(CatalogHotelProviderMapping.id).where(CatalogHotelProviderMapping.provider == data.provider, CatalogHotelProviderMapping.provider_hotel_id == data.provider_hotel_id)): raise HTTPException(status_code=409, detail="این شناسه قبلاً ثبت شده است")
        row = CatalogHotelProviderMapping(hotel_id=hotel_id, provider=data.provider, provider_hotel_id=data.provider_hotel_id, status="unverified"); db.add(row); db.flush()
        audit(db, user, "catalog_hotel.provider_mapping_proposed", "catalog_hotel", {"hotel_id": hotel_id, "provider": data.provider, "provider_hotel_id": data.provider_hotel_id}); db.commit()
        return {"id": row.id, "provider": row.provider, "provider_hotel_id": row.provider_hotel_id, "status": row.status}

    # ---- Agency quotes ---------------------------------------------------------------------------------------------
    def quote_out(q: m.AgencyQuote, offer_title: Optional[str] = None, customer: Optional[str] = None) -> dict:
        return {"id": q.id, "agency_id": q.agency_id, "offer_id": q.offer_id, "offer_title": offer_title or q.offer_title, "service_type": q.service_type, "customer_user_id": q.customer_user_id, "customer_name": customer,
                "amount": q.amount, "currency": q.currency, "valid_until": _aware(q.valid_until).isoformat(), "status": q.status, "note": q.note, "reservation_id": q.reservation_id, "created_at": q.created_at.isoformat(),
                "decided_at": q.decided_at.isoformat() if q.decided_at else None}

    def expire(db: Session, q: m.AgencyQuote) -> m.AgencyQuote:
        if q.status == "sent" and _aware(q.valid_until) <= now(): q.status = "expired"
        return q

    @router.get("/agency/{agency_id}/offers")
    def agency_offers(agency_id: str, q: str = "", user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency_for(db, agency_id, user)
        stmt = select(m.Offer).where(m.Offer.tenant_id == user.tenant_id, m.Offer.status == "active", m.Offer.valid_until > now(), m.Offer.amount > 0, m.Offer.available_units > 0)
        if q.strip(): stmt = stmt.where(m.Offer.title.contains(q.strip()))
        return {"items": [{"id": o.id, "title": o.title, "service_type": o.service_type, "amount": o.amount, "currency": o.currency, "valid_until": _aware(o.valid_until).isoformat()} for o in db.scalars(stmt.order_by(m.Offer.valid_until).limit(50))]}

    @router.get("/agency/{agency_id}/quotes")
    def agency_quotes(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user)
        rows = [expire(db, q) for q in db.scalars(select(m.AgencyQuote).where(m.AgencyQuote.tenant_id == user.tenant_id, m.AgencyQuote.agency_id == agency.id).order_by(m.AgencyQuote.created_at.desc()).limit(200))]
        names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_({q.customer_user_id for q in rows}), User.tenant_id == user.tenant_id))} if rows else {}
        db.commit()
        return {"sales_channel_linked": bool(agency.sales_channel_id), "items": [quote_out(q, customer=names.get(q.customer_user_id)) for q in rows]}

    @router.post("/agency/{agency_id}/quotes", status_code=201)
    def create_quote(agency_id: str, data: QuoteIn, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user)
        if not agency.sales_channel_id: raise HTTPException(status_code=409, detail="برای این آژانس کانال فروش ثبت نشده است")
        offer = db.scalar(select(m.Offer).where(m.Offer.id == data.offer_id, m.Offer.tenant_id == user.tenant_id))
        if offer is None or offer.status != "active" or _aware(offer.valid_until) <= now() or offer.amount <= 0 or offer.available_units <= 0: raise HTTPException(status_code=422, detail="پیشنهاد تأمین‌کننده فعال و معتبر نیست")
        customer = db.scalar(select(User).where(User.id == data.customer_user_id, User.tenant_id == user.tenant_id))
        if customer is None or not role_has_permission(customer.role, "reservation:create") or role_has_permission(customer.role, "platform:manage"): raise HTTPException(status_code=422, detail="مشتری باید کاربرِ دارای امکان رزرو در همین مجموعه باشد")
        row = m.AgencyQuote(tenant_id=user.tenant_id, agency_id=agency.id, created_by_user_id=user.id, customer_user_id=customer.id, offer_id=offer.id, offer_title=offer.title, service_type=offer.service_type, amount=offer.amount,
                            currency=offer.currency, valid_until=offer.valid_until, status="sent", note=(data.note or "").strip() or None)
        db.add(row); db.flush()
        audit(db, user, "agency_quote.sent", "agency_quote", {"quote_id": row.id, "agency_id": agency.id, "offer_id": offer.id, "customer_user_id": customer.id, "amount": offer.amount}); db.commit()
        return quote_out(row, customer=customer.name)

    @router.post("/agency/{agency_id}/quotes/{quote_id}/cancel")
    def cancel_quote(agency_id: str, quote_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user)
        q = db.scalar(select(m.AgencyQuote).where(m.AgencyQuote.id == quote_id, m.AgencyQuote.agency_id == agency.id, m.AgencyQuote.tenant_id == user.tenant_id).with_for_update())
        if q is None: raise HTTPException(status_code=404, detail="پیشنهاد قیمت پیدا نشد")
        if expire(db, q).status not in ("sent", "accepted"): raise HTTPException(status_code=409, detail="این پیشنهاد قیمت قابل لغو نیست")
        q.status, q.decided_at = "cancelled", now()
        audit(db, user, "agency_quote.cancelled", "agency_quote", {"quote_id": q.id}); db.commit()
        return quote_out(q)

    @router.post("/agency/{agency_id}/quotes/{quote_id}/link-booking")
    def link_booking(agency_id: str, quote_id: str, data: LinkBookingIn, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user)
        q = db.scalar(select(m.AgencyQuote).where(m.AgencyQuote.id == quote_id, m.AgencyQuote.agency_id == agency.id, m.AgencyQuote.tenant_id == user.tenant_id).with_for_update())
        if q is None: raise HTTPException(status_code=404, detail="پیشنهاد قیمت پیدا نشد")
        if q.status != "accepted": raise HTTPException(status_code=409, detail="فقط پیشنهاد پذیرفته‌شده به رزرو وصل می‌شود")
        r = db.scalar(select(m.Reservation).where(m.Reservation.id == data.reservation_id, m.Reservation.tenant_id == user.tenant_id))
        if r is None or r.user_id != q.customer_user_id or r.sales_channel_id != agency.sales_channel_id or _aware(r.created_at) < _aware(q.decided_at): raise HTTPException(status_code=422, detail="این رزرو با مشتری، کانال فروش یا زمان این پیشنهاد هم‌خوان نیست")
        if db.scalar(select(m.AgencyQuote.id).where(m.AgencyQuote.tenant_id == user.tenant_id, m.AgencyQuote.reservation_id == r.id)): raise HTTPException(status_code=409, detail="این رزرو به پیشنهاد دیگری وصل است")
        q.status, q.reservation_id = "booked", r.id
        audit(db, user, "agency_quote.booked", "agency_quote", {"quote_id": q.id, "reservation_id": r.id}); db.commit()
        return quote_out(q)

    @router.get("/agency/{agency_id}/credit")
    def agency_credit(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user)
        account = db.scalar(select(m.CreditAccount).where(m.CreditAccount.id == agency.credit_account_id, m.CreditAccount.tenant_id == user.tenant_id)) if agency.credit_account_id else None
        if account is None: return {"linked": False, "items": []}
        return {"linked": True, "currency": account.currency, "limit_amount": account.limit_amount, "balances": m.credit_balances(db, tenant_id=user.tenant_id, credit_account_id=account.id), "items": []}

    @router.get("/me/agency-quotes")
    def my_quotes(user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        rows = [expire(db, q) for q in db.scalars(select(m.AgencyQuote).where(m.AgencyQuote.tenant_id == user.tenant_id, m.AgencyQuote.customer_user_id == user.id).order_by(m.AgencyQuote.created_at.desc()).limit(100))]
        agencies = {a.id: a for a in db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id, m.Agency.id.in_({q.agency_id for q in rows})))} if rows else {}
        db.commit()
        return {"items": [{**{k: v for k, v in quote_out(q).items() if k not in ("customer_user_id", "customer_name")}, "agency_name": agencies[q.agency_id].display_name if q.agency_id in agencies else None,
                           "booking": {"offer_id": q.offer_id, "sales_channel_id": agencies[q.agency_id].sales_channel_id} if q.status == "accepted" and q.agency_id in agencies else None} for q in rows]}

    @router.post("/me/agency-quotes/{quote_id}/decision")
    def decide_quote(quote_id: str, data: DecisionIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        q = db.scalar(select(m.AgencyQuote).where(m.AgencyQuote.id == quote_id, m.AgencyQuote.tenant_id == user.tenant_id, m.AgencyQuote.customer_user_id == user.id).with_for_update())
        if q is None: raise HTTPException(status_code=404, detail="پیشنهاد قیمت در این حساب نیست")
        if expire(db, q).status != "sent":
            db.commit(); raise HTTPException(status_code=409, detail="این پیشنهاد قیمت دیگر قابل تصمیم‌گیری نیست")
        offer = db.scalar(select(m.Offer).where(m.Offer.id == q.offer_id, m.Offer.tenant_id == user.tenant_id))
        if data.decision == "accept" and (offer is None or offer.status != "active" or offer.amount != q.amount or offer.currency != q.currency or offer.available_units <= 0):
            q.status, q.decided_at = "expired", now(); db.commit()
            raise HTTPException(status_code=409, detail="قیمت یا موجودی پیشنهاد تأمین‌کننده تغییر کرده است؛ از آژانس پیشنهاد تازه بخواهید")
        q.status, q.decided_at = ("accepted" if data.decision == "accept" else "declined"), now()
        audit(db, user, f"agency_quote.{q.status}", "agency_quote", {"quote_id": q.id}); db.commit()
        return {"id": q.id, "status": q.status}

    # ---- Commission ledger -----------------------------------------------------------------------------------------
    def entry_out(e: m.AgencyCommissionEntry, agency_name: Optional[str] = None) -> dict:
        return {"id": e.id, "agency_id": e.agency_id, "agency_name": agency_name, "reservation_id": e.reservation_id, "base_amount": e.base_amount, "commission_bps": e.commission_bps, "amount": e.amount, "currency": e.currency, "status": e.status,
                "external_reference": e.external_reference, "reversal_reason": e.reversal_reason, "created_at": e.created_at.isoformat(), "settled_at": e.settled_at.isoformat() if e.settled_at else None}

    def entry_for(db: Session, entry_id: str, user) -> m.AgencyCommissionEntry:
        e = db.scalar(select(m.AgencyCommissionEntry).where(m.AgencyCommissionEntry.id == entry_id, m.AgencyCommissionEntry.tenant_id == user.tenant_id).with_for_update())
        if e is None: raise HTTPException(status_code=404, detail="ثبت کمیسیون پیدا نشد")
        return e

    def move(db: Session, e: m.AgencyCommissionEntry, target: str, user, **extra) -> dict:
        if target not in COMMISSION_FLOW[e.status]: raise HTTPException(status_code=409, detail=f"انتقال از «{e.status}» به «{target}» مجاز نیست")
        previous, e.status = e.status, target
        for k, v in extra.items(): setattr(e, k, v)
        audit(db, user, f"commission.{target}", "commission", {"entry_id": e.id, "from": previous, "amount": e.amount, "agency_id": e.agency_id}); db.commit()
        return entry_out(e)

    @router.get("/finance/commissions")
    def commissions(status: Optional[str] = None, agency_id: Optional[str] = None, user=Depends(require_permission("ledger:read")), db: Session = Depends(get_db)) -> dict:
        stmt = select(m.AgencyCommissionEntry).where(m.AgencyCommissionEntry.tenant_id == user.tenant_id)
        if status: stmt = stmt.where(m.AgencyCommissionEntry.status == status)
        if agency_id: stmt = stmt.where(m.AgencyCommissionEntry.agency_id == agency_id)
        rows = db.scalars(stmt.order_by(m.AgencyCommissionEntry.created_at.desc()).limit(300)).all()
        names = {a.id: a.display_name for a in db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id))}
        posted = select(m.AgencyCommissionEntry.reservation_id).where(m.AgencyCommissionEntry.tenant_id == user.tenant_id)
        channels = {a.sales_channel_id: a for a in db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id, m.Agency.sales_channel_id.is_not(None)))}
        pending = []
        for r in (db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == user.tenant_id, m.Reservation.sales_channel_id.in_(set(channels)), m.Reservation.confirmed_at.is_not(None), m.Reservation.id.notin_(posted)).limit(200)) if channels else []):
            amount, currency = _total(r)
            if amount: pending.append({"reservation_id": r.id, "booking_reference": r.booking_reference, "agency_id": channels[r.sales_channel_id].id, "agency_name": channels[r.sales_channel_id].display_name, "base_amount": amount, "currency": currency,
                                       "commission_bps": channels[r.sales_channel_id].commission_bps, "amount": amount * channels[r.sales_channel_id].commission_bps // 10000})
        return {"items": [entry_out(e, names.get(e.agency_id)) for e in rows], "not_posted": pending, "flow": {k: sorted(v) for k, v in COMMISSION_FLOW.items()}}

    @router.post("/finance/commissions/accrue", status_code=201)
    def accrue(data: AccrueIn, user=Depends(require_permission("settlement:manage")), db: Session = Depends(get_db)) -> dict:
        r = db.scalar(select(m.Reservation).where(m.Reservation.id == data.reservation_id, m.Reservation.tenant_id == user.tenant_id).with_for_update())
        agency = db.scalar(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id, m.Agency.sales_channel_id == r.sales_channel_id)) if r is not None and r.sales_channel_id else None
        amount, currency = _total(r) if r is not None else (None, None)
        if r is None or agency is None or r.confirmed_at is None or amount is None: raise HTTPException(status_code=422, detail="فقط رزرو تأییدشدهٔ دارای مبلغ روی کانال فروش یک آژانس قابل ثبت کمیسیون است")
        if agency.commission_bps <= 0: raise HTTPException(status_code=422, detail="نرخ کمیسیون این آژانس صفر است")
        prior = db.scalar(select(m.AgencyCommissionEntry).where(m.AgencyCommissionEntry.tenant_id == user.tenant_id, m.AgencyCommissionEntry.reservation_id == r.id))
        if prior is not None: raise HTTPException(status_code=409, detail="برای این رزرو قبلاً کمیسیون ثبت شده است")
        e = m.AgencyCommissionEntry(tenant_id=user.tenant_id, agency_id=agency.id, reservation_id=r.id, base_amount=amount, commission_bps=agency.commission_bps, amount=amount * agency.commission_bps // 10000, currency=currency, status="accrued", posted_by_user_id=user.id)
        db.add(e); db.flush()
        audit(db, user, "commission.accrued", "commission", {"entry_id": e.id, "agency_id": agency.id, "reservation_id": r.id, "amount": e.amount}); db.commit()
        return entry_out(e, agency.display_name)

    @router.post("/finance/commissions/{entry_id}/approve")
    def approve(entry_id: str, user=Depends(require_permission("settlement:manage")), db: Session = Depends(get_db)) -> dict:
        return move(db, entry_for(db, entry_id, user), "approved", user)

    @router.post("/finance/commissions/{entry_id}/settle")
    def settle(entry_id: str, data: SettleIn, user=Depends(require_permission("settlement:manage")), db: Session = Depends(get_db)) -> dict:
        return move(db, entry_for(db, entry_id, user), "settled", user, external_reference=data.external_reference.strip(), settled_at=now())

    @router.post("/finance/commissions/{entry_id}/reverse")
    def reverse(entry_id: str, data: ReasonIn, user=Depends(require_permission("settlement:manage")), db: Session = Depends(get_db)) -> dict:
        return move(db, entry_for(db, entry_id, user), "reversed", user, reversal_reason=data.reason.strip())

    @router.get("/agency/{agency_id}/commission-ledger")
    def agency_ledger(agency_id: str, user=Depends(agency_user), db: Session = Depends(get_db)) -> dict:
        agency = agency_for(db, agency_id, user)
        rows = db.scalars(select(m.AgencyCommissionEntry).where(m.AgencyCommissionEntry.tenant_id == user.tenant_id, m.AgencyCommissionEntry.agency_id == agency.id).order_by(m.AgencyCommissionEntry.created_at.desc())).all()
        totals: dict[tuple, int] = {}
        for e in rows: totals[(e.status, e.currency)] = totals.get((e.status, e.currency), 0) + e.amount
        return {"items": [entry_out(e) for e in rows], "totals": [{"status": s, "currency": c, "amount": v} for (s, c), v in sorted(totals.items())]}

    # ---- Accounting views: sums over stored rows, formula stated -----------------------------------------------------
    @router.get("/finance/accounting")
    def accounting(user=Depends(require_permission("ledger:read")), db: Session = Depends(get_db)) -> dict:
        t = user.tenant_id
        paid: dict[str, tuple[int, int]] = {}
        for p in db.scalars(select(m.PaymentIntent).where(m.PaymentIntent.tenant_id == t)):
            c, f = paid.get(p.reservation_id, (0, 0)); paid[p.reservation_id] = (c + (p.captured_amount or 0), f + (p.refunded_amount or 0))
        receivables = []
        for inv in db.scalars(select(m.Invoice).where(m.Invoice.tenant_id == t, m.Invoice.status == "issued").order_by(m.Invoice.issued_at.desc()).limit(300)):
            captured, refunded = paid.get(inv.reservation_id, (0, 0))
            outstanding = inv.total_amount - (captured - refunded)
            if outstanding > 0: receivables.append({"invoice_number": inv.invoice_number, "reservation_id": inv.reservation_id, "invoiced": inv.total_amount, "tax": inv.tax_amount, "captured": captured, "refunded": refunded, "outstanding": outstanding, "currency": inv.currency})
        suppliers = {s.id: s.display_name for s in db.scalars(select(m.Supplier).where(m.Supplier.tenant_id == t))}
        payables = [{"supplier_id": sid, "supplier_name": suppliers.get(sid), "currency": cur, "count": n, "amount": int(total)} for sid, cur, n, total in
                    db.execute(select(m.SettlementRecord.supplier_id, m.SettlementRecord.currency, func.count(), func.sum(m.SettlementRecord.amount)).where(m.SettlementRecord.tenant_id == t, m.SettlementRecord.status == "pending").group_by(m.SettlementRecord.supplier_id, m.SettlementRecord.currency))]
        agencies = {a.id: a.display_name for a in db.scalars(select(m.Agency).where(m.Agency.tenant_id == t))}
        commissions = [{"agency_id": aid, "agency_name": agencies.get(aid), "status": st, "currency": cur, "count": n, "amount": int(total)} for aid, st, cur, n, total in
                       db.execute(select(m.AgencyCommissionEntry.agency_id, m.AgencyCommissionEntry.status, m.AgencyCommissionEntry.currency, func.count(), func.sum(m.AgencyCommissionEntry.amount)).where(m.AgencyCommissionEntry.tenant_id == t)
                                  .group_by(m.AgencyCommissionEntry.agency_id, m.AgencyCommissionEntry.status, m.AgencyCommissionEntry.currency))]
        credit = [{"credit_account_id": c.id, "organization_id": c.organization_id, "currency": c.currency, "limit_amount": c.limit_amount, **m.credit_balances(db, tenant_id=t, credit_account_id=c.id)} for c in db.scalars(select(m.CreditAccount).where(m.CreditAccount.tenant_id == t).limit(200))]
        tax = [{"currency": cur, "invoices": n, "tax_amount": int(total or 0), "taxable_subtotal": int(sub or 0)} for cur, n, total, sub in
               db.execute(select(m.Invoice.currency, func.count(), func.sum(m.Invoice.tax_amount), func.sum(m.Invoice.subtotal_amount)).where(m.Invoice.tenant_id == t, m.Invoice.status == "issued").group_by(m.Invoice.currency))]
        return {"receivables": {"formula": "outstanding = invoice.total_amount − (Σ captured_amount − Σ refunded_amount) for the invoice's reservation; shown when > 0", "items": receivables},
                "supplier_payables": {"formula": "Σ settlement_records.amount where status = pending, per supplier and currency", "items": payables},
                "commissions": {"formula": "Σ agency_commission_entries.amount per agency, status and currency (accrued → approved → settled | reversed)", "items": commissions},
                "organization_credit": {"formula": "credit_accounts.limit_amount with balances from the credit ledger", "items": credit},
                "tax_summary": {"formula": "Σ invoices.tax_amount and Σ invoices.subtotal_amount where status = issued, per currency", "items": tax},
                "basis": "stored_rows_only", "approved_chart_of_accounts": False}

    return router
