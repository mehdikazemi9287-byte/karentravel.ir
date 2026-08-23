from __future__ import annotations

import json
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .database import set_tenant_context


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid4_str() -> str:
    return str(uuid.uuid4())


class OperationalMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Organization(OperationalMixin, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="active")


class Department(OperationalMixin, Base):
    __tablename__ = "departments"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("tenant_id", "organization_id", "code", name="uq_department_code"),)


class CostCenter(OperationalMixin, Base):
    __tablename__ = "cost_centers"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(64))
    budget_amount: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "organization_id", "code", name="uq_cost_center_code"),)


class EmployeeAssignment(OperationalMixin, Base):
    __tablename__ = "employee_assignments"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    department_id: Mapped[Optional[str]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    cost_center_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "organization_id", name="uq_employee_assignment"),)


class UserProfile(OperationalMixin, Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_type: Mapped[str] = mapped_column(String(32), default="customer")
    locale: Mapped[str] = mapped_column(String(16), default="fa-IR")
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_profile_user"),)


class RolePermission(OperationalMixin, Base):
    __tablename__ = "role_permissions"
    role: Mapped[str] = mapped_column(String(48), index=True)
    permission: Mapped[str] = mapped_column(String(80), index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "role", "permission", name="uq_role_permission"),)


class RefreshTokenSession(OperationalMixin, Base):
    __tablename__ = "refresh_token_sessions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    family_id: Mapped[str] = mapped_column(String(36), default=uuid4_str, index=True)
    device_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)


class OTPChallenge(OperationalMixin, Base):
    __tablename__ = "otp_challenges"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(32), default="login")
    identifier_hash: Mapped[str] = mapped_column(String(64), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    delivery_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_otp_tenant_challenge"),)


class AuthenticationState(OperationalMixin, Base):
    __tablename__ = "authentication_states"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_auth_state_user"),)


class AuthenticationAudit(OperationalMixin, Base):
    __tablename__ = "authentication_audits"
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    challenge_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    device_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")


class Membership(OperationalMixin, Base):
    __tablename__ = "memberships"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[Optional[str]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(48), index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "organization_id", name="uq_membership_scope"),)


class Supplier(OperationalMixin, Base):
    __tablename__ = "suppliers"
    supplier_type: Mapped[str] = mapped_column(String(48), index=True)
    display_name: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(32), default="sample")


class Agency(OperationalMixin, Base):
    __tablename__ = "agencies"
    display_name: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(32), default="sample")
    supplier_id: Mapped[Optional[str]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    parent_agency_id: Mapped[Optional[str]] = mapped_column(ForeignKey("agencies.id"), nullable=True)
    markup_bps: Mapped[int] = mapped_column(Integer, default=0)
    commission_bps: Mapped[int] = mapped_column(Integer, default=0)


class WhiteLabelConfiguration(OperationalMixin, Base):
    __tablename__ = "white_label_configurations"
    organization_id: Mapped[Optional[str]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(160))
    logo_reference: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(16), default="#0E7490")
    secondary_color: Mapped[str] = mapped_column(String(16), default="#082F49")
    custom_domain: Mapped[Optional[str]] = mapped_column(String(253), nullable=True)
    domain_status: Mapped[str] = mapped_column(String(24), default="unverified")
    support_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled_services_json: Mapped[str] = mapped_column(Text, default="[]")
    organization_policy_json: Mapped[str] = mapped_column(Text, default="{}")
    feature_flags_json: Mapped[str] = mapped_column(Text, default="{}")
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_white_label_tenant"),)


class ProviderContract(OperationalMixin, Base):
    __tablename__ = "provider_contracts"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    provider_key: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(24), default="disabled")
    config_reference: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)


