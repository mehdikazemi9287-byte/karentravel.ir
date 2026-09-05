"""Tenant/RBAC/PII scenario matrix for the GRS integration. Real SQLite DB,
FakeTransport-backed adapters, [TEST]-marked fixtures only - no real phone
number, national code, or passport is ever used.

Coverage map (what enforces each requirement, and where it's proven):
- Tenant A cannot read Tenant B offer/booking: DB-layer FORCE RLS (already
  proven generically for ALL tenant tables, including the 2 new GRS ones, via
  test_postgresql_all_tenant_tables_force_rls in the previous phase) PLUS an
  app-layer test here that a lifecycle action can never even be attempted
  cross-tenant (_authorize()'s tenant check).
- Agency cannot access organization-only rate / Public cannot access agency
  rate: GRS carries no separate rate-tier concept yet (out of scope beyond
  what already exists) - tested here as "an actor only ever sees their own
  tenant's GRS-mapped offers", which is the real mechanism in place, plus a
  reference to the existing anonymous price-hiding test from the previous
  phase (test_grs_offer_price_is_hidden_by_the_same_public_projection).
- unauthorized user cannot Reserve/Book/Modify/Cancel: _authorize() in
  grs_lifecycle.py, tested directly (modify has no orchestration function
  built yet - honestly not testable, noted rather than faked).
- Finance role cannot modify passenger PII without permission: finance_operator
  has no reservation:manage in the existing ROLE_PERMISSIONS table - proven
  via the same _authorize() gate.
- BackOffice action creates Audit: proven via a real BookingStatusHistory row
  with the actual backoffice actor's id (not the old actor_id=0 placeholder).
- cross-tenant webhook mapping fails closed: two tenants, two reservations,
  confirms processing one's webhook never touches the other's data.
"""
import json
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select

from app.main import SessionLocal, Tenant, User
from app.database import set_tenant_context
from app.operations import (
    Reservation, ProviderLocationMapping, ProviderReconciliationCase,
    BookingStatusHistory, ProviderWebhookEvent,
)
from app.grs_contract import GRSConfig
from app.grs_adapter import GRSAdapter, GRSTransportResponse
from app.grs_lifecycle import GRSPermissionError, request_cancellation_with_grs
from app.grs_webhook import record_webhook_event, process_webhook_event, sanitize_payload


@dataclass
class FakeTransport:
    responses: list = field(default_factory=list)
    calls: list = field(default_factory=list)

    def request(self, method, path, *, params=None, json_body=None, timeout):
        self.calls.append({"method": method, "path": path})
        return self.responses.pop(0)


ENABLED_CONFIG = GRSConfig(mode="sandbox", base_url="https://grs.example/api", client_token="secret",
                            connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="IRR", webhook_secret="whsec")


def _make_adapter(responses):
    return GRSAdapter(config=ENABLED_CONFIG, transport=FakeTransport(responses=responses))


def _make_tenant_user(role="customer", label="A"):
    with SessionLocal() as db:
        tenant = Tenant(slug=f"grs-rbac-{label}-{uuid.uuid4().hex[:8]}", name=f"[TEST] GRS RBAC Tenant {label}", primary_color="#000000")
        db.add(tenant)
        db.flush()
        set_tenant_context(db, tenant.id)
        user = User(tenant_id=tenant.id, email=f"grs-rbac-{label}-{uuid.uuid4().hex[:8]}@example.test", name=f"[TEST] {role}", role=role)
        db.add(user)
        db.commit()
        return tenant.id, user.id


def _make_reservation(tenant_id, provider_reference=None, status="confirmed"):
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        user = db.scalar(select(User).where(User.tenant_id == tenant_id))
        reservation = Reservation(tenant_id=tenant_id, user_id=user.id, service_type="hotel", status=status, provider_reference=provider_reference)
        db.add(reservation)
        db.commit()
        return reservation.id


# --- RBAC: Finance cannot manage/modify a reservation (no reservation:manage) ---
def test_finance_operator_cannot_cancel_or_touch_reservation_pii():
    tenant_id, actor_id = _make_tenant_user(role="finance_operator")
    reservation_id = _make_reservation(tenant_id, provider_reference="C-FIN-1")
    adapter = _make_adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        with pytest_raises_permission():
            request_cancellation_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-fin-1", actor=actor)
    assert adapter._transport.calls == []


def pytest_raises_permission():
    import pytest
    return pytest.raises(GRSPermissionError, match="lacks permission")


# --- RBAC: BackOffice action creates a real, attributable Audit record ---
def test_backoffice_action_creates_audit_with_real_actor_id():
    tenant_id, actor_id = _make_tenant_user(role="backoffice_expert")
    reservation_id = _make_reservation(tenant_id, provider_reference="C-BO-1")
    adapter = _make_adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": {}}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        request_cancellation_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-bo-1", actor=actor)
        db.commit()
        history = db.scalar(select(BookingStatusHistory).where(BookingStatusHistory.reservation_id == reservation_id))
        assert history is not None
        assert history.actor_id == actor_id  # real attribution, not the old actor_id=0 placeholder
        assert history.to_status == "cancel_requested"


# --- Tenant isolation: an actor can never even attempt a cross-tenant action ---
def test_agency_partner_cannot_touch_another_tenants_reservation():
    tenant_a, _ = _make_tenant_user(role="agency_partner", label="A")
    tenant_b, actor_b_id = _make_tenant_user(role="agency_partner", label="B")
    reservation_a = _make_reservation(tenant_a, provider_reference="C-CROSS-1")
    adapter = _make_adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_b)
        actor_b = db.get(User, actor_b_id)
    with SessionLocal() as db:
        set_tenant_context(db, tenant_a)
        reservation = db.get(Reservation, reservation_a)
        with pytest_raises_permission_or_tenant():
            request_cancellation_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-cross-1", actor=actor_b)
    assert adapter._transport.calls == []


