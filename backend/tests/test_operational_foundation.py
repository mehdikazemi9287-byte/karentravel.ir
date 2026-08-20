from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.main import SessionLocal, User
from app.operations import (
    FinancialLedgerEntry,
    OutboxEvent,
    Reservation,
    Trip,
    TripEventRecord,
    Wallet,
    ingest_trip_event,
    post_ledger,
    transition_reservation,
)
from app.providers import ADAPTERS, ProviderContext
import app.main as main_module


def test_tenant_scoped_reservation_queries_are_isolated():
    with SessionLocal() as db:
        aftab = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        faraz = db.scalar(select(User).where(User.email == "employee@faraz.test"))
        reservation = Reservation(tenant_id=aftab.tenant_id, user_id=aftab.id, service_type="tour_hotel", status="draft")
        db.add(reservation)
        db.commit()
        leaked = db.scalar(select(Reservation).where(Reservation.id == reservation.id, Reservation.tenant_id == faraz.tenant_id))
        assert leaked is None


def test_booking_transition_is_validated_and_idempotent():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="flight", status="draft")
        db.add(reservation)
        db.flush()
        transition_reservation(db, reservation, "pending", user.id, "command-transition-1")
        transition_reservation(db, reservation, "pending", user.id, "command-transition-1")
        db.commit()
        assert reservation.status == "pending"
        assert db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == reservation.id)) == 1
        with pytest.raises(ValueError):
            transition_reservation(db, reservation, "completed", user.id, "command-transition-invalid")


def test_ledger_commands_are_idempotent_and_reversals_are_append_only():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        wallet = Wallet(tenant_id=user.tenant_id, owner_type="user", owner_reference=str(user.id))
        db.add(wallet)
        db.flush()
        authorization = post_ledger(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="ledger-auth-1", entry_type="reserve", amount=900000)
        duplicate = post_ledger(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="ledger-auth-1", entry_type="reserve", amount=900000)
        db.flush()
        assert duplicate.id == authorization.id
        reversal = post_ledger(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="ledger-reversal-1", entry_type="release", amount=900000, reversal_of_id=authorization.id)
        db.commit()
        entries = db.scalars(select(FinancialLedgerEntry).where(FinancialLedgerEntry.wallet_id == wallet.id)).all()
        assert len(entries) == 2
        assert reversal.reversal_of_id == authorization.id


def test_trip_event_ingestion_deduplicates_and_creates_outbox():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        trip = Trip(tenant_id=user.tenant_id, user_id=user.id, title="سفر شیراز", origin="تهران", destination="شیراز")
        db.add(trip)
        db.flush()
        first = ingest_trip_event(db, TripEventRecord(tenant_id=user.tenant_id, trip_id=trip.id, event_key="provider-flight-42", event_type="flight_delayed", severity="warning", source="provider", title="زمان پرواز تغییر کرد", message="اطلاعات نمونه", effective_at=datetime.now(timezone.utc), deep_link=f"/trips/{trip.id}?event=provider-flight-42"))
        db.flush()
        second = ingest_trip_event(db, TripEventRecord(tenant_id=user.tenant_id, trip_id=trip.id, event_key="provider-flight-42", event_type="flight_delayed", severity="warning", source="provider", title="تکراری", message="نباید ثبت شود"))
        db.commit()
        assert second.id == first.id
        assert db.scalar(select(func.count()).select_from(TripEventRecord).where(TripEventRecord.event_key == "provider-flight-42")) == 1
        assert db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_id == trip.id)) == 1


def test_external_adapters_fail_closed_without_credentials():
    result = ADAPTERS["flight"].execute("search", {"origin": "THR", "destination": "SYZ"}, ProviderContext(tenant_id=1, correlation_id="correlation-1", idempotency_key="provider-command-1"))
    assert result["ok"] is False
    assert result["status"] == "not_sent"
    assert result["reason"] == "external_provider_not_configured"


def test_production_configuration_rejects_development_secret(monkeypatch):
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    monkeypatch.setattr(main_module, "JWT_SECRET", "development-only-change-before-production")
    with pytest.raises(RuntimeError):
        main_module.validate_production_config()
