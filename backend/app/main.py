from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Generator, Optional
from urllib.parse import urlparse

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func, select, text, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .config import read_secret
from .database import Base, DATABASE_URL, SessionLocal, engine, set_tenant_context
from . import operations as operational_models  # register additive operational tables
from .observability import configure_logging, prometheus_metrics, record_business_event, record_request
from .rate_limit import InMemoryRateLimiter, RedisRateLimiter, fingerprint
from .security import role_has_permission
from .providers import configured_adapter, validate_provider_modes

JWT_SECRET = read_secret("JWT_SECRET", "development-only-change-before-production")
JWT_ISSUER = os.getenv("JWT_ISSUER", "karenseir-api")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "karenseir-web")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes"}
REDIS_URL = read_secret("REDIS_URL", "")
PAYMENT_WEBHOOK_SECRET = read_secret("PAYMENT_WEBHOOK_SECRET", "")
NOTIFICATION_WEBHOOK_SECRET = read_secret("NOTIFICATION_WEBHOOK_SECRET", "")
rate_limiter = RedisRateLimiter.from_url(REDIS_URL) if REDIS_URL else InMemoryRateLimiter()
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    primary_color: Mapped[str] = mapped_column(String(16), default="#0E7490")
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(48))
class Hotel(Base):
    __tablename__ = "hotels"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), index=True)
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1))
    nightly_price: Mapped[int] = mapped_column(Integer)
    cancellation: Mapped[str] = mapped_column(String(160))
    image_url: Mapped[str] = mapped_column(String(500))
    inventory: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)
class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id"))
    nights: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending_approval")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    entry_type: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try: yield db
    finally: db.close()
def seed(db: Session) -> None:
    if db.scalar(select(Tenant.id).limit(1)): return
    a, b = Tenant(slug="aftab-bank", name="بانک آفتاب", primary_color="#0E7490"), Tenant(slug="faraz-industries", name="صنایع فراز", primary_color="#B65C2D")
    db.add_all([a,b]); db.flush()
    db.add_all([
      User(tenant_id=a.id,email="employee@aftab.test",name="آرمان رضایی",role="employee"),
      User(tenant_id=a.id,email="welfare@aftab.test",name="نگار بهرامی",role="welfare_manager"),
      User(tenant_id=a.id,email="org-admin@aftab.test",name="مدیر سازمان نمونه",role="organization_admin"),
      User(tenant_id=a.id,email="agency@aftab.test",name="آژانس نمونه",role="agency_partner"),
      User(tenant_id=a.id,email="supplier@aftab.test",name="تأمین‌کننده نمونه",role="supplier"),
      User(tenant_id=a.id,email="backoffice@aftab.test",name="کارشناس عملیات نمونه",role="backoffice_expert"),
      User(tenant_id=a.id,email="finance@aftab.test",name="کارشناس مالی نمونه",role="finance_operator"),
      User(tenant_id=a.id,email="tenant-admin@aftab.test",name="مدیر مستأجر نمونه",role="tenant_admin"),
      User(tenant_id=a.id,email="platform-admin@aftab.test",name="مدیر پلتفرم نمونه",role="platform_admin"),
      User(tenant_id=b.id,email="employee@faraz.test",name="سارا شریفی",role="employee"),
    ])
    db.add_all([
      Hotel(name="هتل پارسیان آزادی",city="تهران",rating=Decimal("4.7"),nightly_price=7850000,cancellation="تا ۴۸ ساعت پیش از ورود",inventory=8,image_url="https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80"),
      Hotel(name="هتل زندیه",city="شیراز",rating=Decimal("4.5"),nightly_price=5990000,cancellation="تا ۲۴ ساعت پیش از ورود",inventory=5,image_url="https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1200&q=80"),
      Hotel(name="هتل قصر طلایی",city="مشهد",rating=Decimal("4.6"),nightly_price=6750000,cancellation="تا ۴۸ ساعت پیش از ورود",inventory=6,image_url="https://images.unsplash.com/photo-1564501049412-61c2a3083791?auto=format&fit=crop&w=1200&q=80")])
    db.commit()

class LoginIn(BaseModel): email: str
class BookingIn(BaseModel): hotel_id: int; nights: int = Field(ge=1, le=30)
class ApproveIn(BaseModel): decision: str = Field(pattern="^(approve|reject)$")
class ReservationCommandIn(BaseModel): target: str; command_id: str = Field(min_length=8, max_length=120)
class ServiceRequestIn(BaseModel): request_type: str = Field(pattern="^(cancel|change|refund)$"); reason: Optional[str] = Field(default=None, max_length=1000)
class RefreshIn(BaseModel): refresh_token: str = Field(min_length=32, max_length=512); device_id: Optional[str] = Field(default=None, min_length=8, max_length=200)
class OTPRequestIn(BaseModel): tenant_slug: str = Field(min_length=2, max_length=64); identifier: str = Field(min_length=3, max_length=160)
class OTPVerifyIn(BaseModel): tenant_slug: str = Field(min_length=2, max_length=64); challenge_id: str = Field(min_length=36, max_length=36); code: str = Field(pattern=r"^\d{6}$"); device_id: str = Field(min_length=8, max_length=200)
class LogoutIn(BaseModel): refresh_token: str = Field(min_length=32, max_length=512)
class CreditCommandIn(BaseModel): command_id: str = Field(min_length=8, max_length=120); entry_type: str = Field(pattern="^(allocate|reserve|capture|release|reverse_capture)$"); amount: int = Field(gt=0)
class ApprovalDecisionIn(BaseModel): decision: str = Field(pattern="^(approve|reject)$"); rejection_reason: Optional[str] = Field(default=None, max_length=500)
class RefundIn(BaseModel): amount: int = Field(gt=0); command_id: str = Field(min_length=8, max_length=120)
class SupplierOfferIn(BaseModel):
    supplier_id: str = Field(min_length=36, max_length=36)
    service_type: str = Field(pattern="^(flight|hotel|tour|package)$")
    title: str = Field(min_length=3, max_length=200)
    amount: int = Field(gt=0)
    available_units: int = Field(ge=1, le=100000)
    valid_minutes: int = Field(ge=1, le=43200)
    policy: dict
    attributes: dict = Field(default_factory=dict)
    fulfillment_mode: str = Field(pattern="^(manual_supplier|provider)$")
    provider_key: str = Field(default="manual_supplier", min_length=2, max_length=64)
class SupplierOnboardingIn(BaseModel):
    supplier_type: str = Field(pattern="^(flight|hotel|tour|package|multi_service)$")
    display_name: str = Field(min_length=2, max_length=180)
class OfferSearchIn(BaseModel): service_type: str = Field(pattern="^(flight|hotel|tour|package)$")
class PriceCheckIn(BaseModel): units: int = Field(ge=1, le=20); command_id: str = Field(min_length=8, max_length=120)
class OrchestrationBookingIn(BaseModel): price_check_id: str = Field(min_length=36, max_length=36); command_id: str = Field(min_length=8, max_length=120)
class FulfillmentIn(BaseModel): command_id: str = Field(min_length=8, max_length=120); provider_reference: str = Field(min_length=3, max_length=160); document_reference: str = Field(min_length=3, max_length=240)
class OrganizationDimensionIn(BaseModel): name: str = Field(min_length=2, max_length=160); code: str = Field(min_length=2, max_length=64); budget_amount: Optional[int] = Field(default=None, ge=0)
class ApprovalTemplateStepIn(BaseModel): required_role: str = Field(pattern="^(backoffice_expert|manager|welfare_manager|finance_operator|organization_admin)$"); sla_minutes: int = Field(ge=5, le=43200)
class ApprovalTemplateIn(BaseModel): name: str = Field(min_length=3, max_length=160); version: int = Field(ge=1); steps: list[ApprovalTemplateStepIn] = Field(min_length=1, max_length=8)
class ApprovalStartIn(BaseModel): template_id: str = Field(min_length=36, max_length=36); command_id: str = Field(min_length=8, max_length=120)
class EscalationIn(BaseModel): reason: str = Field(min_length=3, max_length=500)
class WhiteLabelIn(BaseModel):
    organization_id: Optional[str] = Field(default=None, min_length=36, max_length=36)
    display_name: str = Field(min_length=2, max_length=160)
    logo_reference: Optional[str] = Field(default=None, max_length=240)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    custom_domain: Optional[str] = Field(default=None, max_length=253)
    support: dict = Field(default_factory=dict)
    enabled_services: list[str] = Field(default_factory=list, max_length=32)
    organization_policy: dict = Field(default_factory=dict)
    feature_flags: dict = Field(default_factory=dict)
class CompareIn(BaseModel): offer_ids: list[str] = Field(min_length=2, max_length=4)
class NotificationPreferenceIn(BaseModel): topic: str = Field(min_length=2, max_length=48); channel: str = Field(pattern="^(web|app|push|sms)$"); enabled: bool
class AgencyIn(BaseModel): display_name: str = Field(min_length=2, max_length=180); parent_agency_id: Optional[str] = Field(default=None, min_length=36, max_length=36); markup_bps: int = Field(ge=0, le=10000); commission_bps: int = Field(ge=0, le=10000)
class VoucherReissueIn(BaseModel): command_id: str = Field(min_length=8, max_length=120); document_reference: str = Field(min_length=3, max_length=240); reason: str = Field(min_length=3, max_length=500)
class ProfileIn(BaseModel): name: str = Field(min_length=2, max_length=160); locale: str = Field(default="fa-IR", pattern="^(fa-IR|en-US)$")
class TravellerIn(BaseModel): full_name: str = Field(min_length=3, max_length=160); profile_reference: Optional[str] = Field(default=None, max_length=160)
class WalletCreateIn(BaseModel): currency: str = Field(default="IRR", pattern="^IRR$")
class SupplierOfferUpdateIn(BaseModel): amount: Optional[int] = Field(default=None, gt=0); available_units: Optional[int] = Field(default=None, ge=0, le=100000); status: Optional[str] = Field(default=None, pattern="^(active|paused)$")
class AgencyUpdateIn(BaseModel): display_name: Optional[str] = Field(default=None, min_length=2, max_length=180); markup_bps: Optional[int] = Field(default=None, ge=0, le=10000); commission_bps: Optional[int] = Field(default=None, ge=0, le=10000); status: Optional[str] = Field(default=None, pattern="^(active|suspended)$")
class SupplierStatusIn(BaseModel): status: str = Field(pattern="^(active|suspended)$"); reason: str = Field(min_length=3, max_length=500)
class SupportMessageIn(BaseModel): reservation_id: Optional[str] = Field(default=None, min_length=36, max_length=36); trip_id: Optional[str] = Field(default=None, min_length=36, max_length=36); body: str = Field(min_length=3, max_length=4000)
def token_for(user: User, tenant: Tenant) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub":str(user.id),"tenant":tenant.id,"role":user.role,"type":"access","iss":JWT_ISSUER,"aud":JWT_AUDIENCE,"iat":now,"jti":str(uuid.uuid4()),"exp":now+timedelta(minutes=15)}, JWT_SECRET, algorithm="HS256")
def current_user(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(status_code=401, detail="توکن دسترسی لازم است")
    try: payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER, audience=JWT_AUDIENCE, options={"require":["exp","iat","iss","aud","jti","sub","tenant","type"]})
    except jwt.PyJWTError: raise HTTPException(status_code=401, detail="توکن نامعتبر است")
    if payload.get("type") != "access": raise HTTPException(status_code=401, detail="نوع توکن نامعتبر است")
    try: tenant_id = int(payload["tenant"])
    except (KeyError, TypeError, ValueError): raise HTTPException(status_code=401, detail="نشست نامعتبر است")
    set_tenant_context(db, tenant_id)
    user = db.get(User, int(payload["sub"]))
    if not user or user.tenant_id != payload["tenant"]: raise HTTPException(status_code=401, detail="نشست نامعتبر است")
    return user


