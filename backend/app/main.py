from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import unicodedata
import uuid
from types import SimpleNamespace
from difflib import SequenceMatcher
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Generator, Optional
from urllib.parse import urlparse

import jwt
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func, select, text, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .config import read_secret
from .database import Base, DATABASE_URL, SessionLocal, engine, set_tenant_context
from . import operations as operational_models  # register additive operational tables
from .observability import configure_logging, prometheus_metrics, record_business_event, record_request
from .rate_limit import InMemoryRateLimiter, RedisRateLimiter, fingerprint
from .security import role_has_permission
from .providers import configured_adapter, validate_provider_modes
from .version import read_build_info

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
ECOSYSTEM_SERVICE_PATTERN = "^(flight|hotel|train|tour|package|accommodation|vacation_rental|cruise|visa|car_rental|restaurant|event_hall|pool_sport|attraction|travel_guide|handicraft|tourist_transportation)$"

class SupplierOfferIn(BaseModel):
    supplier_id: str = Field(min_length=36, max_length=36)
    service_type: str = Field(pattern=ECOSYSTEM_SERVICE_PATTERN)
    title: str = Field(min_length=3, max_length=200)
    amount: int = Field(gt=0)
    available_units: int = Field(ge=1, le=100000)
    valid_minutes: int = Field(ge=1, le=43200)
    policy: dict
    attributes: dict = Field(default_factory=dict)
    fulfillment_mode: str = Field(pattern="^(manual_supplier|provider)$")
    provider_key: str = Field(default="manual_supplier", min_length=2, max_length=64)
class SupplierOnboardingIn(BaseModel):
    supplier_type: str = Field(pattern="^(flight|hotel|train|tour|package|accommodation|vacation_rental|cruise|visa|car_rental|restaurant|event_hall|pool_sport|attraction|travel_guide|handicraft|tourist_transportation|multi_service)$")
    display_name: str = Field(min_length=2, max_length=180)
class OfferSearchIn(BaseModel):
    service_type: str = Field(pattern=ECOSYSTEM_SERVICE_PATTERN)
    query: Optional[str] = Field(default=None, max_length=200)
    min_price: Optional[int] = Field(default=None, ge=0)
    max_price: Optional[int] = Field(default=None, ge=0)
    min_review_score: Optional[float] = Field(default=None, ge=0, le=10)
    refundable: Optional[bool] = None
    amenities: list[str] = Field(default_factory=list, max_length=20)
    instant_booking: Optional[bool] = None
    flexible_dates: bool = False
    map_bounds: Optional[dict[str, float]] = None
    sort: str = Field(default="recommended", pattern="^(recommended|price_asc|price_desc|review_desc|freshness)$")
    include_stale: bool = False
    check_in: Optional[str] = Field(default=None, max_length=10)
    check_out: Optional[str] = Field(default=None, max_length=10)
    travellers: int = Field(default=1, ge=1, le=20)
class UnifiedSearchIn(BaseModel):
    verticals: list[str] = Field(min_length=1, max_length=4)
    query: Optional[str] = Field(default=None, max_length=500)
    origin: Optional[str] = Field(default=None, max_length=120)
    destination: Optional[str] = Field(default=None, max_length=120)
    flexibility: str = Field(default="exact", pattern="^(exact|plus_minus_1|plus_minus_3|weekend|whole_month|flexible_month|nearby_dates)$")
    travellers: int = Field(default=1, ge=1, le=20)
    filters: dict = Field(default_factory=dict)
    sort: str = Field(default="recommended", pattern="^(recommended|lowest_price|best_value|highest_rated|best_location|most_flexible|cheapest|best|fastest)$")
    include_stale: bool = False
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=100)
LEISURE_SERVICE_TYPES_PATTERN = "^(restaurant|event_hall|pool_sport|attraction)$"
LEISURE_BOOKING_MODES_PATTERN = "^(DISCOVERY_ONLY|SESSION_BASED|TIMED_ENTRY|TABLE_RESERVATION|MEAL_VOUCHER|FIXED_PACKAGE|EVENT_TICKET|VENUE_INQUIRY)$"
LEISURE_TICKET_CODE_PATTERN = "^(adult|child|infant|vip|generic)$"

class PlaceIn(BaseModel):
    supplier_id: str = Field(min_length=36, max_length=36)
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]{3,180}$")
    place_type: str = Field(pattern=LEISURE_SERVICE_TYPES_PATTERN)
    category: Optional[str] = Field(default=None, max_length=64)
    city: str = Field(min_length=2, max_length=120)
    address: Optional[str] = Field(default=None, max_length=300)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    opening_hours: dict = Field(default_factory=dict)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    rules: dict = Field(default_factory=dict)
    media: list[str] = Field(default_factory=list, max_length=20)
class ExperienceProductIn(BaseModel):
    service_type: str = Field(pattern=LEISURE_SERVICE_TYPES_PATTERN)
    subtype: Optional[str] = Field(default=None, max_length=64)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=4000)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=10080)
    booking_mode: str = Field(pattern=LEISURE_BOOKING_MODES_PATTERN)
    cancellation_policy: dict = Field(default_factory=dict)
    restrictions: dict = Field(default_factory=dict)
class LeisureSessionIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    sales_start_at: Optional[datetime] = None
    sales_end_at: Optional[datetime] = None
    capacity_total: int = Field(ge=1, le=100000)
    restrictions: dict = Field(default_factory=dict)
class LeisureTicketTypeIn(BaseModel):
    code: str = Field(pattern=LEISURE_TICKET_CODE_PATTERN)
    label: str = Field(min_length=2, max_length=120)
    price: int = Field(gt=0)
    currency: str = Field(default="IRR", min_length=3, max_length=3)
    quota: Optional[int] = Field(default=None, ge=1)
    min_age: Optional[int] = Field(default=None, ge=0, le=120)
    max_age: Optional[int] = Field(default=None, ge=0, le=120)
    restrictions: dict = Field(default_factory=dict)
    active: bool = True
class LeisureTicketSelectionIn(BaseModel):
    ticket_type_id: str = Field(min_length=36, max_length=36)
    quantity: int = Field(ge=1, le=50)
class LeisureSessionPriceCheckIn(BaseModel):
    selections: list[LeisureTicketSelectionIn] = Field(min_length=1, max_length=10)
    command_id: str = Field(min_length=8, max_length=120)
    organization_id: Optional[str] = Field(default=None, min_length=36, max_length=36)
class AdmissionTicketRedeemIn(BaseModel):
    qr_token: str = Field(min_length=16, max_length=64)
class SavedSearchIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    query: dict
    command_id: str = Field(min_length=8, max_length=120)
    alert_type: Optional[str] = Field(default=None, pattern="^(price|availability|fare_drop)$")
class BudgetTripIn(BaseModel):
    origin: str = Field(min_length=2, max_length=120)
    destination: Optional[str] = Field(default=None, max_length=120)
    travellers: int = Field(default=1, ge=1, le=20)
    budget: int = Field(gt=0)
    interests: list[str] = Field(default_factory=list, max_length=20)
class VacationPropertyIn(BaseModel):
    supplier_id: str = Field(min_length=36, max_length=36); title: str = Field(min_length=3, max_length=200); slug: str = Field(pattern=r"^[a-z0-9-]{3,180}$"); city: str = Field(min_length=2, max_length=120); property_type: str = Field(pattern="^(villa|suite|furnished_apartment|cabin|ecolodge|rural|coastal|forest|mountain)$"); capacity: int = Field(ge=1, le=100); bedrooms: int = Field(ge=0, le=50); details: dict = Field(default_factory=dict)
class VacationUnitIn(BaseModel):
    title: str = Field(min_length=2, max_length=160); capacity: int = Field(ge=1, le=100); available_units: int = Field(ge=1, le=100); nightly_price: int = Field(gt=0); pricing: dict = Field(default_factory=dict)
class VacationBookIn(BaseModel):
    check_in: datetime; check_out: datetime; guests: int = Field(ge=1, le=100); command_id: str = Field(min_length=8, max_length=120)
class TourProductIn(BaseModel):
    supplier_id: str = Field(min_length=36, max_length=36); title: str = Field(min_length=3, max_length=200); slug: str = Field(pattern=r"^[a-z0-9-]{3,180}$"); origin: str = Field(min_length=2, max_length=120); destination: str = Field(min_length=2, max_length=120); tour_type: str = Field(min_length=2, max_length=48); details: dict = Field(default_factory=dict)
class TourDepartureIn(BaseModel):
    starts_at: datetime; ends_at: datetime; booking_deadline: datetime; capacity: int = Field(ge=1, le=10000); base_price: int = Field(gt=0); pricing: dict = Field(default_factory=dict)
class TourBookIn(BaseModel):
    travellers: int = Field(ge=1, le=100); room_type: str = Field(default="double", pattern="^(single|double|triple|extra_bed)$"); command_id: str = Field(min_length=8, max_length=120)
class CruiseSailingIn(BaseModel):
    supplier_id: Optional[str] = Field(default=None, min_length=36, max_length=36); title: str = Field(min_length=3, max_length=200); cruise_line: str = Field(min_length=2, max_length=160); ship: str = Field(min_length=2, max_length=160); departure_port: str = Field(min_length=2, max_length=160); arrival_port: str = Field(min_length=2, max_length=160); starts_at: datetime; nights: int = Field(ge=1, le=365); details: dict = Field(default_factory=dict)
class VisaProductIn(BaseModel):
    destination_country: str = Field(min_length=2, max_length=120); visa_type: str = Field(min_length=2, max_length=64); title: str = Field(min_length=3, max_length=200); source_url: str = Field(pattern=r"^https://"); source_verified_at: datetime; details: dict = Field(default_factory=dict)
class VisaApplicationIn(BaseModel):
    purpose: str = Field(min_length=2, max_length=80); travel_at: datetime; trip_id: Optional[str] = Field(default=None, min_length=36, max_length=36); command_id: str = Field(min_length=8, max_length=120)
    tour_reservation_id: Optional[str] = Field(default=None, min_length=36, max_length=36)
class VisaApplicantIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=160); passport_country: str = Field(min_length=2, max_length=120); passport_reference: str = Field(min_length=6, max_length=160)
class VisaDocumentIn(BaseModel):
    document_type: str = Field(min_length=2, max_length=64); storage_reference: str = Field(min_length=6, max_length=240)
class VisaDocumentReviewIn(BaseModel):
    status: str = Field(pattern="^(accepted|rejected|needs_replacement)$"); review_note: Optional[str] = Field(default=None, max_length=500)
class PriceCheckIn(BaseModel):
    units: int = Field(ge=1, le=20)
    command_id: str = Field(min_length=8, max_length=120)
    expected_final_price: Optional[int] = Field(default=None, gt=0)
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
class CreditAccountCreateIn(BaseModel): organization_id: str = Field(min_length=36, max_length=36); limit_amount: int = Field(gt=0); currency: str = Field(default="IRR", pattern="^IRR$"); command_id: str = Field(min_length=8, max_length=120)
class SupplierOfferUpdateIn(BaseModel): amount: Optional[int] = Field(default=None, gt=0); available_units: Optional[int] = Field(default=None, ge=0, le=100000); status: Optional[str] = Field(default=None, pattern="^(active|paused)$")
class AgencyUpdateIn(BaseModel): display_name: Optional[str] = Field(default=None, min_length=2, max_length=180); markup_bps: Optional[int] = Field(default=None, ge=0, le=10000); commission_bps: Optional[int] = Field(default=None, ge=0, le=10000); status: Optional[str] = Field(default=None, pattern="^(active|suspended)$")
class SupplierStatusIn(BaseModel): status: str = Field(pattern="^(active|suspended)$"); reason: str = Field(min_length=3, max_length=500)
class SupportMessageIn(BaseModel): reservation_id: Optional[str] = Field(default=None, min_length=36, max_length=36); trip_id: Optional[str] = Field(default=None, min_length=36, max_length=36); body: str = Field(min_length=3, max_length=4000)
class SupportCaseIn(BaseModel): reservation_id: Optional[str] = Field(default=None, min_length=36, max_length=36); trip_id: Optional[str] = Field(default=None, min_length=36, max_length=36); subject: str = Field(min_length=3, max_length=200); body: str = Field(min_length=3, max_length=4000); priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
class SupportReplyIn(BaseModel): body: str = Field(min_length=3, max_length=4000)
class SupportAssignmentIn(BaseModel): assigned_to_user_id: Optional[int] = Field(default=None, gt=0); status: str = Field(pattern="^(open|in_progress|resolved|closed)$")
class InstallmentDecisionIn(BaseModel): decision: str = Field(pattern="^(activate|reject)$"); reason: Optional[str] = Field(default=None, max_length=500)
class AdminRoleIn(BaseModel): role: str = Field(pattern="^(employee|customer|manager|welfare_manager|organization_admin|agency_partner|supplier|backoffice_expert|finance_operator|tenant_admin)$"); reason: str = Field(min_length=3, max_length=500)
class SavedTripIn(BaseModel): title: str = Field(min_length=2, max_length=160); command_id: str = Field(min_length=8, max_length=120)
class SavedItemIn(BaseModel): service_type: str = Field(pattern=ECOSYSTEM_SERVICE_PATTERN); source_reference: str = Field(min_length=2, max_length=200); offer_id: Optional[str] = Field(default=None, min_length=36, max_length=36); state: str = Field(default="wishlist", pattern="^(wishlist|basket)$"); command_id: str = Field(min_length=8, max_length=120)
class SavedItemMoveIn(BaseModel): state: str = Field(pattern="^(wishlist|basket)$"); command_id: str = Field(min_length=8, max_length=120)
class CommandIn(BaseModel): command_id: str = Field(min_length=8, max_length=120)
class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int = Field(ge=1, le=5); title: str = Field(min_length=2, max_length=160); body: str = Field(min_length=10, max_length=5000); service_type: str = Field(pattern=ECOSYSTEM_SERVICE_PATTERN); service_reference: str = Field(min_length=2, max_length=200); provider_reference: Optional[str] = Field(default=None, max_length=160); reservation_id: Optional[str] = Field(default=None, min_length=36, max_length=36); command_id: str = Field(min_length=8, max_length=120)
class ReviewModerationIn(BaseModel): state: str = Field(pattern="^(approved|rejected|flagged)$"); reason: str = Field(min_length=3, max_length=500)
class ReviewResponseIn(BaseModel): supplier_id: str = Field(min_length=36, max_length=36); body: str = Field(min_length=3, max_length=2000); command_id: str = Field(min_length=8, max_length=120)
class ReviewReportIn(BaseModel): reason: str = Field(pattern="^(spam|fraud|abuse|privacy|irrelevant|other)$"); detail: Optional[str] = Field(default=None, max_length=500); command_id: str = Field(min_length=8, max_length=120)
class DestinationIn(BaseModel): parent_id: Optional[str] = Field(default=None, min_length=36, max_length=36); kind: str = Field(pattern="^(country|province|city|district|poi)$"); name_fa: str = Field(min_length=2, max_length=160); name_en: Optional[str] = Field(default=None, max_length=160); slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160); latitude: Optional[float] = Field(default=None, ge=-90, le=90); longitude: Optional[float] = Field(default=None, ge=-180, le=180); description: str = Field(default="", max_length=5000); seasonality: list[str] = Field(default_factory=list, max_length=12); categories: list[str] = Field(default_factory=list, max_length=30); highlights: list[str] = Field(default_factory=list, max_length=30); nearby_slugs: list[str] = Field(default_factory=list, max_length=30)
class ItineraryIn(BaseModel): title: str = Field(min_length=2, max_length=160); destination_id: Optional[str] = Field(default=None, min_length=36, max_length=36); budget_amount: Optional[int] = Field(default=None, ge=0); command_id: str = Field(min_length=8, max_length=120)
class ItineraryItemIn(BaseModel): offer_id: Optional[str] = Field(default=None, min_length=36, max_length=36); service_type: str = Field(pattern=ECOSYSTEM_SERVICE_PATTERN); title: str = Field(min_length=2, max_length=200); day_number: int = Field(ge=1, le=365); position: int = Field(ge=1, le=100); command_id: str = Field(min_length=8, max_length=120)
class ItineraryItemUpdateIn(BaseModel): day_number: int = Field(ge=1, le=365); position: int = Field(ge=1, le=100); replacement_offer_id: Optional[str] = Field(default=None, min_length=36, max_length=36); command_id: str = Field(min_length=8, max_length=120)
class ItineraryUpdateIn(BaseModel): title: str = Field(min_length=2, max_length=160); budget_amount: Optional[int] = Field(default=None, ge=0); status: str = Field(default="draft", pattern="^(draft|saved|archived)$"); command_id: str = Field(min_length=8, max_length=120)
class CheckoutCreateIn(BaseModel): command_id: str = Field(min_length=8, max_length=120)
class CheckoutStepIn(BaseModel): command_id: str = Field(min_length=8, max_length=120); traveller_ids: list[str] = Field(default_factory=list, max_length=20); acknowledged: Optional[bool] = None; wallet_amount: int = Field(default=0, ge=0); credit_amount: int = Field(default=0, ge=0)
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


def _record_payment_trip_event(db: Session, *, tenant_id: int, intent: "operational_models.PaymentIntent", event_key: str, event_type: str, title: str, message: str, severity: str = "info") -> None:
    """Payment status changes are real operational events too; the Trip Timeline
    was previously silent about them even though bookings/cancellations already
    appear there. Guarded on reservation.trip_id exactly like transition_reservation."""
    reservation = db.get(operational_models.Reservation, intent.reservation_id)
    if reservation is None or not reservation.trip_id:
        return
    operational_models.record_trip_event(db, tenant_id=tenant_id, trip_id=reservation.trip_id, reservation_id=reservation.id, event_key=event_key, event_type=event_type, source="system", title=title, message=message, severity=severity, deep_link=f"/manage-booking/{reservation.id}")


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


def _villa_stay_pricing(unit: "operational_models.VacationUnit", check_in: datetime, check_out: datetime) -> dict:
    """Deterministic seasonal/weekend/min-stay pricing for a vacation-rental
    stay. `unit.pricing_json` optionally carries: `min_stay` (int nights),
    `weekend_days` (list of Python weekday ints, Mon=0..Sun=6; default
    Thursday/Friday [3,4]), `weekend_price` (int, overrides base on weekend
    nights) and `seasonal_rates` (list of {start:"MM-DD", end:"MM-DD",
    nightly_price:int}, checked before the weekend rate and wrapping the
    year boundary when start > end). Falls back to `unit.nightly_price` for
    every night when no pricing config is set, matching prior flat pricing.
    """
    try:
        pricing = json.loads(unit.pricing_json or "{}")
        if not isinstance(pricing, dict):
            pricing = {}
    except json.JSONDecodeError:
        pricing = {}
    nights = (check_out.date() - check_in.date()).days
    min_stay = int(pricing.get("min_stay") or 1)
    if min_stay < 1:
        min_stay = 1
    if nights < min_stay:
        raise HTTPException(status_code=422, detail=f"حداقل تعداد شب اقامت برای این واحد {min_stay} شب است")
    weekend_days = pricing.get("weekend_days") if isinstance(pricing.get("weekend_days"), list) else [3, 4]
    weekend_days = {int(day) for day in weekend_days if isinstance(day, int) and 0 <= day <= 6}
    weekend_price = pricing.get("weekend_price")
    weekend_price = int(weekend_price) if isinstance(weekend_price, int) and weekend_price > 0 else None
    seasonal_rates = pricing.get("seasonal_rates") if isinstance(pricing.get("seasonal_rates"), list) else []
    breakdown: list[dict] = []
    total = 0
    current = check_in.date()
    for _ in range(nights):
        nightly, source = unit.nightly_price, "base"
        month_day = current.strftime("%m-%d")
        for season in seasonal_rates:
            if not isinstance(season, dict):
                continue
            start, end, rate = season.get("start"), season.get("end"), season.get("nightly_price")
            if not (isinstance(start, str) and isinstance(end, str) and isinstance(rate, int) and rate > 0):
                continue
            in_season = (start <= month_day <= end) if start <= end else (month_day >= start or month_day <= end)
            if in_season:
                nightly, source = rate, "seasonal"
                break
        if source == "base" and weekend_price is not None and current.weekday() in weekend_days:
            nightly, source = weekend_price, "weekend"
        breakdown.append({"date": current.isoformat(), "nightly_price": nightly, "rate_source": source})
        total += nightly
        current += timedelta(days=1)
    return {"total_amount": total, "nights": nights, "min_stay": min_stay, "currency": unit.currency, "nightly_breakdown": breakdown}


def validate_production_config() -> None:
    origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
    if ENVIRONMENT == "production":
        if JWT_SECRET == "development-only-change-before-production" or JWT_SECRET.startswith("replace-with-") or len(JWT_SECRET) < 32:
            raise RuntimeError("JWT_SECRET must be a non-default value of at least 32 characters")
        if not DATABASE_URL.startswith("postgresql"):
            raise RuntimeError("Production DATABASE_URL must use PostgreSQL")
        allow_http_preview = os.getenv("ALLOW_HTTP_ORIGIN_PREVIEW") == "1"
        if not origins or "*" in origins or (not allow_http_preview and any(origin.startswith("http://") for origin in origins)):
            raise RuntimeError("Production CORS_ORIGINS must contain explicit HTTPS origins (or set ALLOW_HTTP_ORIGIN_PREVIEW=1 for a temporary no-TLS preview only)")
        if allow_http_preview:
            logging.getLogger("karenseir").warning("ALLOW_HTTP_ORIGIN_PREVIEW is set: CORS is running over plain HTTP. This must never be used for real production traffic with real users.")
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
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS","http://localhost:3000").split(","), allow_credentials=False, allow_methods=["GET","POST","PUT","DELETE"], allow_headers=["Authorization","Content-Type","Idempotency-Key","X-Request-ID","X-Correlation-ID"])


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
@app.get("/system/version")
def system_version(db: Session = Depends(get_db)) -> dict:
    build_info = read_build_info()
    migration_head = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return {"service":"karenseir-api","environment":ENVIRONMENT,"git_commit":build_info["git_commit"],"build_timestamp_utc":build_info["build_timestamp_utc"],"migration_head":migration_head}
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
    if DATABASE_URL.startswith("postgresql"):
        # Cross-tenant lookup-by-email cannot be scoped by RLS (no tenant is known yet).
        # Route it through a narrowly-scoped SECURITY DEFINER function instead of
        # running this query under a broadly RLS-bypassing role/connection.
        row = db.execute(text("SELECT user_id, tenant_id, user_name, user_role FROM find_login_identity(:email)"), {"email": data.email}).first()
        user = SimpleNamespace(id=row.user_id, tenant_id=row.tenant_id, name=row.user_name, role=row.user_role) if row else None
    else:
        user = db.scalar(select(User).where(User.email == data.email))
    if not user: raise HTTPException(status_code=401, detail="کاربر نمونه پیدا نشد")
    set_tenant_context(db, user.tenant_id)
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