class TravelProduct(OperationalMixin, Base):
    __tablename__ = "travel_products"
    supplier_id: Mapped[Optional[str]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    product_type: Mapped[str] = mapped_column(String(48), index=True)
    external_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    inventory_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class Offer(OperationalMixin, Base):
    __tablename__ = "offers"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("travel_products.id"), nullable=True)
    service_type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    available_units: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    provider_key: Mapped[str] = mapped_column(String(64), default="manual_supplier")
    fulfillment_mode: Mapped[str] = mapped_column(String(24), default="manual_supplier")
    attributes_json: Mapped[str] = mapped_column(Text, default="{}")
    policy_json: Mapped[str] = mapped_column(Text, default="{}")
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PriceCheck(OperationalMixin, Base):
    __tablename__ = "price_checks"
    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    units: Mapped[int] = mapped_column(Integer, default=1)
    snapshot_json: Mapped[str] = mapped_column(Text)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_price_check_command"),)


class SearchRequest(OperationalMixin, Base):
    __tablename__ = "search_requests"
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    service_type: Mapped[str] = mapped_column(String(48), index=True)
    criteria_json: Mapped[str] = mapped_column(Text, default="{}")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)


class SearchEntity(OperationalMixin, Base):
    __tablename__ = "search_entities"
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    normalized_title: Mapped[str] = mapped_column(String(240), index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    popularity_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", "normalized_title", name="uq_search_entity_normalized"),)


class SavedSearch(OperationalMixin, Base):
    __tablename__ = "saved_searches"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    query_json: Mapped[str] = mapped_column(Text)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    alert_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    alert_status: Mapped[str] = mapped_column(String(24), default="disabled")
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_saved_search_command"), UniqueConstraint("tenant_id", "user_id", "query_hash", name="uq_saved_search_query"))


class SavedTrip(OperationalMixin, Base):
    __tablename__ = "saved_trips"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_saved_trip_command"),)


class SavedTripItem(OperationalMixin, Base):
    __tablename__ = "saved_trip_items"
    saved_trip_id: Mapped[str] = mapped_column(ForeignKey("saved_trips.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    offer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("offers.id"), nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String(48), index=True)
    source_reference: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(24), default="wishlist", index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_saved_item_command"),)


class Review(OperationalMixin, Base):
    __tablename__ = "reviews"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String(48), index=True)
    service_reference: Mapped[str] = mapped_column(String(200), index=True)
    provider_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    rating: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    verified_booking: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    moderation_state: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    analysis_state: Mapped[str] = mapped_column(String(24), default="not_requested")
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_review_command"),)


class ReviewSupplierResponse(OperationalMixin, Base):
    __tablename__ = "review_supplier_responses"
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    responder_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "review_id", name="uq_review_supplier_response"), UniqueConstraint("tenant_id", "command_id", name="uq_review_response_command"))


class ReviewReport(OperationalMixin, Base):
    __tablename__ = "review_reports"
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), index=True)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(48))
    detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    command_id: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_review_report_command"), UniqueConstraint("tenant_id", "review_id", "reporter_user_id", name="uq_review_report_once"))


class Destination(OperationalMixin, Base):
    __tablename__ = "destinations"
    parent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("destinations.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    name_fa: Mapped[str] = mapped_column(String(160))
    name_en: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    slug: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    seasonality_json: Mapped[str] = mapped_column(Text, default="[]")
    categories_json: Mapped[str] = mapped_column(Text, default="[]")
    highlights_json: Mapped[str] = mapped_column(Text, default="[]")
    nearby_slugs_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_destination_slug"),)


class EditableItinerary(OperationalMixin, Base):
    __tablename__ = "editable_itineraries"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    destination_id: Mapped[Optional[str]] = mapped_column(ForeignKey("destinations.id"), nullable=True)
    budget_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_itinerary_command"),)


class EditableItineraryItem(OperationalMixin, Base):
    __tablename__ = "editable_itinerary_items"
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("editable_itineraries.id"), index=True)
    offer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("offers.id"), nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    day_number: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    availability_state: Mapped[str] = mapped_column(String(48), default="needs_live_availability_check")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_itinerary_item_command"), UniqueConstraint("tenant_id", "itinerary_id", "day_number", "position", name="uq_itinerary_position"))


