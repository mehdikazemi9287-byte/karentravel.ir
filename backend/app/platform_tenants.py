"""Platform tenant management (مدیریت مستأجرها و وایت‌لیبل در سطح پلتفرم).

Only `platform_admin` may use these endpoints. Each tenant keeps its own data behind row-level security; to read
or write inside another tenant the request switches the session's tenant context explicitly for that step and
switches back to the caller's tenant before writing the audit row. Nothing here copies data between tenants.

* list tenants with brand, domain, enabled services and live counts (users, reservations, suppliers)
* create a tenant together with its first tenant admin and its white-label row
* update a tenant's name, brand colours, custom domain (re-verification needed after a change) and services
"""
from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import operations as m

SERVICES = ("flight", "hotel", "tour", "train", "bus", "visa", "vacation_rental", "car_rental", "cruise", "insurance", "cip", "transfer")
SERVICE_FA = {"flight": "پرواز", "hotel": "هتل", "tour": "تور", "train": "قطار", "bus": "اتوبوس", "visa": "ویزا", "vacation_rental": "اقامتگاه",
              "car_rental": "اجاره‌ی خودرو", "cruise": "سفر دریایی", "insurance": "بیمه", "cip": "تشریفات فرودگاهی", "transfer": "ترانسفر"}
RESERVED_SLUGS = {"admin", "api", "app", "www", "platform", "karenseir", "public"}


def valid_domain(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    d = d.lower().strip().rstrip(".")
    if not re.fullmatch(r"(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}", d):
        raise HTTPException(status_code=422, detail="دامنه معتبر نیست")
    return d


class TenantCreateIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{2,40}[a-z0-9]$")
    name: str = Field(min_length=2, max_length=160)
    primary_color: str = Field(default="#3A1B3D", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(default="#EF5B3D", pattern=r"^#[0-9A-Fa-f]{6}$")
    custom_domain: Optional[str] = Field(default=None, max_length=253)
    enabled_services: list[str] = Field(default_factory=list, max_length=32)
    admin_email: str = Field(pattern=r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-zA-Z]{2,24}$")
    admin_name: str = Field(min_length=2, max_length=160)


class TenantUpdateIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    custom_domain: Optional[str] = Field(default=None, max_length=253)
    enabled_services: list[str] = Field(default_factory=list, max_length=32)


def platform_tenants_router(get_db, current_user, User, Tenant, set_tenant_context, audit=None):
    api = APIRouter(tags=["platform-tenants"])

    def platform(user=Depends(current_user)):
        if user.role != "platform_admin":
            raise HTTPException(status_code=403, detail="فقط مدیر پلتفرم به مدیریت مستأجرها دسترسی دارد")
        return user

    def _services(items: list[str]) -> list[str]:
        bad = [s for s in items if s not in SERVICES]
        if bad:
            raise HTTPException(status_code=422, detail="خدمت نامعتبر: " + "، ".join(bad))
        return sorted(set(items))

    def _audit(db: Session, user, action: str, detail: dict):
        set_tenant_context(db, user.tenant_id)
        if audit:
            audit(db, user, action, "tenant", detail)

    def _summary(db: Session, t) -> dict:
        set_tenant_context(db, t.id)
        wl = db.scalar(select(m.WhiteLabelConfiguration).where(m.WhiteLabelConfiguration.tenant_id == t.id))
        count = lambda model: int(db.scalar(select(func.count(model.id)).where(model.tenant_id == t.id)) or 0)  # noqa: E731
        admins = [n for n, in db.execute(select(User.email).where(User.tenant_id == t.id, User.role == "tenant_admin").order_by(User.id).limit(3)).all()]
        return {"id": t.id, "slug": t.slug, "name": t.name, "primary_color": wl.primary_color if wl else t.primary_color,
                "secondary_color": wl.secondary_color if wl else None, "display_name": wl.display_name if wl else t.name,
                "custom_domain": wl.custom_domain if wl else None, "domain_status": wl.domain_status if wl else None,
                "enabled_services": json.loads(wl.enabled_services_json or "[]") if wl else [], "has_white_label": wl is not None,
                "counts": {"users": count(User), "reservations": count(m.Reservation), "suppliers": count(m.Supplier)}, "admins": admins}

    @api.get("/platform/tenants")
    def list_tenants(user=Depends(platform), db: Session = Depends(get_db)):
        items = [_summary(db, t) for t in db.scalars(select(Tenant).order_by(Tenant.id)).all()]
        set_tenant_context(db, user.tenant_id)
        return {"items": items, "services": [{"key": k, "label": SERVICE_FA[k]} for k in SERVICES]}

    @api.post("/platform/tenants", status_code=201)
    def create_tenant(data: TenantCreateIn, user=Depends(platform), db: Session = Depends(get_db)):
        if data.slug in RESERVED_SLUGS:
            raise HTTPException(status_code=422, detail="این نامک رزرو شده است")
        if db.scalar(select(Tenant.id).where(Tenant.slug == data.slug)) is not None:
            raise HTTPException(status_code=409, detail="مستأجری با این نامک وجود دارد")
        domain = valid_domain(data.custom_domain)
        services = _services(data.enabled_services)
        email = data.admin_email.strip().lower()
        t = Tenant(slug=data.slug, name=data.name, primary_color=data.primary_color.upper())
        db.add(t)
        db.flush()
        set_tenant_context(db, t.id)
        admin = User(tenant_id=t.id, email=email, name=data.admin_name, role="tenant_admin")
        db.add(admin)
        db.add(m.WhiteLabelConfiguration(tenant_id=t.id, display_name=data.name, primary_color=data.primary_color.upper(),
                                         secondary_color=data.secondary_color.upper(), custom_domain=domain, domain_status="unverified",
                                         enabled_services_json=json.dumps(services)))
        try:
            db.flush()
        except IntegrityError:  # users.email is unique across all tenants
            db.rollback()
            raise HTTPException(status_code=409, detail="این ایمیل برای کاربر دیگری ثبت شده است")
        out = _summary(db, t)
        _audit(db, user, "platform.tenant.created", {"tenant_id": t.id, "slug": t.slug, "admin": email})
        db.commit()
        return out

    @api.put("/platform/tenants/{tenant_id}")
    def update_tenant(tenant_id: int, data: TenantUpdateIn, user=Depends(platform), db: Session = Depends(get_db)):
        t = db.get(Tenant, tenant_id)
        if t is None:
            raise HTTPException(status_code=404, detail="مستأجر یافت نشد")
        domain = valid_domain(data.custom_domain)
        services = _services(data.enabled_services)
        t.name, t.primary_color = data.name, data.primary_color.upper()
        set_tenant_context(db, t.id)
        wl = db.scalar(select(m.WhiteLabelConfiguration).where(m.WhiteLabelConfiguration.tenant_id == t.id).with_for_update())
        if wl is None:
            wl = m.WhiteLabelConfiguration(tenant_id=t.id, display_name=data.name)
            db.add(wl)
        if wl.custom_domain != domain:
            wl.domain_status = "unverified"
        wl.display_name, wl.primary_color, wl.secondary_color, wl.custom_domain = data.name, data.primary_color.upper(), data.secondary_color.upper(), domain
        wl.enabled_services_json = json.dumps(services)
        db.flush()
        out = _summary(db, t)
        _audit(db, user, "platform.tenant.updated", {"tenant_id": t.id, "domain": domain, "services": services})
        db.commit()
        return out

    return api