@app.get("/me/organization-credit")
def my_organization_credit(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Real Organization Credit accounts the current employee can fund a checkout from
    (their own organization's, IRR only) with real ledger-derived balances. Distinct
    from Wallet: available = limit_amount minus what's currently reserved/consumed."""
    organization_ids = [a.organization_id for a in db.scalars(select(operational_models.EmployeeAssignment).where(operational_models.EmployeeAssignment.tenant_id == user.tenant_id, operational_models.EmployeeAssignment.user_id == user.id)).all()]
    if not organization_ids: return []
    rows = db.scalars(select(operational_models.CreditAccount).where(operational_models.CreditAccount.tenant_id == user.tenant_id, operational_models.CreditAccount.organization_id.in_(organization_ids))).all()
    return [{"id": row.id, "organization_id": row.organization_id, "currency": row.currency, **operational_models.credit_balances(db, tenant_id=user.tenant_id, credit_account_id=row.id)} for row in rows]


@app.post("/organizations/{organization_id}/credit-accounts", status_code=status.HTTP_201_CREATED)
def create_credit_account(organization_id: str, data: CreditAccountCreateIn, user: User = Depends(require_permission("credit:manage")), db: Session = Depends(get_db)) -> dict:
    if data.organization_id != organization_id: raise HTTPException(status_code=422, detail="سازمان مسیر و بدنه درخواست یکسان نیست")
    organization = db.scalar(select(operational_models.Organization).where(operational_models.Organization.id == organization_id, operational_models.Organization.tenant_id == user.tenant_id))
    if organization is None: raise HTTPException(status_code=404, detail="سازمان در این tenant وجود ندارد")
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "credit_account.create", operational_models.IdempotencyKey.key == data.command_id))
    if prior: return json.loads(prior.response_json or "{}")
    row = db.scalar(select(operational_models.CreditAccount).where(operational_models.CreditAccount.tenant_id == user.tenant_id, operational_models.CreditAccount.organization_id == organization_id, operational_models.CreditAccount.currency == data.currency))
    if row is None:
        row = operational_models.CreditAccount(tenant_id=user.tenant_id, organization_id=organization_id, currency=data.currency, limit_amount=data.limit_amount)
        db.add(row); db.flush()
    response = {"id": row.id, "organization_id": row.organization_id, "currency": row.currency, **operational_models.credit_balances(db, tenant_id=user.tenant_id, credit_account_id=row.id)}
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="credit_account.create", key=data.command_id, request_hash=_secure_hash(f"{organization_id}:{data.currency}"), response_json=json.dumps(response))); db.commit(); return response


@app.post("/organization-credit/{credit_account_id}/commands")
def organization_credit_command(credit_account_id: str, data: CreditCommandIn, user: User = Depends(require_permission("credit:manage")), db: Session = Depends(get_db)) -> dict:
    try:
        entry = operational_models.apply_organization_credit_command(db, tenant_id=user.tenant_id, credit_account_id=credit_account_id, command_id=data.command_id, entry_type=data.entry_type, amount=data.amount)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"entry_id": entry.id, "command_id": entry.command_id, **operational_models.credit_balances(db, tenant_id=user.tenant_id, credit_account_id=credit_account_id)}


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
        callback_state = jwt.encode({"iss": JWT_ISSUER, "aud": "karenseir-zarinpal-callback", "tenant_id": user.tenant_id, "payment_intent_id": intent.id, "user_id": user.id, "amount": intent.amount, "exp": datetime.now(timezone.utc) + timedelta(minutes=30), "iat": datetime.now(timezone.utc), "jti": str(uuid.uuid4())}, JWT_SECRET, algorithm="HS256")
        result = ADAPTERS["payment"].execute("initiate", {"payment_intent_id": intent.id, "amount": intent.amount, "currency": intent.currency, "callback_state": callback_state}, ProviderContext(tenant_id=user.tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=intent.command_id))
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
    intent.provider_authority = str(result.get("authority", result.get("reference", "")))[:160] or None
    db.commit()
    record_business_event("payment", "initiated")
    return {"id": intent.id, "status": intent.status, "redirect_url": redirect_url}


@app.get("/payments/zarinpal/callback")
def zarinpal_callback(state_token: str = Query(alias="state", min_length=20), authority: str = Query(alias="Authority", min_length=36, max_length=36), callback_status: str = Query(alias="Status", pattern="^(OK|NOK)$"), db: Session = Depends(get_db)) -> dict:
    try:
        claims = jwt.decode(state_token, JWT_SECRET, algorithms=["HS256"], audience="karenseir-zarinpal-callback", issuer=JWT_ISSUER, options={"require": ["exp", "iat", "jti", "tenant_id", "payment_intent_id", "user_id", "amount"]})
        tenant_id = int(claims["tenant_id"]); payment_id = str(claims["payment_intent_id"]); user_id = int(claims["user_id"]); claimed_amount = int(claims["amount"])
    except (jwt.InvalidTokenError, TypeError, ValueError, KeyError): raise HTTPException(status_code=401, detail="state پرداخت نامعتبر یا منقضی است")
    set_tenant_context(db, tenant_id)
    intent = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.id == payment_id, operational_models.PaymentIntent.tenant_id == tenant_id, operational_models.PaymentIntent.user_id == user_id).with_for_update())
    if intent is None: raise HTTPException(status_code=404, detail="Payment Intent در tenant معتبر وجود ندارد")
    if claimed_amount != intent.amount: raise HTTPException(status_code=409, detail="مبلغ state با Payment Intent تطابق ندارد")
    if intent.provider_authority != authority: raise HTTPException(status_code=409, detail="Authority با Payment Intent تطابق ندارد")
    if callback_status != "OK":
        if intent.status == "initiated":
            intent.status = "failed"; db.add(operational_models.OutboxEvent(tenant_id=tenant_id, aggregate_type="payment", aggregate_id=intent.id, event_type="payment.zarinpal.cancelled", payload_json="{}", correlation_id=str(uuid.uuid4()), idempotency_key=f"zarinpal-cancel:{authority}"))
            _record_payment_trip_event(db, tenant_id=tenant_id, intent=intent, event_key=f"payment-failed:{authority}", event_type="payment.failed", title="پرداخت ناموفق بود", message=f"پرداخت رزرو در درگاه لغو یا ناموفق شد.", severity="warning")
            db.commit()
        return {"status": "cancelled", "payment_status": intent.status}
    if intent.status == "captured" and intent.provider_capture_reference: return {"status": "duplicate", "payment_status": "captured", "ref_id": intent.provider_capture_reference}
    if intent.status != "initiated": raise HTTPException(status_code=409, detail="Payment Intent قابل verify نیست")
    from .providers import ADAPTERS, ProviderContext
    result = ADAPTERS["payment"].execute("verify", {"payment_intent_id": intent.id, "amount": intent.amount, "currency": intent.currency, "authority": authority}, ProviderContext(tenant_id=tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=f"zarinpal-verify:{authority}"))
    if not result.get("ok") or result.get("authority") != authority or int(result.get("amount", 0)) != intent.amount: raise HTTPException(status_code=502, detail="تأیید server-side زرین‌پال ناموفق بود")
    ref_id = str(result.get("ref_id", ""))[:160]
    if not ref_id: raise HTTPException(status_code=502, detail="RefID معتبر دریافت نشد")
    event_id = f"zarinpal:{authority}:{ref_id}"; prior = db.scalar(select(operational_models.PaymentEvent).where(operational_models.PaymentEvent.provider_key == "zarinpal", operational_models.PaymentEvent.provider_event_id == event_id))
    if prior: return {"status": "duplicate", "payment_status": intent.status, "ref_id": ref_id}
    intent.status = "captured"; intent.captured_amount = intent.amount; intent.provider_capture_reference = ref_id; intent.provider_reference = ref_id
    db.add(operational_models.PaymentEvent(tenant_id=tenant_id, payment_intent_id=intent.id, provider_key="zarinpal", provider_event_id=event_id, event_type="captured", payload_hash=_secure_hash(f"{authority}:{intent.amount}:{ref_id}"))); db.add(operational_models.OutboxEvent(tenant_id=tenant_id, aggregate_type="payment", aggregate_id=intent.id, event_type="payment.zarinpal.captured", payload_json=json.dumps({"authority": authority, "ref_id": ref_id}), correlation_id=str(uuid.uuid4()), idempotency_key=event_id))
    _record_payment_trip_event(db, tenant_id=tenant_id, intent=intent, event_key=f"payment-captured:{event_id}", event_type="payment.captured", title="پرداخت با موفقیت انجام شد", message=f"مبلغ {intent.amount:,} {intent.currency} با موفقیت پرداخت شد.")
    db.commit(); record_business_event("payment", "captured"); return {"status": "accepted", "payment_status": "captured", "ref_id": ref_id}


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
    _payment_event_titles = {"captured": ("پرداخت با موفقیت انجام شد", f"مبلغ {callback_amount:,} {intent.currency} با موفقیت پرداخت شد.", "info"), "failed": ("پرداخت ناموفق بود", "پرداخت رزرو ناموفق شد.", "warning"), "refund_succeeded": ("استرداد انجام شد", f"مبلغ {callback_amount:,} {intent.currency} به روش پرداخت اصلی بازگردانده شد.", "info")}
    if target in _payment_event_titles:
        title, message, severity = _payment_event_titles[target]
        _record_payment_trip_event(db, tenant_id=tenant_id, intent=intent, event_key=f"payment-{target}:{event_id}", event_type=f"payment.{target}", title=title, message=message, severity=severity)
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


# Travel-commerce verticals are additive and deliberately keep provider/payment
# success outside the catalog and inventory transactions below.
def _commerce_event(db: Session, *, tenant_id: int, kind: str, aggregate_id: str, command_id: str, payload: dict) -> None:
    db.add(operational_models.OutboxEvent(tenant_id=tenant_id, aggregate_type=kind, aggregate_id=aggregate_id, event_type=f"{kind}.changed", payload_json=json.dumps(payload, sort_keys=True), correlation_id=str(uuid.uuid4()), idempotency_key=command_id))


@app.post("/supplier/vacation-properties", status_code=201)
def create_vacation_property(data: VacationPropertyIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    supplier = db.scalar(select(operational_models.Supplier).where(operational_models.Supplier.id == data.supplier_id, operational_models.Supplier.tenant_id == user.tenant_id, operational_models.Supplier.status == "active"))
    if supplier is None: raise HTTPException(409, "تأمین‌کننده فعال وجود ندارد")
    row = operational_models.VacationProperty(tenant_id=user.tenant_id, supplier_id=supplier.id, title=data.title, slug=data.slug, city=data.city, property_type=data.property_type, capacity=data.capacity, bedrooms=data.bedrooms, status="published", details_json=json.dumps(data.details, sort_keys=True)); db.add(row); db.flush(); _commerce_event(db, tenant_id=user.tenant_id, kind="vacation_property", aggregate_id=row.id, command_id=f"property:{row.id}", payload={"status": row.status}); db.commit(); return {"id": row.id, "slug": row.slug, "status": row.status}


@app.post("/supplier/vacation-properties/{property_id}/units", status_code=201)
def create_vacation_unit(property_id: str, data: VacationUnitIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    prop = db.scalar(select(operational_models.VacationProperty).where(operational_models.VacationProperty.id == property_id, operational_models.VacationProperty.tenant_id == user.tenant_id))
    if prop is None: raise HTTPException(404, "اقامتگاه وجود ندارد")
    row = operational_models.VacationUnit(tenant_id=user.tenant_id, property_id=prop.id, title=data.title, capacity=data.capacity, available_units=data.available_units, nightly_price=data.nightly_price, pricing_json=json.dumps(data.pricing, sort_keys=True)); db.add(row); db.commit(); return {"id": row.id, "property_id": row.property_id, "status": row.status}


@app.get("/vacation-rentals")
def list_vacation_rentals(city: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    query = select(operational_models.VacationProperty).where(operational_models.VacationProperty.tenant_id == user.tenant_id, operational_models.VacationProperty.status == "published")
    if city: query = query.where(operational_models.VacationProperty.city == city)
    rows = db.scalars(query.order_by(operational_models.VacationProperty.created_at.desc())).all()
    return [{"id": r.id, "slug": r.slug, "title": r.title, "city": r.city, "property_type": r.property_type, "capacity": r.capacity, "bedrooms": r.bedrooms, "details": json.loads(r.details_json)} for r in rows]


@app.get("/vacation-rentals/{property_id}")
def vacation_rental_detail(property_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.VacationProperty).where(operational_models.VacationProperty.id == property_id, operational_models.VacationProperty.tenant_id == user.tenant_id, operational_models.VacationProperty.status == "published"))
    if row is None: raise HTTPException(404, "اقامتگاه وجود ندارد")
    units = db.scalars(select(operational_models.VacationUnit).where(operational_models.VacationUnit.property_id == row.id, operational_models.VacationUnit.tenant_id == user.tenant_id, operational_models.VacationUnit.status == "active")).all()
    return {"id": row.id, "title": row.title, "city": row.city, "property_type": row.property_type, "capacity": row.capacity, "bedrooms": row.bedrooms, "details": json.loads(row.details_json), "units": [{"id": u.id, "title": u.title, "capacity": u.capacity, "available_units": u.available_units, "nightly_price": u.nightly_price, "currency": u.currency, "pricing": json.loads(u.pricing_json)} for u in units]}


@app.post("/vacation-units/{unit_id}/reservations", status_code=201)
def book_vacation_unit(unit_id: str, data: VacationBookIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.VacationReservation).where(operational_models.VacationReservation.tenant_id == user.tenant_id, operational_models.VacationReservation.command_id == data.command_id))
    if prior:
        if prior.unit_id != unit_id: raise HTTPException(409, "کلید تکرار برای رزرو دیگری استفاده شده است")
        return {"id": prior.id, "status": prior.status, "total_amount": prior.total_amount}
    check_in, check_out = _aware(data.check_in), _aware(data.check_out)
    if check_out <= check_in or check_in < datetime.now(timezone.utc): raise HTTPException(422, "بازه اقامت معتبر نیست")
    unit = db.scalar(select(operational_models.VacationUnit).where(operational_models.VacationUnit.id == unit_id, operational_models.VacationUnit.tenant_id == user.tenant_id, operational_models.VacationUnit.status == "active").with_for_update())
    if unit is None or data.guests > unit.capacity: raise HTTPException(409, "واحد یا ظرفیت معتبر نیست")
    overlaps = db.scalar(select(func.count()).select_from(operational_models.VacationReservation).where(operational_models.VacationReservation.tenant_id == user.tenant_id, operational_models.VacationReservation.unit_id == unit.id, operational_models.VacationReservation.status.in_(("held", "confirmed")), operational_models.VacationReservation.check_in < check_out, operational_models.VacationReservation.check_out > check_in)) or 0
    if overlaps >= unit.available_units: raise HTTPException(409, "این بازه دیگر موجود نیست")
    pricing = _villa_stay_pricing(unit, check_in, check_out); nights, total = pricing["nights"], pricing["total_amount"]
    prop = db.scalar(select(operational_models.VacationProperty).where(operational_models.VacationProperty.id == unit.property_id, operational_models.VacationProperty.tenant_id == user.tenant_id))
    prop_details = json.loads(prop.details_json) if prop else {}
    policy = prop_details.get("cancellation_policy") if isinstance(prop_details.get("cancellation_policy"), dict) else {}
    reservation = operational_models.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="vacation_rental", status="reserved", booking_reference=f"KS-VILLA-{uuid.uuid4().hex[:10].upper()}", price_snapshot_json=json.dumps({"total_amount": total, "currency": unit.currency, "nights": nights, "guests": data.guests, "min_stay": pricing["min_stay"], "nightly_breakdown": pricing["nightly_breakdown"]}, sort_keys=True), policy_at_booking_json=json.dumps(policy, sort_keys=True), current_policy_json=json.dumps(policy, sort_keys=True)); db.add(reservation); db.flush(); row = operational_models.VacationReservation(tenant_id=user.tenant_id, unit_id=unit.id, user_id=user.id, reservation_id=reservation.id, check_in=check_in, check_out=check_out, guests=data.guests, total_amount=total, command_id=data.command_id); db.add(row); db.flush(); _commerce_event(db, tenant_id=user.tenant_id, kind="vacation_reservation", aggregate_id=row.id, command_id=data.command_id, payload={"status": row.status, "reservation_id": reservation.id})
    trip = operational_models.ensure_trip_for_reservation(db, reservation, title=f"سفر به {prop.city}", destination=prop.city, starts_at=check_in, ends_at=check_out)
    operational_models.record_trip_event(db, tenant_id=user.tenant_id, trip_id=trip.id, reservation_id=reservation.id, event_key=f"booking-created:{data.command_id}", event_type="booking.created", source="system", title="رزرو ویلا ثبت شد", message=f"رزرو {reservation.booking_reference} برای {prop.title} در {prop.city} ثبت شد.", deep_link=f"/manage-booking/{reservation.id}")
    db.commit(); return {"id": row.id, "reservation_id": reservation.id, "status": row.status, "total_amount": row.total_amount, "currency": unit.currency, "payment_required": True, "checkout_url": f"/checkout/{reservation.id}", "price_breakdown": pricing["nightly_breakdown"]}


@app.post("/supplier/tours", status_code=201)
def create_tour(data: TourProductIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    supplier = db.scalar(select(operational_models.Supplier).where(operational_models.Supplier.id == data.supplier_id, operational_models.Supplier.tenant_id == user.tenant_id, operational_models.Supplier.status == "active"))
    if supplier is None: raise HTTPException(409, "تأمین‌کننده فعال وجود ندارد")
    row = operational_models.TourProduct(tenant_id=user.tenant_id, supplier_id=supplier.id, title=data.title, slug=data.slug, origin=data.origin, destination=data.destination, tour_type=data.tour_type, status="published", details_json=json.dumps(data.details, sort_keys=True)); db.add(row); db.commit(); return {"id": row.id, "slug": row.slug, "status": row.status}


@app.post("/supplier/tours/{tour_id}/departures", status_code=201)
def create_tour_departure(tour_id: str, data: TourDepartureIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    tour = db.scalar(select(operational_models.TourProduct).where(operational_models.TourProduct.id == tour_id, operational_models.TourProduct.tenant_id == user.tenant_id))
    if tour is None or _aware(data.ends_at) <= _aware(data.starts_at) or _aware(data.booking_deadline) > _aware(data.starts_at): raise HTTPException(422, "تور یا تاریخ حرکت معتبر نیست")
    row = operational_models.TourDeparture(tenant_id=user.tenant_id, tour_id=tour.id, starts_at=data.starts_at, ends_at=data.ends_at, booking_deadline=data.booking_deadline, capacity=data.capacity, remaining=data.capacity, base_price=data.base_price, pricing_json=json.dumps(data.pricing, sort_keys=True)); db.add(row); db.commit(); return {"id": row.id, "remaining": row.remaining, "status": row.status}


@app.get("/tour-products")
def list_tours(destination: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    query = select(operational_models.TourProduct).where(operational_models.TourProduct.tenant_id == user.tenant_id, operational_models.TourProduct.status == "published")
    if destination: query = query.where(operational_models.TourProduct.destination == destination)
    rows = db.scalars(query).all(); return [{"id": r.id, "slug": r.slug, "title": r.title, "origin": r.origin, "destination": r.destination, "tour_type": r.tour_type, "details": json.loads(r.details_json)} for r in rows]


@app.get("/tour-products/{tour_id}")
def tour_detail(tour_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.TourProduct).where(operational_models.TourProduct.id == tour_id, operational_models.TourProduct.tenant_id == user.tenant_id, operational_models.TourProduct.status == "published"))
    if row is None: raise HTTPException(404, "تور وجود ندارد")
    departures = db.scalars(select(operational_models.TourDeparture).where(operational_models.TourDeparture.tour_id == row.id, operational_models.TourDeparture.tenant_id == user.tenant_id, operational_models.TourDeparture.status == "active")).all()
    details = json.loads(row.details_json)
    return {"id": row.id, "title": row.title, "origin": row.origin, "destination": row.destination, "tour_type": row.tour_type, "details": details, "visa_status": details.get("visa_status", "VISA_STATUS_UNKNOWN"), "visa_assistance_available": bool(details.get("visa_assistance_available", False)), "departures": [{"id": d.id, "starts_at": d.starts_at.isoformat(), "ends_at": d.ends_at.isoformat(), "remaining": d.remaining, "base_price": d.base_price, "currency": d.currency, "pricing": json.loads(d.pricing_json)} for d in departures]}


@app.post("/tour-departures/{departure_id}/reservations", status_code=201)
def book_tour(departure_id: str, data: TourBookIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.TourReservation).where(operational_models.TourReservation.tenant_id == user.tenant_id, operational_models.TourReservation.command_id == data.command_id))
    if prior:
        if prior.departure_id != departure_id: raise HTTPException(409, "کلید تکرار برای رزرو دیگری استفاده شده است")
        return {"id": prior.id, "status": prior.status, "total_amount": prior.total_amount}
    departure = db.scalar(select(operational_models.TourDeparture).where(operational_models.TourDeparture.id == departure_id, operational_models.TourDeparture.tenant_id == user.tenant_id).with_for_update())
    now = datetime.now(timezone.utc)
    if departure is None or departure.status != "active" or _aware(departure.booking_deadline) <= now or departure.remaining < data.travellers: raise HTTPException(409, "ظرفیت یا مهلت رزرو تور معتبر نیست")
    pricing = json.loads(departure.pricing_json); surcharge = int(pricing.get(f"{data.room_type}_surcharge", 0)); total = (departure.base_price + surcharge) * data.travellers
    tour = db.scalar(select(operational_models.TourProduct).where(operational_models.TourProduct.id == departure.tour_id, operational_models.TourProduct.tenant_id == user.tenant_id)); details = json.loads(tour.details_json) if tour else {}; policy = details.get("cancellation_policy") if isinstance(details.get("cancellation_policy"), dict) else {}; reservation = operational_models.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="tour", status="reserved", booking_reference=f"KS-TOUR-{uuid.uuid4().hex[:10].upper()}", price_snapshot_json=json.dumps({"total_amount": total, "currency": departure.currency, "travellers": data.travellers, "room_type": data.room_type, "departure_id": departure.id, "visa_status": details.get("visa_status", "VISA_STATUS_UNKNOWN")}, sort_keys=True), policy_at_booking_json=json.dumps(policy, sort_keys=True), current_policy_json=json.dumps(policy, sort_keys=True)); db.add(reservation); db.flush(); departure.remaining -= data.travellers; row = operational_models.TourReservation(tenant_id=user.tenant_id, departure_id=departure.id, user_id=user.id, reservation_id=reservation.id, travellers=data.travellers, room_type=data.room_type, total_amount=total, command_id=data.command_id); db.add(row); db.flush(); _commerce_event(db, tenant_id=user.tenant_id, kind="tour_reservation", aggregate_id=row.id, command_id=data.command_id, payload={"status": row.status, "remaining": departure.remaining, "reservation_id": reservation.id, "visa_status": details.get("visa_status", "VISA_STATUS_UNKNOWN")})
    tour_title = tour.title if tour else "تور"; tour_destination = tour.destination if tour else ""
    trip = operational_models.ensure_trip_for_reservation(db, reservation, title=tour_title, destination=tour_destination, origin=(tour.origin if tour else None), starts_at=departure.starts_at, ends_at=departure.ends_at)
    operational_models.record_trip_event(db, tenant_id=user.tenant_id, trip_id=trip.id, reservation_id=reservation.id, event_key=f"booking-created:{data.command_id}", event_type="booking.created", source="system", title="رزرو تور ثبت شد", message=f"رزرو {reservation.booking_reference} برای {tour_title} ثبت شد.", deep_link=f"/manage-booking/{reservation.id}")
    db.commit(); return {"id": row.id, "reservation_id": reservation.id, "checkout_url": f"/checkout/{reservation.id}", "status": row.status, "total_amount": row.total_amount, "currency": departure.currency, "payment_required": True, "voucher": None, "visa_status": details.get("visa_status", "VISA_STATUS_UNKNOWN")}


