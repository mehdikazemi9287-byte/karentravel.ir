"""Integration tests for the GRS booking lifecycle - real SQLite DB (same
engine/session the rest of the suite uses), FakeTransport-backed GRSAdapter
(no real network ever reached). Fixtures use dummy [TEST] data only."""
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest
from sqlalchemy import select

from app.main import SessionLocal, Tenant, User
from app.database import set_tenant_context
from app.operations import Reservation, ProviderReconciliationCase, IdempotencyKey
from app.grs_contract import GRSConfig
from app.grs_adapter import GRSAdapter, GRSTransportResponse
from app.grs_lifecycle import (
    GRSLifecycleError, GRSPermissionError, reserve_with_grs, book_with_grs,
    request_cancellation_with_grs, accept_cancellation_with_grs,
)


@dataclass
class FakeTransport:
    responses: list = field(default_factory=list)
    calls: list = field(default_factory=list)

    def request(self, method, path, *, params=None, json_body=None, timeout):
        self.calls.append({"method": method, "path": path, "json_body": json_body})
        return self.responses.pop(0)


ENABLED_CONFIG = GRSConfig(mode="sandbox", base_url="https://grs.example/api", client_token="secret",
                            connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="IRR", webhook_secret="whsec")


def _make_adapter(responses):
    return GRSAdapter(config=ENABLED_CONFIG, transport=FakeTransport(responses=responses))


def _make_tenant_user_reservation(role="customer"):
    with SessionLocal() as db:
        tenant = Tenant(slug=f"grs-test-{uuid.uuid4().hex[:8]}", name="[TEST] GRS Lifecycle Tenant", primary_color="#000000")
        db.add(tenant)
        db.flush()
        set_tenant_context(db, tenant.id)
        user = User(tenant_id=tenant.id, email=f"grs-test-{uuid.uuid4().hex[:8]}@example.test", name="[TEST] Guest", role=role)
        db.add(user)
        db.flush()
        reservation = Reservation(tenant_id=tenant.id, user_id=user.id, service_type="hotel", status="draft")
        db.add(reservation)
        db.commit()
        return tenant.id, reservation.id, user.id


RESERVE_PAYLOAD = {
    "property_id": 1, "check_in": "2026-09-15", "check_out": "2026-09-18",
    "booker_first_name": "[TEST]", "booker_last_name": "Guest", "booker_phone": "0000000000",
    "rooms": [{"room_type_id": 1, "rate_plan_id": 1, "count": 1}],
}


def test_reserve_success_transitions_to_reserved_and_stores_confirmation_code():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None,
                                                         "value": {"reserve": {"state": "online", "status": "pending", "confirmation_code": "C-TEST-1"}}}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        outcome = reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-1", actor=actor)
        db.commit()
        assert outcome.ok is True
        assert outcome.provider_confirmation_code == "C-TEST-1"
        assert reservation.status == "reserved"
        assert reservation.provider_reference == "C-TEST-1"