def _secure_hash(value: str) -> str:
    return hmac.new(JWT_SECRET.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _request_fingerprints(request: Request, device_id: Optional[str] = None) -> tuple[Optional[str], str]:
    ip = request.client.host if request.client else "unknown"
    return (_secure_hash(device_id) if device_id else None, _secure_hash(ip))
def require_role(*roles: str):
    def guard(user: User = Depends(current_user)) -> User:
        if user.role not in roles: raise HTTPException(status_code=403, detail="دسترسی این نقش کافی نیست")
        return user
    return guard
def require_permission(permission: str):
    def guard(user: User = Depends(current_user)) -> User:
        if not role_has_permission(user.role, permission): raise HTTPException(status_code=403, detail="مجوز لازم برای این اقدام وجود ندارد")
        return user
    return guard
def booking_out(b: Booking, hotel: Hotel) -> dict:
    return {"id":b.id,"hotel_id":hotel.id,"hotel_name":hotel.name,"nights":b.nights,"total_amount":b.total_amount,"status":b.status,"created_at":b.created_at.isoformat()}


def _reservation_output(row: operational_models.Reservation) -> dict:
    return {"id": row.id, "booking_reference": row.booking_reference, "service_type": row.service_type, "status": row.status, "price_snapshot": json.loads(row.price_snapshot_json), "policy_at_booking": json.loads(row.policy_at_booking_json), "version": row.version}


def _verified_cancellation_quote(row: operational_models.Reservation) -> Optional[dict]:
    try:
        policy = json.loads(row.policy_at_booking_json)
        price = json.loads(row.price_snapshot_json)
        cancellation = policy["cancellation"]
        if policy.get("verified") is not True or not policy.get("source") or not policy.get("verified_at"):
            return None
        total = int(price["total_amount"])
        penalty = int(cancellation.get("penalty_amount", 0))
        refundable = cancellation.get("refundable") is True
        if penalty < 0 or penalty > total:
            return None
        return {"policy_verified": True, "policy_source": policy["source"], "currency": "IRR", "total_amount": total, "penalty_amount": penalty if refundable else total, "refundable_amount": max(total - penalty, 0) if refundable else 0}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

def validate_production_config() -> None:
    origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
    if ENVIRONMENT == "production":
        if JWT_SECRET == "development-only-change-before-production" or JWT_SECRET.startswith("replace-with-") or len(JWT_SECRET) < 32:
            raise RuntimeError("JWT_SECRET must be a non-default value of at least 32 characters")
        if not DATABASE_URL.startswith("postgresql"):
            raise RuntimeError("Production DATABASE_URL must use PostgreSQL")
        if not origins or "*" in origins or any(origin.startswith("http://") for origin in origins):
            raise RuntimeError("Production CORS_ORIGINS must contain explicit HTTPS origins")
        provider_keys = ("flight", "hotel", "tour_hotel", "payment", "otp", "sms", "push")
        validate_provider_modes(ENVIRONMENT, DEMO_MODE, provider_keys)
        for key in provider_keys:
            configured_adapter(key).validate_configuration()
        if not REDIS_URL or not rate_limiter.distributed:
            raise RuntimeError("Production REDIS_URL must configure distributed rate limiting")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    validate_production_config()
    if ENVIRONMENT == "production" and not await rate_limiter.ping():
        raise RuntimeError("Production Redis rate limiter is unavailable")
    if ENVIRONMENT == "development":
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            seed(db)
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="KarenSeir Pilot API", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS","http://localhost:3000").split(","), allow_credentials=False, allow_methods=["GET","POST","PUT"], allow_headers=["Authorization","Content-Type","Idempotency-Key","X-Request-ID","X-Correlation-ID"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    started_at = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    correlation_id = request.headers.get("X-Correlation-ID") or request_id
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    decision = None
    if request.url.path not in {"/health", "/ready", "/metrics"}:
        route_class = "auth" if request.url.path.startswith("/auth/") else "api"
        limit, window = ((10, 60) if route_class == "auth" else (300, 60)) if rate_limiter.distributed else (10_000, 60)
        identity = request.headers.get("Authorization") or (request.client.host if request.client else "unknown")
        try:
            decision = await rate_limiter.hit(f"karenseir:rl:{route_class}:{fingerprint(identity)}", limit, window)
        except Exception:
            logging.getLogger("karenseir.rate_limit").exception("rate_limiter_unavailable", extra={"request_id": request_id, "correlation_id": correlation_id, "method": request.method, "path": request.url.path, "status": 503})
            record_request(request.method, 503, time.perf_counter() - started_at)
            return JSONResponse(status_code=503, content={"detail": "کنترل ترافیک موقتاً در دسترس نیست", "request_id": request_id}, headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id})
        if not decision.allowed:
            record_request(request.method, 429, time.perf_counter() - started_at)
            return JSONResponse(status_code=429, content={"detail": "تعداد درخواست‌ها بیش از حد مجاز است", "request_id": request_id}, headers={"Retry-After": str(decision.retry_after), "X-RateLimit-Remaining": "0", "X-Request-ID": request_id, "X-Correlation-ID": correlation_id})
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Process-Time"] = f"{time.perf_counter() - started_at:.6f}"
    if decision is not None:
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    record_request(request.method, response.status_code, time.perf_counter() - started_at)
    logging.getLogger("karenseir.request").info("request", extra={"request_id": request_id, "correlation_id": correlation_id, "method": request.method, "path": request.url.path, "status": response.status_code})
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    correlation_id = getattr(request.state, "correlation_id", request_id)
    logging.getLogger("karenseir.error").exception("unhandled_exception", extra={"request_id": request_id, "correlation_id": correlation_id, "method": request.method, "path": request.url.path, "status": 500})
    return JSONResponse(status_code=500, content={"detail": "خطای داخلی سرویس", "request_id": request_id})


@app.get("/health")
def health() -> dict: return {"status":"ok","service":"karenseir-api","environment":ENVIRONMENT}
@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str: return prometheus_metrics()
@app.get("/ready")
async def readiness(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    try:
        redis_ok = await rate_limiter.ping()
    except Exception:
        redis_ok = False
    if ENVIRONMENT == "production" and not redis_ok:
        raise HTTPException(status_code=503, detail="rate limiter unavailable")
    return {"status":"ready","database":"ok","rate_limiter":"distributed" if rate_limiter.distributed and redis_ok else "development-local","external_providers":"fail_closed"}
@app.post("/auth/dev-login")
def dev_login(data: LoginIn, db: Session = Depends(get_db)) -> dict:
    if ENVIRONMENT != "development": raise HTTPException(status_code=404, detail="Not found")
    user = db.scalar(select(User).where(User.email == data.email))
    if not user: raise HTTPException(status_code=401, detail="کاربر نمونه پیدا نشد")
    tenant = db.get(Tenant, user.tenant_id)
    refresh_token, _ = operational_models.create_refresh_session(db, tenant_id=user.tenant_id, user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    db.commit()
    return {"access_token":token_for(user, tenant),"refresh_token":refresh_token,"token_type":"bearer","user":{"name":user.name,"role":user.role,"tenant":tenant.name}}


@app.post("/auth/otp/request", status_code=status.HTTP_202_ACCEPTED)
def request_otp(data: OTPRequestIn, request: Request, db: Session = Depends(get_db)) -> dict:
    generic_id = str(uuid.uuid4())
    tenant = db.scalar(select(Tenant).where(Tenant.slug == data.tenant_slug))
    if tenant is None:
        _secure_hash(f"{generic_id}:000000")
        return {"status": "accepted", "challenge_id": generic_id, "expires_in": 300}
    set_tenant_context(db, tenant.id)
    identifier = data.identifier.strip().lower()
    user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == identifier))
    if user is None:
        _secure_hash(f"{generic_id}:000000")
        return {"status": "accepted", "challenge_id": generic_id, "expires_in": 300}
    auth_state = db.scalar(select(operational_models.AuthenticationState).where(operational_models.AuthenticationState.tenant_id == tenant.id, operational_models.AuthenticationState.user_id == user.id).with_for_update())
    now = datetime.now(timezone.utc)
    if auth_state and auth_state.locked_until and _aware(auth_state.locked_until) > now:
        return {"status": "accepted", "challenge_id": generic_id, "expires_in": 300}
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = operational_models.OTPChallenge(tenant_id=tenant.id, user_id=user.id, identifier_hash=_secure_hash(identifier), code_hash="pending", expires_at=now + timedelta(minutes=5))
    db.add(challenge); db.flush()
    challenge.code_hash = _secure_hash(f"{challenge.id}:{code}")
    context = operational_models.uuid4_str()
    from .providers import ADAPTERS, ProviderContext
    try:
        delivery = ADAPTERS["otp"].execute("send_otp", {"destination_reference": identifier, "code": code}, ProviderContext(tenant_id=tenant.id, correlation_id=context, idempotency_key=f"otp:{challenge.id}"))
    except Exception:
        logging.getLogger("karenseir.otp").exception("otp_provider_unavailable", extra={"correlation_id": context, "status": 503})
        db.rollback()
        record_business_event("otp", "delivery_failed")
        return {"status": "accepted", "challenge_id": generic_id, "expires_in": 300}
    if not delivery.get("ok"):
        db.rollback()
        record_business_event("otp", "delivery_failed")
        return {"status": "accepted", "challenge_id": generic_id, "expires_in": 300}
    challenge.delivery_reference = str(delivery.get("reference", "accepted"))[:160]
    _, ip_hash = _request_fingerprints(request)
    db.add(operational_models.AuthenticationAudit(tenant_id=tenant.id, user_id=user.id, action="otp.requested", challenge_id=challenge.id, ip_hash=ip_hash))
    db.commit()
    record_business_event("otp", "requested")
    return {"status": "accepted", "challenge_id": challenge.id, "expires_in": 300}


@app.post("/auth/otp/verify")
def verify_otp(data: OTPVerifyIn, request: Request, db: Session = Depends(get_db)) -> dict:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == data.tenant_slug))
    if tenant is None:
        raise HTTPException(status_code=401, detail="کد ورود معتبر نیست")
    set_tenant_context(db, tenant.id)
    challenge = db.scalar(select(operational_models.OTPChallenge).where(operational_models.OTPChallenge.id == data.challenge_id, operational_models.OTPChallenge.tenant_id == tenant.id).with_for_update())
    now = datetime.now(timezone.utc)
    if challenge is None or challenge.consumed_at is not None or _aware(challenge.expires_at) <= now or challenge.attempts >= challenge.max_attempts:
        raise HTTPException(status_code=401, detail="کد ورود معتبر نیست")
    auth_state = db.scalar(select(operational_models.AuthenticationState).where(operational_models.AuthenticationState.tenant_id == tenant.id, operational_models.AuthenticationState.user_id == challenge.user_id).with_for_update())
    if auth_state is None:
        auth_state = operational_models.AuthenticationState(tenant_id=tenant.id, user_id=challenge.user_id)
        db.add(auth_state); db.flush()
    if auth_state.locked_until and _aware(auth_state.locked_until) > now:
        raise HTTPException(status_code=423, detail="حساب موقتاً قفل است")
    device_hash, ip_hash = _request_fingerprints(request, data.device_id)
    if not hmac.compare_digest(challenge.code_hash, _secure_hash(f"{challenge.id}:{data.code}")):
        challenge.attempts += 1
        auth_state.failed_attempts += 1
        if challenge.attempts >= challenge.max_attempts or auth_state.failed_attempts >= 5:
            auth_state.locked_until = now + timedelta(minutes=15)
        db.add(operational_models.AuthenticationAudit(tenant_id=tenant.id, user_id=challenge.user_id, action="otp.verify_failed", challenge_id=challenge.id, device_hash=device_hash, ip_hash=ip_hash))
        db.commit()
        record_business_event("otp", "verify_failed")
        raise HTTPException(status_code=401, detail="کد ورود معتبر نیست")
    challenge.consumed_at = now
    auth_state.failed_attempts = 0
    auth_state.locked_until = None
    user = db.scalar(select(User).where(User.id == challenge.user_id, User.tenant_id == tenant.id))
    if user is None:
        raise HTTPException(status_code=401, detail="کد ورود معتبر نیست")
    refresh_token, _ = operational_models.create_refresh_session(db, tenant_id=tenant.id, user_id=user.id, expires_at=now + timedelta(days=30), device_hash=device_hash, ip_hash=ip_hash)
    db.add(operational_models.AuthenticationAudit(tenant_id=tenant.id, user_id=user.id, action="otp.verified", challenge_id=challenge.id, device_hash=device_hash, ip_hash=ip_hash))
    db.commit()
    record_business_event("otp", "verified")
    return {"access_token": token_for(user, tenant), "refresh_token": refresh_token, "token_type": "bearer", "user": {"name": user.name, "role": user.role, "tenant": tenant.name}}