@app.get("/cruises")
def list_cruises(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(operational_models.CruiseSailing).where(operational_models.CruiseSailing.tenant_id == user.tenant_id)).all()
    return {"items": [{"id": r.id, "title": r.title, "cruise_line": r.cruise_line, "ship": r.ship, "departure_port": r.departure_port, "arrival_port": r.arrival_port, "starts_at": r.starts_at.isoformat(), "nights": r.nights, "status": r.status, "details": json.loads(r.details_json)} for r in rows], "live_booking": False, "provider_status": "BLOCKED_EXTERNAL_CREDENTIAL"}


@app.post("/cruises/{sailing_id}/book")
def book_cruise(sailing_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.CruiseSailing).where(operational_models.CruiseSailing.id == sailing_id, operational_models.CruiseSailing.tenant_id == user.tenant_id))
    if row is None: raise HTTPException(404, "سفر دریایی وجود ندارد")
    raise HTTPException(503, detail={"code": "LIVE_PROVIDER_UNAVAILABLE", "message": "رزرو زنده کروز تا اتصال Provider قراردادی غیرفعال است"})


@app.post("/backoffice/visa-products", status_code=201)
def create_visa_product(data: VisaProductIn, user: User = Depends(require_permission("support:manage")), db: Session = Depends(get_db)) -> dict:
    row = operational_models.VisaProduct(tenant_id=user.tenant_id, destination_country=data.destination_country, visa_type=data.visa_type, title=data.title, source_url=data.source_url, source_verified_at=data.source_verified_at, details_json=json.dumps(data.details, sort_keys=True)); db.add(row); db.commit(); return {"id": row.id, "status": row.status}


@app.get("/visa-products")
def list_visa_products(destination_country: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    query = select(operational_models.VisaProduct).where(operational_models.VisaProduct.tenant_id == user.tenant_id, operational_models.VisaProduct.status == "published")
    if destination_country: query = query.where(operational_models.VisaProduct.destination_country == destination_country)
    rows = db.scalars(query).all(); return [{"id": r.id, "title": r.title, "destination_country": r.destination_country, "visa_type": r.visa_type, "source_url": r.source_url, "source_verified_at": r.source_verified_at.isoformat(), "details": json.loads(r.details_json), "guarantee": False, "eligibility": "requires_human_review"} for r in rows]


@app.post("/visa-products/{product_id}/applications", status_code=201)
def start_visa_application(product_id: str, data: VisaApplicationIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.VisaApplication).where(operational_models.VisaApplication.tenant_id == user.tenant_id, operational_models.VisaApplication.command_id == data.command_id))
    if prior: return {"id": prior.id, "status": prior.status}
    product = db.scalar(select(operational_models.VisaProduct).where(operational_models.VisaProduct.id == product_id, operational_models.VisaProduct.tenant_id == user.tenant_id, operational_models.VisaProduct.status == "published"))
    if product is None: raise HTTPException(404, "خدمت ویزا وجود ندارد")
    if data.trip_id and db.scalar(select(operational_models.Trip.id).where(operational_models.Trip.id == data.trip_id, operational_models.Trip.tenant_id == user.tenant_id, operational_models.Trip.user_id == user.id)) is None: raise HTTPException(404, "سفر متعلق به این حساب نیست")
    tour_reservation = None
    if data.tour_reservation_id:
        tour_reservation = db.scalar(select(operational_models.TourReservation).where(operational_models.TourReservation.id == data.tour_reservation_id, operational_models.TourReservation.tenant_id == user.tenant_id, operational_models.TourReservation.user_id == user.id))
        if tour_reservation is None: raise HTTPException(404, "رزرو تور متعلق به این حساب نیست")
    row = operational_models.VisaApplication(tenant_id=user.tenant_id, product_id=product.id, user_id=user.id, trip_id=data.trip_id, tour_reservation_id=tour_reservation.id if tour_reservation else None, purpose=data.purpose, travel_at=data.travel_at, command_id=data.command_id); db.add(row); db.flush(); db.add(operational_models.VisaTimelineEvent(tenant_id=user.tenant_id, application_id=row.id, event_type="started", source_type="system", message="پرونده ایجاد شد؛ صدور ویزا تضمین نمی‌شود.", event_key=f"visa-start:{row.id}"));
    if tour_reservation: db.add(operational_models.VisaTimelineEvent(tenant_id=user.tenant_id, application_id=row.id, event_type="tour_linked", source_type="system", message="پرونده ویزا به رزرو تور متصل شد.", event_key=f"visa-tour:{row.id}:{tour_reservation.id}"))
    db.commit(); return {"id": row.id, "status": row.status, "guarantee": False, "tour_reservation_id": row.tour_reservation_id}


@app.post("/visa-applications/{application_id}/applicants", status_code=201)
def add_visa_applicant(application_id: str, data: VisaApplicantIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    app_row = db.scalar(select(operational_models.VisaApplication).where(operational_models.VisaApplication.id == application_id, operational_models.VisaApplication.tenant_id == user.tenant_id, operational_models.VisaApplication.user_id == user.id))
    if app_row is None: raise HTTPException(404, "پرونده در این حساب وجود ندارد")
    row = operational_models.VisaApplicant(tenant_id=user.tenant_id, application_id=app_row.id, full_name=data.full_name, passport_country=data.passport_country, passport_reference=_secure_hash(data.passport_reference)); db.add(row); db.commit(); return {"id": row.id, "full_name": row.full_name, "passport_country": row.passport_country}


@app.post("/visa-applications/{application_id}/documents", status_code=201)
def upload_visa_document(application_id: str, data: VisaDocumentIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    app_row = db.scalar(select(operational_models.VisaApplication).where(operational_models.VisaApplication.id == application_id, operational_models.VisaApplication.tenant_id == user.tenant_id, operational_models.VisaApplication.user_id == user.id))
    if app_row is None: raise HTTPException(404, "پرونده در این حساب وجود ندارد")
    row = db.scalar(select(operational_models.VisaDocument).where(operational_models.VisaDocument.tenant_id == user.tenant_id, operational_models.VisaDocument.application_id == app_row.id, operational_models.VisaDocument.document_type == data.document_type))
    if row is None: row = operational_models.VisaDocument(tenant_id=user.tenant_id, application_id=app_row.id, document_type=data.document_type); db.add(row)
    row.storage_reference = data.storage_reference; row.status = "uploaded"; row.review_note = None; db.commit(); return {"id": row.id, "document_type": row.document_type, "status": row.status}


@app.put("/backoffice/visa-documents/{document_id}")
def review_visa_document(document_id: str, data: VisaDocumentReviewIn, user: User = Depends(require_permission("support:manage")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.VisaDocument).where(operational_models.VisaDocument.id == document_id, operational_models.VisaDocument.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(404, "مدرک وجود ندارد")
    row.status = data.status; row.review_note = data.review_note; db.add(operational_models.VisaTimelineEvent(tenant_id=user.tenant_id, application_id=row.application_id, event_type="document_reviewed", source_type="human_agent", actor_id=user.id, message=f"وضعیت مدرک {row.document_type}: {row.status}", event_key=f"visa-doc:{row.id}:{row.updated_at.isoformat()}")); db.commit(); return {"id": row.id, "status": row.status, "source_type": "human_agent"}


@app.get("/visa-applications/{application_id}")
def visa_application_detail(application_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.VisaApplication).where(operational_models.VisaApplication.id == application_id, operational_models.VisaApplication.tenant_id == user.tenant_id, operational_models.VisaApplication.user_id == user.id))
    if row is None: raise HTTPException(404, "پرونده در این حساب وجود ندارد")
    applicants = db.scalars(select(operational_models.VisaApplicant).where(operational_models.VisaApplicant.application_id == row.id, operational_models.VisaApplicant.tenant_id == user.tenant_id)).all(); documents = db.scalars(select(operational_models.VisaDocument).where(operational_models.VisaDocument.application_id == row.id, operational_models.VisaDocument.tenant_id == user.tenant_id)).all(); timeline = db.scalars(select(operational_models.VisaTimelineEvent).where(operational_models.VisaTimelineEvent.application_id == row.id, operational_models.VisaTimelineEvent.tenant_id == user.tenant_id).order_by(operational_models.VisaTimelineEvent.created_at)).all()
    return {"id": row.id, "status": row.status, "purpose": row.purpose, "travel_at": row.travel_at.isoformat(), "guarantee": False, "trip_id": row.trip_id, "tour_reservation_id": row.tour_reservation_id, "applicants": [{"id": a.id, "full_name": a.full_name, "passport_country": a.passport_country} for a in applicants], "documents": [{"id": d.id, "document_type": d.document_type, "status": d.status, "review_note": d.review_note} for d in documents], "timeline": [{"event_type": e.event_type, "source_type": e.source_type, "message": e.message, "created_at": e.created_at.isoformat()} for e in timeline]}


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


_SEARCH_TRANSLATION = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "ؤ": "و", "إ": "ا", "أ": "ا", "ٱ": "ا", "‌": " ", "‍": " ", "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9", "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9"})
_AUTOCOMPLETE_ENTITIES = (
    {"id": "city-tehran", "title": "تهران", "type": "city", "code": "THR", "country": "ایران", "popularity": 100, "aliases": ["تهرون", "Tehran"]},
    {"id": "city-shiraz", "title": "شیراز", "type": "city", "code": "SYZ", "country": "ایران", "popularity": 92, "aliases": ["Shiraz"]},
    {"id": "city-mashhad", "title": "مشهد", "type": "city", "code": "MHD", "country": "ایران", "popularity": 96, "aliases": ["Mashhad"]},
    {"id": "city-yazd", "title": "یزد", "type": "city", "code": "AZD", "country": "ایران", "popularity": 78, "aliases": ["Yazd"]},
    {"id": "city-isfahan", "title": "اصفهان", "type": "city", "code": "IFN", "country": "ایران", "popularity": 90, "aliases": ["Isfahan", "Esfahan"]},
    {"id": "city-kish", "title": "کیش", "type": "city", "code": "KIH", "country": "ایران", "popularity": 86, "aliases": ["Kish"]},
    {"id": "city-qeshm", "title": "قشم", "type": "city", "code": "GSM", "country": "ایران", "popularity": 82, "aliases": ["Qeshm"]},
    {"id": "airport-thr", "title": "فرودگاه مهرآباد", "type": "airport", "code": "THR", "city": "تهران", "country": "ایران", "popularity": 94, "aliases": ["Mehrabad"]},
    {"id": "airport-ika", "title": "فرودگاه امام خمینی", "type": "airport", "code": "IKA", "city": "تهران", "country": "ایران", "popularity": 91, "aliases": ["Imam Khomeini Airport"]},
    {"id": "poi-hafezieh", "title": "حافظیه", "type": "attraction", "city": "شیراز", "country": "ایران", "popularity": 75, "aliases": ["Hafezieh"]},
    {"id": "poi-persepolis", "title": "تخت جمشید", "type": "attraction", "city": "مرودشت", "country": "ایران", "popularity": 88, "aliases": ["Persepolis"]},
)


def _normalize_search_text(value: str) -> str:
    translated = unicodedata.normalize("NFKC", value).translate(_SEARCH_TRANSLATION)
    without_marks = "".join(char for char in translated if unicodedata.category(char) != "Mn")
    without_punctuation = " ".join(re.sub(r"[^\w\s]", " ", without_marks, flags=re.UNICODE).casefold().split())
    aliases = {"tehran": "تهران", "تهرون": "تهران", "thr": "تهران", "shiraz": "شیراز", "syz": "شیراز", "mashhad": "مشهد", "mhd": "مشهد", "isfahan": "اصفهان", "esfahan": "اصفهان", "ifn": "اصفهان"}
    return " ".join(aliases.get(token, token) for token in without_punctuation.split())


def _match_score(query: str, candidate: str, aliases: list[str] | None = None) -> tuple[int, str]:
    values = [_normalize_search_text(candidate), *[_normalize_search_text(item) for item in aliases or []]]
    if query in values: return 400, "exact"
    if any(value.startswith(query) for value in values): return 300, "prefix"
    if any(query in value for value in values): return 200, "contains"
    ratio = max((SequenceMatcher(None, query, value).ratio() for value in values), default=0)
    return (100 + int(ratio * 50), "fuzzy") if ratio >= 0.72 else (0, "none")


def _search_datetime(value: object, fallback: datetime) -> datetime:
    if isinstance(value, str):
        try:
            return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return fallback
    return fallback


@app.get("/search/autocomplete")
def search_autocomplete(q: str, service_type: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    normalized = _normalize_search_text(q)
    if len(normalized) < 2:
        raise HTTPException(status_code=422, detail="حداقل دو نویسه برای پیشنهاد لازم است")
    if service_type and not __import__("re").fullmatch(ECOSYSTEM_SERVICE_PATTERN[1:-1], service_type):
        raise HTTPException(status_code=422, detail="نوع خدمت معتبر نیست")
    statement = select(operational_models.Offer).where(operational_models.Offer.tenant_id == user.tenant_id, operational_models.Offer.status == "active")
    if service_type: statement = statement.where(operational_models.Offer.service_type == service_type)
    rows = db.scalars(statement.limit(100)).all()
    suggestions: list[dict] = []
    seen: set[tuple[str, str]] = set()
    persisted = db.scalars(select(operational_models.SearchEntity).where(operational_models.SearchEntity.tenant_id == user.tenant_id, operational_models.SearchEntity.status == "active").limit(100)).all()
    candidates = [*list(_AUTOCOMPLETE_ENTITIES), *[{"id": row.id, "title": row.title, "type": row.entity_type, "code": row.code, "city": row.city, "country": row.country, "subtitle": row.subtitle, "popularity": row.popularity_score, "aliases": json.loads(row.aliases_json or "[]"), "coordinates": [float(row.latitude), float(row.longitude)] if row.latitude is not None and row.longitude is not None else None} for row in persisted]]
    for item in candidates:
        score, match_type = _match_score(normalized, item["title"], item.get("aliases", []) + ([item["code"]] if item.get("code") else []) + ([item["city"]] if item.get("city") else []))
        if score:
            key = (item["title"], item["type"]); seen.add(key)
            suggestions.append({"id": item["id"], "title": item["title"], "label": item["title"], "subtitle": item.get("subtitle") or " · ".join(filter(None, [item.get("city"), item.get("country")])), "normalized": _normalize_search_text(item["title"]), "entity_type": item["type"], "city": item.get("city"), "country": item.get("country"), "code": item.get("code"), "coordinates": item.get("coordinates"), "popularity_score": item.get("popularity", 0), "match_type": match_type, "ranking_score": score + item.get("popularity", 0), "source": "tenant_entity_catalog" if isinstance(item["id"], str) and len(item["id"]) == 36 else "karenseir_geo_catalog"})
    for row in rows:
        score, match_type = _match_score(normalized, row.title)
        if score and (row.title, row.service_type) not in seen:
            attrs = json.loads(row.attributes_json or "{}")
            seen.add((row.title, row.service_type)); suggestions.append({"id": row.id, "title": row.title, "label": row.title, "subtitle": attrs.get("city"), "normalized": _normalize_search_text(row.title), "entity_type": row.service_type, "city": attrs.get("city"), "country": attrs.get("country", "ایران"), "code": attrs.get("code"), "coordinates": [attrs.get("latitude"), attrs.get("longitude")] if attrs.get("latitude") is not None else None, "popularity_score": int(attrs.get("popularity_score", 0)), "match_type": match_type, "ranking_score": score + int(attrs.get("popularity_score", 0)), "source": "tenant_offer"})
    suggestions.sort(key=lambda item: (-item["ranking_score"], item["title"]))
    return {"query": q, "normalized_query": normalized, "suggestions": suggestions[:10], "cache_policy": "private_tenant_30s"}


@app.get("/search/autocomplete/public")
def public_search_autocomplete(q: str) -> dict:
    """Expose only the non-tenant geographic catalog for pre-login search."""
    normalized = _normalize_search_text(q)
    if len(normalized) < 2:
        raise HTTPException(status_code=422, detail="حداقل دو نویسه برای پیشنهاد لازم است")
    suggestions = []
    for item in _AUTOCOMPLETE_ENTITIES:
        score, match_type = _match_score(normalized, item["title"], item.get("aliases", []) + ([item["code"]] if item.get("code") else []) + ([item["city"]] if item.get("city") else []))
        if score:
            suggestions.append({"id": item["id"], "title": item["title"], "subtitle": " · ".join(filter(None, [item.get("city"), item.get("country")])), "entity_type": item["type"], "city": item.get("city"), "country": item.get("country"), "code": item.get("code"), "coordinates": item.get("coordinates"), "popularity_score": item.get("popularity", 0), "match_type": match_type, "ranking_score": score + item.get("popularity", 0), "source": "karenseir_geo_catalog"})
    suggestions.sort(key=lambda item: (-item["ranking_score"], item["title"]))
    return {"query": q, "normalized_query": normalized, "suggestions": suggestions[:10], "cache_policy": "public_5m", "tenant_data_included": False}


def _grs_hotel_offers_for_search(*, tenant_id: int, query: str, min_price: Optional[int], max_price: Optional[int], min_review_score: Optional[float], refundable: Optional[bool], instant_booking: Optional[bool], check_in: Optional[str], check_out: Optional[str], travellers: int = 1, db: Session, adapter=None) -> list[dict]:
    """GRS-sourced hotel offers normalized into the exact search_offers() result
    shape - Manual/Existing providers are never touched by this function. Never
    raises and never blocks the rest of Search: any disablement, missing
    location mapping, missing dates, failure or timeout is a partial provider
    failure (empty list + a recorded business event), never a Search-wide error.
    Returns [] immediately when GRS is disabled (today's only real state in
    every environment) - this is the zero-cost, zero-behavior-change path.

    Known, deliberate limitation: the current internal Search contract
    (UnifiedSearchIn/OfferSearchIn) does not yet collect check_in/check_out
    end-to-end from the frontend (the frontend already has depart/return in the
    UI, but does not send them as `filters.check_in`/`filters.check_out` yet -
    a separate, frontend-side change this phase's UI-freeze constraint
    explicitly forbids making). Without dates, GRS's mandatory check_in/
    check_out requirement cannot be honestly satisfied, so this returns []
    rather than guessing a date range.
    """
    from .providers import configured_mode
    if adapter is None and configured_mode("hotel") == "disabled":
        # Zero-cost real-world path: GRS is disabled everywhere today, so this
        # returns before touching ADAPTERS/DB/config at all. When a test
        # explicitly injects an adapter, that adapter's own mode/validate_
        # configuration() is the source of truth instead (GRSAdapter.execute()
        # already fails closed on disabled/misconfigured on its own).
        return []
    if not check_in or not check_out:
        return []
    try:
        from .providers import ADAPTERS, ProviderContext
        from .grs_contract import GRSConfig
        from .grs_location import GRSLocationQueryMode
        resolved_adapter = adapter if adapter is not None else ADAPTERS["hotel"]
        # Use the actual adapter's own config (real path: env-derived inside
        # GRSAdapter itself; test path: whatever was injected) rather than a
        # fresh GRSConfig.from_env() here, which would ignore an injected
        # test adapter's config entirely and always see the disabled default.
        config = getattr(resolved_adapter, "_config", None) or GRSConfig.from_env()
        if not config.can_accept_bookable_prices():
            return []
        normalized_query = _normalize_search_text(query)
        candidates = db.scalars(select(operational_models.ProviderLocationMapping).where(operational_models.ProviderLocationMapping.tenant_id == tenant_id, operational_models.ProviderLocationMapping.provider_key == "grs")).all()
        mapping = next((item for item in candidates if _normalize_search_text(item.provider_name) == normalized_query), None)
        if mapping is None:
            return []
        mode = GRSLocationQueryMode.CITY_ID if mapping.location_kind == "city" else GRSLocationQueryMode.COUNTRY_ID
        payload: dict = {"mode": mode.value, "check_in": check_in, "check_out": check_out, "adults_count": max(1, travellers)}
        if mode is GRSLocationQueryMode.CITY_ID:
            payload["city_id"] = int(mapping.provider_location_id)
        else:
            payload["country_id"] = int(mapping.provider_location_id)
        context = ProviderContext(tenant_id=tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=f"grs-search:{uuid.uuid4()}")
        result = resolved_adapter.execute("search_suggestions", payload, context)
        if not result.get("ok"):
            record_business_event("provider", "grs_search_partial_failure")
            return []
        suggestions = result.get("value")
        if not isinstance(suggestions, list):
            record_business_event("provider", "grs_search_partial_failure")
            return []
        now = datetime.now(timezone.utc)
        normalized: list[dict] = []
        for suggestion in suggestions:
            property_id = suggestion.get("property_id")
            property_name = str(suggestion.get("property_name", ""))
            for room in suggestion.get("rooms", []) or []:
                for rate_plan in room.get("rate_plans", []) or []:
                    price = next((p for p in (rate_plan.get("prices") or []) if not p.get("closed") and int(p.get("inventory", 0) or 0) > 0), None)
                    if price is None:
                        continue
                    amount = int(price.get("daily_rate", price.get("grs_rate", 0)) or 0)
                    if amount <= 0:
                        continue
                    entity_id = f"grs:{property_id}:{room.get('room_type_id')}:{rate_plan.get('id')}"
                    cancelable = bool(rate_plan.get("cancelable"))
                    normalized.append({
                        "id": entity_id, "offer_id": entity_id, "entity_id": entity_id,
                        "service_type": "hotel", "title": property_name, "provider": "grs",
                        "provider_status": "provider_required",
                        "last_updated_at": now.isoformat(), "observed_at": now.isoformat(),
                        "availability_checked_at": now.isoformat(), "price_checked_at": now.isoformat(),
                        "freshness_ttl_seconds": 300, "freshness": "live", "freshness_state": "LIVE",
                        "amount": amount, "base_price": amount, "taxes": 0, "fees": 0, "discounts": 0,
                        "total_amount": amount, "final_price": amount, "currency": config.money_unit,
                        "available": True, "availability_state": "CONFIRMED", "inventory_status": "available",
                        "available_units": int(price.get("inventory", 0) or 0),
                        "cancellation_policy": {"refundable": cancelable}, "policy_verified": True,
                        "quality_score": None, "review_score": None, "location": {},
                        "attributes": {"room_type_name": room.get("room_type_name", ""), "rate_plan_name": rate_plan.get("name", ""), "grs_property_id": property_id},
                        "valid_until": (now + timedelta(hours=1)).isoformat(),
                        "ranking_breakdown": {}, "ranking_score": 0.0, "ranking_explanation": [],
                    })
        filtered: list[dict] = []
        for item in normalized:
            if min_price is not None and item["amount"] < min_price:
                continue
            if max_price is not None and item["amount"] > max_price:
                continue
            if refundable is not None and item["cancellation_policy"].get("refundable") is not refundable:
                continue
            if min_review_score is not None:
                continue  # GRS suggestion data carries no review score - never fabricated, so excluded when this filter is active
            if instant_booking is not None:
                continue  # GRS suggestion data carries no instant-booking flag - same reasoning
            filtered.append(item)
        return filtered
    except Exception:
        record_business_event("provider", "grs_search_partial_failure")
        return []


@app.post("/search/offers")
def search_offers(data: OfferSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    if data.min_price is not None and data.max_price is not None and data.min_price > data.max_price:
        raise HTTPException(status_code=422, detail="بازه قیمت معتبر نیست")
    bounds = data.map_bounds
    if bounds is not None:
        required = {"north", "south", "east", "west"}
        if set(bounds) != required or bounds["north"] <= bounds["south"] or bounds["east"] <= bounds["west"]:
            raise HTTPException(status_code=422, detail="محدوده نقشه معتبر نیست")
    now = datetime.now(timezone.utc)
    statement = select(operational_models.Offer).where(operational_models.Offer.tenant_id == user.tenant_id, operational_models.Offer.service_type == data.service_type, operational_models.Offer.status == "active", operational_models.Offer.available_units > 0, operational_models.Offer.valid_until > now)
    if data.min_price is not None: statement = statement.where(operational_models.Offer.amount >= data.min_price)
    if data.max_price is not None: statement = statement.where(operational_models.Offer.amount <= data.max_price)
    rows = db.scalars(statement).all()
    normalized_query = _normalize_search_text(data.query or "")
    results: list[dict] = []
    for row in rows:
        attrs = json.loads(row.attributes_json or "{}")
        policy = json.loads(row.policy_json or "{}")
        searchable = _normalize_search_text(" ".join(str(value) for value in [row.title, attrs.get("city", ""), attrs.get("origin", ""), attrs.get("destination", ""), attrs.get("province", ""), attrs.get("airport", ""), attrs.get("poi", "")]))
        if normalized_query and normalized_query not in searchable: continue
        review_score = float(attrs.get("review_score", attrs.get("rating", 0)) or 0)
        if data.min_review_score is not None and review_score < data.min_review_score: continue
        cancellation = policy.get("cancellation", {}) if policy.get("verified") is True else None
        if data.refundable is not None and (cancellation or {}).get("refundable") is not data.refundable: continue
        available_amenities = {_normalize_search_text(str(item)) for item in attrs.get("amenities", [])}
        if any(_normalize_search_text(item) not in available_amenities for item in data.amenities): continue
        if data.instant_booking is not None and bool(attrs.get("instant_booking", row.fulfillment_mode == "manual_supplier")) is not data.instant_booking: continue
        if bounds is not None:
            lat, lng = attrs.get("latitude"), attrs.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)) or not (bounds["south"] <= lat <= bounds["north"] and bounds["west"] <= lng <= bounds["east"]): continue
        fallback_observed = _aware(row.updated_at or row.created_at or now)
        observed_at = _search_datetime(attrs.get("observed_at"), fallback_observed)
        ttl_default = 3600 if row.fulfillment_mode == "manual_supplier" else 300
        ttl_seconds = max(30, min(int(attrs.get("freshness_ttl_seconds", ttl_default)), 86400))
        stale = observed_at + timedelta(seconds=ttl_seconds) <= now
        if stale and not data.include_stale: continue
        taxes = max(0, int(attrs.get("taxes", 0) or 0)); fees = max(0, int(attrs.get("fees", 0) or 0)); discounts = max(0, int(attrs.get("discounts", 0) or 0))
        final_price = max(0, row.amount + taxes + fees - discounts)
        entity_id = attrs.get("entity_id") or hashlib.sha256(f"{row.service_type}:{_normalize_search_text(row.title)}:{_normalize_search_text(str(attrs.get('city', '')))}".encode()).hexdigest()[:24]
        result = {"id": row.id, "offer_id": row.id, "entity_id": entity_id, "service_type": row.service_type, "title": row.title, "provider": row.provider_key, "provider_status": "supplier_verified" if row.fulfillment_mode == "manual_supplier" else "provider_required", "last_updated_at": observed_at.isoformat(), "observed_at": observed_at.isoformat(), "availability_checked_at": _search_datetime(attrs.get("availability_checked_at"), observed_at).isoformat(), "price_checked_at": _search_datetime(attrs.get("price_checked_at"), observed_at).isoformat(), "freshness_ttl_seconds": ttl_seconds, "freshness": "stale" if stale else "live", "freshness_state": "STALE" if stale else "LIVE", "amount": row.amount, "base_price": row.amount, "taxes": taxes, "fees": fees, "discounts": discounts, "total_amount": final_price, "final_price": final_price, "currency": row.currency, "available": not stale, "availability_state": "REQUIRES_RECHECK" if stale else "CONFIRMED", "inventory_status": "available" if not stale else "stale_unknown", "available_units": row.available_units if not stale else None, "cancellation_policy": cancellation, "policy_verified": policy.get("verified") is True, "quality_score": attrs.get("quality_score", attrs.get("quality")), "review_score": review_score or None, "location": {key: attrs.get(key) for key in ("city", "province", "latitude", "longitude") if attrs.get(key) is not None}, "attributes": attrs, "valid_until": _aware(row.valid_until).isoformat()}
        breakdown = {"price": round(1000000000 / max(result["total_amount"], 1), 4), "reviews": review_score * 10, "flexibility": 10 if cancellation and cancellation.get("refundable") else 0, "policy": 5 if attrs.get("organization_policy_compliant") else 0, "freshness": 0 if stale else 15, "provider_reliability": float(attrs.get("provider_reliability", 5))}
        result["ranking_breakdown"] = breakdown; result["ranking_score"] = round(sum(breakdown.values()), 4)
        result["ranking_explanation"] = [label for enabled, label in ((not stale, "داده تازه"), (review_score >= 8, "امتیاز کاربران بالا"), (bool(cancellation and cancellation.get("refundable")), "امکان استرداد"), (bool(attrs.get("organization_policy_compliant")), "منطبق با سیاست سازمان")) if enabled]
        results.append(result)
    if data.service_type == "hotel":
        results.extend(_grs_hotel_offers_for_search(tenant_id=user.tenant_id, query=data.query or "", min_price=data.min_price, max_price=data.max_price, min_review_score=data.min_review_score, refundable=data.refundable, instant_booking=data.instant_booking, check_in=data.check_in, check_out=data.check_out, travellers=data.travellers, db=db))
    sorters = {"price_asc": lambda item: (item["total_amount"], -item["ranking_score"]), "price_desc": lambda item: (-item["total_amount"], -item["ranking_score"]), "review_desc": lambda item: (-(item["review_score"] or 0), item["total_amount"]), "freshness": lambda item: (item["freshness"] != "live", item["last_updated_at"]), "recommended": lambda item: (-item["ranking_score"], item["total_amount"])}
    results.sort(key=sorters[data.sort])
    criteria = data.model_dump(); criteria["normalized_query"] = normalized_query; criteria["result_count"] = len(results)
    db.add(operational_models.SearchRequest(tenant_id=user.tenant_id, user_id=user.id, service_type=data.service_type, criteria_json=json.dumps(criteria, sort_keys=True), correlation_id=str(uuid.uuid4())))
    db.commit()
    return results


@app.get("/search/recent")
def recent_searches(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.SearchRequest).where(operational_models.SearchRequest.tenant_id == user.tenant_id, operational_models.SearchRequest.user_id == user.id).order_by(operational_models.SearchRequest.created_at.desc()).limit(10)).all()
    return [{"id": row.id, "service_type": row.service_type, "criteria": json.loads(row.criteria_json), "searched_at": row.created_at.isoformat()} for row in rows]