class VacationProperty(OperationalMixin, Base):
    __tablename__ = "vacation_properties"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(180))
    city: Mapped[str] = mapped_column(String(120), index=True)
    property_type: Mapped[str] = mapped_column(String(48), index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_vacation_property_slug"),)


class VacationUnit(OperationalMixin, Base):
    __tablename__ = "vacation_units"
    property_id: Mapped[str] = mapped_column(ForeignKey("vacation_properties.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    capacity: Mapped[int] = mapped_column(Integer)
    available_units: Mapped[int] = mapped_column(Integer, default=1)
    nightly_price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    pricing_json: Mapped[str] = mapped_column(Text, default="{}")


class VacationReservation(OperationalMixin, Base):
    __tablename__ = "vacation_reservations"
    unit_id: Mapped[str] = mapped_column(ForeignKey("vacation_units.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    check_out: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    guests: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="held", index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_vacation_reservation_command"),)


class TourProduct(OperationalMixin, Base):
    __tablename__ = "tour_products"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(180))
    origin: Mapped[str] = mapped_column(String(120), index=True)
    destination: Mapped[str] = mapped_column(String(120), index=True)
    tour_type: Mapped[str] = mapped_column(String(48), index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_tour_product_slug"),)


class TourDeparture(OperationalMixin, Base):
    __tablename__ = "tour_departures"
    tour_id: Mapped[str] = mapped_column(ForeignKey("tour_products.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booking_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    remaining: Mapped[int] = mapped_column(Integer)
    base_price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    pricing_json: Mapped[str] = mapped_column(Text, default="{}")


class TourReservation(OperationalMixin, Base):
    __tablename__ = "tour_reservations"
    departure_id: Mapped[str] = mapped_column(ForeignKey("tour_departures.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    travellers: Mapped[int] = mapped_column(Integer)
    room_type: Mapped[str] = mapped_column(String(32), default="double")
    total_amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="held", index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    voucher_reference: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_tour_reservation_command"),)


class CruiseSailing(OperationalMixin, Base):
    __tablename__ = "cruise_sailings"
    supplier_id: Mapped[Optional[str]] = mapped_column(ForeignKey("suppliers.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    cruise_line: Mapped[str] = mapped_column(String(160))
    ship: Mapped[str] = mapped_column(String(160))
    departure_port: Mapped[str] = mapped_column(String(160))
    arrival_port: Mapped[str] = mapped_column(String(160))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    nights: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="catalog_only", index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")


class VisaProduct(OperationalMixin, Base):
    __tablename__ = "visa_products"
    destination_country: Mapped[str] = mapped_column(String(120), index=True)
    visa_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    source_url: Mapped[str] = mapped_column(String(500))
    source_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details_json: Mapped[str] = mapped_column(Text, default="{}")


class VisaApplication(OperationalMixin, Base):
    __tablename__ = "visa_applications"
    product_id: Mapped[str] = mapped_column(ForeignKey("visa_products.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True, index=True)
    tour_reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("tour_reservations.id"), nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(String(80))
    travel_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="started", index=True)
    case_manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_visa_application_command"),)


class VisaApplicant(OperationalMixin, Base):
    __tablename__ = "visa_applicants"
    application_id: Mapped[str] = mapped_column(ForeignKey("visa_applications.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    passport_country: Mapped[str] = mapped_column(String(120))
    passport_reference: Mapped[str] = mapped_column(String(160))


class VisaDocument(OperationalMixin, Base):
    __tablename__ = "visa_documents"
    application_id: Mapped[str] = mapped_column(ForeignKey("visa_applications.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="missing", index=True)
    storage_reference: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "application_id", "document_type", name="uq_visa_document_type"),)


class VisaTimelineEvent(OperationalMixin, Base):
    __tablename__ = "visa_timeline_events"
    application_id: Mapped[str] = mapped_column(ForeignKey("visa_applications.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    event_key: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "event_key", name="uq_visa_timeline_event_key"),)


class Reservation(OperationalMixin, Base):
    __tablename__ = "reservations"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_type: Mapped[str] = mapped_column(String(48), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    provider_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    price_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    policy_at_booking_json: Mapped[str] = mapped_column(Text, default="{}")
    current_policy_json: Mapped[str] = mapped_column(Text, default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1)
    booking_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    price_check_id: Mapped[Optional[str]] = mapped_column(ForeignKey("price_checks.id"), nullable=True, index=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True, index=True)


class CheckoutSession(OperationalMixin, Base):
    __tablename__ = "checkout_sessions"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(32), default="review", index=True)
    price_snapshot_hash: Mapped[str] = mapped_column(String(64))
    policy_snapshot_hash: Mapped[str] = mapped_column(String(64))
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    payment_intent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("payment_intents.id"), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_checkout_command"),)


class BookingStatusHistory(OperationalMixin, Base):
    __tablename__ = "booking_status_history"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    command_id: Mapped[str] = mapped_column(String(120))
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_booking_history_command"),)


class BookingItem(OperationalMixin, Base):
    __tablename__ = "booking_items"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("travel_products.id"), nullable=True)
    item_type: Mapped[str] = mapped_column(String(48))
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")


class Traveller(OperationalMixin, Base):
    __tablename__ = "travellers"
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(160))
    profile_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)


class ReservationTraveller(Base):
    __tablename__ = "reservation_travellers"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), primary_key=True)
    traveller_id: Mapped[str] = mapped_column(ForeignKey("travellers.id"), primary_key=True)


class Ticket(OperationalMixin, Base):
    __tablename__ = "tickets"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    document_reference: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)


class Voucher(OperationalMixin, Base):
    __tablename__ = "vouchers"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    document_reference: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)


class BookingServiceRequest(OperationalMixin, Base):
    __tablename__ = "booking_service_requests"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(32), index=True)
    case_type: Mapped[str] = mapped_column(String(32), default="voluntary")
    status: Mapped[str] = mapped_column(String(32), default="submitted", index=True)
    quote_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Wallet(OperationalMixin, Base):
    __tablename__ = "wallets"
    owner_type: Mapped[str] = mapped_column(String(32))
    owner_reference: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    __table_args__ = (UniqueConstraint("tenant_id", "owner_type", "owner_reference", "currency", name="uq_wallet_owner"),)


class CreditAccount(OperationalMixin, Base):
    __tablename__ = "credit_accounts"
    organization_id: Mapped[Optional[str]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    limit_amount: Mapped[int] = mapped_column(Integer, default=0)


class InstallmentPlan(OperationalMixin, Base):
    __tablename__ = "installment_plans"
    organization_id: Mapped[Optional[str]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    terms_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="disabled")


class InstallmentAgreement(OperationalMixin, Base):
    __tablename__ = "installment_agreements"
    plan_id: Mapped[str] = mapped_column(ForeignKey("installment_plans.id"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    principal_amount: Mapped[int] = mapped_column(Integer)
    total_payable: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    schedule_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="requested", index=True)
    activated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_installment_agreement_command"), UniqueConstraint("tenant_id", "reservation_id", name="uq_installment_reservation"))


class PricingRule(OperationalMixin, Base):
    __tablename__ = "pricing_rules"
    rule_type: Mapped[str] = mapped_column(String(32), index=True)
    service_type: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    configuration_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="disabled")


class SettlementRecord(OperationalMixin, Base):
    __tablename__ = "settlement_records"
    supplier_id: Mapped[Optional[str]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    external_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)


class FinancialLedgerEntry(OperationalMixin, Base):
    __tablename__ = "financial_ledger_entries"
    wallet_id: Mapped[str] = mapped_column(ForeignKey("wallets.id"), index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    command_id: Mapped[str] = mapped_column(String(80))
    entry_type: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reversal_of_id: Mapped[Optional[str]] = mapped_column(ForeignKey("financial_ledger_entries.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_ledger_command"),)


class PaymentIntent(OperationalMixin, Base):
    __tablename__ = "payment_intents"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    provider_key: Mapped[str] = mapped_column(String(64), default="payment")
    provider_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    provider_authority: Mapped[Optional[str]] = mapped_column(String(160), nullable=True, index=True)
    provider_capture_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    captured_amount: Mapped[int] = mapped_column(Integer, default=0)
    refunded_amount: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_payment_command"),)


class PaymentEvent(OperationalMixin, Base):
    __tablename__ = "payment_events"
    payment_intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id"), index=True)
    provider_event_id: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("provider_key", "provider_event_id", name="uq_payment_provider_event"),)
    provider_key: Mapped[str] = mapped_column(String(64))


class RefundRecord(OperationalMixin, Base):
    __tablename__ = "refund_records"
    payment_intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="requested", index=True)
    provider_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_refund_command"),)


class Invoice(OperationalMixin, Base):
    __tablename__ = "invoices"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    subtotal_amount: Mapped[int] = mapped_column(Integer)
    tax_amount: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    status: Mapped[str] = mapped_column(String(24), default="issued", index=True)
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_invoice_command"), UniqueConstraint("tenant_id", "reservation_id", name="uq_invoice_reservation"))


class ApprovalWorkflow(OperationalMixin, Base):
    __tablename__ = "approval_workflows"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    approver_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    policy_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    template_id: Mapped[Optional[str]] = mapped_column(ForeignKey("approval_templates.id"), nullable=True)
    current_step_order: Mapped[int] = mapped_column(Integer, default=1)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0)


class ApprovalTemplate(OperationalMixin, Base):
    __tablename__ = "approval_templates"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="active")
    __table_args__ = (UniqueConstraint("tenant_id", "organization_id", "name", "version", name="uq_approval_template_version"),)


class ApprovalTemplateStep(OperationalMixin, Base):
    __tablename__ = "approval_template_steps"
    template_id: Mapped[str] = mapped_column(ForeignKey("approval_templates.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    required_role: Mapped[str] = mapped_column(String(48))
    sla_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    __table_args__ = (UniqueConstraint("tenant_id", "template_id", "step_order", name="uq_approval_template_step"),)


class ApprovalInstanceStep(OperationalMixin, Base):
    __tablename__ = "approval_instance_steps"
    workflow_id: Mapped[str] = mapped_column(ForeignKey("approval_workflows.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    required_role: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(24), default="waiting")
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "workflow_id", "step_order", name="uq_approval_instance_step"),)


class Trip(OperationalMixin, Base):
    __tablename__ = "trips"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    origin: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    destination: Mapped[str] = mapped_column(String(120), index=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planned")


class TripEventRecord(OperationalMixin, Base):
    __tablename__ = "trip_events"
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    event_key: Mapped[str] = mapped_column(String(120))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(24), default="info")
    source: Mapped[str] = mapped_column(String(32), default="system")
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(24), default="customer")
    deep_link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "event_key", name="uq_trip_event_key"),)


class NotificationRecord(OperationalMixin, Base):
    __tablename__ = "notifications"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    trip_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trip_events.id"), nullable=True)
    topic: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    deep_link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")


class NotificationDeliveryAttempt(OperationalMixin, Base):
    __tablename__ = "notification_delivery_attempts"
    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id"), index=True)
    channel: Mapped[str] = mapped_column(String(24))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="not_sent")
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    receipt_event_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True, unique=True)


class NotificationPreference(OperationalMixin, Base):
    __tablename__ = "notification_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic: Mapped[str] = mapped_column(String(48))
    channel: Mapped[str] = mapped_column(String(24))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "topic", "channel", name="uq_notification_preference"),)