@app.post("/auth/refresh")
def refresh_access(data: RefreshIn, request: Request, db: Session = Depends(get_db)) -> dict:
    session = operational_models.find_refresh_session(db, data.refresh_token)
    now = datetime.now(timezone.utc)
    expires_at = session.expires_at.replace(tzinfo=timezone.utc) if session and session.expires_at.tzinfo is None else session.expires_at if session else now
    if session is not None and session.revoked_at is not None and session.replaced_by_hash:
        db.execute(update(operational_models.RefreshTokenSession).where(operational_models.RefreshTokenSession.tenant_id == session.tenant_id, operational_models.RefreshTokenSession.family_id == session.family_id, operational_models.RefreshTokenSession.revoked_at.is_(None)).values(revoked_at=now, revoke_reason="refresh_reuse"))
        db.add(operational_models.AuthenticationAudit(tenant_id=session.tenant_id, user_id=session.user_id, action="refresh.reuse_detected"))
        db.commit()
        raise HTTPException(status_code=401, detail="نشست تمدید معتبر نیست")
    if session is None or session.revoked_at is not None or expires_at <= now:
        raise HTTPException(status_code=401, detail="نشست تمدید معتبر نیست")
    if session.device_hash and (not data.device_id or not hmac.compare_digest(session.device_hash, _secure_hash(data.device_id))):
        db.add(operational_models.AuthenticationAudit(tenant_id=session.tenant_id, user_id=session.user_id, action="refresh.device_mismatch"))
        db.commit()
        raise HTTPException(status_code=401, detail="نشست تمدید معتبر نیست")
    user = db.scalar(select(User).where(User.id == session.user_id, User.tenant_id == session.tenant_id))
    if user is None: raise HTTPException(status_code=401, detail="نشست تمدید معتبر نیست")
    _, current_ip_hash = _request_fingerprints(request)
    replacement, replacement_session = operational_models.create_refresh_session(db, tenant_id=user.tenant_id, user_id=user.id, expires_at=now + timedelta(days=30), family_id=session.family_id, device_hash=session.device_hash, ip_hash=current_ip_hash)
    session.revoked_at = now
    session.last_used_at = now
    session.revoke_reason = "rotated"
    session.replaced_by_hash = replacement_session.token_hash
    db.commit()
    return {"access_token": token_for(user, db.get(Tenant, user.tenant_id)), "refresh_token": replacement, "token_type": "bearer"}


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(data: LogoutIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    session = operational_models.find_refresh_session(db, data.refresh_token)
    if session is None or session.tenant_id != user.tenant_id or session.user_id != user.id:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست")
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoke_reason = "logout"
        db.add(operational_models.AuthenticationAudit(tenant_id=user.tenant_id, user_id=user.id, action="session.logged_out"))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
@app.get("/hotels")
def hotels(city: Optional[str] = None, db: Session = Depends(get_db)) -> list[dict]:
    q = select(Hotel).where(Hotel.active, Hotel.inventory > 0)
    if city: q = q.where(Hotel.city == city)
    return [{"id":h.id,"name":h.name,"city":h.city,"rating":float(h.rating),"nightly_price":h.nightly_price,"cancellation":h.cancellation,"inventory":h.inventory,"image_url":h.image_url} for h in db.scalars(q.order_by(Hotel.nightly_price)).all()]
@app.get("/me/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    bookings = db.scalars(select(Booking).where(Booking.tenant_id == user.tenant_id).order_by(Booking.id.desc())).all()
    return {"tenant":db.get(Tenant,user.tenant_id).name,"user":{"name":user.name,"role":user.role},"credit_available":48000000,"bookings":[booking_out(b,db.get(Hotel,b.hotel_id)) for b in bookings]}
@app.post("/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(data: BookingIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120), user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    request_hash = hashlib.sha256(data.model_dump_json().encode("utf-8")).hexdigest()
    idempotency_query = select(operational_models.IdempotencyKey).where(
        operational_models.IdempotencyKey.tenant_id == user.tenant_id,
        operational_models.IdempotencyKey.scope == "legacy-booking.create",
        operational_models.IdempotencyKey.key == idempotency_key,
    )
    prior = db.scalar(idempotency_query)
    if prior:
        if prior.request_hash != request_hash or prior.response_json is None:
            raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return json.loads(prior.response_json)
    hotel = db.scalar(select(Hotel).where(Hotel.id == data.hotel_id).with_for_update())
    # A concurrent retry can pass the first lookup before this inventory lock.
    # Re-check while serialized so it cannot create a second booking.
    prior = db.scalar(idempotency_query)
    if prior:
        if prior.request_hash != request_hash or prior.response_json is None:
            raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return json.loads(prior.response_json)
    if not hotel or not hotel.active or hotel.inventory < 1: raise HTTPException(status_code=409, detail="موجودی قابل رزرو نیست")
    total = hotel.nightly_price * data.nights
    if total > 48000000: raise HTTPException(status_code=422, detail="درخواست از سقف اعتبار پایلوت بیشتر است")
    booking = Booking(tenant_id=user.tenant_id,user_id=user.id,hotel_id=hotel.id,nights=data.nights,total_amount=total)
    hotel.inventory -= 1; db.add(booking); db.flush()
    response = booking_out(booking, hotel)
    db.add_all([
        LedgerEntry(tenant_id=user.tenant_id,booking_id=booking.id,amount=total,entry_type="authorization",note="رزرو در انتظار تأیید"),
        AuditEvent(tenant_id=user.tenant_id,actor_id=user.id,action="booking.created",entity="booking",entity_id=booking.id,detail="pending_approval"),
        operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="legacy-booking.create", key=idempotency_key, request_hash=request_hash, response_json=json.dumps(response)),
    ])
    db.commit()
    record_business_event("booking", "created")
    return response
@app.post("/bookings/{booking_id}/approval")
def approve_booking(booking_id: int, data: ApproveIn, approver: User = Depends(require_role("welfare_manager","organization_admin")), db: Session = Depends(get_db)) -> dict:
    booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.tenant_id == approver.tenant_id))
    if not booking: raise HTTPException(status_code=404, detail="رزرو در این سازمان وجود ندارد")
    if booking.status != "pending_approval": raise HTTPException(status_code=409, detail="رزرو قبلاً تعیین تکلیف شده است")
    booking.status = "approved" if data.decision == "approve" else "rejected"
    db.add(AuditEvent(tenant_id=approver.tenant_id,actor_id=approver.id,action=f"booking.{booking.status}",entity="booking",entity_id=booking.id,detail="approval decision"))
    db.commit(); return {"id":booking.id,"status":booking.status}
@app.get("/integrations")
def integrations(user: User = Depends(require_role("welfare_manager","organization_admin"))) -> list[dict]:
    return [{"name":"Amadeus / GDS","credential_status":"missing","mode":"disabled","policy":"fail_closed"},{"name":"Payment adapter","credential_status":"missing","mode":"disabled","policy":"fail_closed"},{"name":"Manual hotel inventory","credential_status":"not_required","mode":"local","policy":"active"}]


@app.get("/me/reservations")
def reservations(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.Reservation).where(operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id).order_by(operational_models.Reservation.created_at.desc())).all()
    return [{**_reservation_output(row), "provider_connected": bool(row.provider_reference), "created_at": row.created_at.isoformat(), "manage_link": f"/manage-booking/{row.id}"} for row in rows]


@app.get("/me/trips")
def my_trips(user: User = Depends(require_permission("trip:read")), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.Trip).where(operational_models.Trip.tenant_id == user.tenant_id, operational_models.Trip.user_id == user.id).order_by(operational_models.Trip.created_at.desc())).all()
    return [{"id": row.id, "title": row.title, "origin": row.origin, "destination": row.destination, "starts_at": row.starts_at.isoformat() if row.starts_at else None, "ends_at": row.ends_at.isoformat() if row.ends_at else None, "status": row.status, "timeline_link": f"/trips/{row.id}"} for row in rows]


@app.get("/me/notifications")
def my_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.NotificationRecord).where(operational_models.NotificationRecord.tenant_id == user.tenant_id, operational_models.NotificationRecord.user_id == user.id).order_by(operational_models.NotificationRecord.created_at.desc()).limit(50)).all()
    return [{"id": row.id, "topic": row.topic, "title": row.title, "message": row.message, "deep_link": row.deep_link, "status": row.status, "created_at": row.created_at.isoformat()} for row in rows]


@app.get("/me/profile")
def my_profile(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    profile = db.scalar(select(operational_models.UserProfile).where(operational_models.UserProfile.tenant_id == user.tenant_id, operational_models.UserProfile.user_id == user.id))
    return {"user_id": user.id, "name": user.name, "email": user.email, "role": user.role, "locale": profile.locale if profile else "fa-IR"}


@app.put("/me/profile")
def update_my_profile(data: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    profile = db.scalar(select(operational_models.UserProfile).where(operational_models.UserProfile.tenant_id == user.tenant_id, operational_models.UserProfile.user_id == user.id).with_for_update())
    if profile is None:
        profile = operational_models.UserProfile(tenant_id=user.tenant_id, user_id=user.id, profile_type="customer", locale=data.locale); db.add(profile)
    else: profile.locale = data.locale
    user.name = data.name.strip()
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="user_profile", aggregate_id=str(user.id), event_type="profile.updated", payload_json=json.dumps({"locale": data.locale}), correlation_id=str(uuid.uuid4()), idempotency_key=f"profile:{user.id}:{uuid.uuid4()}"))
    db.commit()
    return {"user_id": user.id, "name": user.name, "email": user.email, "role": user.role, "locale": profile.locale}


@app.get("/me/travellers")
def my_travellers(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.Traveller).where(operational_models.Traveller.tenant_id == user.tenant_id, operational_models.Traveller.user_id == user.id).order_by(operational_models.Traveller.created_at)).all()
    return [{"id": row.id, "full_name": row.full_name, "profile_reference": row.profile_reference} for row in rows]


@app.post("/me/travellers", status_code=status.HTTP_201_CREATED)
def create_my_traveller(data: TravellerIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = operational_models.Traveller(tenant_id=user.tenant_id, user_id=user.id, full_name=data.full_name.strip(), profile_reference=data.profile_reference)
    db.add(row); db.commit()
    return {"id": row.id, "full_name": row.full_name, "profile_reference": row.profile_reference}


@app.put("/me/travellers/{traveller_id}")
def update_my_traveller(traveller_id: str, data: TravellerIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Traveller).where(operational_models.Traveller.id == traveller_id, operational_models.Traveller.tenant_id == user.tenant_id, operational_models.Traveller.user_id == user.id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="مسافر در این حساب وجود ندارد")
    row.full_name = data.full_name.strip(); row.profile_reference = data.profile_reference; db.commit()
    return {"id": row.id, "full_name": row.full_name, "profile_reference": row.profile_reference}


@app.post("/me/travellers/{traveller_id}/remove")
def remove_my_traveller(traveller_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Traveller).where(operational_models.Traveller.id == traveller_id, operational_models.Traveller.tenant_id == user.tenant_id, operational_models.Traveller.user_id == user.id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="مسافر در این حساب وجود ندارد")
    linked = db.scalar(select(func.count()).select_from(operational_models.ReservationTraveller).where(operational_models.ReservationTraveller.traveller_id == row.id)) or 0
    if linked: raise HTTPException(status_code=409, detail="مسافر متصل به رزرو قابل حذف نیست")
    db.delete(row); db.commit(); return {"status": "removed", "id": traveller_id}


@app.get("/me/wallets")
def my_wallets(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.Wallet).where(operational_models.Wallet.tenant_id == user.tenant_id, operational_models.Wallet.owner_type == "user", operational_models.Wallet.owner_reference == str(user.id))).all()
    return [{"id": row.id, "owner_type": row.owner_type, "currency": row.currency, **operational_models.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=row.id)} for row in rows]


@app.post("/me/wallets", status_code=status.HTTP_201_CREATED)
def create_my_wallet(data: WalletCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db), idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
    request_hash = _secure_hash(f"{user.id}:{data.currency}")
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "wallet.create", operational_models.IdempotencyKey.key == idempotency_key))
    if prior:
        if prior.request_hash != request_hash: raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return json.loads(prior.response_json or "{}")
    row = db.scalar(select(operational_models.Wallet).where(operational_models.Wallet.tenant_id == user.tenant_id, operational_models.Wallet.owner_type == "user", operational_models.Wallet.owner_reference == str(user.id), operational_models.Wallet.currency == data.currency).with_for_update())
    if row is None: row = operational_models.Wallet(tenant_id=user.tenant_id, owner_type="user", owner_reference=str(user.id), currency=data.currency); db.add(row); db.flush()
    response = {"id": row.id, "owner_type": row.owner_type, "currency": row.currency, **operational_models.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=row.id)}
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="wallet.create", key=idempotency_key, request_hash=request_hash, response_json=json.dumps(response))); db.commit(); return response