def _structured_search_intent(data: UnifiedSearchIn) -> dict:
    normalized = _normalize_search_text(data.query or "")
    destination = data.destination
    if not destination:
        for item in _AUTOCOMPLETE_ENTITIES:
            entity_terms = [_normalize_search_text(item["title"]), *[_normalize_search_text(alias) for alias in item.get("aliases", [])]]
            if item["type"] == "city" and any(term in normalized.split() for term in entity_terms):
                destination = item["title"]; break
    numbers = [int(value) for value in re.findall(r"\d+", normalized)]
    travellers = next((value for value in numbers if re.search(rf"{value}\s*(نفر|مسافر)", normalized)), data.travellers)
    nights = next((value for value in numbers if re.search(rf"{value}\s*(شب|روز)", normalized)), None)
    star = next((value for value in range(1, 6) if re.search(rf"{value}\s*ستاره", normalized)), None)
    departure_window = "morning" if "صبح" in normalized else "evening" if "عصر" in normalized else None
    return {"normalized_query": normalized, "origin": data.origin, "destination": destination, "travellers": travellers, "nights": nights, "star_rating": star, "departure_window": departure_window, "flexibility": data.flexibility, "filters": data.filters, "transactional_data_source": "provider_offer_layer"}


@app.post("/search/voice/transcribe")
async def transcribe_voice_search(user: User = Depends(current_user), audio: UploadFile = File(...)) -> dict:
    """Speech-to-text for the natural-language Search entry. Follows the same
    fail-closed provider pattern as every other external integration in this
    app (payment/SMS/OTP/etc.): with no authorized STT credential configured,
    this always returns 503 rather than fabricating a transcript. The client
    falls back to browser SpeechRecognition (optional enhancement) or plain
    text entry, both of which remain fully available. Audio is bounded and
    never persisted, logged, or written to disk -- it is read into memory
    only long enough to enforce the size limit, then discarded.
    """
    from .providers import configured_mode
    max_bytes = 2 * 1024 * 1024
    body = await audio.read(max_bytes + 1)
    too_large = len(body) > max_bytes
    del body
    if too_large:
        raise HTTPException(status_code=413, detail="فایل صوتی بیش از حد مجاز است؛ حداکثر مدت ضبط را رعایت کنید.")
    mode = configured_mode("stt")
    if mode == "sandbox":
        # An authorized STT provider would be called here via the same
        # ResilientAdapter/SandboxAdapter contract used by every other
        # integration; none is configured in this environment.
        pass
    raise HTTPException(status_code=503, detail={"code": "STT_PROVIDER_UNAVAILABLE", "message": "سرویس تبدیل گفتار به متن هنوز متصل نیست؛ لطفاً جمله سفر را تایپ کنید."})