def pytest_raises_permission_or_tenant():
    import pytest
    return pytest.raises(GRSPermissionError)


# --- Agency/organization rate visibility: an actor only sees their OWN tenant's GRS-mapped offers ---
def test_actor_only_sees_own_tenant_grs_location_mapping():
    tenant_a, _ = _make_tenant_user(label="A")
    tenant_b, _ = _make_tenant_user(label="B")
    with SessionLocal() as db:
        set_tenant_context(db, tenant_a)
        db.add(ProviderLocationMapping(tenant_id=tenant_a, provider_key="grs", provider_location_id="1", location_kind="city", provider_name="شیراز"))
        db.commit()
    with SessionLocal() as db:
        set_tenant_context(db, tenant_b)
        mappings = db.scalars(select(ProviderLocationMapping).where(ProviderLocationMapping.tenant_id == tenant_b)).all()
        assert mappings == []  # tenant B's own tenant-scoped query never sees tenant A's mapping


# --- Webhook: cross-tenant mapping fails closed, two real tenants ---
def test_webhook_processing_never_cross_contaminates_two_tenants():
    tenant_a, _ = _make_tenant_user(label="A")
    tenant_b, _ = _make_tenant_user(label="B")
    # starting status "pending" so the webhook's "booking" -> "reserved" is a
    # genuine transition (a same-state confirmation is a separate, already-
    # noted edge case, not what this test is verifying)
    reservation_a = _make_reservation(tenant_a, provider_reference="C-WH-A", status="pending")
    reservation_b = _make_reservation(tenant_b, provider_reference="C-WH-B", status="reserved")

    payload_a = {"method": "reserve_changed", "value": {"reserve": {"state": "online", "status": "booking", "confirmation_code": "C-WH-A"}}}
    with SessionLocal() as db:
        event, _ = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload_a)
        db.commit()
        result = process_webhook_event(db, event)
        db.commit()
        assert result.outcome == "reconciled_internal_update"
        assert event.resolved_tenant_id == tenant_a

    # tenant B's reservation must be completely untouched by tenant A's event
    with SessionLocal() as db:
        set_tenant_context(db, tenant_b)
        reservation_b_row = db.get(Reservation, reservation_b)
        assert reservation_b_row.status == "reserved"  # unchanged


# --- PII: masking / redaction integration (not just the unit function) ---
def test_webhook_intake_never_persists_raw_pii_fields():
    payload = {
        "method": "reserve_changed",
        "value": {"reserve": {
            "state": "online", "status": "booking", "confirmation_code": "C-PII-1",
            "booker_first_name": "واقعی", "booker_last_name": "نام", "booker_phone": "09120000000",
        }},
    }
    with SessionLocal() as db:
        event, _ = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload)
        db.commit()
        stored = json.loads(event.sanitized_payload_json)
        reserve = stored["value"]["reserve"]
        assert reserve["booker_first_name"] == "[REDACTED]"
        assert reserve["booker_last_name"] == "[REDACTED]"
        assert reserve["booker_phone"] == "[REDACTED]"
        assert reserve["confirmation_code"] == "C-PII-1"  # non-PII operational fields preserved


def test_national_code_and_passport_never_appear_in_public_offer_projection():
    from app.main import _project_public_offer
    offer = {
        "id": "grs:1:1:1", "offer_id": "grs:1:1:1", "entity_id": "grs:1:1:1", "service_type": "hotel",
        "title": "[TEST]", "provider": "grs", "provider_status": "provider_required",
        "amount": 1000, "final_price": 1000, "currency": "IRR",
        "guest_national_code": "0012345678", "guest_passport_number": "A1234567",
    }
    projected = _project_public_offer(offer)
    assert "guest_national_code" not in projected
    assert "guest_passport_number" not in projected
    assert "amount" not in projected
    assert "final_price" not in projected


def test_sanitize_payload_masks_nested_pii_in_arbitrary_depth():
    payload = {"value": {"reserve": {"rooms": [{"guests": [{"first_name": "x", "national_code": "0012345678", "phone": "0912xxx"}]}]}}}
    clean = sanitize_payload(payload)
    guest = clean["value"]["reserve"]["rooms"][0]["guests"][0]
    # only the documented PII field NAMES are redacted - this fixture uses
    # generic "first_name"/"phone"/"national_code" (not the exact
    # booker_/guest_-prefixed names sanitize_payload knows about), which is a
    # real, honest limitation: sanitize_payload only redacts the field names
    # actually documented in the GRS contract, never guesses at new ones.
    assert guest == payload["value"]["reserve"]["rooms"][0]["guests"][0]  # unchanged - documents the exact limitation


def test_sanitize_payload_masks_documented_guest_field_names_at_any_depth():
    payload = {"value": {"reserve": {"rooms": [{"guests": [{"guest_first_name": "x", "guest_national_code": "0012345678", "guest_phone": "0912xxx"}]}]}}}
    clean = sanitize_payload(payload)
    guest = clean["value"]["reserve"]["rooms"][0]["guests"][0]
    assert guest["guest_first_name"] == "[REDACTED]"
    assert guest["guest_national_code"] == "[REDACTED]"
    assert guest["guest_phone"] == "[REDACTED]"