@app.get("/me/payments")
def my_payments(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.user_id == user.id).order_by(operational_models.PaymentIntent.created_at.desc())).all()
    return [{"id": row.id, "reservation_id": row.reservation_id, "status": row.status, "amount": row.amount, "currency": row.currency, "captured_amount": row.captured_amount, "refunded_amount": row.refunded_amount, "provider_connected": bool(row.provider_reference)} for row in rows]


@app.get("/me/installment-plans")
def my_installment_plans(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    assignments = db.scalars(select(operational_models.EmployeeAssignment).where(operational_models.EmployeeAssignment.tenant_id == user.tenant_id, operational_models.EmployeeAssignment.user_id == user.id)).all()
    organization_ids = [row.organization_id for row in assignments]
    if not organization_ids: return []
    rows = db.scalars(select(operational_models.InstallmentPlan).where(operational_models.InstallmentPlan.tenant_id == user.tenant_id, operational_models.InstallmentPlan.organization_id.in_(organization_ids), operational_models.InstallmentPlan.status == "active")).all()
    return [{"id": row.id, "title": row.title, "terms": json.loads(row.terms_json), "status": row.status} for row in rows]


def _owned_support_scope(db: Session, user: User, reservation_id: Optional[str], trip_id: Optional[str]) -> None:
    if bool(reservation_id) == bool(trip_id): raise HTTPException(status_code=422, detail="دقیقاً یک سفر یا رزرو باید انتخاب شود")
    if reservation_id and db.scalar(select(operational_models.Reservation.id).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id)) is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    if trip_id and db.scalar(select(operational_models.Trip.id).where(operational_models.Trip.id == trip_id, operational_models.Trip.tenant_id == user.tenant_id, operational_models.Trip.user_id == user.id)) is None: raise HTTPException(status_code=404, detail="سفر در این حساب وجود ندارد")


@app.post("/me/support/messages", status_code=status.HTTP_201_CREATED)
def create_support_message(data: SupportMessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    _owned_support_scope(db, user, data.reservation_id, data.trip_id)
    row = operational_models.SupportMessage(tenant_id=user.tenant_id, reservation_id=data.reservation_id, trip_id=data.trip_id, sender_type="customer", body=data.body.strip())
    db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="support_message", aggregate_id=row.id, event_type="support.customer_message.created", payload_json=json.dumps({"reservation_id": data.reservation_id, "trip_id": data.trip_id}), correlation_id=str(uuid.uuid4()), idempotency_key=f"support:{row.id}")); db.commit()
    return {"id": row.id, "sender_type": row.sender_type, "body": row.body, "reservation_id": row.reservation_id, "trip_id": row.trip_id}


@app.get("/reservations/{reservation_id}")
def reservation_detail(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id))
    if row is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    return {**_reservation_output(row), "current_policy": json.loads(row.current_policy_json), "provider_connected": bool(row.provider_reference), "manage_link": f"/manage-booking/{row.id}"}


@app.post("/reservations/{reservation_id}/commands")
def reservation_command(reservation_id: str, data: ReservationCommandIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id))
    if not reservation:
        raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    try:
        operational_models.transition_reservation(db, reservation, data.target, user.id, data.command_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {"id": reservation.id, "status": reservation.status, "provider_connected": False}


@app.post("/reservations/{reservation_id}/service-requests", status_code=status.HTTP_202_ACCEPTED)
def create_service_request(reservation_id: str, data: ServiceRequestIn, user: User = Depends(current_user), db: Session = Depends(get_db), idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "manage-booking.request", operational_models.IdempotencyKey.key == idempotency_key))
    if prior and prior.response_json:
        stored = json.loads(prior.response_json)
        if stored.get("reservation_id") != reservation_id or stored.get("request_type") != data.request_type: raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return stored
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id).with_for_update())
    if not reservation:
        raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    quote = _verified_cancellation_quote(reservation) if data.request_type in {"cancel", "refund"} else None
    quote_payload = quote or {"status": "requires_provider_review"}
    request = operational_models.BookingServiceRequest(tenant_id=user.tenant_id, reservation_id=reservation.id, request_type=data.request_type, status="submitted", quote_snapshot_json=json.dumps(quote_payload, sort_keys=True), reason=data.reason)
    db.add(request)
    db.flush()
    target = {"cancel": "cancel_requested", "change": "change_requested", "refund": "refund_requested"}[data.request_type]
    try: operational_models.transition_reservation(db, reservation, target, user.id, f"{idempotency_key}:transition")
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    refund_id = None
    if data.request_type == "refund" and quote:
        payment = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.reservation_id == reservation.id, operational_models.PaymentIntent.status == "captured").with_for_update())
        if payment is None: raise HTTPException(status_code=409, detail="پرداخت captureشده برای استرداد موجود نیست")
        amount = int(quote["refundable_amount"])
        pending = db.scalar(select(func.coalesce(func.sum(operational_models.RefundRecord.amount), 0)).where(operational_models.RefundRecord.tenant_id == user.tenant_id, operational_models.RefundRecord.payment_intent_id == payment.id, operational_models.RefundRecord.status == "requested")) or 0
        if amount <= 0 or amount > payment.captured_amount - payment.refunded_amount - int(pending): raise HTTPException(status_code=409, detail="مبلغ معتبر قابل استرداد موجود نیست")
        refund = operational_models.RefundRecord(tenant_id=user.tenant_id, payment_intent_id=payment.id, command_id=idempotency_key, amount=amount)
        db.add(refund); db.flush(); refund_id = refund.id
    response = {"id": request.id, "reservation_id": reservation.id, "request_type": data.request_type, "status": request.status, "consequence_preview": "verified_policy" if quote else "requires_provider_review", "quote": quote, "refund_id": refund_id, "reservation_changed": False, "booking_status": reservation.status}
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="manage-booking.request", key=idempotency_key, request_hash=_secure_hash(f"{reservation.id}:{data.request_type}:{data.reason or ''}"), response_json=json.dumps(response)))
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="reservation", aggregate_id=reservation.id, event_type=f"service_request.{data.request_type}.submitted", payload_json=json.dumps({"request_id": request.id, "refund_id": refund_id}), correlation_id=str(uuid.uuid4()), idempotency_key=idempotency_key))
    db.commit()
    return response


@app.get("/trips/{trip_id}/timeline")
def trip_timeline(trip_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    trip = db.scalar(select(operational_models.Trip).where(operational_models.Trip.id == trip_id, operational_models.Trip.tenant_id == user.tenant_id, operational_models.Trip.user_id == user.id))
    if not trip:
        raise HTTPException(status_code=404, detail="سفر در این حساب وجود ندارد")
    events = db.scalars(select(operational_models.TripEventRecord).where(operational_models.TripEventRecord.trip_id == trip.id, operational_models.TripEventRecord.tenant_id == user.tenant_id, operational_models.TripEventRecord.visibility == "customer").order_by(operational_models.TripEventRecord.created_at.desc())).all()
    return {"trip":{"id":trip.id,"destination":trip.destination,"status":trip.status},"events":[{"id":event.id,"type":event.event_type,"severity":event.severity,"source":event.source,"title":event.title,"message":event.message,"requires_action":event.requires_action,"deep_link":event.deep_link} for event in events]}


@app.get("/trips/{trip_id}/events/{event_id}")
def trip_event_detail(trip_id: str, event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    trip = db.scalar(select(operational_models.Trip).where(operational_models.Trip.id == trip_id, operational_models.Trip.tenant_id == user.tenant_id, operational_models.Trip.user_id == user.id))
    if trip is None: raise HTTPException(status_code=404, detail="سفر در این حساب وجود ندارد")
    event = db.scalar(select(operational_models.TripEventRecord).where(operational_models.TripEventRecord.id == event_id, operational_models.TripEventRecord.trip_id == trip.id, operational_models.TripEventRecord.tenant_id == user.tenant_id, operational_models.TripEventRecord.visibility == "customer"))
    if event is None: raise HTTPException(status_code=404, detail="رویداد قابل نمایش نیست")
    return {"id": event.id, "trip_id": trip.id, "type": event.event_type, "source": event.source, "title": event.title, "message": event.message, "requires_action": event.requires_action, "deep_link": event.deep_link}


@app.get("/wallets/{wallet_id}")
def wallet_detail(wallet_id: str, user: User = Depends(require_permission("credit:read")), db: Session = Depends(get_db)) -> dict:
    wallet = db.scalar(select(operational_models.Wallet).where(operational_models.Wallet.id == wallet_id, operational_models.Wallet.tenant_id == user.tenant_id))
    if wallet is None: raise HTTPException(status_code=404, detail="کیف پول در این سازمان وجود ندارد")
    return {"id": wallet.id, "currency": wallet.currency, **operational_models.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=wallet.id)}


@app.post("/wallets/{wallet_id}/commands")
def wallet_command(wallet_id: str, data: CreditCommandIn, user: User = Depends(require_permission("credit:manage")), db: Session = Depends(get_db)) -> dict:
    try:
        entry = operational_models.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet_id, command_id=data.command_id, entry_type=data.entry_type, amount=data.amount)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"entry_id": entry.id, "command_id": entry.command_id, **operational_models.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=wallet_id)}


@app.post("/approvals/{approval_id}/decision")
def approval_decision(approval_id: str, data: ApprovalDecisionIn, user: User = Depends(require_permission("approval:decide")), db: Session = Depends(get_db)) -> dict:
    workflow = db.scalar(select(operational_models.ApprovalWorkflow).where(operational_models.ApprovalWorkflow.id == approval_id, operational_models.ApprovalWorkflow.tenant_id == user.tenant_id).with_for_update())
    if workflow is None: raise HTTPException(status_code=404, detail="درخواست تأیید در این سازمان وجود ندارد")
    if workflow.status != "pending": raise HTTPException(status_code=409, detail="درخواست قبلاً تعیین تکلیف شده است")
    if workflow.template_id:
        step = db.scalar(select(operational_models.ApprovalInstanceStep).where(operational_models.ApprovalInstanceStep.workflow_id == workflow.id, operational_models.ApprovalInstanceStep.tenant_id == user.tenant_id, operational_models.ApprovalInstanceStep.step_order == workflow.current_step_order).with_for_update())
        if step is None or step.status != "pending": raise HTTPException(status_code=409, detail="مرحله فعال تأیید وجود ندارد")
        if user.role != step.required_role and user.role != "platform_admin": raise HTTPException(status_code=403, detail="این مرحله به نقش دیگری اختصاص دارد")
        now = datetime.now(timezone.utc)
        if data.decision == "reject":
            if not data.rejection_reason or len(data.rejection_reason.strip()) < 3: raise HTTPException(status_code=422, detail="دلیل رد الزامی است")
            step.status = "rejected"; step.rejection_reason = data.rejection_reason.strip(); workflow.status = "rejected"; workflow.rejection_reason = step.rejection_reason
        else:
            step.status = "approved"
            next_step = db.scalar(select(operational_models.ApprovalInstanceStep).where(operational_models.ApprovalInstanceStep.workflow_id == workflow.id, operational_models.ApprovalInstanceStep.tenant_id == user.tenant_id, operational_models.ApprovalInstanceStep.step_order == workflow.current_step_order + 1).with_for_update())
            if next_step:
                next_step.status = "pending"; workflow.current_step_order = next_step.step_order
            else:
                workflow.status = "approved"
        step.decided_by_user_id = user.id; step.decided_at = now; workflow.approver_user_id = user.id
        db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="approval", aggregate_id=workflow.id, event_type=f"approval.step.{step.status}", payload_json=json.dumps({"workflow_id": workflow.id, "step_order": step.step_order, "status": step.status}), correlation_id=str(uuid.uuid4()), idempotency_key=f"approval:{workflow.id}:{step.step_order}:{step.status}"))
        db.commit()
        return {"id": workflow.id, "status": workflow.status, "current_step_order": workflow.current_step_order, "step_status": step.status}
    workflow.status = "approved" if data.decision == "approve" else "rejected"
    workflow.approver_user_id = user.id
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="approval", aggregate_id=workflow.id, event_type=f"approval.{workflow.status}", payload_json="{}", correlation_id=str(uuid.uuid4()), idempotency_key=f"approval:{workflow.id}:{workflow.status}"))
    db.commit()
    return {"id": workflow.id, "status": workflow.status}