@app.post("/search/v2")
def unified_search(data: UnifiedSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    started = time.perf_counter()
    allowed = re.compile(ECOSYSTEM_SERVICE_PATTERN)
    if any(not allowed.fullmatch(vertical) for vertical in data.verticals):
        raise HTTPException(status_code=422, detail="نوع خدمت معتبر نیست")
    intent = _structured_search_intent(data)
    query = data.destination or intent.get("destination") or data.query
    allowed_filter_keys = {"min_price", "max_price", "min_review_score", "refundable", "amenities", "instant_booking", "map_bounds"}
    safe_filters = {key: value for key, value in data.filters.items() if key in allowed_filter_keys}
    legacy_sort = {"lowest_price": "price_asc", "cheapest": "price_asc", "highest_rated": "review_desc"}.get(data.sort, "recommended")
    offers: list[dict] = []
    for vertical in data.verticals:
        offers.extend(search_offers(OfferSearchIn(service_type=vertical, query=query, flexible_dates=data.flexibility != "exact", sort=legacy_sort, include_stale=data.include_stale, check_in=data.filters.get("check_in"), check_out=data.filters.get("check_out"), travellers=data.travellers, **safe_filters), user, db))
    groups: dict[str, dict] = {}
    for offer in offers:
        group = groups.setdefault(offer["entity_id"], {"entity_id": offer["entity_id"], "title": offer["title"], "service_type": offer["service_type"], "offers": []})
        group["offers"].append(offer)
    entities = []
    for group in groups.values():
        group["offers"].sort(key=lambda item: (item["final_price"], -item["ranking_score"]))
        group["best_offer"] = group["offers"][0]; group["provider_count"] = len({item["provider"] for item in group["offers"]})
        group["ranking_score"] = max(item["ranking_score"] for item in group["offers"]); entities.append(group)
    entity_sorters = {"lowest_price": lambda item: item["best_offer"]["final_price"], "cheapest": lambda item: item["best_offer"]["final_price"], "highest_rated": lambda item: -(item["best_offer"]["review_score"] or 0), "best_location": lambda item: -float(item["best_offer"]["attributes"].get("location_score", 0)), "most_flexible": lambda item: not bool((item["best_offer"].get("cancellation_policy") or {}).get("refundable")), "fastest": lambda item: float(item["best_offer"]["attributes"].get("duration_minutes", 10**9))}
    entities.sort(key=entity_sorters.get(data.sort, lambda item: -item["ranking_score"]))
    offset = (data.page - 1) * data.page_size; page_items = entities[offset:offset + data.page_size]
    recovery = [] if entities else [{"type": "nearby_dates", "message": "تاریخ‌های ±۱ روز را بررسی کنید", "fabricated_price": False}, {"type": "fewer_filters", "message": "برخی فیلترها را حذف کنید", "fabricated_price": False}]
    record_business_event("search", "success" if entities else "zero_result")
    return {"structured_query": intent, "entities": page_items, "pagination": {"page": data.page, "page_size": data.page_size, "total": len(entities)}, "freshness_policy": "provider_and_vertical_specific", "availability_recheck_required_before_checkout": True, "price_recheck_required_before_checkout": True, "zero_result_recovery": recovery, "provider_diagnostics": [{"provider": key, "status": "available", "offer_count": sum(1 for item in offers if item["provider"] == key)} for key in sorted({item["provider"] for item in offers})], "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}


_PUBLIC_SEARCH_TENANT_SLUG = "karenseir-public"
_PUBLIC_SEARCH_IDENTITY_ROLE = "public_search_identity"
_PUBLIC_SAFE_OFFER_KEYS = {"id", "offer_id", "entity_id", "service_type", "title", "provider", "provider_status", "freshness", "freshness_state", "observed_at", "availability_state", "inventory_status", "available", "cancellation_policy", "policy_verified", "review_score", "location", "attributes", "ranking_explanation"}


def _public_search_identity(db: Session) -> User:
    """Anonymous discovery runs as a real, seeded system identity scoped to the
    dedicated public-catalog tenant — never a corporate tenant. If that tenant/
    identity has not been seeded yet, discovery is unavailable (fail closed),
    never silently falls back to a private tenant."""
    tenant = db.scalar(select(Tenant).where(Tenant.slug == _PUBLIC_SEARCH_TENANT_SLUG))
    if tenant is None:
        raise HTTPException(status_code=503, detail="کاتالوگ عمومی هنوز راه‌اندازی نشده است")
    set_tenant_context(db, tenant.id)
    identity = db.scalar(select(User).where(User.tenant_id == tenant.id, User.role == _PUBLIC_SEARCH_IDENTITY_ROLE))
    if identity is None:
        raise HTTPException(status_code=503, detail="کاتالوگ عمومی هنوز راه‌اندازی نشده است")
    return identity


def _project_public_offer(offer: dict) -> dict:
    return {key: value for key, value in offer.items() if key in _PUBLIC_SAFE_OFFER_KEYS}


@app.post("/search/v2/public")
def unified_search_public(data: UnifiedSearchIn, db: Session = Depends(get_db)) -> dict:
    """Anonymous discovery. Reuses the exact Search v2 engine (unified_search) —
    no parallel search implementation — scoped only to the public-catalog tenant,
    then strips negotiated-price/eligibility fields before returning. A corporate
    tenant (e.g. aftab-bank, faraz-industries) is never read by this path."""
    identity = _public_search_identity(db)
    result = unified_search(data, identity, db)
    for entity in result["entities"]:
        entity["offers"] = [_project_public_offer(offer) for offer in entity["offers"]]
        entity["best_offer"] = _project_public_offer(entity["best_offer"])
    result["tenant_data_included"] = False
    return result


@app.post("/search/saved", status_code=status.HTTP_201_CREATED)
def save_search(data: SavedSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    encoded = json.dumps(data.query, sort_keys=True, separators=(",", ":")); query_hash = _secure_hash(encoded)
    row = db.scalar(select(operational_models.SavedSearch).where(operational_models.SavedSearch.tenant_id == user.tenant_id, operational_models.SavedSearch.user_id == user.id, (operational_models.SavedSearch.command_id == data.command_id) | (operational_models.SavedSearch.query_hash == query_hash)))
    if row:
        if row.query_hash != query_hash: raise HTTPException(status_code=409, detail="کلید تکرار برای جست‌وجوی دیگری استفاده شده است")
    else:
        row = operational_models.SavedSearch(tenant_id=user.tenant_id, user_id=user.id, title=data.title, query_json=encoded, query_hash=query_hash, command_id=data.command_id, alert_type=data.alert_type, alert_status="external_blocked" if data.alert_type else "disabled")
        db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="saved_search", aggregate_id=row.id, event_type="search.saved", payload_json=json.dumps({"saved_search_id": row.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit()
    return {"id": row.id, "title": row.title, "query": json.loads(row.query_json), "alert_type": row.alert_type, "alert_status": row.alert_status, "external_delivery": False}


@app.get("/search/saved")
def list_saved_searches(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.SavedSearch).where(operational_models.SavedSearch.tenant_id == user.tenant_id, operational_models.SavedSearch.user_id == user.id).order_by(operational_models.SavedSearch.created_at.desc())).all()
    return [{"id": row.id, "title": row.title, "query": json.loads(row.query_json), "alert_type": row.alert_type, "alert_status": row.alert_status} for row in rows]


@app.delete("/search/saved/{saved_search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(saved_search_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    row = db.scalar(select(operational_models.SavedSearch).where(operational_models.SavedSearch.id == saved_search_id, operational_models.SavedSearch.tenant_id == user.tenant_id, operational_models.SavedSearch.user_id == user.id))
    if row is None: raise HTTPException(status_code=404, detail="جست‌وجوی ذخیره‌شده پیدا نشد")
    db.delete(row); db.commit(); return Response(status_code=204)


@app.post("/search/budget-trips")
def budget_trips(data: BudgetTripIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    results = unified_search(UnifiedSearchIn(verticals=["flight", "hotel", "tour", "package"], origin=data.origin, destination=data.destination, travellers=data.travellers, filters={"max_price": data.budget}, sort="best_value", page_size=100), user, db)
    candidates = [item for item in results["entities"] if item["best_offer"]["final_price"] * data.travellers <= data.budget and item["best_offer"]["freshness_state"] == "LIVE"]
    cheapest = min(candidates, key=lambda item: item["best_offer"]["final_price"], default=None); quality = max(candidates, key=lambda item: item["best_offer"]["quality_score"] or 0, default=None); value = max(candidates, key=lambda item: item["ranking_score"], default=None)
    return {"budget": data.budget, "categories": {"cheapest": cheapest, "best_value": value, "best_quality": quality, "ai_recommended": None}, "bookable_only_with_live_inventory": True, "ai_status": "not_configured"}


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
    attributes = json.loads(offer.attributes_json); final_unit_price = max(0, offer.amount + int(attributes.get("taxes", 0) or 0) + int(attributes.get("fees", 0) or 0) - int(attributes.get("discounts", 0) or 0)); final_total = final_unit_price * data.units
    if data.expected_final_price is not None and data.expected_final_price != final_total:
        raise HTTPException(status_code=409, detail={"code": "PRICE_CHANGED", "old_price": data.expected_final_price, "new_price": final_total, "delta": final_total - data.expected_final_price, "checked_at": now.isoformat()})
    snapshot = {"offer_id": offer.id, "service_type": offer.service_type, "supplier_id": offer.supplier_id, "title": offer.title, "unit_amount": final_unit_price, "units": data.units, "total_amount": final_total, "currency": offer.currency, "policy": json.loads(offer.policy_json), "attributes": attributes, "provider_key": offer.provider_key, "fulfillment_mode": offer.fulfillment_mode, "checked_at": now.isoformat(), "availability_state": "CONFIRMED", "price_state": "RECHECKED"}
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
    attrs = snapshot.get("attributes") or {}
    leisure_session_id = attrs.get("leisure_session_id")
    if leisure_session_id:
        leisure_session = db.scalar(select(operational_models.LeisureSession).where(operational_models.LeisureSession.id == leisure_session_id, operational_models.LeisureSession.tenant_id == user.tenant_id).with_for_update())
        if leisure_session is None or leisure_session.capacity_available < check.units:
            raise HTTPException(status_code=409, detail="ظرفیت این جلسه کافی نیست")
        leisure_session.capacity_available -= check.units
    trip = operational_models.ensure_trip_for_reservation(db, reservation, title=snapshot["title"], destination=attrs.get("city") or attrs.get("destination") or snapshot["title"])
    operational_models.record_trip_event(db, tenant_id=user.tenant_id, trip_id=trip.id, reservation_id=reservation.id, event_key=f"booking-created:{data.command_id}", event_type="booking.created", source="system", title="رزرو ثبت شد", message=f"رزرو {reservation.booking_reference} برای {snapshot['title']} ثبت شد.", deep_link=f"/manage-booking/{reservation.id}")
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
        existing_ticket = db.scalar(select(operational_models.Ticket).where(operational_models.Ticket.tenant_id == user.tenant_id, operational_models.Ticket.reservation_id == reservation.id, operational_models.Ticket.qr_token.isnot(None)))
        return {"reservation": _reservation_output(reservation), "voucher": {"id": existing_voucher.id, "status": existing_voucher.status, "revision": existing_voucher.revision}, "admission_ticket": ({"id": existing_ticket.id, "status": existing_ticket.status, "qr_token": existing_ticket.qr_token} if existing_ticket else None)}
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
    leisure_session_id = (item_snapshot.get("attributes") or {}).get("leisure_session_id")
    admission_ticket = None
    if leisure_session_id:
        admission_ticket = operational_models.Ticket(tenant_id=user.tenant_id, reservation_id=reservation.id, status="issued", leisure_session_id=leisure_session_id, qr_token=secrets.token_urlsafe(32))
        db.add(admission_ticket); db.flush()
        db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="ticket", aggregate_id=admission_ticket.id, event_type="admission_ticket.issued", payload_json=json.dumps({"reservation_id": reservation.id, "ticket_id": admission_ticket.id}), correlation_id=str(uuid.uuid4()), idempotency_key=f"{data.command_id}:ticket"))
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="voucher", aggregate_id=voucher.id, event_type="voucher.issued", payload_json=json.dumps({"reservation_id": reservation.id, "voucher_id": voucher.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id))
    invoice = _issue_invoice_for_reservation(db, reservation=reservation, tenant_id=user.tenant_id, actor_user_id=user.id, command_id=f"auto-invoice:{data.command_id}"[:120])
    db.commit(); record_business_event("booking", "issued")
    return {"reservation": _reservation_output(reservation), "voucher": {"id": voucher.id, "status": voucher.status, "revision": voucher.revision}, "invoice": _invoice_output(invoice) if invoice else None, "admission_ticket": ({"id": admission_ticket.id, "status": admission_ticket.status, "qr_token": admission_ticket.qr_token} if admission_ticket else None)}


def _leisure_place_output(place) -> dict:
    return {"id": place.id, "supplier_id": place.supplier_id, "name": place.name, "slug": place.slug, "place_type": place.place_type, "category": place.category, "city": place.city, "address": place.address, "latitude": float(place.latitude) if place.latitude is not None else None, "longitude": float(place.longitude) if place.longitude is not None else None, "opening_hours": json.loads(place.opening_hours_json), "amenities": json.loads(place.amenities_json), "rules": json.loads(place.rules_json), "media": json.loads(place.media_json), "status": place.status}


def _leisure_product_output(product) -> dict:
    return {"id": product.id, "place_id": product.place_id, "supplier_id": product.supplier_id, "service_type": product.service_type, "subtype": product.subtype, "title": product.title, "description": product.description, "duration_minutes": product.duration_minutes, "booking_mode": product.booking_mode, "cancellation_policy": json.loads(product.cancellation_policy_json), "restrictions": json.loads(product.restrictions_json), "status": product.status}


def _leisure_session_output(session) -> dict:
    return {"id": session.id, "experience_product_id": session.experience_product_id, "starts_at": session.starts_at.isoformat(), "ends_at": session.ends_at.isoformat(), "sales_start_at": session.sales_start_at.isoformat() if session.sales_start_at else None, "sales_end_at": session.sales_end_at.isoformat() if session.sales_end_at else None, "capacity_total": session.capacity_total, "capacity_available": session.capacity_available, "status": session.status, "restrictions": json.loads(session.restrictions_json)}


def _leisure_ticket_type_output(row) -> dict:
    return {"id": row.id, "code": row.code, "label": row.label, "price": row.price, "currency": row.currency, "quota": row.quota, "min_age": row.min_age, "max_age": row.max_age, "restrictions": json.loads(row.restrictions_json), "active": row.active}


def _sync_leisure_session_offer(db: Session, *, tenant_id: int, product: "operational_models.ExperienceProduct", place: "operational_models.Place", session: "operational_models.LeisureSession") -> None:
    """Keep a session's backing generic Offer row (searchable via the
    existing, unmodified unified_search/search_offers engine) in sync with
    its real ticket types and remaining capacity. One Offer per session;
    sessions of the same product share entity_id so search groups them."""
    ticket_types = db.scalars(select(operational_models.LeisureTicketType).where(operational_models.LeisureTicketType.tenant_id == tenant_id, operational_models.LeisureTicketType.experience_product_id == product.id, operational_models.LeisureTicketType.active.is_(True))).all()
    now = datetime.now(timezone.utc)
    sellable = session.status == "active" and session.capacity_available > 0 and _aware(session.ends_at) > now and (session.sales_start_at is None or _aware(session.sales_start_at) <= now) and (session.sales_end_at is None or _aware(session.sales_end_at) > now)
    from_price = min((t.price for t in ticket_types), default=0)
    attrs = {"entity_id": f"leisure-product:{product.id}", "leisure_place_id": place.id, "leisure_product_id": product.id, "leisure_session_id": session.id, "place_type": place.place_type, "booking_mode": product.booking_mode, "subtype": product.subtype, "city": place.city, "address": place.address, "latitude": float(place.latitude) if place.latitude is not None else None, "longitude": float(place.longitude) if place.longitude is not None else None, "session_starts_at": session.starts_at.isoformat(), "session_ends_at": session.ends_at.isoformat(), "ticket_types": [_leisure_ticket_type_output(t) for t in ticket_types], "amenities": json.loads(place.amenities_json), "observed_at": now.isoformat()}
    policy = json.loads(product.cancellation_policy_json or "{}")
    status = "active" if (sellable and ticket_types) else "draft"
    if session.offer_id:
        offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == session.offer_id, operational_models.Offer.tenant_id == tenant_id).with_for_update())
    else:
        offer = None
    if offer is None:
        offer = operational_models.Offer(tenant_id=tenant_id, supplier_id=product.supplier_id, service_type=product.service_type, title=f"{product.title} · {place.city}", amount=from_price, currency=(ticket_types[0].currency if ticket_types else "IRR"), available_units=max(0, session.capacity_available), status=status, provider_key="manual_supplier", fulfillment_mode="manual_supplier", attributes_json=json.dumps(attrs, sort_keys=True), policy_json=json.dumps(policy, sort_keys=True), valid_until=session.ends_at)
        db.add(offer); db.flush(); session.offer_id = offer.id
    else:
        offer.amount = from_price; offer.available_units = max(0, session.capacity_available); offer.status = status; offer.attributes_json = json.dumps(attrs, sort_keys=True); offer.policy_json = json.dumps(policy, sort_keys=True); offer.valid_until = session.ends_at; offer.title = f"{product.title} · {place.city}"


def _apply_leisure_pricing_rule(db: Session, *, tenant_id: int, service_type: str, organization_id: Optional[str], base_amount: int) -> tuple[int, Optional[dict]]:
    """Wire the existing (previously unwired) PricingRule model into leisure
    pricing. No discount is invented here: this only applies a rule an admin
    has explicitly configured for this tenant/service_type/organization."""
    if organization_id is None:
        return base_amount, None
    rule = db.scalar(select(operational_models.PricingRule).where(operational_models.PricingRule.tenant_id == tenant_id, operational_models.PricingRule.status == "active", operational_models.PricingRule.service_type == service_type))
    if rule is None:
        rule = db.scalar(select(operational_models.PricingRule).where(operational_models.PricingRule.tenant_id == tenant_id, operational_models.PricingRule.status == "active", operational_models.PricingRule.service_type.is_(None)))
    if rule is None:
        return base_amount, None
    config = json.loads(rule.configuration_json or "{}")
    if config.get("scope") == "organization" and config.get("organization_id") not in (None, organization_id):
        return base_amount, None
    discount_type, discount_value = config.get("discount_type"), config.get("discount_value")
    if discount_type == "percent" and isinstance(discount_value, (int, float)) and 0 < discount_value <= 100:
        return max(0, base_amount - int(base_amount * discount_value / 100)), {"rule_id": rule.id, "discount_type": "percent", "discount_value": discount_value}
    if discount_type == "fixed" and isinstance(discount_value, (int, float)) and discount_value > 0:
        return max(0, base_amount - int(discount_value)), {"rule_id": rule.id, "discount_type": "fixed", "discount_value": discount_value}
    return base_amount, None


@app.post("/supplier/places", status_code=201)
def create_place(data: PlaceIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    supplier = db.scalar(select(operational_models.Supplier).where(operational_models.Supplier.id == data.supplier_id, operational_models.Supplier.tenant_id == user.tenant_id, operational_models.Supplier.status == "active"))
    if supplier is None: raise HTTPException(409, "تأمین‌کننده فعال وجود ندارد")
    row = operational_models.Place(tenant_id=user.tenant_id, supplier_id=supplier.id, name=data.name, slug=data.slug, place_type=data.place_type, category=data.category, city=data.city, address=data.address, latitude=data.latitude, longitude=data.longitude, opening_hours_json=json.dumps(data.opening_hours, sort_keys=True), amenities_json=json.dumps(data.amenities, sort_keys=True), rules_json=json.dumps(data.rules, sort_keys=True), media_json=json.dumps(data.media, sort_keys=True), status="published")
    db.add(row); db.commit()
    return _leisure_place_output(row)


@app.get("/places/{place_id}")
def place_detail(place_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Place).where(operational_models.Place.id == place_id, operational_models.Place.tenant_id == user.tenant_id, operational_models.Place.status == "published"))
    if row is None: raise HTTPException(404, "مکان وجود ندارد")
    return _leisure_place_output(row)


@app.post("/supplier/places/{place_id}/experience-products", status_code=201)
def create_experience_product(place_id: str, data: ExperienceProductIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    place = db.scalar(select(operational_models.Place).where(operational_models.Place.id == place_id, operational_models.Place.tenant_id == user.tenant_id))
    if place is None: raise HTTPException(404, "مکان در این tenant وجود ندارد")
    row = operational_models.ExperienceProduct(tenant_id=user.tenant_id, place_id=place.id, supplier_id=place.supplier_id, service_type=data.service_type, subtype=data.subtype, title=data.title, description=data.description, duration_minutes=data.duration_minutes, booking_mode=data.booking_mode, cancellation_policy_json=json.dumps(data.cancellation_policy, sort_keys=True), restrictions_json=json.dumps(data.restrictions, sort_keys=True), status="published")
    db.add(row); db.commit()
    return _leisure_product_output(row)


@app.post("/supplier/experience-products/{product_id}/ticket-types", status_code=201)
def create_leisure_ticket_type(product_id: str, data: LeisureTicketTypeIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    product = db.scalar(select(operational_models.ExperienceProduct).where(operational_models.ExperienceProduct.id == product_id, operational_models.ExperienceProduct.tenant_id == user.tenant_id))
    if product is None: raise HTTPException(404, "محصول در این tenant وجود ندارد")
    if data.min_age is not None and data.max_age is not None and data.min_age > data.max_age: raise HTTPException(422, "بازه سنی معتبر نیست")
    row = operational_models.LeisureTicketType(tenant_id=user.tenant_id, experience_product_id=product.id, code=data.code, label=data.label, price=data.price, currency=data.currency, quota=data.quota, min_age=data.min_age, max_age=data.max_age, restrictions_json=json.dumps(data.restrictions, sort_keys=True), active=data.active)
    db.add(row); db.flush()
    place = db.scalar(select(operational_models.Place).where(operational_models.Place.id == product.place_id, operational_models.Place.tenant_id == user.tenant_id))
    sessions = db.scalars(select(operational_models.LeisureSession).where(operational_models.LeisureSession.tenant_id == user.tenant_id, operational_models.LeisureSession.experience_product_id == product.id)).all()
    for session in sessions: _sync_leisure_session_offer(db, tenant_id=user.tenant_id, product=product, place=place, session=session)
    db.commit()
    return _leisure_ticket_type_output(row)


@app.post("/supplier/experience-products/{product_id}/sessions", status_code=201)
def create_leisure_session(product_id: str, data: LeisureSessionIn, user: User = Depends(require_permission("inventory:manage")), db: Session = Depends(get_db)) -> dict:
    product = db.scalar(select(operational_models.ExperienceProduct).where(operational_models.ExperienceProduct.id == product_id, operational_models.ExperienceProduct.tenant_id == user.tenant_id))
    if product is None: raise HTTPException(404, "محصول در این tenant وجود ندارد")
    if _aware(data.ends_at) <= _aware(data.starts_at): raise HTTPException(422, "بازه زمانی جلسه معتبر نیست")
    place = db.scalar(select(operational_models.Place).where(operational_models.Place.id == product.place_id, operational_models.Place.tenant_id == user.tenant_id))
    row = operational_models.LeisureSession(tenant_id=user.tenant_id, experience_product_id=product.id, starts_at=data.starts_at, ends_at=data.ends_at, sales_start_at=data.sales_start_at, sales_end_at=data.sales_end_at, capacity_total=data.capacity_total, capacity_available=data.capacity_total, restrictions_json=json.dumps(data.restrictions, sort_keys=True))
    db.add(row); db.flush()
    _sync_leisure_session_offer(db, tenant_id=user.tenant_id, product=product, place=place, session=row)
    db.commit()
    return _leisure_session_output(row)


@app.get("/experience-products/{product_id}")
def experience_product_detail(product_id: str, date: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    product = db.scalar(select(operational_models.ExperienceProduct).where(operational_models.ExperienceProduct.id == product_id, operational_models.ExperienceProduct.tenant_id == user.tenant_id, operational_models.ExperienceProduct.status == "published"))
    if product is None: raise HTTPException(404, "محصول وجود ندارد")
    place = db.scalar(select(operational_models.Place).where(operational_models.Place.id == product.place_id, operational_models.Place.tenant_id == user.tenant_id))
    now = datetime.now(timezone.utc)
    query = select(operational_models.LeisureSession).where(operational_models.LeisureSession.tenant_id == user.tenant_id, operational_models.LeisureSession.experience_product_id == product.id, operational_models.LeisureSession.status == "active", operational_models.LeisureSession.ends_at > now)
    if date:
        try:
            day = datetime.fromisoformat(date).date()
        except ValueError:
            raise HTTPException(422, "تاریخ معتبر نیست")
        query = query.where(func.date(operational_models.LeisureSession.starts_at) == day)
    sessions = db.scalars(query.order_by(operational_models.LeisureSession.starts_at)).all()
    ticket_types = db.scalars(select(operational_models.LeisureTicketType).where(operational_models.LeisureTicketType.tenant_id == user.tenant_id, operational_models.LeisureTicketType.experience_product_id == product.id, operational_models.LeisureTicketType.active.is_(True))).all()
    return {"place": _leisure_place_output(place) if place else None, "product": _leisure_product_output(product), "sessions": [_leisure_session_output(s) for s in sessions], "ticket_types": [_leisure_ticket_type_output(t) for t in ticket_types]}


@app.post("/leisure-sessions/{session_id}/price-check", status_code=201)
def leisure_session_price_check(session_id: str, data: LeisureSessionPriceCheckIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(operational_models.PriceCheck).where(operational_models.PriceCheck.tenant_id == user.tenant_id, operational_models.PriceCheck.command_id == data.command_id))
    if existing:
        snapshot = json.loads(existing.snapshot_json)
        if snapshot.get("leisure_session_id") != session_id:
            raise HTTPException(409, "کلید تکرار برای درخواست دیگری استفاده شده است")
        return {"id": existing.id, "offer_id": existing.offer_id, "amount": existing.amount, "currency": existing.currency, "expires_at": existing.expires_at.isoformat(), "ticket_breakdown": snapshot.get("ticket_breakdown", [])}
    session = db.scalar(select(operational_models.LeisureSession).where(operational_models.LeisureSession.id == session_id, operational_models.LeisureSession.tenant_id == user.tenant_id, operational_models.LeisureSession.status == "active").with_for_update())
    now = datetime.now(timezone.utc)
    if session is None or _aware(session.ends_at) <= now: raise HTTPException(409, "جلسه معتبر نیست")
    if session.sales_start_at is not None and _aware(session.sales_start_at) > now: raise HTTPException(409, "فروش این جلسه هنوز آغاز نشده است")
    if session.sales_end_at is not None and _aware(session.sales_end_at) <= now: raise HTTPException(409, "فروش این جلسه به پایان رسیده است")
    product = db.scalar(select(operational_models.ExperienceProduct).where(operational_models.ExperienceProduct.id == session.experience_product_id, operational_models.ExperienceProduct.tenant_id == user.tenant_id))
    if product is None or product.status != "published": raise HTTPException(409, "محصول معتبر نیست")
    place = db.scalar(select(operational_models.Place).where(operational_models.Place.id == product.place_id, operational_models.Place.tenant_id == user.tenant_id))
    if session.offer_id is None: raise HTTPException(409, "این جلسه هنوز قابل فروش نیست")
    offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == session.offer_id, operational_models.Offer.tenant_id == user.tenant_id, operational_models.Offer.status == "active"))
    if offer is None: raise HTTPException(409, "این جلسه هنوز قابل فروش نیست")
    ticket_type_rows = {row.id: row for row in db.scalars(select(operational_models.LeisureTicketType).where(operational_models.LeisureTicketType.tenant_id == user.tenant_id, operational_models.LeisureTicketType.experience_product_id == product.id, operational_models.LeisureTicketType.active.is_(True)))}
    total_units, base_amount, breakdown, seen_codes = 0, 0, [], set()
    for selection in data.selections:
        ticket_type = ticket_type_rows.get(selection.ticket_type_id)
        if ticket_type is None: raise HTTPException(422, "نوع بلیت معتبر نیست")
        if ticket_type.code in seen_codes: raise HTTPException(422, "هر نوع بلیت فقط یک‌بار در انتخاب مجاز است")
        seen_codes.add(ticket_type.code)
        if ticket_type.quota is not None and selection.quantity > ticket_type.quota: raise HTTPException(409, "سهمیه این نوع بلیت کافی نیست")
        total_units += selection.quantity; base_amount += ticket_type.price * selection.quantity
        breakdown.append({"ticket_type_id": ticket_type.id, "code": ticket_type.code, "label": ticket_type.label, "unit_price": ticket_type.price, "quantity": selection.quantity, "subtotal": ticket_type.price * selection.quantity})
    if total_units == 0: raise HTTPException(422, "حداقل یک بلیت باید انتخاب شود")
    if total_units > session.capacity_available: raise HTTPException(409, "ظرفیت این جلسه کافی نیست")
    organization_id = data.organization_id
    if organization_id is not None:
        membership = db.scalar(select(operational_models.Membership).where(operational_models.Membership.tenant_id == user.tenant_id, operational_models.Membership.user_id == user.id, operational_models.Membership.organization_id == organization_id))
        if membership is None: raise HTTPException(403, "کاربر عضو این سازمان نیست")
    final_amount, applied_rule = _apply_leisure_pricing_rule(db, tenant_id=user.tenant_id, service_type=product.service_type, organization_id=organization_id, base_amount=base_amount)
    attrs = json.loads(offer.attributes_json)
    snapshot_attrs = {**attrs, "leisure_session_id": session.id, "leisure_product_id": product.id, "ticket_breakdown": breakdown, "organization_id": organization_id, "applied_pricing_rule": applied_rule}
    snapshot = {"offer_id": offer.id, "service_type": product.service_type, "supplier_id": product.supplier_id, "title": f"{product.title} · {place.city if place else ''}", "unit_amount": None, "units": total_units, "total_amount": final_amount, "currency": offer.currency, "policy": json.loads(product.cancellation_policy_json or "{}"), "attributes": snapshot_attrs, "provider_key": offer.provider_key, "fulfillment_mode": offer.fulfillment_mode, "checked_at": now.isoformat(), "availability_state": "CONFIRMED", "price_state": "RECHECKED", "leisure_session_id": session.id, "ticket_breakdown": breakdown}
    encoded = json.dumps(snapshot, sort_keys=True)
    expires_at = now + timedelta(minutes=10)
    if session.sales_end_at is not None: expires_at = min(expires_at, _aware(session.sales_end_at))
    row = operational_models.PriceCheck(tenant_id=user.tenant_id, offer_id=offer.id, user_id=user.id, command_id=data.command_id, amount=final_amount, currency=offer.currency, units=total_units, snapshot_json=encoded, snapshot_hash=_secure_hash(encoded), expires_at=expires_at)
    db.add(row); db.commit()
    return {"id": row.id, "offer_id": row.offer_id, "amount": row.amount, "currency": row.currency, "expires_at": row.expires_at.isoformat(), "ticket_breakdown": breakdown, "applied_pricing_rule": applied_rule}


@app.get("/reservations/{reservation_id}/admission-tickets")
def list_admission_tickets(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id))
    if reservation is None: raise HTTPException(404, "رزرو در این حساب وجود ندارد")
    rows = db.scalars(select(operational_models.Ticket).where(operational_models.Ticket.tenant_id == user.tenant_id, operational_models.Ticket.reservation_id == reservation.id, operational_models.Ticket.qr_token.isnot(None))).all()
    return {"items": [{"id": r.id, "status": r.status, "qr_token": r.qr_token, "redeemed_at": r.redeemed_at.isoformat() if r.redeemed_at else None} for r in rows]}


@app.get("/admission-tickets/validate")
def validate_admission_ticket(qr_token: str = Query(min_length=16, max_length=64), user: User = Depends(require_permission("reservation:fulfill")), db: Session = Depends(get_db)) -> dict:
    ticket = db.scalar(select(operational_models.Ticket).where(operational_models.Ticket.tenant_id == user.tenant_id, operational_models.Ticket.qr_token == qr_token))
    if ticket is None: raise HTTPException(404, "بلیت معتبر نیست")
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == ticket.reservation_id, operational_models.Reservation.tenant_id == user.tenant_id))
    session = db.scalar(select(operational_models.LeisureSession).where(operational_models.LeisureSession.id == ticket.leisure_session_id, operational_models.LeisureSession.tenant_id == user.tenant_id)) if ticket.leisure_session_id else None
    now = datetime.now(timezone.utc)
    expired = session is not None and _aware(session.ends_at) <= now
    return {"id": ticket.id, "status": ticket.status, "reservation_status": reservation.status if reservation else None, "session": _leisure_session_output(session) if session else None, "redeemable": ticket.status == "issued" and reservation is not None and reservation.status == "issued" and not expired, "redeemed_at": ticket.redeemed_at.isoformat() if ticket.redeemed_at else None}