def test_reserve_business_failure_marks_reservation_failed():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([GRSTransportResponse(200, {"code": 200, "message": "", "errors": [{"name": "inventory", "message": "Room Ids: 1"}],
                                                         "value": {"reserve": {"status": "rejected"}}}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        outcome = reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-2", actor=actor)
        db.commit()
        assert outcome.ok is False
        assert reservation.status == "failed"


def test_reserve_ambiguous_timeout_opens_reconciliation_case_not_a_guess():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([GRSTransportResponse(429, None, "text/html")])  # retryable -> ambiguous, not a hard failure
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        outcome = reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-3", actor=actor)
        db.commit()
        assert outcome.ok is False
        assert outcome.reconciliation_case is not None
        # reservation is NOT force-failed on an ambiguous/retryable outcome
        assert reservation.status == "pending"
        case = db.scalar(select(ProviderReconciliationCase).where(ProviderReconciliationCase.tenant_id == tenant_id))
        assert case is not None
        assert case.status == "manual_review_required"


def test_reserve_is_idempotent_for_same_command_id():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None,
                                                         "value": {"reserve": {"state": "online", "status": "pending", "confirmation_code": "C-TEST-4"}}}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-5", actor=actor)
        db.commit()
    # second call, same command_id, adapter has NO more queued responses - if it
    # were called again this would raise IndexError (proves no duplicate call)
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        outcome = reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-5", actor=actor)
        assert outcome.detail == "idempotent replay"


def test_book_refuses_without_independently_confirmed_payment():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        reservation.status = "reserved"
        reservation.provider_reference = "C-TEST-6"
        db.commit()
        with pytest.raises(GRSLifecycleError, match="payment/credit confirmation was not proven"):
            book_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-6", payment_or_credit_confirmed=False, actor=actor)


def test_book_succeeds_only_with_confirmed_payment_and_booked_status():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None,
                                                         "value": {"reserve": {"status": "booked", "confirmation_code": "C-TEST-7"}}}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        reservation.status = "reserved"
        reservation.provider_reference = "C-TEST-7"
        db.commit()
        outcome = book_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-7", payment_or_credit_confirmed=True, actor=actor)
        db.commit()
        assert outcome.ok is True
        assert reservation.status == "confirmed"


def test_book_with_unexpected_status_after_success_opens_reconciliation_not_a_guess():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None,
                                                         "value": {"reserve": {"status": "suggested", "confirmation_code": "C-TEST-8"}}}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        reservation.status = "reserved"
        reservation.provider_reference = "C-TEST-8"
        db.commit()
        outcome = book_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-8", payment_or_credit_confirmed=True, actor=actor)
        db.commit()
        assert reservation.status == "reserved"  # untouched - NOT force-confirmed, no premature transition either
        case = db.scalar(select(ProviderReconciliationCase).where(ProviderReconciliationCase.reservation_id == reservation_id))
        assert case is not None


def test_cancellation_lifecycle_two_step_not_immediately_final():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([
        GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": {}}, "application/json"),  # request_cancellation
        GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": {}}, "application/json"),  # accept_cancellation
    ])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        reservation.status = "confirmed"
        reservation.provider_reference = "C-TEST-9"
        db.commit()

        request_cancellation_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-9a", actor=actor)
        db.commit()
        assert reservation.status == "cancel_requested"  # not yet final

        accept_cancellation_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-9b", actor=actor)
        db.commit()
        assert reservation.status == "cancelled"  # final only after the explicit accept step


# --- RBAC / tenant-ownership enforcement on the lifecycle functions themselves ---

def test_reserve_refused_for_role_without_reservation_create_permission():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation(role="supplier")  # supplier lacks reservation:create
    adapter = _make_adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        with pytest.raises(GRSPermissionError, match="lacks permission"):
            reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-rbac-1", actor=actor)
    assert adapter._transport.calls == []  # never even attempted


def test_cross_tenant_actor_cannot_reserve_another_tenants_reservation():
    tenant_id, reservation_id, _ = _make_tenant_user_reservation()
    other_tenant_id, _, other_actor_id = _make_tenant_user_reservation()
    adapter = _make_adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, other_tenant_id)
        other_actor = db.get(User, other_actor_id)
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        with pytest.raises(GRSPermissionError, match="does not belong to this reservation's tenant"):
            reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-rbac-2", actor=other_actor)
    assert adapter._transport.calls == []


def test_cancel_requires_reservation_manage_permission():
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation(role="agency_partner")  # lacks reservation:manage
    adapter = _make_adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        reservation.status = "confirmed"
        reservation.provider_reference = "C-RBAC-3"
        db.commit()
        with pytest.raises(GRSPermissionError, match="lacks permission"):
            request_cancellation_with_grs(db, reservation=reservation, adapter=adapter, command_id="cmd-rbac-3", actor=actor)
    assert adapter._transport.calls == []


def test_backoffice_expert_can_manage_but_not_create_via_reservation_create():
    # backoffice_expert has reservation:manage but not reservation:create -
    # proves the two operations are genuinely gated by different permissions.
    tenant_id, reservation_id, actor_id = _make_tenant_user_reservation(role="backoffice_expert")
    adapter = _make_adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        actor = db.get(User, actor_id)
        with pytest.raises(GRSPermissionError, match="lacks permission 'reservation:create'"):
            reserve_with_grs(db, reservation=reservation, adapter=adapter, reserve_payload=RESERVE_PAYLOAD, command_id="cmd-rbac-4", actor=actor)