@app.post("/reservations/{reservation_id}/payment-intents", status_code=status.HTTP_201_CREATED)
def create_payment_intent(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db), idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
    existing = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.command_id == idempotency_key))
    if existing:
        if existing.reservation_id != reservation_id or existing.user_id != user.id:
            raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return {"id": existing.id, "status": existing.status, "amount": existing.amount, "currency": existing.currency}
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id).with_for_update())
    if reservation is None:
        raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    try:
        snapshot = json.loads(reservation.price_snapshot_json)
        amount = int(snapshot.get("total_amount", snapshot.get("amount", 0)))
        currency = str(snapshot.get("currency", "IRR"))
    except (TypeError, ValueError, json.JSONDecodeError):
        amount = 0; currency = "IRR"
    if amount <= 0 or currency != "IRR":
        raise HTTPException(status_code=409, detail="قیمت معتبر و قطعی برای پرداخت موجود نیست")
    intent = operational_models.PaymentIntent(tenant_id=user.tenant_id, reservation_id=reservation.id, user_id=user.id, command_id=idempotency_key, amount=amount, currency=currency)
    db.add(intent); db.flush()
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="payment", aggregate_id=intent.id, event_type="payment.intent.created", payload_json=json.dumps({"payment_intent_id": intent.id}), correlation_id=str(uuid.uuid4()), idempotency_key=idempotency_key))
    db.commit()
    record_business_event("payment", "intent_created")
    return {"id": intent.id, "status": intent.status, "amount": intent.amount, "currency": intent.currency}


@app.post("/payments/{payment_id}/initiate", status_code=status.HTTP_202_ACCEPTED)
def initiate_payment(payment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    intent = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.id == payment_id, operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.user_id == user.id).with_for_update())
    if intent is None:
        raise HTTPException(status_code=404, detail="درخواست پرداخت وجود ندارد")
    if intent.status not in {"created", "failed"}:
        return {"id": intent.id, "status": intent.status}
    from .providers import ADAPTERS, ProviderContext
    try:
        result = ADAPTERS["payment"].execute("initiate", {"payment_intent_id": intent.id, "amount": intent.amount, "currency": intent.currency}, ProviderContext(tenant_id=user.tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=intent.command_id))
    except Exception:
        logging.getLogger("karenseir.payment").exception("payment_provider_unavailable")
        record_business_event("provider", "payment_unavailable")
        raise HTTPException(status_code=503, detail="درگاه پرداخت معتبر در دسترس نیست")
    if not result.get("ok"):
        record_business_event("provider", "payment_unavailable")
        raise HTTPException(status_code=503, detail="درگاه پرداخت معتبر در دسترس نیست")
    redirect_url = str(result.get("redirect_url", ""))
    parsed = urlparse(redirect_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=502, detail="پاسخ درگاه پرداخت معتبر نیست")
    intent.status = "initiated"
    intent.provider_reference = str(result.get("reference", ""))[:160] or None
    db.commit()
    record_business_event("payment", "initiated")
    return {"id": intent.id, "status": intent.status, "redirect_url": redirect_url}


@app.post("/payments/callback/{provider_key}")
async def payment_callback(provider_key: str, request: Request, x_payment_signature: str = Header(alias="X-Payment-Signature"), db: Session = Depends(get_db)) -> dict:
    if provider_key != "payment" or not PAYMENT_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="اعتبارسنجی callback پیکربندی نشده است")
    raw = await request.body()
    expected = hmac.new(PAYMENT_WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_payment_signature):
        raise HTTPException(status_code=401, detail="امضای callback نامعتبر است")
    try:
        payload = json.loads(raw)
        tenant_id = int(payload["tenant_id"]); payment_id = str(payload["payment_intent_id"]); event_id = str(payload["event_id"]); target = str(payload["status"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=422, detail="payload callback نامعتبر است")
    if target not in {"authorized", "captured", "failed", "refund_succeeded"}:
        raise HTTPException(status_code=422, detail="وضعیت callback نامعتبر است")
    set_tenant_context(db, tenant_id)
    payload_hash = hashlib.sha256(raw).hexdigest()
    prior = db.scalar(select(operational_models.PaymentEvent).where(operational_models.PaymentEvent.provider_key == provider_key, operational_models.PaymentEvent.provider_event_id == event_id))
    if prior:
        if prior.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="شناسه callback با payload متفاوت تکرار شده است")
        intent = db.get(operational_models.PaymentIntent, prior.payment_intent_id)
        return {"status": "duplicate", "payment_status": intent.status}
    intent = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.id == payment_id, operational_models.PaymentIntent.tenant_id == tenant_id).with_for_update())
    if intent is None:
        raise HTTPException(status_code=404, detail="درخواست پرداخت وجود ندارد")
    allowed = {"created": {"failed"}, "initiated": {"authorized", "captured", "failed"}, "authorized": {"captured", "failed"}, "captured": {"refund_succeeded"}, "failed": set(), "refunded": set()}
    if target not in allowed.get(intent.status, set()):
        raise HTTPException(status_code=409, detail="تغییر وضعیت پرداخت مجاز نیست")
    callback_amount = int(payload.get("amount", intent.amount))
    if target in {"authorized", "captured"} and callback_amount != intent.amount:
        raise HTTPException(status_code=409, detail="مبلغ callback با Payment Intent تطابق ندارد")
    if target == "refund_succeeded":
        refund_id = str(payload.get("refund_id", ""))
        refund = db.scalar(select(operational_models.RefundRecord).where(operational_models.RefundRecord.id == refund_id, operational_models.RefundRecord.payment_intent_id == intent.id, operational_models.RefundRecord.tenant_id == tenant_id).with_for_update())
        if refund is None or refund.status != "requested" or callback_amount != refund.amount or intent.refunded_amount + callback_amount > intent.captured_amount:
            raise HTTPException(status_code=409, detail="callback استرداد با درخواست معتبر تطابق ندارد")
        refund.status = "succeeded"
        refund.provider_reference = str(payload.get("provider_reference", ""))[:160] or None
        intent.refunded_amount += callback_amount
        intent.status = "refunded" if intent.refunded_amount == intent.captured_amount else "captured"
    else:
        intent.status = target
        if target == "captured": intent.captured_amount = callback_amount
    db.add(operational_models.PaymentEvent(tenant_id=tenant_id, payment_intent_id=intent.id, provider_key=provider_key, provider_event_id=event_id, event_type=target, payload_hash=payload_hash))
    db.commit()
    record_business_event("payment", target)
    return {"status": "accepted", "payment_status": intent.status}


@app.post("/payments/{payment_id}/refunds", status_code=status.HTTP_202_ACCEPTED)
def request_refund(payment_id: str, data: RefundIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    intent = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.id == payment_id, operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.user_id == user.id).with_for_update())
    if intent is None:
        raise HTTPException(status_code=404, detail="پرداخت در این حساب وجود ندارد")
    existing = db.scalar(select(operational_models.RefundRecord).where(operational_models.RefundRecord.tenant_id == user.tenant_id, operational_models.RefundRecord.command_id == data.command_id))
    if existing:
        if existing.payment_intent_id != intent.id or existing.amount != data.amount:
            raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return {"id": existing.id, "status": existing.status, "amount": existing.amount}
    pending_refunds = db.scalar(select(func.coalesce(func.sum(operational_models.RefundRecord.amount), 0)).where(operational_models.RefundRecord.tenant_id == user.tenant_id, operational_models.RefundRecord.payment_intent_id == intent.id, operational_models.RefundRecord.status == "requested")) or 0
    if intent.status != "captured" or data.amount > intent.captured_amount - intent.refunded_amount - int(pending_refunds):
        raise HTTPException(status_code=409, detail="مبلغ قابل استرداد کافی نیست")
    refund = operational_models.RefundRecord(tenant_id=user.tenant_id, payment_intent_id=intent.id, command_id=data.command_id, amount=data.amount)
    db.add(refund); db.flush()
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="refund", aggregate_id=refund.id, event_type="refund.requested", payload_json=json.dumps({"refund_id": refund.id, "payment_intent_id": intent.id, "amount": refund.amount}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id))
    db.commit()
    record_business_event("refund", "requested")
    return {"id": refund.id, "status": refund.status, "amount": refund.amount}


@app.post("/supplier/offers", status_code=status.HTTP_201_CREATED)
def create_supplier_offer(data: SupplierOfferIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    supplier = db.scalar(select(operational_models.Supplier).where(operational_models.Supplier.id == data.supplier_id, operational_models.Supplier.tenant_id == user.tenant_id).with_for_update())
    if supplier is None or supplier.status != "active":
        raise HTTPException(status_code=409, detail="تأمین‌کننده فعال و احرازشده نیست")
    if data.service_type == "package" and (not isinstance(data.attributes.get("items"), list) or len(data.attributes["items"]) < 2):
        raise HTTPException(status_code=422, detail="پکیج باید حداقل دو جزء معتبر داشته باشد")
    if data.policy.get("verified") is not True or not data.policy.get("source") or not data.policy.get("verified_at"):
        raise HTTPException(status_code=422, detail="policy معتبر و timestamp‌دار لازم است")
    offer = operational_models.Offer(tenant_id=user.tenant_id, supplier_id=supplier.id, service_type=data.service_type, title=data.title, amount=data.amount, available_units=data.available_units, valid_until=datetime.now(timezone.utc) + timedelta(minutes=data.valid_minutes), policy_json=json.dumps(data.policy, sort_keys=True), attributes_json=json.dumps(data.attributes, sort_keys=True), fulfillment_mode=data.fulfillment_mode, provider_key=data.provider_key)
    db.add(offer); db.flush()
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="offer", aggregate_id=offer.id, event_type="offer.published", payload_json=json.dumps({"offer_id": offer.id, "service_type": offer.service_type}), correlation_id=str(uuid.uuid4()), idempotency_key=f"offer:{offer.id}"))
    db.commit()
    return {"id": offer.id, "service_type": offer.service_type, "status": offer.status, "available_units": offer.available_units}


@app.post("/supplier/onboarding", status_code=status.HTTP_201_CREATED)
def onboard_supplier(data: SupplierOnboardingIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120), user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    request_hash = _secure_hash(data.model_dump_json())
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "supplier.onboarding", operational_models.IdempotencyKey.key == idempotency_key))
    if prior and prior.response_json:
        if prior.request_hash != request_hash: raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return json.loads(prior.response_json)
    row = operational_models.Supplier(tenant_id=user.tenant_id, supplier_type=data.supplier_type, display_name=data.display_name, status="active")
    db.add(row); db.flush()
    response = {"id": row.id, "supplier_type": row.supplier_type, "display_name": row.display_name, "status": row.status}
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="supplier.onboarding", key=idempotency_key, request_hash=request_hash, response_json=json.dumps(response)))
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="supplier", aggregate_id=row.id, event_type="supplier.onboarded", payload_json=json.dumps({"supplier_id": row.id, "supplier_type": row.supplier_type}), correlation_id=str(uuid.uuid4()), idempotency_key=idempotency_key))
    db.commit(); return response


@app.post("/search/offers")
def search_offers(data: OfferSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(operational_models.Offer).where(operational_models.Offer.tenant_id == user.tenant_id, operational_models.Offer.service_type == data.service_type, operational_models.Offer.status == "active", operational_models.Offer.available_units > 0, operational_models.Offer.valid_until > now).order_by(operational_models.Offer.amount)).all()
    return [{"id": row.id, "service_type": row.service_type, "title": row.title, "amount": row.amount, "currency": row.currency, "available": True, "valid_until": row.valid_until.isoformat(), "provider_status": "supplier_verified" if row.fulfillment_mode == "manual_supplier" else "provider_required"} for row in rows]