class SupportMessage(OperationalMixin, Base):
    __tablename__ = "support_messages"
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    sender_type: Mapped[str] = mapped_column(String(32), index=True)
    body: Mapped[str] = mapped_column(Text)


class SupportCase(OperationalMixin, Base):
    __tablename__ = "support_cases"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True, index=True)
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_support_case_command"),)


class SupportThreadMessage(OperationalMixin, Base):
    __tablename__ = "support_thread_messages"
    case_id: Mapped[str] = mapped_column(ForeignKey("support_cases.id"), index=True)
    sender_type: Mapped[str] = mapped_column(String(32), index=True)
    sender_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)


class AIConversationReference(OperationalMixin, Base):
    __tablename__ = "ai_conversation_references"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True)
    external_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)


class IdempotencyKey(OperationalMixin, Base):
    __tablename__ = "idempotency_keys"
    scope: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(128))
    response_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "scope", "key", name="uq_idempotency_scope_key"),)


class OutboxEvent(OperationalMixin, Base):
    __tablename__ = "outbox_events"
    aggregate_type: Mapped[str] = mapped_column(String(64), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    dead_lettered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


BOOKING_TRANSITIONS = {
    "draft": {"pending", "failed", "expired"},
    "pending": {"reserved", "failed", "expired"},
    "reserved": {"awaiting_payment", "confirmed", "cancel_requested", "expired"},
    "awaiting_payment": {"confirmed", "failed", "expired", "cancel_requested"},
    "confirmed": {"issued", "change_requested", "cancel_requested", "refund_requested"},
    "issued": {"completed", "change_requested", "cancel_requested", "refund_requested"},
    "cancel_requested": {"cancelled", "confirmed"},
    "change_requested": {"changed", "confirmed"},
    "refund_requested": {"refunded", "confirmed"},
    "changed": {"issued", "completed"},
}


TRIP_STATUS_TITLES = {
    "pending": "در انتظار تأیید", "reserved": "رزرو شد", "awaiting_payment": "در انتظار پرداخت",
    "confirmed": "تأیید شد", "issued": "صادر شد", "completed": "تکمیل شد",
    "cancel_requested": "درخواست کنسلی ثبت شد", "change_requested": "درخواست تغییر ثبت شد",
    "refund_requested": "درخواست استرداد ثبت شد", "cancelled": "کنسل شد",
    "changed": "تغییر یافت", "refunded": "استرداد شد", "failed": "ناموفق شد", "expired": "منقضی شد",
}


def ensure_trip_for_reservation(db: Session, reservation: Reservation, *, title: str, destination: str, origin: Optional[str] = None, starts_at: Optional[datetime] = None, ends_at: Optional[datetime] = None) -> "Trip":
    """Find-or-create the Trip a reservation belongs to. One reservation
    always maps to exactly one trip; this is what turns a booking into
    something that shows up in My Trips / Trip Timeline instead of just
    existing as an isolated Reservation row."""
    if reservation.trip_id:
        existing = db.get(Trip, reservation.trip_id)
        if existing is not None:
            return existing
    trip = Trip(tenant_id=reservation.tenant_id, user_id=reservation.user_id, title=title, origin=origin, destination=destination, starts_at=starts_at, ends_at=ends_at, status="planned")
    db.add(trip); db.flush()
    reservation.trip_id = trip.id
    return trip


def record_trip_event(db: Session, *, tenant_id: int, trip_id: str, event_key: str, event_type: str, source: str, title: str, message: str, reservation_id: Optional[str] = None, severity: str = "info", requires_action: bool = False, deep_link: Optional[str] = None) -> None:
    """Append one Trip Timeline entry, idempotently (same event_key is a
    no-op). `source` must be one of system/ai/human_agent/provider so the
    timeline can honestly distinguish who/what made the change."""
    exists = db.scalar(select(TripEventRecord.id).where(TripEventRecord.tenant_id == tenant_id, TripEventRecord.event_key == event_key))
    if exists:
        return
    db.add(TripEventRecord(tenant_id=tenant_id, trip_id=trip_id, reservation_id=reservation_id, event_key=event_key, event_type=event_type, source=source, title=title, message=message, severity=severity, requires_action=requires_action, effective_at=utcnow(), deep_link=deep_link))


def transition_reservation(db: Session, reservation: Reservation, target: str, actor_id: int, command_id: str) -> Reservation:
    prior = next((item for item in db.new if isinstance(item, IdempotencyKey) and item.tenant_id == reservation.tenant_id and item.scope == "reservation.transition" and item.key == command_id), None)
    if prior is None:
        prior = db.scalar(select(IdempotencyKey).where(IdempotencyKey.tenant_id == reservation.tenant_id, IdempotencyKey.scope == "reservation.transition", IdempotencyKey.key == command_id))
    if prior:
        return reservation
    if target not in BOOKING_TRANSITIONS.get(reservation.status, set()):
        raise ValueError(f"invalid reservation transition: {reservation.status} -> {target}")
    previous = reservation.status
    reservation.status = target
    reservation.version += 1
    db.add(IdempotencyKey(tenant_id=reservation.tenant_id, scope="reservation.transition", key=command_id, request_hash=f"{reservation.id}:{target}", response_json=json.dumps({"status": target})))
    db.add(OutboxEvent(tenant_id=reservation.tenant_id, aggregate_type="reservation", aggregate_id=reservation.id, event_type=f"reservation.{target}", payload_json=json.dumps({"actor_id": actor_id, "status": target})))
    db.add(BookingStatusHistory(tenant_id=reservation.tenant_id, reservation_id=reservation.id, from_status=previous, to_status=target, actor_id=actor_id, command_id=command_id))
    if reservation.trip_id:
        label = TRIP_STATUS_TITLES.get(target, target)
        record_trip_event(db, tenant_id=reservation.tenant_id, trip_id=reservation.trip_id, reservation_id=reservation.id, event_key=f"reservation-transition:{command_id}", event_type=f"reservation.{target}", source="system", title=label, message=f"وضعیت رزرو {reservation.booking_reference or reservation.id} از «{TRIP_STATUS_TITLES.get(previous, previous)}» به «{label}» تغییر کرد.", severity="warning" if target in {"cancel_requested", "cancelled", "failed", "expired"} else "info", requires_action=target in {"cancel_requested", "change_requested", "refund_requested"}, deep_link=f"/manage-booking/{reservation.id}")
    return reservation


def post_ledger(db: Session, *, tenant_id: int, wallet_id: str, command_id: str, entry_type: str, amount: int, reservation_id: Optional[str] = None, reversal_of_id: Optional[str] = None) -> FinancialLedgerEntry:
    existing = next((item for item in db.new if isinstance(item, FinancialLedgerEntry) and item.tenant_id == tenant_id and item.command_id == command_id), None)
    if existing is None:
        existing = db.scalar(select(FinancialLedgerEntry).where(FinancialLedgerEntry.tenant_id == tenant_id, FinancialLedgerEntry.command_id == command_id))
    if existing:
        return existing
    if amount <= 0:
        raise ValueError("ledger amount must be positive")
    entry = FinancialLedgerEntry(tenant_id=tenant_id, wallet_id=wallet_id, reservation_id=reservation_id, command_id=command_id, entry_type=entry_type, amount=amount, reversal_of_id=reversal_of_id)
    db.add(entry)
    return entry


def wallet_balances(db: Session, *, tenant_id: int, wallet_id: str) -> dict[str, int]:
    entries = db.scalars(select(FinancialLedgerEntry).where(FinancialLedgerEntry.tenant_id == tenant_id, FinancialLedgerEntry.wallet_id == wallet_id)).all()
    available = reserved = consumed = 0
    for entry in entries:
        if entry.entry_type == "allocate":
            available += entry.amount
        elif entry.entry_type == "reserve":
            available -= entry.amount
            reserved += entry.amount
        elif entry.entry_type == "capture":
            reserved -= entry.amount
            consumed += entry.amount
        elif entry.entry_type == "release":
            reserved -= entry.amount
            available += entry.amount
        elif entry.entry_type == "reverse_capture":
            consumed -= entry.amount
            available += entry.amount
    return {"available": available, "reserved": reserved, "consumed": consumed}


def apply_credit_command(db: Session, *, tenant_id: int, wallet_id: str, command_id: str, entry_type: str, amount: int, reservation_id: Optional[str] = None, reversal_of_id: Optional[str] = None) -> FinancialLedgerEntry:
    wallet = db.scalar(select(Wallet).where(Wallet.id == wallet_id, Wallet.tenant_id == tenant_id).with_for_update())
    if wallet is None:
        raise ValueError("wallet not found in tenant")
    db.flush()
    existing = db.scalar(select(FinancialLedgerEntry).where(FinancialLedgerEntry.tenant_id == tenant_id, FinancialLedgerEntry.command_id == command_id))
    if existing:
        return existing
    balances = wallet_balances(db, tenant_id=tenant_id, wallet_id=wallet_id)
    if entry_type == "reserve" and balances["available"] < amount:
        raise ValueError("insufficient available credit")
    if entry_type in {"capture", "release"} and balances["reserved"] < amount:
        raise ValueError("insufficient reserved credit")
    if entry_type == "reverse_capture" and balances["consumed"] < amount:
        raise ValueError("insufficient consumed credit")
    return post_ledger(db, tenant_id=tenant_id, wallet_id=wallet_id, command_id=command_id, entry_type=entry_type, amount=amount, reservation_id=reservation_id, reversal_of_id=reversal_of_id)


def create_refresh_session(db: Session, *, tenant_id: int, user_id: int, expires_at: datetime, family_id: Optional[str] = None, device_hash: Optional[str] = None, ip_hash: Optional[str] = None) -> tuple[str, RefreshTokenSession]:
    raw_token = f"{tenant_id}.{secrets.token_urlsafe(48)}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session = RefreshTokenSession(tenant_id=tenant_id, user_id=user_id, token_hash=token_hash, expires_at=expires_at, family_id=family_id or uuid4_str(), device_hash=device_hash, ip_hash=ip_hash)
    db.add(session)
    return raw_token, session


def find_refresh_session(db: Session, raw_token: str) -> Optional[RefreshTokenSession]:
    try:
        tenant_id = int(raw_token.split(".", 1)[0])
        set_tenant_context(db, tenant_id)
    except (ValueError, IndexError):
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return db.scalar(select(RefreshTokenSession).where(RefreshTokenSession.tenant_id == tenant_id, RefreshTokenSession.token_hash == token_hash))


def ingest_trip_event(db: Session, event: TripEventRecord) -> TripEventRecord:
    existing = db.scalar(select(TripEventRecord).where(TripEventRecord.tenant_id == event.tenant_id, TripEventRecord.event_key == event.event_key))
    if existing:
        return existing
    db.add(event)
    db.flush()
    trip = db.scalar(select(Trip).where(Trip.id == event.trip_id, Trip.tenant_id == event.tenant_id))
    notification_id = None
    if trip is not None and event.visibility == "customer":
        notification = NotificationRecord(tenant_id=event.tenant_id, user_id=trip.user_id, trip_event_id=event.id, topic="important_trip_changes", title=event.title, message=event.message, deep_link=event.deep_link)
        db.add(notification)
        db.flush()
        notification_id = notification.id
        for channel in ("in_app", "push", "sms"):
            preference_channels = ("web", "app") if channel == "in_app" else (channel,)
            disabled = db.scalar(select(NotificationPreference.id).where(NotificationPreference.tenant_id == event.tenant_id, NotificationPreference.user_id == trip.user_id, NotificationPreference.topic == "important_trip_changes", NotificationPreference.channel.in_(preference_channels), NotificationPreference.enabled.is_(False)).limit(1))
            if disabled is None:
                db.add(NotificationDeliveryAttempt(tenant_id=event.tenant_id, notification_id=notification.id, channel=channel, status="pending" if channel == "in_app" else "not_sent"))
    correlation_id = str(uuid.uuid4())
    db.add(OutboxEvent(tenant_id=event.tenant_id, aggregate_type="trip", aggregate_id=event.trip_id, event_type="trip.event.recorded", payload_json=json.dumps({"trip_event_id": event.id, "notification_id": notification_id, "severity": event.severity}), correlation_id=correlation_id, idempotency_key=event.event_key))
    return event


Index("ix_outbox_ready", OutboxEvent.status, OutboxEvent.available_at)
Index("ix_offers_tenant_search", Offer.tenant_id, Offer.service_type, Offer.status, Offer.valid_until, Offer.amount)
Index("ix_reservations_tenant_user_created", Reservation.tenant_id, Reservation.user_id, Reservation.created_at)
Index("ix_payment_reconciliation", PaymentIntent.tenant_id, PaymentIntent.reservation_id, PaymentIntent.status)
Index("ix_trip_timeline", TripEventRecord.tenant_id, TripEventRecord.trip_id, TripEventRecord.visibility, TripEventRecord.created_at)