@app.post("/admission-tickets/redeem")
def redeem_admission_ticket(data: AdmissionTicketRedeemIn, user: User = Depends(require_permission("reservation:fulfill")), db: Session = Depends(get_db)) -> dict:
    ticket = db.scalar(select(operational_models.Ticket).where(operational_models.Ticket.tenant_id == user.tenant_id, operational_models.Ticket.qr_token == data.qr_token).with_for_update())
    if ticket is None: raise HTTPException(404, "بلیت معتبر نیست")
    if ticket.status == "used":
        raise HTTPException(409, detail={"code": "ALREADY_REDEEMED", "redeemed_at": ticket.redeemed_at.isoformat() if ticket.redeemed_at else None, "redeemed_by": ticket.redeemed_by})
    if ticket.status in ("cancelled", "expired"):
        raise HTTPException(409, detail={"code": f"TICKET_{ticket.status.upper()}"})
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == ticket.reservation_id, operational_models.Reservation.tenant_id == user.tenant_id))
    if reservation is None or reservation.status != "issued":
        raise HTTPException(409, "وضعیت رزرو اجازه ورود نمی‌دهد")
    now = datetime.now(timezone.utc)
    if ticket.leisure_session_id:
        session = db.scalar(select(operational_models.LeisureSession).where(operational_models.LeisureSession.id == ticket.leisure_session_id, operational_models.LeisureSession.tenant_id == user.tenant_id))
        if session is not None and _aware(session.ends_at) <= now:
            ticket.status = "expired"; db.commit()
            raise HTTPException(409, detail={"code": "TICKET_EXPIRED"})
    ticket.status = "used"; ticket.redeemed_at = now; ticket.redeemed_by = user.id
    db.commit()
    return {"id": ticket.id, "status": ticket.status, "redeemed_at": ticket.redeemed_at.isoformat(), "redeemed_by": ticket.redeemed_by}


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
        vertical_fields = {key: attrs.get(key) for key in ({"room","breakfast","review","amenities","provider","location"} if row.service_type == "hotel" else {"airline","baggage","stops","departure","arrival","duration","refundability"} if row.service_type == "flight" else {"operator","class","departure","arrival","facilities","refund_rules"} if row.service_type == "train" else {"duration","transport","hotel","meals","guide","cancellation"}) if attrs.get(key) is not None}
        results.append({"offer_id": row.id, "service_type": row.service_type, "title": row.title, "amount": row.amount, "currency": row.currency, "score": round(sum(breakdown.values()), 2), "breakdown": breakdown, "vertical_fields": vertical_fields, "awards": [], "explanation": [key for key, value in breakdown.items() if value > 0], "valid_until": row.valid_until.isoformat()})
    results.sort(key=lambda item: (-item["score"], item["amount"]))
    award_rules = {"Best Price": lambda item: (-item["amount"], item["offer_id"]), "Best Value": lambda item: (item["score"], item["offer_id"]), "Best Quality": lambda item: (item["breakdown"]["quality"], item["offer_id"]), "Best Flexible": lambda item: (item["breakdown"]["cancellation"], item["offer_id"]), "Best Location": lambda item: (item["breakdown"]["location"], item["offer_id"]), "Recommended": lambda item: (item["score"], item["offer_id"])}
    for award, selector in award_rules.items(): max(results, key=selector)["awards"].append(award)
    comparison_id = str(uuid.uuid4()); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="comparison", aggregate_id=comparison_id, event_type="comparison.scored", payload_json=json.dumps({"service_type": rows[0].service_type, "offer_ids": sorted(data.offer_ids), "award_logic": "deterministic-v1"}, sort_keys=True), correlation_id=comparison_id, idempotency_key=f"comparison:{comparison_id}")); db.commit()
    return {"comparison_id": comparison_id, "service_type": rows[0].service_type, "authoritative": True, "award_logic": "deterministic-v1", "results": results}


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
    reservations = db.scalars(select(operational_models.Reservation).where(operational_models.Reservation.tenant_id == user.tenant_id).order_by(operational_models.Reservation.created_at.desc()).limit(50)).all(); invoiced = set(db.scalars(select(operational_models.Invoice.reservation_id).where(operational_models.Invoice.tenant_id == user.tenant_id)).all())
    cases = db.scalars(select(operational_models.SupportCase).where(operational_models.SupportCase.tenant_id == user.tenant_id).order_by(operational_models.SupportCase.created_at.desc()).limit(50)).all()
    return {"tenant_id": user.tenant_id, "counts": {"users": count(User), "suppliers": count(operational_models.Supplier), "agencies": count(operational_models.Agency), "reservations": count(operational_models.Reservation), "payments": count(operational_models.PaymentIntent), "refunds": count(operational_models.RefundRecord), "wallets": count(operational_models.Wallet), "notifications": count(operational_models.NotificationRecord), "security_events": count(operational_models.AuthenticationAudit), "invoices": count(operational_models.Invoice), "support_cases": count(operational_models.SupportCase)}, "providers": provider_health, "suppliers": [{"id": row.id, "name": row.display_name, "type": row.supplier_type, "status": row.status} for row in suppliers], "reservations": [{**_reservation_output(row), "can_issue_invoice": row.status in {"confirmed", "issued", "completed"} and row.id not in invoiced} for row in reservations], "support_cases": [{"id": row.id, "subject": row.subject, "status": row.status, "priority": row.priority, "assigned_to_user_id": row.assigned_to_user_id} for row in cases]}


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
    installments = db.scalars(select(operational_models.InstallmentAgreement).where(operational_models.InstallmentAgreement.tenant_id == user.tenant_id).order_by(operational_models.InstallmentAgreement.created_at.desc())).all()
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
        "settlements": {"count": len(settlements), "pending_amount": sum(item.amount for item in settlements if item.status == "pending"), "completed_amount": sum(item.amount for item in settlements if item.status == "completed"), "records": [{"id": item.id, "reservation_id": item.reservation_id, "supplier_id": item.supplier_id, "amount": item.amount, "currency": item.currency, "status": item.status} for item in settlements]},
        "installments": [_installment_output(item) for item in installments],
        "summary": {"payment_count": len(payments), "refund_count": len(refunds), "discrepancy_count": discrepancy_count, "status": "needs_review" if discrepancy_count else "balanced"},
    }


def _invoice_output(row: operational_models.Invoice) -> dict:
    return {"id": row.id, "reservation_id": row.reservation_id, "invoice_number": row.invoice_number, "subtotal_amount": row.subtotal_amount, "tax_amount": row.tax_amount, "total_amount": row.total_amount, "currency": row.currency, "status": row.status, "snapshot": json.loads(row.snapshot_json), "issued_at": row.issued_at.isoformat()}


@app.get("/me/invoices")
def my_invoices(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.Invoice).where(operational_models.Invoice.tenant_id == user.tenant_id, operational_models.Invoice.user_id == user.id).order_by(operational_models.Invoice.issued_at.desc())).all()
    return [_invoice_output(row) for row in rows]


def _invoice_tax_policy() -> tuple[int, str]:
    raw_bps = os.getenv("INVOICE_TAX_BPS")
    reference = os.getenv("INVOICE_TAX_POLICY_REFERENCE", "").strip()
    if raw_bps is None:
        if ENVIRONMENT == "production":
            raise HTTPException(status_code=503, detail="سیاست مالیاتی صورتحساب پیکربندی نشده است")
        return 0, "development:not_configured"
    try:
        bps = int(raw_bps)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="پیکربندی نرخ مالیات صورتحساب نامعتبر است") from exc
    if bps < 0 or bps > 10_000 or not reference:
        raise HTTPException(status_code=503, detail="نرخ یا مرجع سیاست مالیاتی صورتحساب نامعتبر است")
    return bps, reference


def _issue_invoice_for_reservation(db: Session, *, reservation: "operational_models.Reservation", tenant_id: int, actor_user_id: int, command_id: str) -> Optional["operational_models.Invoice"]:
    """Shared by the manual invoice:manage endpoint and the automatic issuance on
    fulfillment. Returns None (does not raise) when the reservation isn't invoice-
    ready or has no valid final IRR price yet - callers that need a hard failure
    (the manual endpoint) raise on a None result themselves."""
    prior = db.scalar(select(operational_models.Invoice).where(operational_models.Invoice.tenant_id == tenant_id, operational_models.Invoice.command_id == command_id))
    if prior:
        return prior
    if reservation.status not in {"confirmed", "issued", "completed"}:
        return None
    try:
        snapshot = json.loads(reservation.price_snapshot_json); subtotal = int(snapshot["total_amount"]); currency = str(snapshot.get("currency", "IRR"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if subtotal <= 0 or currency != "IRR":
        return None
    tax_bps, tax_reference = _invoice_tax_policy(); tax_amount = subtotal * tax_bps // 10_000; total_amount = subtotal + tax_amount
    number = f"KSI-{tenant_id}-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}"
    row = operational_models.Invoice(tenant_id=tenant_id, reservation_id=reservation.id, user_id=reservation.user_id, invoice_number=number, command_id=command_id, subtotal_amount=subtotal, tax_amount=tax_amount, total_amount=total_amount, currency=currency, snapshot_json=json.dumps({"reservation": _reservation_output(reservation), "tax_bps": tax_bps, "tax_policy_reference": tax_reference, "issued_by": actor_user_id}, sort_keys=True))
    db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=tenant_id, aggregate_type="invoice", aggregate_id=row.id, event_type="invoice.issued", payload_json=json.dumps({"invoice_id": row.id, "reservation_id": reservation.id}), correlation_id=str(uuid.uuid4()), idempotency_key=command_id))
    return row


@app.post("/reservations/{reservation_id}/invoice", status_code=status.HTTP_201_CREATED)
def issue_invoice(reservation_id: str, user: User = Depends(require_permission("invoice:manage")), db: Session = Depends(get_db), idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
    prior = db.scalar(select(operational_models.Invoice).where(operational_models.Invoice.tenant_id == user.tenant_id, operational_models.Invoice.command_id == idempotency_key))
    if prior:
        if prior.reservation_id != reservation_id: raise HTTPException(status_code=409, detail="کلید تکرار برای رزرو دیگری استفاده شده است")
        return _invoice_output(prior)
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id).with_for_update())
    if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این tenant وجود ندارد")
    if reservation.status not in {"confirmed", "issued", "completed"}: raise HTTPException(status_code=409, detail="رزرو هنوز شرایط صدور صورتحساب را ندارد")
    try: snapshot = json.loads(reservation.price_snapshot_json); subtotal = int(snapshot["total_amount"]); currency = str(snapshot.get("currency", "IRR"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError): raise HTTPException(status_code=409, detail="قیمت معتبر برای صورتحساب وجود ندارد")
    if subtotal <= 0 or currency != "IRR": raise HTTPException(status_code=409, detail="مبلغ معتبر ریالی برای صورتحساب وجود ندارد")
    row = _issue_invoice_for_reservation(db, reservation=reservation, tenant_id=user.tenant_id, actor_user_id=user.id, command_id=idempotency_key)
    if row is None: raise HTTPException(status_code=409, detail="صدور صورتحساب برای این رزرو ممکن نیست")
    db.commit(); return _invoice_output(row)


def _case_output(row: operational_models.SupportCase, messages: list[operational_models.SupportThreadMessage]) -> dict:
    return {"id": row.id, "reservation_id": row.reservation_id, "trip_id": row.trip_id, "subject": row.subject, "status": row.status, "priority": row.priority, "assigned_to_user_id": row.assigned_to_user_id, "messages": [{"id": item.id, "sender_type": item.sender_type, "body": item.body, "created_at": item.created_at.isoformat()} for item in messages]}


@app.get("/support/cases")
def support_cases(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    query = select(operational_models.SupportCase).where(operational_models.SupportCase.tenant_id == user.tenant_id)
    if not role_has_permission(user.role, "support:manage"): query = query.where(operational_models.SupportCase.user_id == user.id)
    rows = db.scalars(query.order_by(operational_models.SupportCase.created_at.desc())).all(); result = []
    for row in rows:
        messages = db.scalars(select(operational_models.SupportThreadMessage).where(operational_models.SupportThreadMessage.tenant_id == user.tenant_id, operational_models.SupportThreadMessage.case_id == row.id).order_by(operational_models.SupportThreadMessage.created_at)).all(); result.append(_case_output(row, messages))
    return result


@app.post("/support/cases", status_code=status.HTTP_201_CREATED)
def create_support_case(data: SupportCaseIn, user: User = Depends(current_user), db: Session = Depends(get_db), idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
    _owned_support_scope(db, user, data.reservation_id, data.trip_id)
    prior = db.scalar(select(operational_models.SupportCase).where(operational_models.SupportCase.tenant_id == user.tenant_id, operational_models.SupportCase.command_id == idempotency_key))
    if prior:
        if prior.user_id != user.id or prior.reservation_id != data.reservation_id or prior.trip_id != data.trip_id or prior.subject != data.subject.strip(): raise HTTPException(status_code=409, detail="کلید تکرار برای پرونده دیگری استفاده شده است")
        messages = db.scalars(select(operational_models.SupportThreadMessage).where(operational_models.SupportThreadMessage.tenant_id == user.tenant_id, operational_models.SupportThreadMessage.case_id == prior.id).order_by(operational_models.SupportThreadMessage.created_at)).all(); return _case_output(prior, messages)
    row = operational_models.SupportCase(tenant_id=user.tenant_id, user_id=user.id, reservation_id=data.reservation_id, trip_id=data.trip_id, subject=data.subject.strip(), priority=data.priority, command_id=idempotency_key)
    db.add(row); db.flush(); message = operational_models.SupportThreadMessage(tenant_id=user.tenant_id, case_id=row.id, sender_type="customer", sender_user_id=user.id, body=data.body.strip()); db.add(message)
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="support_case", aggregate_id=row.id, event_type="support.case.opened", payload_json=json.dumps({"case_id": row.id, "priority": row.priority}), correlation_id=str(uuid.uuid4()), idempotency_key=idempotency_key)); db.commit(); return _case_output(row, [message])


@app.post("/support/cases/{case_id}/human-replies", status_code=status.HTTP_201_CREATED)
def human_support_reply(case_id: str, data: SupportReplyIn, user: User = Depends(require_permission("support:manage")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.SupportCase).where(operational_models.SupportCase.id == case_id, operational_models.SupportCase.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="پرونده پشتیبانی در این tenant وجود ندارد")
    if row.status == "closed": raise HTTPException(status_code=409, detail="پرونده بسته قابل پاسخ نیست")
    message = operational_models.SupportThreadMessage(tenant_id=user.tenant_id, case_id=row.id, sender_type="human_agent", sender_user_id=user.id, body=data.body.strip()); row.status = "in_progress"; row.assigned_to_user_id = row.assigned_to_user_id or user.id; db.add(message); db.flush()
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="support_case", aggregate_id=row.id, event_type="support.human_reply.created", payload_json=json.dumps({"case_id": row.id, "message_id": message.id, "source": "human_agent"}), correlation_id=str(uuid.uuid4()), idempotency_key=f"human-reply:{message.id}")); db.commit(); return {"id": message.id, "case_id": row.id, "sender_type": message.sender_type, "body": message.body, "status": row.status}


@app.put("/support/cases/{case_id}/assignment")
def assign_support_case(case_id: str, data: SupportAssignmentIn, user: User = Depends(require_permission("support:manage")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.SupportCase).where(operational_models.SupportCase.id == case_id, operational_models.SupportCase.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="پرونده پشتیبانی در این tenant وجود ندارد")
    if data.assigned_to_user_id:
        target = db.scalar(select(User).where(User.id == data.assigned_to_user_id, User.tenant_id == user.tenant_id))
        if target is None or not role_has_permission(target.role, "support:manage"): raise HTTPException(status_code=422, detail="کارشناس پشتیبانی معتبر نیست")
    row.assigned_to_user_id = data.assigned_to_user_id; row.status = data.status; db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="support_case", aggregate_id=row.id, event_type=f"support.case.{row.status}", payload_json=json.dumps({"assigned_to_user_id": row.assigned_to_user_id, "actor_id": user.id}), correlation_id=str(uuid.uuid4()), idempotency_key=f"support-state:{row.id}:{uuid.uuid4()}")); db.commit(); return {"id": row.id, "status": row.status, "assigned_to_user_id": row.assigned_to_user_id}


def _installment_output(row: operational_models.InstallmentAgreement) -> dict:
    return {"id": row.id, "plan_id": row.plan_id, "reservation_id": row.reservation_id, "principal_amount": row.principal_amount, "total_payable": row.total_payable, "currency": row.currency, "schedule": json.loads(row.schedule_json), "status": row.status}


@app.get("/me/installments")
def my_installments(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.InstallmentAgreement).where(operational_models.InstallmentAgreement.tenant_id == user.tenant_id, operational_models.InstallmentAgreement.user_id == user.id).order_by(operational_models.InstallmentAgreement.created_at.desc())).all(); return [_installment_output(row) for row in rows]


@app.post("/reservations/{reservation_id}/installments", status_code=status.HTTP_201_CREATED)
def request_installment(reservation_id: str, plan_id: str, user: User = Depends(current_user), db: Session = Depends(get_db), idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
    prior = db.scalar(select(operational_models.InstallmentAgreement).where(operational_models.InstallmentAgreement.tenant_id == user.tenant_id, operational_models.InstallmentAgreement.command_id == idempotency_key))
    if prior:
        if prior.reservation_id != reservation_id or prior.plan_id != plan_id or prior.user_id != user.id: raise HTTPException(status_code=409, detail="کلید تکرار برای درخواست دیگری استفاده شده است")
        return _installment_output(prior)
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id).with_for_update())
    if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    assignments = db.scalars(select(operational_models.EmployeeAssignment).where(operational_models.EmployeeAssignment.tenant_id == user.tenant_id, operational_models.EmployeeAssignment.user_id == user.id)).all(); organization_ids = [item.organization_id for item in assignments]
    plan = db.scalar(select(operational_models.InstallmentPlan).where(operational_models.InstallmentPlan.id == plan_id, operational_models.InstallmentPlan.tenant_id == user.tenant_id, operational_models.InstallmentPlan.organization_id.in_(organization_ids), operational_models.InstallmentPlan.status == "active")) if organization_ids else None
    if plan is None: raise HTTPException(status_code=404, detail="طرح اقساط فعال و مجاز وجود ندارد")
    try: terms = json.loads(plan.terms_json); months = int(terms["months"]); fee_bps = int(terms.get("fee_bps", 0)); principal = int(json.loads(reservation.price_snapshot_json)["total_amount"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError): raise HTTPException(status_code=409, detail="شرایط معتبر اقساط یا قیمت رزرو وجود ندارد")
    if months < 2 or months > 36 or fee_bps < 0 or fee_bps > 10000 or principal <= 0: raise HTTPException(status_code=409, detail="شرایط اقساط معتبر نیست")
    total = principal + (principal * fee_bps // 10000); base, remainder = divmod(total, months); schedule = [{"number": index + 1, "amount": base + (1 if index < remainder else 0), "status": "scheduled"} for index in range(months)]
    row = operational_models.InstallmentAgreement(tenant_id=user.tenant_id, plan_id=plan.id, reservation_id=reservation.id, user_id=user.id, command_id=idempotency_key, principal_amount=principal, total_payable=total, schedule_json=json.dumps(schedule)); db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="installment", aggregate_id=row.id, event_type="installment.requested", payload_json=json.dumps({"agreement_id": row.id, "reservation_id": reservation.id}), correlation_id=str(uuid.uuid4()), idempotency_key=idempotency_key)); db.commit(); return _installment_output(row)


@app.put("/finance/installments/{agreement_id}/decision")
def installment_decision(agreement_id: str, data: InstallmentDecisionIn, user: User = Depends(require_permission("installment:manage")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.InstallmentAgreement).where(operational_models.InstallmentAgreement.id == agreement_id, operational_models.InstallmentAgreement.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="قرارداد اقساط در این tenant وجود ندارد")
    if row.status != "requested": raise HTTPException(status_code=409, detail="درخواست اقساط قبلاً تعیین تکلیف شده است")
    if data.decision == "reject" and (not data.reason or len(data.reason.strip()) < 3): raise HTTPException(status_code=422, detail="دلیل رد الزامی است")
    row.status = "active" if data.decision == "activate" else "rejected"; row.activated_by_user_id = user.id if data.decision == "activate" else None; db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="installment", aggregate_id=row.id, event_type=f"installment.{row.status}", payload_json=json.dumps({"actor_id": user.id, "reason": data.reason}), correlation_id=str(uuid.uuid4()), idempotency_key=f"installment-decision:{row.id}:{row.status}")); db.commit(); return _installment_output(row)