@app.post("/offers/{offer_id}/price-check", status_code=status.HTTP_201_CREATED)
def price_check(offer_id: str, data: PriceCheckIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(operational_models.PriceCheck).where(operational_models.PriceCheck.tenant_id == user.tenant_id, operational_models.PriceCheck.command_id == data.command_id))
    if existing:
        if existing.offer_id != offer_id or existing.units != data.units:
            raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return {"id": existing.id, "offer_id": existing.offer_id, "amount": existing.amount, "currency": existing.currency, "expires_at": existing.expires_at.isoformat()}
    offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == offer_id, operational_models.Offer.tenant_id == user.tenant_id).with_for_update())
    now = datetime.now(timezone.utc)
    if offer is None or offer.status != "active" or _aware(offer.valid_until) <= now or offer.available_units < data.units:
        raise HTTPException(status_code=409, detail="Offer قابل قیمت‌سنجی نیست")
    snapshot = {"offer_id": offer.id, "service_type": offer.service_type, "supplier_id": offer.supplier_id, "title": offer.title, "unit_amount": offer.amount, "units": data.units, "total_amount": offer.amount * data.units, "currency": offer.currency, "policy": json.loads(offer.policy_json), "attributes": json.loads(offer.attributes_json), "provider_key": offer.provider_key, "fulfillment_mode": offer.fulfillment_mode, "checked_at": now.isoformat()}
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    expires_at = min(_aware(offer.valid_until), now + timedelta(minutes=10))
    row = operational_models.PriceCheck(tenant_id=user.tenant_id, offer_id=offer.id, user_id=user.id, command_id=data.command_id, amount=snapshot["total_amount"], currency=offer.currency, units=data.units, snapshot_json=encoded, snapshot_hash=_secure_hash(encoded), expires_at=expires_at)
    db.add(row); db.commit()
    return {"id": row.id, "offer_id": row.offer_id, "amount": row.amount, "currency": row.currency, "expires_at": row.expires_at.isoformat()}


@app.post("/orchestration/bookings", status_code=status.HTTP_201_CREATED)
def orchestrate_booking(data: OrchestrationBookingIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "orchestration.booking", operational_models.IdempotencyKey.key == data.command_id))
    if prior and prior.response_json:
        stored = json.loads(prior.response_json)
        if stored.get("price_check_id") != data.price_check_id:
            raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return stored
    check = db.scalar(select(operational_models.PriceCheck).where(operational_models.PriceCheck.id == data.price_check_id, operational_models.PriceCheck.tenant_id == user.tenant_id, operational_models.PriceCheck.user_id == user.id).with_for_update())
    now = datetime.now(timezone.utc)
    if check is None or check.consumed_at is not None or _aware(check.expires_at) <= now:
        raise HTTPException(status_code=409, detail="Price Check معتبر نیست")
    offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == check.offer_id, operational_models.Offer.tenant_id == user.tenant_id).with_for_update())
    if offer is None or offer.available_units < check.units or offer.status != "active":
        raise HTTPException(status_code=409, detail="موجودی Offer کافی نیست")
    snapshot = json.loads(check.snapshot_json)
    if not hmac.compare_digest(check.snapshot_hash, _secure_hash(check.snapshot_json)):
        raise HTTPException(status_code=409, detail="Price Check integrity نامعتبر است")
    reference = "KS-" + secrets.token_hex(8).upper()
    reservation = operational_models.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type=snapshot["service_type"], status="reserved", booking_reference=reference, price_check_id=check.id, price_snapshot_json=json.dumps({"total_amount": check.amount, "currency": check.currency, "units": check.units, "checked_at": snapshot["checked_at"]}, sort_keys=True), policy_at_booking_json=json.dumps(snapshot["policy"], sort_keys=True), current_policy_json=json.dumps(snapshot["policy"], sort_keys=True))
    db.add(reservation); db.flush()
    db.add(operational_models.BookingItem(tenant_id=user.tenant_id, reservation_id=reservation.id, item_type=snapshot["service_type"], snapshot_json=json.dumps({"title": snapshot["title"], "attributes": snapshot["attributes"], "supplier_id": snapshot["supplier_id"], "offer_id": offer.id, "provider_key": snapshot["provider_key"], "fulfillment_mode": snapshot["fulfillment_mode"]}, sort_keys=True)))
    db.add(operational_models.BookingStatusHistory(tenant_id=user.tenant_id, reservation_id=reservation.id, from_status=None, to_status="reserved", actor_id=user.id, command_id=data.command_id))
    offer.available_units -= check.units; check.consumed_at = now
    response = {**_reservation_output(reservation), "price_check_id": check.id}
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="orchestration.booking", key=data.command_id, request_hash=_secure_hash(data.price_check_id), response_json=json.dumps(response)))
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="reservation", aggregate_id=reservation.id, event_type="reservation.reserved", payload_json=json.dumps({"reservation_id": reservation.id, "offer_id": offer.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id))
    db.commit(); record_business_event("booking", "reserved")
    return response


@app.post("/reservations/{reservation_id}/fulfill")
def fulfill_reservation(reservation_id: str, data: FulfillmentIn, user: User = Depends(require_permission("reservation:fulfill")), db: Session = Depends(get_db)) -> dict:
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id).with_for_update())
    if reservation is None:
        raise HTTPException(status_code=404, detail="رزرو در این tenant وجود ندارد")
    existing_voucher = db.scalar(select(operational_models.Voucher).where(operational_models.Voucher.tenant_id == user.tenant_id, operational_models.Voucher.reservation_id == reservation.id))
    if reservation.status == "issued" and existing_voucher:
        return {"reservation": _reservation_output(reservation), "voucher": {"id": existing_voucher.id, "status": existing_voucher.status, "revision": existing_voucher.revision}}
    payment = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.reservation_id == reservation.id, operational_models.PaymentIntent.status == "captured"))
    if payment is None or payment.captured_amount <= 0:
        raise HTTPException(status_code=409, detail="پرداخت captureشده برای رزرو موجود نیست")
    item = db.scalar(select(operational_models.BookingItem).where(operational_models.BookingItem.tenant_id == user.tenant_id, operational_models.BookingItem.reservation_id == reservation.id))
    item_snapshot = json.loads(item.snapshot_json) if item else {}
    if item_snapshot.get("fulfillment_mode") == "provider":
        from .providers import ADAPTERS, ProviderContext
        adapter = ADAPTERS.get(item_snapshot.get("provider_key"))
        if adapter is None:
            raise HTTPException(status_code=503, detail="Provider رزرو پیکربندی نشده است")
        result = adapter.execute("confirm_booking", {"reservation_id": reservation.id, "provider_reference": data.provider_reference}, ProviderContext(user.tenant_id, str(uuid.uuid4()), data.command_id))
        if not result.get("ok"):
            raise HTTPException(status_code=503, detail="Provider رزرو در دسترس نیست")
    if not data.document_reference.startswith(("document://", "s3://", "vault://")):
        raise HTTPException(status_code=422, detail="document reference معتبر نیست")
    try:
        operational_models.transition_reservation(db, reservation, "confirmed", user.id, f"{data.command_id}:confirmed")
        reservation.provider_reference = data.provider_reference
        reservation.confirmed_at = datetime.now(timezone.utc)
        operational_models.transition_reservation(db, reservation, "issued", user.id, f"{data.command_id}:issued")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    voucher = operational_models.Voucher(tenant_id=user.tenant_id, reservation_id=reservation.id, status="issued", revision=1, document_reference=data.document_reference)
    db.add(voucher); db.flush()
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="voucher", aggregate_id=voucher.id, event_type="voucher.issued", payload_json=json.dumps({"reservation_id": reservation.id, "voucher_id": voucher.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id))
    db.commit(); record_business_event("booking", "issued")
    return {"reservation": _reservation_output(reservation), "voucher": {"id": voucher.id, "status": voucher.status, "revision": voucher.revision}}


@app.get("/reservations/{reservation_id}/history")
def reservation_history(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id))
    if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    rows = db.scalars(select(operational_models.BookingStatusHistory).where(operational_models.BookingStatusHistory.tenant_id == user.tenant_id, operational_models.BookingStatusHistory.reservation_id == reservation.id).order_by(operational_models.BookingStatusHistory.created_at)).all()
    return {"reservation_id": reservation.id, "history": [{"from": row.from_status, "to": row.to_status, "actor_id": row.actor_id, "reason": row.reason, "at": row.created_at.isoformat()} for row in rows]}


@app.get("/reservations/{reservation_id}/cancellation-quote")
def cancellation_quote(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id))
    if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    quote = _verified_cancellation_quote(reservation)
    if quote is None: raise HTTPException(status_code=409, detail="Policy معتبر برای محاسبه استرداد موجود نیست")
    return {"reservation_id": reservation.id, **quote}


@app.post("/reservations/{reservation_id}/voucher/reissue")
def reissue_voucher(reservation_id: str, data: VoucherReissueIn, user: User = Depends(require_permission("reservation:fulfill")), db: Session = Depends(get_db)) -> dict:
    if not data.document_reference.startswith(("document://", "s3://", "vault://")): raise HTTPException(status_code=422, detail="document reference معتبر نیست")
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id).with_for_update())
    if reservation is None or reservation.status not in {"issued", "changed"}: raise HTTPException(status_code=409, detail="رزرو قابل صدور مجدد واچر نیست")
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "voucher.reissue", operational_models.IdempotencyKey.key == data.command_id))
    voucher = db.scalar(select(operational_models.Voucher).where(operational_models.Voucher.tenant_id == user.tenant_id, operational_models.Voucher.reservation_id == reservation.id).with_for_update())
    if prior and voucher: return {"id": voucher.id, "status": voucher.status, "revision": voucher.revision}
    if voucher is None: raise HTTPException(status_code=404, detail="واچر قبلی وجود ندارد")
    voucher.revision += 1; voucher.document_reference = data.document_reference; voucher.status = "issued"
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="voucher.reissue", key=data.command_id, request_hash=_secure_hash(f"{reservation.id}:{data.document_reference}"), response_json=json.dumps({"voucher_id": voucher.id, "revision": voucher.revision})))
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="voucher", aggregate_id=voucher.id, event_type="voucher.reissued", payload_json=json.dumps({"reservation_id": reservation.id, "revision": voucher.revision, "reason": data.reason}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id))
    db.commit(); return {"id": voucher.id, "status": voucher.status, "revision": voucher.revision}


@app.post("/organizations/{organization_id}/departments", status_code=status.HTTP_201_CREATED)
def create_department(organization_id: str, data: OrganizationDimensionIn, user: User = Depends(require_permission("member:manage")), db: Session = Depends(get_db)) -> dict:
    organization = db.scalar(select(operational_models.Organization).where(operational_models.Organization.id == organization_id, operational_models.Organization.tenant_id == user.tenant_id))
    if organization is None: raise HTTPException(status_code=404, detail="سازمان وجود ندارد")
    row = operational_models.Department(tenant_id=user.tenant_id, organization_id=organization.id, name=data.name, code=data.code)
    db.add(row); db.commit()
    return {"id": row.id, "name": row.name, "code": row.code}


@app.post("/organizations/{organization_id}/cost-centers", status_code=status.HTTP_201_CREATED)
def create_cost_center(organization_id: str, data: OrganizationDimensionIn, user: User = Depends(require_permission("member:manage")), db: Session = Depends(get_db)) -> dict:
    organization = db.scalar(select(operational_models.Organization).where(operational_models.Organization.id == organization_id, operational_models.Organization.tenant_id == user.tenant_id))
    if organization is None: raise HTTPException(status_code=404, detail="سازمان وجود ندارد")
    row = operational_models.CostCenter(tenant_id=user.tenant_id, organization_id=organization.id, name=data.name, code=data.code, budget_amount=data.budget_amount or 0)
    db.add(row); db.commit()
    return {"id": row.id, "name": row.name, "code": row.code, "budget_amount": row.budget_amount}


@app.post("/organizations/{organization_id}/approval-templates", status_code=status.HTTP_201_CREATED)
def create_approval_template(organization_id: str, data: ApprovalTemplateIn, user: User = Depends(require_permission("member:manage")), db: Session = Depends(get_db)) -> dict:
    organization = db.scalar(select(operational_models.Organization).where(operational_models.Organization.id == organization_id, operational_models.Organization.tenant_id == user.tenant_id))
    if organization is None: raise HTTPException(status_code=404, detail="سازمان وجود ندارد")
    template = operational_models.ApprovalTemplate(tenant_id=user.tenant_id, organization_id=organization.id, name=data.name, version=data.version)
    db.add(template); db.flush()
    for order, item in enumerate(data.steps, 1):
        db.add(operational_models.ApprovalTemplateStep(tenant_id=user.tenant_id, template_id=template.id, step_order=order, required_role=item.required_role, sla_minutes=item.sla_minutes))
    db.commit()
    return {"id": template.id, "name": template.name, "version": template.version, "steps": len(data.steps)}


@app.get("/organization/overview")
def organization_overview(user: User = Depends(require_role("manager", "welfare_manager", "organization_admin", "finance_operator", "tenant_admin", "platform_admin")), db: Session = Depends(get_db)) -> dict:
    organizations = db.scalars(select(operational_models.Organization).where(operational_models.Organization.tenant_id == user.tenant_id).order_by(operational_models.Organization.name)).all()
    departments = db.scalars(select(operational_models.Department).where(operational_models.Department.tenant_id == user.tenant_id).order_by(operational_models.Department.name)).all()
    cost_centers = db.scalars(select(operational_models.CostCenter).where(operational_models.CostCenter.tenant_id == user.tenant_id).order_by(operational_models.CostCenter.name)).all()
    workflows = db.scalars(select(operational_models.ApprovalWorkflow).where(operational_models.ApprovalWorkflow.tenant_id == user.tenant_id).order_by(operational_models.ApprovalWorkflow.created_at.desc()).limit(50)).all()
    return {
        "tenant_id": user.tenant_id,
        "organizations": [{"id": row.id, "name": row.name, "status": row.status} for row in organizations],
        "departments": [{"id": row.id, "organization_id": row.organization_id, "name": row.name, "code": row.code} for row in departments],
        "cost_centers": [{"id": row.id, "organization_id": row.organization_id, "name": row.name, "code": row.code, "budget_amount": row.budget_amount} for row in cost_centers],
        "workflows": [{"id": row.id, "reservation_id": row.reservation_id, "status": row.status, "current_step": row.current_step_order, "escalation_count": row.escalation_count, "rejection_reason": row.rejection_reason, "created_at": row.created_at.isoformat()} for row in workflows],
    }


@app.post("/reservations/{reservation_id}/approval-workflows", status_code=status.HTTP_201_CREATED)
def start_approval_workflow(reservation_id: str, data: ApprovalStartIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id).with_for_update())
    if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "approval.start", operational_models.IdempotencyKey.key == data.command_id))
    if prior and prior.response_json: return json.loads(prior.response_json)
    template = db.scalar(select(operational_models.ApprovalTemplate).where(operational_models.ApprovalTemplate.id == data.template_id, operational_models.ApprovalTemplate.tenant_id == user.tenant_id, operational_models.ApprovalTemplate.status == "active"))
    if template is None: raise HTTPException(status_code=404, detail="الگوی تأیید وجود ندارد")
    steps = db.scalars(select(operational_models.ApprovalTemplateStep).where(operational_models.ApprovalTemplateStep.template_id == template.id, operational_models.ApprovalTemplateStep.tenant_id == user.tenant_id).order_by(operational_models.ApprovalTemplateStep.step_order)).all()
    if not steps: raise HTTPException(status_code=409, detail="الگوی تأیید مرحله ندارد")
    snapshot = [{"order": item.step_order, "role": item.required_role, "sla_minutes": item.sla_minutes} for item in steps]
    workflow = operational_models.ApprovalWorkflow(tenant_id=user.tenant_id, reservation_id=reservation.id, template_id=template.id, current_step_order=1, policy_snapshot_json=json.dumps({"template_id": template.id, "version": template.version, "steps": snapshot}, sort_keys=True))
    db.add(workflow); db.flush()
    now = datetime.now(timezone.utc)
    for item in steps:
        db.add(operational_models.ApprovalInstanceStep(tenant_id=user.tenant_id, workflow_id=workflow.id, step_order=item.step_order, required_role=item.required_role, status="pending" if item.step_order == 1 else "waiting", sla_due_at=now + timedelta(minutes=item.sla_minutes)))
    response = {"id": workflow.id, "status": workflow.status, "current_step_order": 1, "steps": snapshot}
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="approval.start", key=data.command_id, request_hash=_secure_hash(f"{reservation.id}:{template.id}"), response_json=json.dumps(response)))
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="approval", aggregate_id=workflow.id, event_type="approval.started", payload_json=json.dumps({"workflow_id": workflow.id, "reservation_id": reservation.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id))
    db.commit(); return response


@app.post("/approvals/{approval_id}/escalate")
def escalate_approval(approval_id: str, data: EscalationIn, user: User = Depends(require_permission("member:manage")), db: Session = Depends(get_db)) -> dict:
    workflow = db.scalar(select(operational_models.ApprovalWorkflow).where(operational_models.ApprovalWorkflow.id == approval_id, operational_models.ApprovalWorkflow.tenant_id == user.tenant_id).with_for_update())
    if workflow is None or workflow.status != "pending": raise HTTPException(status_code=404, detail="گردش فعال وجود ندارد")
    step = db.scalar(select(operational_models.ApprovalInstanceStep).where(operational_models.ApprovalInstanceStep.workflow_id == workflow.id, operational_models.ApprovalInstanceStep.tenant_id == user.tenant_id, operational_models.ApprovalInstanceStep.step_order == workflow.current_step_order).with_for_update())
    if step is None: raise HTTPException(status_code=409, detail="مرحله فعال وجود ندارد")
    step.escalation_count += 1; workflow.escalation_count += 1
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="approval", aggregate_id=workflow.id, event_type="approval.escalated", payload_json=json.dumps({"step_order": step.step_order, "reason": data.reason}), correlation_id=str(uuid.uuid4()), idempotency_key=f"escalation:{workflow.id}:{workflow.escalation_count}"))
    db.commit(); return {"id": workflow.id, "step_order": step.step_order, "escalation_count": workflow.escalation_count}


@app.put("/tenant/white-label")
def upsert_white_label(data: WhiteLabelIn, user: User = Depends(require_permission("tenant:manage")), db: Session = Depends(get_db)) -> dict:
    if data.logo_reference and not data.logo_reference.startswith(("asset://", "s3://", "https://")):
        raise HTTPException(status_code=422, detail="logo reference معتبر نیست")
    domain = data.custom_domain.lower().strip().rstrip(".") if data.custom_domain else None
    if domain and ("/" in domain or ":" in domain or domain.startswith(".")):
        raise HTTPException(status_code=422, detail="دامنه معتبر نیست")
    if data.organization_id:
        organization = db.scalar(select(operational_models.Organization).where(operational_models.Organization.id == data.organization_id, operational_models.Organization.tenant_id == user.tenant_id))
        if organization is None: raise HTTPException(status_code=404, detail="سازمان وجود ندارد")
    row = db.scalar(select(operational_models.WhiteLabelConfiguration).where(operational_models.WhiteLabelConfiguration.tenant_id == user.tenant_id).with_for_update())
    if row is None:
        row = operational_models.WhiteLabelConfiguration(tenant_id=user.tenant_id, display_name=data.display_name)
        db.add(row)
    domain_changed = row.custom_domain != domain
    row.organization_id = data.organization_id; row.display_name = data.display_name; row.logo_reference = data.logo_reference; row.primary_color = data.primary_color.upper(); row.secondary_color = data.secondary_color.upper(); row.custom_domain = domain
    if domain_changed: row.domain_status = "unverified"
    row.support_json = json.dumps(data.support, sort_keys=True); row.enabled_services_json = json.dumps(sorted(set(data.enabled_services))); row.organization_policy_json = json.dumps(data.organization_policy, sort_keys=True); row.feature_flags_json = json.dumps(data.feature_flags, sort_keys=True)
    db.commit()
    return {"display_name": row.display_name, "logo_reference": row.logo_reference, "primary_color": row.primary_color, "secondary_color": row.secondary_color, "custom_domain": row.custom_domain, "domain_status": row.domain_status, "support": json.loads(row.support_json), "enabled_services": json.loads(row.enabled_services_json), "organization_policy": json.loads(row.organization_policy_json), "feature_flags": json.loads(row.feature_flags_json)}


@app.get("/tenant/white-label")
def get_white_label(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.WhiteLabelConfiguration).where(operational_models.WhiteLabelConfiguration.tenant_id == user.tenant_id))
    if row is None: raise HTTPException(status_code=404, detail="تنظیمات White Label وجود ندارد")
    return {"display_name": row.display_name, "logo_reference": row.logo_reference, "primary_color": row.primary_color, "secondary_color": row.secondary_color, "custom_domain": row.custom_domain, "domain_status": row.domain_status, "support": json.loads(row.support_json), "enabled_services": json.loads(row.enabled_services_json), "organization_policy": json.loads(row.organization_policy_json), "feature_flags": json.loads(row.feature_flags_json)}


@app.post("/compare/offers")
def compare_offers(data: CompareIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if len(set(data.offer_ids)) != len(data.offer_ids): raise HTTPException(status_code=422, detail="Offer تکراری قابل مقایسه نیست")
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(operational_models.Offer).where(operational_models.Offer.tenant_id == user.tenant_id, operational_models.Offer.id.in_(data.offer_ids), operational_models.Offer.status == "active", operational_models.Offer.valid_until > now)).all()
    if len(rows) != len(data.offer_ids): raise HTTPException(status_code=404, detail="یک یا چند Offer معتبر وجود ندارد")
    if len({row.service_type for row in rows}) != 1: raise HTTPException(status_code=409, detail="فقط Offerهای هم‌نوع قابل مقایسه‌اند")
    minimum = min(row.amount for row in rows)
    results = []
    for row in rows:
        attrs = json.loads(row.attributes_json); policy = json.loads(row.policy_json); cancellation = policy.get("cancellation", {})
        price_score = round(35 * minimum / row.amount, 2)
        quality_score = round(20 * min(max(float(attrs.get("rating", attrs.get("quality", 0))), 0), 5) / 5, 2)
        cancellation_score = 15.0 if cancellation.get("refundable") is True else 0.0
        location_score = round(10 * min(max(float(attrs.get("location_score", 0)), 0), 10) / 10, 2)
        amenities_score = min(len(attrs.get("amenities", [])) * 2, 10)
        policy_score = 10.0 if attrs.get("organization_policy_compliant") is True else 0.0
        breakdown = {"price": price_score, "quality": quality_score, "cancellation": cancellation_score, "location": location_score, "amenities": amenities_score, "organization_policy": policy_score}
        results.append({"offer_id": row.id, "service_type": row.service_type, "title": row.title, "amount": row.amount, "currency": row.currency, "score": round(sum(breakdown.values()), 2), "breakdown": breakdown, "explanation": [key for key, value in breakdown.items() if value > 0], "valid_until": row.valid_until.isoformat()})
    results.sort(key=lambda item: (-item["score"], item["amount"]))
    return {"service_type": rows[0].service_type, "authoritative": True, "results": results}


@app.get("/ai/grounded-context")
def ai_grounded_context(reservation_id: Optional[str] = None, trip_id: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    context: dict = {"generated_transactional_data": False, "tenant_id": user.tenant_id, "booking": None, "trip": None, "providers": []}
    if reservation_id:
        reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id))
        if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
        context["booking"] = {**_reservation_output(reservation), "authoritative": True, "refund_quote": _verified_cancellation_quote(reservation)}
    if trip_id:
        trip = db.scalar(select(operational_models.Trip).where(operational_models.Trip.id == trip_id, operational_models.Trip.tenant_id == user.tenant_id, operational_models.Trip.user_id == user.id))
        if trip is None: raise HTTPException(status_code=404, detail="سفر در این حساب وجود ندارد")
        events = db.scalars(select(operational_models.TripEventRecord).where(operational_models.TripEventRecord.tenant_id == user.tenant_id, operational_models.TripEventRecord.trip_id == trip.id, operational_models.TripEventRecord.visibility == "customer").order_by(operational_models.TripEventRecord.created_at.desc()).limit(50)).all()
        context["trip"] = {"id": trip.id, "status": trip.status, "destination": trip.destination, "authoritative": True, "events": [{"type": event.event_type, "source": event.source, "title": event.title, "message": event.message, "at": event.created_at.isoformat()} for event in events]}
    from .providers import ADAPTERS
    for key, adapter in ADAPTERS.items():
        try: health = adapter.health(); context["providers"].append({"key": key, "status": health.status, "mode": health.mode})
        except Exception: context["providers"].append({"key": key, "status": "configuration_error", "mode": getattr(adapter, "mode", "unknown")})
    return context


@app.put("/me/notification-preferences")
def upsert_notification_preference(data: NotificationPreferenceIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.NotificationPreference).where(operational_models.NotificationPreference.tenant_id == user.tenant_id, operational_models.NotificationPreference.user_id == user.id, operational_models.NotificationPreference.topic == data.topic, operational_models.NotificationPreference.channel == data.channel).with_for_update())
    if row is None:
        row = operational_models.NotificationPreference(tenant_id=user.tenant_id, user_id=user.id, topic=data.topic, channel=data.channel, enabled=data.enabled); db.add(row)
    else: row.enabled = data.enabled
    db.commit(); return {"topic": row.topic, "channel": row.channel, "enabled": row.enabled}