@app.post("/finance/reservations/{reservation_id}/settlements", status_code=status.HTTP_201_CREATED)
def post_settlement(reservation_id: str, user: User = Depends(require_permission("settlement:manage")), db: Session = Depends(get_db), idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
    prior_key = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "settlement.post", operational_models.IdempotencyKey.key == idempotency_key))
    if prior_key:
        if prior_key.request_hash != _secure_hash(reservation_id): raise HTTPException(status_code=409, detail="کلید تکرار برای تسویه دیگری استفاده شده است")
        return json.loads(prior_key.response_json or "{}")
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id).with_for_update())
    if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این tenant وجود ندارد")
    payment = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.reservation_id == reservation.id, operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.status == "captured").with_for_update())
    if payment is None: raise HTTPException(status_code=409, detail="پرداخت captureشده برای تسویه وجود ندارد")
    price_check = db.scalar(select(operational_models.PriceCheck).where(operational_models.PriceCheck.id == reservation.price_check_id, operational_models.PriceCheck.tenant_id == user.tenant_id)) if reservation.price_check_id else None
    offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == price_check.offer_id, operational_models.Offer.tenant_id == user.tenant_id)) if price_check else None
    if offer is None: raise HTTPException(status_code=409, detail="تأمین‌کننده معتبر رزرو برای تسویه وجود ندارد")
    already = db.scalar(select(func.coalesce(func.sum(operational_models.SettlementRecord.amount), 0)).where(operational_models.SettlementRecord.tenant_id == user.tenant_id, operational_models.SettlementRecord.reservation_id == reservation.id)) or 0; amount = payment.captured_amount - payment.refunded_amount - int(already)
    if amount <= 0: raise HTTPException(status_code=409, detail="مبلغ قابل تسویه باقی نمانده است")
    row = operational_models.SettlementRecord(tenant_id=user.tenant_id, supplier_id=offer.supplier_id, reservation_id=reservation.id, amount=amount, currency=payment.currency, status="pending"); db.add(row); db.flush(); response = {"id": row.id, "reservation_id": reservation.id, "supplier_id": row.supplier_id, "amount": row.amount, "currency": row.currency, "status": row.status, "external_transfer_claimed": False}
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="settlement.post", key=idempotency_key, request_hash=_secure_hash(reservation.id), response_json=json.dumps(response))); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="settlement", aggregate_id=row.id, event_type="settlement.posted_pending", payload_json=json.dumps(response), correlation_id=str(uuid.uuid4()), idempotency_key=idempotency_key)); db.commit(); return response


@app.get("/admin/users")
def admin_users(user: User = Depends(require_permission("member:manage")), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(User).where(User.tenant_id == user.tenant_id).order_by(User.id)).all(); return [{"id": row.id, "name": row.name, "email": row.email, "role": row.role, "mutable": row.role != "platform_admin" and row.id != user.id} for row in rows]


@app.put("/admin/users/{target_user_id}/role")
def change_user_role(target_user_id: int, data: AdminRoleIn, user: User = Depends(require_permission("member:manage")), db: Session = Depends(get_db)) -> dict:
    target = db.scalar(select(User).where(User.id == target_user_id, User.tenant_id == user.tenant_id).with_for_update())
    if target is None: raise HTTPException(status_code=404, detail="کاربر در این tenant وجود ندارد")
    if target.id == user.id: raise HTTPException(status_code=409, detail="تغییر نقش خود از این مسیر مجاز نیست")
    if target.role == "platform_admin": raise HTTPException(status_code=403, detail="مدیر پلتفرم از tenant قابل تغییر نیست")
    if user.role == "organization_admin" and data.role not in {"employee", "customer", "manager", "welfare_manager"}: raise HTTPException(status_code=403, detail="مدیر سازمان مجاز به اعطای نقش سطح tenant نیست")
    previous = target.role; target.role = data.role; db.add(AuditEvent(tenant_id=user.tenant_id, actor_id=user.id, action="user.role_changed", entity="user", entity_id=target.id, detail=json.dumps({"from": previous, "to": target.role, "reason": data.reason}, sort_keys=True))); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="user", aggregate_id=str(target.id), event_type="admin.user_role.changed", payload_json=json.dumps({"from": previous, "to": target.role, "actor_id": user.id}, sort_keys=True), correlation_id=str(uuid.uuid4()), idempotency_key=f"role:{target.id}:{uuid.uuid4()}")); db.commit(); return {"id": target.id, "name": target.name, "email": target.email, "role": target.role}


def _saved_trip_output(db: Session, row: operational_models.SavedTrip) -> dict:
    items = db.scalars(select(operational_models.SavedTripItem).where(operational_models.SavedTripItem.tenant_id == row.tenant_id, operational_models.SavedTripItem.saved_trip_id == row.id).order_by(operational_models.SavedTripItem.state, operational_models.SavedTripItem.position, operational_models.SavedTripItem.created_at)).all()
    return {"id": row.id, "title": row.title, "status": row.status, "items": [{"id": item.id, "service_type": item.service_type, "source_reference": item.source_reference, "offer_id": item.offer_id, "state": item.state, "position": item.position, "snapshot": json.loads(item.snapshot_json)} for item in items]}


@app.post("/saved-trips", status_code=status.HTTP_201_CREATED)
def create_saved_trip(data: SavedTripIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.SavedTrip).where(operational_models.SavedTrip.tenant_id == user.tenant_id, operational_models.SavedTrip.command_id == data.command_id))
    if prior:
        if prior.user_id != user.id or prior.title != data.title.strip(): raise HTTPException(status_code=409, detail="کلید تکرار برای سفر دیگری استفاده شده است")
        return _saved_trip_output(db, prior)
    row = operational_models.SavedTrip(tenant_id=user.tenant_id, user_id=user.id, title=data.title.strip(), command_id=data.command_id); db.add(row); db.flush()
    db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="saved_trip", aggregate_id=row.id, event_type="saved_trip.created", payload_json=json.dumps({"user_id": user.id, "title": row.title}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _saved_trip_output(db, row)


@app.get("/me/saved-trips")
def my_saved_trips(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.SavedTrip).where(operational_models.SavedTrip.tenant_id == user.tenant_id, operational_models.SavedTrip.user_id == user.id, operational_models.SavedTrip.status == "active").order_by(operational_models.SavedTrip.updated_at.desc())).all(); return [_saved_trip_output(db, row) for row in rows]


@app.post("/saved-trips/{trip_id}/items", status_code=status.HTTP_201_CREATED)
def add_saved_trip_item(trip_id: str, data: SavedItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    trip = db.scalar(select(operational_models.SavedTrip).where(operational_models.SavedTrip.id == trip_id, operational_models.SavedTrip.tenant_id == user.tenant_id, operational_models.SavedTrip.user_id == user.id).with_for_update())
    if trip is None: raise HTTPException(status_code=404, detail="سفر ذخیره‌شده وجود ندارد")
    prior = db.scalar(select(operational_models.SavedTripItem).where(operational_models.SavedTripItem.tenant_id == user.tenant_id, operational_models.SavedTripItem.command_id == data.command_id))
    if prior:
        if prior.saved_trip_id != trip.id or prior.source_reference != data.source_reference or prior.state != data.state: raise HTTPException(status_code=409, detail="کلید تکرار برای آیتم دیگری استفاده شده است")
        return _saved_trip_output(db, trip)
    offer = None
    if data.offer_id:
        offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == data.offer_id, operational_models.Offer.tenant_id == user.tenant_id))
        if offer is None or offer.service_type != data.service_type: raise HTTPException(status_code=404, detail="Offer معتبر در این tenant وجود ندارد")
    snapshot = {"authoritative": False, "needs_live_availability_check": True}
    if offer:
        now = datetime.now(timezone.utc); snapshot = {"authoritative": True, "offer_id": offer.id, "provider": offer.provider_key, "amount": offer.amount, "currency": offer.currency, "observed_at": _aware(offer.updated_at).isoformat(), "valid_until": _aware(offer.valid_until).isoformat(), "needs_live_availability_check": _aware(offer.valid_until) <= now}
    position = db.scalar(select(func.coalesce(func.max(operational_models.SavedTripItem.position), 0)).where(operational_models.SavedTripItem.tenant_id == user.tenant_id, operational_models.SavedTripItem.saved_trip_id == trip.id, operational_models.SavedTripItem.state == data.state)) or 0
    item = operational_models.SavedTripItem(tenant_id=user.tenant_id, saved_trip_id=trip.id, user_id=user.id, offer_id=data.offer_id, service_type=data.service_type, source_reference=data.source_reference, state=data.state, position=int(position) + 1, snapshot_json=json.dumps(snapshot, sort_keys=True), command_id=data.command_id); db.add(item); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="saved_trip", aggregate_id=trip.id, event_type=f"saved_trip.item.{data.state}.added", payload_json=json.dumps({"item_id": item.id, "service_type": item.service_type}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _saved_trip_output(db, trip)


def _saved_item_mutation(trip_id: str, item_id: str, command_id: str, target_state: Optional[str], user: User, db: Session) -> dict:
    scope = "saved_item.remove" if target_state is None else "saved_item.move"
    request_hash = _secure_hash(f"{trip_id}:{item_id}:{target_state or 'removed'}")
    prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == scope, operational_models.IdempotencyKey.key == command_id))
    if prior:
        if prior.request_hash != request_hash: raise HTTPException(status_code=409, detail="کلید تکرار برای فرمان دیگری استفاده شده است")
        return json.loads(prior.response_json or "{}")
    trip = db.scalar(select(operational_models.SavedTrip).where(operational_models.SavedTrip.id == trip_id, operational_models.SavedTrip.tenant_id == user.tenant_id, operational_models.SavedTrip.user_id == user.id).with_for_update())
    item = db.scalar(select(operational_models.SavedTripItem).where(operational_models.SavedTripItem.id == item_id, operational_models.SavedTripItem.saved_trip_id == trip_id, operational_models.SavedTripItem.tenant_id == user.tenant_id, operational_models.SavedTripItem.user_id == user.id).with_for_update()) if trip else None
    if trip is None or item is None: raise HTTPException(status_code=404, detail="آیتم سفر ذخیره‌شده وجود ندارد")
    event_type = "saved_trip.item.removed"
    if target_state is None: db.delete(item)
    else:
        item.state = target_state; item.position = int(db.scalar(select(func.coalesce(func.max(operational_models.SavedTripItem.position), 0)).where(operational_models.SavedTripItem.tenant_id == user.tenant_id, operational_models.SavedTripItem.saved_trip_id == trip.id, operational_models.SavedTripItem.state == target_state)) or 0) + 1; event_type = f"saved_trip.item.moved_to_{target_state}"
    db.flush(); response = _saved_trip_output(db, trip); db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope=scope, key=command_id, request_hash=request_hash, response_json=json.dumps(response))); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="saved_trip", aggregate_id=trip.id, event_type=event_type, payload_json=json.dumps({"item_id": item_id}), correlation_id=str(uuid.uuid4()), idempotency_key=command_id)); db.commit(); return response


@app.put("/saved-trips/{trip_id}/items/{item_id}")
def move_saved_item(trip_id: str, item_id: str, data: SavedItemMoveIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict: return _saved_item_mutation(trip_id, item_id, data.command_id, data.state, user, db)


@app.delete("/saved-trips/{trip_id}/items/{item_id}")
def remove_saved_item(trip_id: str, item_id: str, data: CommandIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict: return _saved_item_mutation(trip_id, item_id, data.command_id, None, user, db)


def _review_output(row: operational_models.Review, response: Optional[operational_models.ReviewSupplierResponse] = None) -> dict:
    return {"id": row.id, "rating": row.rating, "title": row.title, "body": row.body, "service_type": row.service_type, "service_reference": row.service_reference, "provider_reference": row.provider_reference, "reservation_id": row.reservation_id, "verified_booking": row.verified_booking, "moderation_state": row.moderation_state, "analysis": {"state": row.analysis_state, "summary": None, "topics": [], "sentiment": None}, "supplier_response": {"body": response.body, "created_at": response.created_at.isoformat()} if response else None, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}


@app.post("/reviews", status_code=status.HTTP_201_CREATED)
def create_review(data: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.Review).where(operational_models.Review.tenant_id == user.tenant_id, operational_models.Review.command_id == data.command_id))
    if prior:
        if prior.user_id != user.id or prior.service_reference != data.service_reference: raise HTTPException(status_code=409, detail="کلید تکرار برای review دیگری استفاده شده است")
        return _review_output(prior)
    reservation = None
    if data.reservation_id:
        reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == data.reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id))
        if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
        if reservation.service_type != data.service_type: raise HTTPException(status_code=422, detail="نوع review با رزرو سازگار نیست")
    verified = bool(reservation and reservation.status in {"issued", "completed"} and reservation.provider_reference)
    row = operational_models.Review(tenant_id=user.tenant_id, user_id=user.id, reservation_id=data.reservation_id, service_type=data.service_type, service_reference=data.service_reference, provider_reference=data.provider_reference or (reservation.provider_reference if reservation else None), rating=data.rating, title=data.title.strip(), body=data.body.strip(), verified_booking=verified, command_id=data.command_id); db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="review", aggregate_id=row.id, event_type="review.created", payload_json=json.dumps({"verified_booking": verified, "service_type": row.service_type}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _review_output(row)


@app.put("/reviews/{review_id}/moderation")
def moderate_review(review_id: str, data: ReviewModerationIn, user: User = Depends(require_role("backoffice_expert", "tenant_admin", "platform_admin")), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Review).where(operational_models.Review.id == review_id, operational_models.Review.tenant_id == user.tenant_id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="Review در این tenant وجود ندارد")
    row.moderation_state = data.state; db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="review", aggregate_id=row.id, event_type=f"review.moderation.{data.state}", payload_json=json.dumps({"actor_id": user.id, "reason": data.reason}), correlation_id=str(uuid.uuid4()), idempotency_key=f"review-moderation:{row.id}:{uuid.uuid4()}")); db.commit(); return _review_output(row)


@app.post("/reviews/{review_id}/supplier-response", status_code=status.HTTP_201_CREATED)
def supplier_review_response(review_id: str, data: ReviewResponseIn, user: User = Depends(require_role("supplier")), db: Session = Depends(get_db)) -> dict:
    review = db.scalar(select(operational_models.Review).where(operational_models.Review.id == review_id, operational_models.Review.tenant_id == user.tenant_id))
    supplier = db.scalar(select(operational_models.Supplier).where(operational_models.Supplier.id == data.supplier_id, operational_models.Supplier.tenant_id == user.tenant_id))
    if review is None or supplier is None: raise HTTPException(status_code=404, detail="Review یا تأمین‌کننده در این tenant وجود ندارد")
    prior = db.scalar(select(operational_models.ReviewSupplierResponse).where(operational_models.ReviewSupplierResponse.tenant_id == user.tenant_id, operational_models.ReviewSupplierResponse.command_id == data.command_id))
    if prior:
        if prior.review_id != review.id: raise HTTPException(status_code=409, detail="کلید تکرار برای پاسخ دیگری استفاده شده است")
        return _review_output(review, prior)
    if db.scalar(select(operational_models.ReviewSupplierResponse).where(operational_models.ReviewSupplierResponse.tenant_id == user.tenant_id, operational_models.ReviewSupplierResponse.review_id == review.id)): raise HTTPException(status_code=409, detail="پاسخ تأمین‌کننده قبلاً ثبت شده است")
    response = operational_models.ReviewSupplierResponse(tenant_id=user.tenant_id, review_id=review.id, supplier_id=supplier.id, responder_user_id=user.id, body=data.body.strip(), command_id=data.command_id); db.add(response); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="review", aggregate_id=review.id, event_type="review.supplier_response.created", payload_json=json.dumps({"response_id": response.id, "supplier_id": supplier.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _review_output(review, response)


@app.post("/destinations", status_code=status.HTTP_201_CREATED)
def create_destination(data: DestinationIn, user: User = Depends(require_role("backoffice_expert", "tenant_admin", "platform_admin")), db: Session = Depends(get_db)) -> dict:
    if data.parent_id and db.scalar(select(operational_models.Destination).where(operational_models.Destination.id == data.parent_id, operational_models.Destination.tenant_id == user.tenant_id)) is None: raise HTTPException(status_code=404, detail="مقصد والد وجود ندارد")
    if db.scalar(select(operational_models.Destination).where(operational_models.Destination.tenant_id == user.tenant_id, operational_models.Destination.slug == data.slug)): raise HTTPException(status_code=409, detail="slug مقصد تکراری است")
    row = operational_models.Destination(tenant_id=user.tenant_id, **{**data.model_dump(exclude={"seasonality", "categories", "highlights", "nearby_slugs"}), "seasonality_json": json.dumps(data.seasonality), "categories_json": json.dumps(data.categories), "highlights_json": json.dumps(data.highlights), "nearby_slugs_json": json.dumps(data.nearby_slugs)}); db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="destination", aggregate_id=row.id, event_type="destination.published", payload_json=json.dumps({"slug": row.slug, "kind": row.kind}), correlation_id=str(uuid.uuid4()), idempotency_key=f"destination:{row.id}")); db.commit(); return {"id": row.id, "slug": row.slug, "name_fa": row.name_fa, "kind": row.kind}


def _destination_output(db: Session, row: operational_models.Destination) -> dict:
    offers = db.scalars(select(operational_models.Offer).where(operational_models.Offer.tenant_id == row.tenant_id, operational_models.Offer.status == "active", operational_models.Offer.valid_until > datetime.now(timezone.utc))).all(); counts: dict[str, int] = {}
    for offer in offers:
        attrs = json.loads(offer.attributes_json or "{}")
        if attrs.get("destination_slug") == row.slug: counts[offer.service_type] = counts.get(offer.service_type, 0) + 1
    return {"id": row.id, "parent_id": row.parent_id, "kind": row.kind, "name_fa": row.name_fa, "name_en": row.name_en, "slug": row.slug, "geo": {"latitude": float(row.latitude) if row.latitude is not None else None, "longitude": float(row.longitude) if row.longitude is not None else None}, "description": row.description, "seasonality": json.loads(row.seasonality_json), "categories": json.loads(row.categories_json), "highlights": json.loads(row.highlights_json), "nearby_destinations": json.loads(row.nearby_slugs_json), "service_counts": counts}


@app.get("/destinations")
def list_destinations(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.Destination).where(operational_models.Destination.tenant_id == user.tenant_id, operational_models.Destination.status == "published").order_by(operational_models.Destination.kind, operational_models.Destination.name_fa)).all(); return [_destination_output(db, row) for row in rows]


@app.get("/destinations/{slug}")
def destination_detail(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.Destination).where(operational_models.Destination.slug == slug, operational_models.Destination.tenant_id == user.tenant_id, operational_models.Destination.status == "published"))
    if row is None: raise HTTPException(status_code=404, detail="مقصد وجود ندارد")
    return _destination_output(db, row)


def _public_tenant(db: Session, tenant_slug: str) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None: raise HTTPException(status_code=404, detail="کاتالوگ عمومی tenant وجود ندارد")
    set_tenant_context(db, tenant.id); return tenant


@app.get("/public/tenants/{tenant_slug}/destinations")
def public_destinations(tenant_slug: str, db: Session = Depends(get_db)) -> list[dict]:
    tenant = _public_tenant(db, tenant_slug); rows = db.scalars(select(operational_models.Destination).where(operational_models.Destination.tenant_id == tenant.id, operational_models.Destination.status == "published").order_by(operational_models.Destination.kind, operational_models.Destination.name_fa)).all(); return [_destination_output(db, row) for row in rows]


@app.get("/public/tenants/{tenant_slug}/destinations/{slug}")
def public_destination_detail(tenant_slug: str, slug: str, db: Session = Depends(get_db)) -> dict:
    tenant = _public_tenant(db, tenant_slug); row = db.scalar(select(operational_models.Destination).where(operational_models.Destination.tenant_id == tenant.id, operational_models.Destination.slug == slug, operational_models.Destination.status == "published"))
    if row is None: raise HTTPException(status_code=404, detail="مقصد منتشرشده وجود ندارد")
    return _destination_output(db, row)


def _itinerary_output(db: Session, row: operational_models.EditableItinerary) -> dict:
    items = db.scalars(select(operational_models.EditableItineraryItem).where(operational_models.EditableItineraryItem.tenant_id == row.tenant_id, operational_models.EditableItineraryItem.itinerary_id == row.id).order_by(operational_models.EditableItineraryItem.day_number, operational_models.EditableItineraryItem.position)).all(); return {"id": row.id, "title": row.title, "destination_id": row.destination_id, "budget_amount": row.budget_amount, "currency": row.currency, "status": row.status, "items": [{"id": item.id, "offer_id": item.offer_id, "service_type": item.service_type, "title": item.title, "day_number": item.day_number, "position": item.position, "availability_state": item.availability_state, "snapshot": json.loads(item.snapshot_json)} for item in items]}