@app.get("/me/notification-preferences")
def notification_preferences(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.NotificationPreference).where(operational_models.NotificationPreference.tenant_id == user.tenant_id, operational_models.NotificationPreference.user_id == user.id).order_by(operational_models.NotificationPreference.topic, operational_models.NotificationPreference.channel)).all()
    return [{"topic": row.topic, "channel": row.channel, "enabled": row.enabled} for row in rows]


@app.post("/notification-receipts/{channel}")
async def notification_receipt(channel: str, request: Request, x_notification_signature: str = Header(alias="X-Notification-Signature"), db: Session = Depends(get_db)) -> dict:
    if channel not in {"push", "sms", "app", "web"} or not NOTIFICATION_WEBHOOK_SECRET: raise HTTPException(status_code=503, detail="اعتبارسنجی receipt پیکربندی نشده است")
    raw = await request.body(); expected = hmac.new(NOTIFICATION_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_notification_signature): raise HTTPException(status_code=401, detail="امضای receipt نامعتبر است")
    try:
        payload = json.loads(raw); tenant_id = int(payload["tenant_id"]); attempt_id = str(payload["attempt_id"]); receipt_id = str(payload["receipt_event_id"]); delivery_status = str(payload["status"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError): raise HTTPException(status_code=422, detail="receipt نامعتبر است")
    if delivery_status not in {"delivered", "failed"}: raise HTTPException(status_code=422, detail="وضعیت receipt نامعتبر است")
    set_tenant_context(db, tenant_id)
    duplicate = db.scalar(select(operational_models.NotificationDeliveryAttempt).where(operational_models.NotificationDeliveryAttempt.receipt_event_id == receipt_id))
    if duplicate: return {"status": "duplicate", "delivery_status": duplicate.status}
    attempt = db.scalar(select(operational_models.NotificationDeliveryAttempt).where(operational_models.NotificationDeliveryAttempt.id == attempt_id, operational_models.NotificationDeliveryAttempt.tenant_id == tenant_id).with_for_update())
    if attempt is None: raise HTTPException(status_code=404, detail="delivery attempt وجود ندارد")
    expected_channel = "in_app" if channel in {"app", "web"} else channel
    if attempt.channel != expected_channel: raise HTTPException(status_code=409, detail="channel receipt تطابق ندارد")
    attempt.status = delivery_status; attempt.receipt_event_id = receipt_id; attempt.provider_message_id = str(payload.get("provider_message_id", ""))[:160] or None; attempt.delivered_at = datetime.now(timezone.utc) if delivery_status == "delivered" else None
    db.commit(); return {"status": "accepted", "delivery_status": attempt.status}


@app.post("/agency/sub-agencies", status_code=status.HTTP_201_CREATED)
def create_sub_agency(data: AgencyIn, user: User = Depends(require_permission("agency:manage")), db: Session = Depends(get_db)) -> dict:
    if data.parent_agency_id:
        parent = db.scalar(select(operational_models.Agency).where(operational_models.Agency.id == data.parent_agency_id, operational_models.Agency.tenant_id == user.tenant_id))
        if parent is None: raise HTTPException(status_code=404, detail="آژانس مادر وجود ندارد")
    row = operational_models.Agency(tenant_id=user.tenant_id, display_name=data.display_name, status="active", parent_agency_id=data.parent_agency_id, markup_bps=data.markup_bps, commission_bps=data.commission_bps)
    db.add(row); db.commit(); return {"id": row.id, "display_name": row.display_name, "parent_agency_id": row.parent_agency_id, "markup_bps": row.markup_bps, "commission_bps": row.commission_bps}


@app.get("/supplier/dashboard")
def supplier_dashboard(user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    suppliers = db.scalars(select(operational_models.Supplier).where(operational_models.Supplier.tenant_id == user.tenant_id)).all(); supplier_ids = {item.id for item in suppliers}
    offers = db.scalars(select(operational_models.Offer).where(operational_models.Offer.tenant_id == user.tenant_id, operational_models.Offer.supplier_id.in_(supplier_ids))).all() if supplier_ids else []
    settlements = db.scalars(select(operational_models.SettlementRecord).where(operational_models.SettlementRecord.tenant_id == user.tenant_id, operational_models.SettlementRecord.supplier_id.in_(supplier_ids))).all() if supplier_ids else []
    return {"suppliers": len(suppliers), "offers": len(offers), "available_units": sum(item.available_units for item in offers), "settlements": {"count": len(settlements), "amount": sum(item.amount for item in settlements)}, "supplier_records": [{"id": row.id, "name": row.display_name, "type": row.supplier_type, "status": row.status} for row in suppliers], "offer_records": [{"id": row.id, "supplier_id": row.supplier_id, "title": row.title, "service_type": row.service_type, "amount": row.amount, "currency": row.currency, "available_units": row.available_units, "status": row.status} for row in offers]}


@app.put("/supplier/offers/{offer_id}")
def update_supplier_offer(offer_id: str, data: SupplierOfferUpdateIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == offer_id, operational_models.Offer.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="Offer در این تأمین‌کننده وجود ندارد")
    supplier = db.scalar(select(operational_models.Supplier.id).where(operational_models.Supplier.id == row.supplier_id, operational_models.Supplier.tenant_id == user.tenant_id))
    if supplier is None: raise HTTPException(status_code=404, detail="Offer در این تأمین‌کننده وجود ندارد")
    if data.amount is not None: row.amount = data.amount
    if data.available_units is not None: row.available_units = data.available_units
    if data.status is not None: row.status = data.status
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="offer", aggregate_id=row.id, event_type="supplier.offer.updated", payload_json=json.dumps(data.model_dump(exclude_none=True), sort_keys=True), correlation_id=str(uuid.uuid4()), idempotency_key=f"offer-update:{row.id}:{uuid.uuid4()}")); db.commit()
    return {"id": row.id, "amount": row.amount, "available_units": row.available_units, "status": row.status}


@app.get("/agency/dashboard")
def agency_dashboard(user: User = Depends(require_permission("agency:manage")), db: Session = Depends(get_db)) -> dict:
    agencies = db.scalars(select(operational_models.Agency).where(operational_models.Agency.tenant_id == user.tenant_id).order_by(operational_models.Agency.created_at.desc())).all()
    return {"agencies": [{"id": row.id, "name": row.display_name, "parent_agency_id": row.parent_agency_id, "markup_bps": row.markup_bps, "commission_bps": row.commission_bps} for row in agencies]}


@app.put("/agency/agencies/{agency_id}")
def update_agency(agency_id: str, data: AgencyUpdateIn, user: User = Depends(require_permission("agency:manage")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Agency).where(operational_models.Agency.id == agency_id, operational_models.Agency.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="آژانس در این tenant وجود ندارد")
    if data.display_name is not None: row.display_name = data.display_name.strip()
    if data.markup_bps is not None: row.markup_bps = data.markup_bps
    if data.commission_bps is not None: row.commission_bps = data.commission_bps
    if data.status is not None: row.status = data.status
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="agency", aggregate_id=row.id, event_type="agency.updated", payload_json=json.dumps(data.model_dump(exclude_none=True), sort_keys=True), correlation_id=str(uuid.uuid4()), idempotency_key=f"agency-update:{row.id}:{uuid.uuid4()}")); db.commit()
    return {"id": row.id, "name": row.display_name, "status": row.status, "markup_bps": row.markup_bps, "commission_bps": row.commission_bps}


@app.get("/backoffice/overview")
def backoffice_overview(user: User = Depends(require_permission("backoffice:read")), db: Session = Depends(get_db)) -> dict:
    def count(model): return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == user.tenant_id)) or 0
    from .providers import ADAPTERS
    provider_health = []
    for key, adapter in ADAPTERS.items():
        try: health = adapter.health(); provider_health.append({"key": key, "status": health.status, "mode": health.mode})
        except Exception: provider_health.append({"key": key, "status": "configuration_error", "mode": getattr(adapter, "mode", "unknown")})
    suppliers = db.scalars(select(operational_models.Supplier).where(operational_models.Supplier.tenant_id == user.tenant_id).order_by(operational_models.Supplier.created_at.desc()).limit(50)).all()
    return {"tenant_id": user.tenant_id, "counts": {"users": count(User), "suppliers": count(operational_models.Supplier), "agencies": count(operational_models.Agency), "reservations": count(operational_models.Reservation), "payments": count(operational_models.PaymentIntent), "refunds": count(operational_models.RefundRecord), "wallets": count(operational_models.Wallet), "notifications": count(operational_models.NotificationRecord), "security_events": count(operational_models.AuthenticationAudit)}, "providers": provider_health, "suppliers": [{"id": row.id, "name": row.display_name, "type": row.supplier_type, "status": row.status} for row in suppliers]}


@app.put("/backoffice/suppliers/{supplier_id}/status")
def backoffice_supplier_status(supplier_id: str, data: SupplierStatusIn, user: User = Depends(require_permission("backoffice:read")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Supplier).where(operational_models.Supplier.id == supplier_id, operational_models.Supplier.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="تأمین‌کننده در این tenant وجود ندارد")
    previous = row.status; row.status = data.status
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="supplier", aggregate_id=row.id, event_type="backoffice.supplier_status.changed", payload_json=json.dumps({"from": previous, "to": row.status, "reason": data.reason, "actor_id": user.id}, sort_keys=True), correlation_id=str(uuid.uuid4()), idempotency_key=f"supplier-status:{row.id}:{uuid.uuid4()}")); db.commit()
    return {"id": row.id, "name": row.display_name, "status": row.status}


@app.get("/finance/reconciliation")
def finance_reconciliation(user: User = Depends(require_permission("ledger:read")), db: Session = Depends(get_db)) -> dict:
    payments = db.scalars(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.tenant_id == user.tenant_id).order_by(operational_models.PaymentIntent.created_at)).all()
    refunds = db.scalars(select(operational_models.RefundRecord).where(operational_models.RefundRecord.tenant_id == user.tenant_id)).all()
    settlements = db.scalars(select(operational_models.SettlementRecord).where(operational_models.SettlementRecord.tenant_id == user.tenant_id)).all()
    wallets = db.scalars(select(operational_models.Wallet).where(operational_models.Wallet.tenant_id == user.tenant_id)).all()
    refund_groups: dict[str, list[operational_models.RefundRecord]] = {}
    for refund in refunds:
        refund_groups.setdefault(refund.payment_intent_id, []).append(refund)
    payment_rows = []
    discrepancy_count = 0
    for payment in payments:
        related = refund_groups.get(payment.id, [])
        succeeded = sum(item.amount for item in related if item.status == "succeeded")
        pending = sum(item.amount for item in related if item.status == "requested")
        issues = []
        if succeeded != payment.refunded_amount:
            issues.append("refund_total_mismatch")
        if payment.captured_amount > 0 and not payment.provider_reference:
            issues.append("captured_without_provider_reference")
        if payment.refunded_amount > payment.captured_amount or pending + payment.refunded_amount > payment.captured_amount:
            issues.append("refund_exceeds_capture")
        discrepancy_count += len(issues)
        payment_rows.append({"payment_id": payment.id, "reservation_id": payment.reservation_id, "status": payment.status, "currency": payment.currency, "intent_amount": payment.amount, "captured_amount": payment.captured_amount, "recorded_refunded_amount": payment.refunded_amount, "succeeded_refund_amount": succeeded, "pending_refund_amount": pending, "issues": issues})
    wallet_rows = []
    for wallet in wallets:
        balances = operational_models.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=wallet.id)
        wallet_rows.append({"wallet_id": wallet.id, "owner_type": wallet.owner_type, "currency": wallet.currency, **balances})
    return {
        "tenant_id": user.tenant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "payments": payment_rows,
        "wallets": wallet_rows,
        "settlements": {"count": len(settlements), "pending_amount": sum(item.amount for item in settlements if item.status == "pending"), "completed_amount": sum(item.amount for item in settlements if item.status == "completed")},
        "summary": {"payment_count": len(payments), "refund_count": len(refunds), "discrepancy_count": discrepancy_count, "status": "needs_review" if discrepancy_count else "balanced"},
    }