@app.post("/itineraries", status_code=status.HTTP_201_CREATED)
def create_itinerary(data: ItineraryIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.command_id == data.command_id))
    if prior:
        if prior.user_id != user.id or prior.title != data.title.strip(): raise HTTPException(status_code=409, detail="کلید تکرار برای برنامه دیگری استفاده شده است")
        return _itinerary_output(db, prior)
    if data.destination_id and db.scalar(select(operational_models.Destination).where(operational_models.Destination.id == data.destination_id, operational_models.Destination.tenant_id == user.tenant_id)) is None: raise HTTPException(status_code=404, detail="مقصد وجود ندارد")
    row = operational_models.EditableItinerary(tenant_id=user.tenant_id, user_id=user.id, title=data.title.strip(), destination_id=data.destination_id, budget_amount=data.budget_amount, command_id=data.command_id); db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="itinerary", aggregate_id=row.id, event_type="itinerary.created", payload_json=json.dumps({"user_id": user.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _itinerary_output(db, row)


@app.get("/me/itineraries")
def my_itineraries(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.user_id == user.id).order_by(operational_models.EditableItinerary.updated_at.desc())).all(); return [_itinerary_output(db, row) for row in rows]


@app.post("/itineraries/{itinerary_id}/items", status_code=status.HTTP_201_CREATED)
def add_itinerary_item(itinerary_id: str, data: ItineraryItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    itinerary = db.scalar(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.id == itinerary_id, operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.user_id == user.id).with_for_update())
    if itinerary is None: raise HTTPException(status_code=404, detail="برنامه سفر وجود ندارد")
    prior = db.scalar(select(operational_models.EditableItineraryItem).where(operational_models.EditableItineraryItem.tenant_id == user.tenant_id, operational_models.EditableItineraryItem.command_id == data.command_id))
    if prior:
        if prior.itinerary_id != itinerary.id: raise HTTPException(status_code=409, detail="کلید تکرار برای آیتم دیگری استفاده شده است")
        return _itinerary_output(db, itinerary)
    offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == data.offer_id, operational_models.Offer.tenant_id == user.tenant_id)) if data.offer_id else None
    if data.offer_id and (offer is None or offer.service_type != data.service_type): raise HTTPException(status_code=404, detail="Offer معتبر وجود ندارد")
    fresh = bool(offer and offer.status == "active" and offer.available_units > 0 and _aware(offer.valid_until) > datetime.now(timezone.utc)); snapshot = {"transactional_data_generated": False, "source": "search_offer" if offer else "user_plan", "offer_id": offer.id if offer else None, "amount": offer.amount if offer else None, "currency": offer.currency if offer else None, "valid_until": _aware(offer.valid_until).isoformat() if offer else None}
    row = operational_models.EditableItineraryItem(tenant_id=user.tenant_id, itinerary_id=itinerary.id, offer_id=data.offer_id, service_type=data.service_type, title=data.title.strip(), day_number=data.day_number, position=data.position, availability_state="live_at_save_time" if fresh else "needs_live_availability_check", snapshot_json=json.dumps(snapshot), command_id=data.command_id); db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="itinerary", aggregate_id=itinerary.id, event_type="itinerary.item.added", payload_json=json.dumps({"item_id": row.id, "availability_state": row.availability_state}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _itinerary_output(db, itinerary)


@app.put("/itineraries/{itinerary_id}/items/{item_id}")
def update_itinerary_item(itinerary_id: str, item_id: str, data: ItineraryItemUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    itinerary = db.scalar(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.id == itinerary_id, operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.user_id == user.id).with_for_update()); item = db.scalar(select(operational_models.EditableItineraryItem).where(operational_models.EditableItineraryItem.id == item_id, operational_models.EditableItineraryItem.itinerary_id == itinerary_id, operational_models.EditableItineraryItem.tenant_id == user.tenant_id).with_for_update()) if itinerary else None
    if itinerary is None or item is None: raise HTTPException(status_code=404, detail="آیتم برنامه سفر وجود ندارد")
    key = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "itinerary.item.update", operational_models.IdempotencyKey.key == data.command_id)); request_hash = _secure_hash(data.model_dump_json())
    if key:
        if key.request_hash != request_hash: raise HTTPException(status_code=409, detail="کلید تکرار برای تغییر دیگری استفاده شده است")
        return json.loads(key.response_json or "{}")
    if data.replacement_offer_id:
        offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == data.replacement_offer_id, operational_models.Offer.tenant_id == user.tenant_id, operational_models.Offer.service_type == item.service_type))
        if offer is None: raise HTTPException(status_code=404, detail="Offer جایگزین معتبر نیست")
        item.offer_id = offer.id; item.availability_state = "live_at_save_time" if offer.status == "active" and offer.available_units > 0 and _aware(offer.valid_until) > datetime.now(timezone.utc) else "needs_live_availability_check"; item.snapshot_json = json.dumps({"transactional_data_generated": False, "source": "search_offer", "offer_id": offer.id, "amount": offer.amount, "currency": offer.currency, "valid_until": _aware(offer.valid_until).isoformat()})
    item.day_number = data.day_number; item.position = data.position; db.flush(); response = _itinerary_output(db, itinerary); db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="itinerary.item.update", key=data.command_id, request_hash=request_hash, response_json=json.dumps(response))); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="itinerary", aggregate_id=itinerary.id, event_type="itinerary.item.updated", payload_json=json.dumps({"item_id": item.id, "day_number": item.day_number, "position": item.position}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return response


@app.put("/itineraries/{itinerary_id}")
def update_itinerary(itinerary_id: str, data: ItineraryUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.id == itinerary_id, operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.user_id == user.id).with_for_update())
    if row is None: raise HTTPException(status_code=404, detail="برنامه سفر وجود ندارد")
    request_hash = _secure_hash(data.model_dump_json()); prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == "itinerary.update", operational_models.IdempotencyKey.key == data.command_id))
    if prior:
        if prior.request_hash != request_hash: raise HTTPException(status_code=409, detail="کلید تکرار برای تغییر دیگری استفاده شده است")
        return json.loads(prior.response_json or "{}")
    row.title = data.title.strip(); row.budget_amount = data.budget_amount; row.status = data.status; db.flush(); response = _itinerary_output(db, row)
    db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope="itinerary.update", key=data.command_id, request_hash=request_hash, response_json=json.dumps(response))); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="itinerary", aggregate_id=row.id, event_type="itinerary.updated", payload_json=json.dumps({"budget_amount": row.budget_amount, "status": row.status}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return response


@app.delete("/itineraries/{itinerary_id}/items/{item_id}")
def remove_itinerary_item(itinerary_id: str, item_id: str, data: CommandIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.id == itinerary_id, operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.user_id == user.id).with_for_update()); item = db.scalar(select(operational_models.EditableItineraryItem).where(operational_models.EditableItineraryItem.id == item_id, operational_models.EditableItineraryItem.itinerary_id == itinerary_id, operational_models.EditableItineraryItem.tenant_id == user.tenant_id)) if row else None
    if row is None or item is None: raise HTTPException(status_code=404, detail="آیتم برنامه سفر وجود ندارد")
    scope = "itinerary.item.remove"; prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == scope, operational_models.IdempotencyKey.key == data.command_id))
    if prior: return json.loads(prior.response_json or "{}")
    db.delete(item); db.flush(); response = _itinerary_output(db, row); db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope=scope, key=data.command_id, request_hash=_secure_hash(item_id), response_json=json.dumps(response))); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="itinerary", aggregate_id=row.id, event_type="itinerary.item.removed", payload_json=json.dumps({"item_id": item_id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return response


@app.post("/itineraries/{itinerary_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_itinerary(itinerary_id: str, data: CommandIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    source = db.scalar(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.id == itinerary_id, operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.user_id == user.id))
    if source is None: raise HTTPException(status_code=404, detail="برنامه سفر وجود ندارد")
    prior = db.scalar(select(operational_models.EditableItinerary).where(operational_models.EditableItinerary.tenant_id == user.tenant_id, operational_models.EditableItinerary.command_id == data.command_id))
    if prior: return _itinerary_output(db, prior)
    clone = operational_models.EditableItinerary(tenant_id=user.tenant_id, user_id=user.id, title=f"کپی {source.title}"[:160], destination_id=source.destination_id, budget_amount=source.budget_amount, currency=source.currency, command_id=data.command_id); db.add(clone); db.flush()
    items = db.scalars(select(operational_models.EditableItineraryItem).where(operational_models.EditableItineraryItem.tenant_id == user.tenant_id, operational_models.EditableItineraryItem.itinerary_id == source.id)).all()
    for item in items: db.add(operational_models.EditableItineraryItem(tenant_id=user.tenant_id, itinerary_id=clone.id, offer_id=item.offer_id, service_type=item.service_type, title=item.title, day_number=item.day_number, position=item.position, availability_state=item.availability_state, snapshot_json=item.snapshot_json, command_id=f"{data.command_id}:{item.id}"[:120]))
    db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="itinerary", aggregate_id=clone.id, event_type="itinerary.duplicated", payload_json=json.dumps({"source_itinerary_id": source.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _itinerary_output(db, clone)


@app.get("/me/reviews")
def my_reviews(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(operational_models.Review).where(operational_models.Review.tenant_id == user.tenant_id, operational_models.Review.user_id == user.id).order_by(operational_models.Review.created_at.desc())).all(); result = []
    for row in rows:
        response = db.scalar(select(operational_models.ReviewSupplierResponse).where(operational_models.ReviewSupplierResponse.tenant_id == user.tenant_id, operational_models.ReviewSupplierResponse.review_id == row.id)); result.append(_review_output(row, response))
    return result


@app.get("/reviews")
def list_reviews(service_type: str = Query(pattern=ECOSYSTEM_SERVICE_PATTERN), service_reference: str = Query(min_length=2, max_length=200), page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=50), user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    base = select(operational_models.Review).where(operational_models.Review.tenant_id == user.tenant_id, operational_models.Review.service_type == service_type, operational_models.Review.service_reference == service_reference, operational_models.Review.moderation_state == "approved")
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0); rows = db.scalars(base.order_by(operational_models.Review.verified_booking.desc(), operational_models.Review.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all(); items = []
    for row in rows:
        response = db.scalar(select(operational_models.ReviewSupplierResponse).where(operational_models.ReviewSupplierResponse.tenant_id == user.tenant_id, operational_models.ReviewSupplierResponse.review_id == row.id)); items.append(_review_output(row, response))
    return {"items": items, "page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}


@app.post("/reviews/{review_id}/reports", status_code=status.HTTP_201_CREATED)
def report_review(review_id: str, data: ReviewReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    review = db.scalar(select(operational_models.Review).where(operational_models.Review.id == review_id, operational_models.Review.tenant_id == user.tenant_id, operational_models.Review.moderation_state == "approved"))
    if review is None: raise HTTPException(status_code=404, detail="Review قابل گزارش وجود ندارد")
    prior = db.scalar(select(operational_models.ReviewReport).where(operational_models.ReviewReport.tenant_id == user.tenant_id, operational_models.ReviewReport.command_id == data.command_id))
    if prior:
        if prior.review_id != review.id or prior.reporter_user_id != user.id or prior.reason != data.reason: raise HTTPException(status_code=409, detail="کلید تکرار برای گزارش دیگری استفاده شده است")
        return {"id": prior.id, "status": prior.status}
    if db.scalar(select(operational_models.ReviewReport).where(operational_models.ReviewReport.tenant_id == user.tenant_id, operational_models.ReviewReport.review_id == review.id, operational_models.ReviewReport.reporter_user_id == user.id)): raise HTTPException(status_code=409, detail="این Review قبلاً گزارش شده است")
    row = operational_models.ReviewReport(tenant_id=user.tenant_id, review_id=review.id, reporter_user_id=user.id, reason=data.reason, detail=data.detail, command_id=data.command_id); db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="review", aggregate_id=review.id, event_type="review.reported", payload_json=json.dumps({"report_id": row.id, "reason": row.reason}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return {"id": row.id, "status": row.status}


CHECKOUT_STAGES = ("review", "traveller", "recheck", "policy", "funding", "invoice", "payment", "awaiting_payment", "awaiting_fulfillment", "completed")


def _checkout_output(row: operational_models.CheckoutSession, reservation: operational_models.Reservation) -> dict:
    return {"id": row.id, "reservation": _reservation_output(reservation), "stage": row.stage, "state": json.loads(row.state_json), "payment_intent_id": row.payment_intent_id, "expires_at": row.expires_at.isoformat(), "server_authoritative": True}


@app.post("/reservations/{reservation_id}/checkout-sessions", status_code=status.HTTP_201_CREATED)
def create_checkout(reservation_id: str, data: CheckoutCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    prior = db.scalar(select(operational_models.CheckoutSession).where(operational_models.CheckoutSession.tenant_id == user.tenant_id, operational_models.CheckoutSession.command_id == data.command_id))
    if prior:
        if prior.reservation_id != reservation_id or prior.user_id != user.id: raise HTTPException(status_code=409, detail="کلید تکرار برای checkout دیگری استفاده شده است")
        reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == prior.reservation_id, operational_models.Reservation.tenant_id == user.tenant_id)); return _checkout_output(prior, reservation)
    reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id).with_for_update())
    if reservation is None: raise HTTPException(status_code=404, detail="رزرو در این حساب وجود ندارد")
    if reservation.status not in {"reserved", "pending_approval", "approved"}: raise HTTPException(status_code=409, detail="رزرو در وضعیت قابل checkout نیست")
    price_hash = _secure_hash(reservation.price_snapshot_json); policy_hash = _secure_hash(reservation.policy_at_booking_json)
    row = operational_models.CheckoutSession(tenant_id=user.tenant_id, reservation_id=reservation.id, user_id=user.id, command_id=data.command_id, price_snapshot_hash=price_hash, policy_snapshot_hash=policy_hash, state_json=json.dumps({"reviewed": True, "funding": {"wallet_amount": 0, "credit_amount": 0}}, sort_keys=True), expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)); db.add(row); db.flush(); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="checkout", aggregate_id=row.id, event_type="checkout.started", payload_json=json.dumps({"reservation_id": reservation.id}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return _checkout_output(row, reservation)


@app.get("/checkout-sessions/{checkout_id}")
def get_checkout(checkout_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(operational_models.CheckoutSession).where(operational_models.CheckoutSession.id == checkout_id, operational_models.CheckoutSession.tenant_id == user.tenant_id, operational_models.CheckoutSession.user_id == user.id)); reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == row.reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id)) if row else None
    if row is None or reservation is None: raise HTTPException(status_code=404, detail="Checkout در این حساب وجود ندارد")
    return _checkout_output(row, reservation)


@app.put("/checkout-sessions/{checkout_id}/steps/{step}")
def advance_checkout(checkout_id: str, step: str, data: CheckoutStepIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if step not in {"traveller", "recheck", "policy", "funding", "invoice", "payment", "confirmation"}: raise HTTPException(status_code=404, detail="مرحله checkout وجود ندارد")
    row = db.scalar(select(operational_models.CheckoutSession).where(operational_models.CheckoutSession.id == checkout_id, operational_models.CheckoutSession.tenant_id == user.tenant_id, operational_models.CheckoutSession.user_id == user.id).with_for_update()); reservation = db.scalar(select(operational_models.Reservation).where(operational_models.Reservation.id == row.reservation_id, operational_models.Reservation.tenant_id == user.tenant_id, operational_models.Reservation.user_id == user.id).with_for_update()) if row else None
    if row is None or reservation is None: raise HTTPException(status_code=404, detail="Checkout در این حساب وجود ندارد")
    if _aware(row.expires_at) <= datetime.now(timezone.utc): raise HTTPException(status_code=409, detail="Checkout منقضی شده است")
    scope = f"checkout.step.{step}"; request_hash = _secure_hash(f"{checkout_id}:{data.model_dump_json()}"); prior = db.scalar(select(operational_models.IdempotencyKey).where(operational_models.IdempotencyKey.tenant_id == user.tenant_id, operational_models.IdempotencyKey.scope == scope, operational_models.IdempotencyKey.key == data.command_id))
    if prior:
        if prior.request_hash != request_hash: raise HTTPException(status_code=409, detail="کلید تکرار برای مرحله دیگری استفاده شده است")
        return json.loads(prior.response_json or "{}")
    expected = {"traveller": "review", "recheck": "traveller", "policy": "recheck", "funding": "policy", "invoice": "funding", "payment": "invoice", "confirmation": "awaiting_payment"}
    if row.stage != expected[step]: raise HTTPException(status_code=409, detail=f"مرحله جاری checkout برابر {row.stage} است")
    state = json.loads(row.state_json)
    if step == "traveller":
        if not data.traveller_ids: raise HTTPException(status_code=422, detail="حداقل یک مسافر معتبر لازم است")
        travellers = db.scalars(select(operational_models.Traveller).where(operational_models.Traveller.tenant_id == user.tenant_id, operational_models.Traveller.user_id == user.id, operational_models.Traveller.id.in_(data.traveller_ids))).all()
        if len(travellers) != len(set(data.traveller_ids)): raise HTTPException(status_code=404, detail="یک یا چند مسافر در این حساب وجود ندارد")
        existing = set(db.scalars(select(operational_models.ReservationTraveller.traveller_id).where(operational_models.ReservationTraveller.reservation_id == reservation.id)).all())
        for traveller_id in set(data.traveller_ids) - existing: db.add(operational_models.ReservationTraveller(reservation_id=reservation.id, traveller_id=traveller_id))
        state["traveller_ids"] = sorted(set(data.traveller_ids)); row.stage = "traveller"
    elif step == "recheck":
        if row.price_snapshot_hash != _secure_hash(reservation.price_snapshot_json): raise HTTPException(status_code=409, detail="قیمت رزرو تغییر کرده و checkout باید از نو آغاز شود")
        item = db.scalar(select(operational_models.BookingItem).where(operational_models.BookingItem.tenant_id == user.tenant_id, operational_models.BookingItem.reservation_id == reservation.id)); snapshot = json.loads(item.snapshot_json) if item else {}; offer_id = snapshot.get("offer_id"); offer = db.scalar(select(operational_models.Offer).where(operational_models.Offer.id == offer_id, operational_models.Offer.tenant_id == user.tenant_id).with_for_update()) if offer_id else None
        price = json.loads(reservation.price_snapshot_json); units = int(price.get("units", 1)); total = int(price.get("total_amount", 0))
        if offer is None or offer.status != "active" or _aware(offer.valid_until) <= datetime.now(timezone.utc): raise HTTPException(status_code=409, detail="موجودی یا Offer تازه در دسترس نیست")
        if offer.amount * units != total: raise HTTPException(status_code=409, detail="قیمت stale یا دستکاری‌شده است")
        state["recheck"] = {"checked_at": datetime.now(timezone.utc).isoformat(), "total_amount": total, "currency": price.get("currency", "IRR"), "offer_id": offer.id}; row.stage = "recheck"
    elif step == "policy":
        if data.acknowledged is not True: raise HTTPException(status_code=422, detail="تأیید صریح policy الزامی است")
        if row.policy_snapshot_hash != _secure_hash(reservation.policy_at_booking_json): raise HTTPException(status_code=409, detail="Policy رزرو تغییر کرده است")
        policy = json.loads(reservation.policy_at_booking_json)
        if policy.get("verified") is not True or not policy.get("source") or not policy.get("verified_at"): raise HTTPException(status_code=409, detail="Policy معتبر و timestampدار موجود نیست")
        state["policy_acknowledged"] = True; state["policy_source"] = policy["source"]; row.stage = "policy"
    elif step == "funding":
        total = int(json.loads(reservation.price_snapshot_json).get("total_amount", 0))
        if data.wallet_amount + data.credit_amount > total: raise HTTPException(status_code=409, detail="مجموع کیف پول و اعتبار سازمانی از مبلغ رزرو بیشتر است")
        if data.wallet_amount:
            wallet = db.scalar(select(operational_models.Wallet).where(operational_models.Wallet.tenant_id == user.tenant_id, operational_models.Wallet.owner_type == "user", operational_models.Wallet.owner_reference == str(user.id), operational_models.Wallet.currency == "IRR").with_for_update())
            if wallet is None: raise HTTPException(status_code=409, detail="کیف پول ریالی معتبر وجود ندارد")
            try: operational_models.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id=f"checkout:{row.id}:wallet:{data.command_id}"[:80], entry_type="reserve", amount=data.wallet_amount, reservation_id=reservation.id)
            except ValueError as exc: raise HTTPException(status_code=409, detail="موجودی قابل استفاده کیف پول کافی نیست") from exc
        if data.credit_amount:
            organization_ids = [a.organization_id for a in db.scalars(select(operational_models.EmployeeAssignment).where(operational_models.EmployeeAssignment.tenant_id == user.tenant_id, operational_models.EmployeeAssignment.user_id == user.id)).all()]
            credit_account = db.scalar(select(operational_models.CreditAccount).where(operational_models.CreditAccount.tenant_id == user.tenant_id, operational_models.CreditAccount.organization_id.in_(organization_ids), operational_models.CreditAccount.currency == "IRR").with_for_update()) if organization_ids else None
            if credit_account is None: raise HTTPException(status_code=409, detail="حساب اعتبار سازمانی مشخص و معتبر برای این حساب وجود ندارد")
            try: operational_models.apply_organization_credit_command(db, tenant_id=user.tenant_id, credit_account_id=credit_account.id, command_id=f"checkout:{row.id}:credit:{data.command_id}"[:80], entry_type="reserve", amount=data.credit_amount, reservation_id=reservation.id)
            except ValueError as exc: raise HTTPException(status_code=409, detail="سقف اعتبار سازمانی کافی نیست") from exc
        state["funding"] = {"wallet_amount": data.wallet_amount, "credit_amount": data.credit_amount, "payable_amount": total - data.wallet_amount - data.credit_amount}; row.stage = "funding"
    elif step == "invoice":
        price = json.loads(reservation.price_snapshot_json); state["invoice_preview"] = {"subtotal_amount": int(price["total_amount"]), "currency": price.get("currency", "IRR"), "final_invoice_after_confirmation": True}; row.stage = "invoice"
    elif step == "payment":
        payable = int(state.get("funding", {}).get("payable_amount", 0))
        if payable <= 0: row.stage = "awaiting_fulfillment"
        else:
            intent = operational_models.PaymentIntent(tenant_id=user.tenant_id, reservation_id=reservation.id, user_id=user.id, command_id=f"checkout:{data.command_id}"[:120], amount=payable, currency="IRR"); db.add(intent); db.flush(); row.payment_intent_id = intent.id; row.stage = "awaiting_payment"; db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="payment", aggregate_id=intent.id, event_type="payment.intent.created", payload_json=json.dumps({"checkout_id": row.id}), correlation_id=str(uuid.uuid4()), idempotency_key=intent.command_id))
    else:
        intent = db.scalar(select(operational_models.PaymentIntent).where(operational_models.PaymentIntent.id == row.payment_intent_id, operational_models.PaymentIntent.tenant_id == user.tenant_id, operational_models.PaymentIntent.user_id == user.id)) if row.payment_intent_id else None
        if intent is None or intent.status != "captured" or intent.captured_amount != intent.amount: raise HTTPException(status_code=409, detail="پرداخت server-verified و کامل وجود ندارد")
        row.stage = "awaiting_fulfillment"; state["payment_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    row.state_json = json.dumps(state, sort_keys=True); db.flush(); response = _checkout_output(row, reservation); db.add(operational_models.IdempotencyKey(tenant_id=user.tenant_id, scope=scope, key=data.command_id, request_hash=request_hash, response_json=json.dumps(response))); db.add(operational_models.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="checkout", aggregate_id=row.id, event_type=f"checkout.{step}.completed", payload_json=json.dumps({"stage": row.stage}), correlation_id=str(uuid.uuid4()), idempotency_key=data.command_id)); db.commit(); return response
