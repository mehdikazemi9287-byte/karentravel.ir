import json
import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.main import User
from app.operations import NotificationDeliveryAttempt, NotificationRecord, OutboxEvent
from app.outbox_worker import process_batch
from datetime import datetime, timedelta, timezone


def _seed_user():
    with SessionLocal() as db:
        user = db.execute(select(User)).scalars().first()
        assert user is not None, 'conftest seed did not create any user'
        return user.tenant_id, user.id


def _make_event():
    tenant_id, user_id = _seed_user()
    with SessionLocal() as db:
        notification = NotificationRecord(tenant_id=tenant_id, user_id=user_id, topic='important_trip_changes', title='t', message='m', status='pending')
        db.add(notification)
        db.flush()
        push_attempt = NotificationDeliveryAttempt(tenant_id=tenant_id, notification_id=notification.id, channel='push', status='not_sent')
        sms_attempt = NotificationDeliveryAttempt(tenant_id=tenant_id, notification_id=notification.id, channel='sms', status='not_sent')
        db.add_all([push_attempt, sms_attempt])
        db.flush()
        event = OutboxEvent(tenant_id=tenant_id, aggregate_type='trip', aggregate_id=str(uuid.uuid4()), event_type='trip.event.recorded', payload_json=json.dumps({'notification_id': notification.id}), status='pending', attempts=0, idempotency_key=str(uuid.uuid4()))
        db.add(event)
        db.commit()
        return event.id, notification.id


def _force_due(event_id):
    """Simulate time passing: exponential backoff pushes available_at into the
    future after each attempt, so a fast test loop must rewind it, otherwise
    every call after the first is correctly skipped (that's the backoff
    working, not a bug) rather than exercising the retry path being tested."""
    with SessionLocal() as db:
        event = db.get(OutboxEvent, event_id)
        event.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()


def _rows(event_id, notification_id):
    with SessionLocal() as db:
        event = db.get(OutboxEvent, event_id)
        push = db.scalar(select(NotificationDeliveryAttempt).where(NotificationDeliveryAttempt.notification_id == notification_id, NotificationDeliveryAttempt.channel == 'push'))
        sms = db.scalar(select(NotificationDeliveryAttempt).where(NotificationDeliveryAttempt.notification_id == notification_id, NotificationDeliveryAttempt.channel == 'sms'))
        return event.status, event.attempts, push.status, push.attempt, sms.status, sms.attempt, sms.error_code


def test_sms_outbox_event_is_picked_up_and_processed():
    event_id, notification_id = _make_event()
    process_batch()
    _, _, _, _, sms_status, sms_attempt, _ = _rows(event_id, notification_id)
    assert sms_attempt == 1, 'sms row was never touched - process_batch did not pick it up'
    assert sms_status != 'not_sent', 'sms row must move out of its initial not_sent state once processed'


def test_missing_sms_provider_fails_closed_not_delivered():
    event_id, notification_id = _make_event()
    process_batch()
    _, _, _, _, sms_status, _, sms_error = _rows(event_id, notification_id)
    assert sms_status in {'retry', 'dead_letter'}, f'no sms provider is configured in the test env - must never be delivered, got {sms_status}'
    assert sms_status != 'delivered'
    assert sms_error == 'external_provider_not_configured'


def test_duplicate_processing_prevented_once_terminal():
    event_id, notification_id = _make_event()
    for _ in range(5):
        _force_due(event_id)
        process_batch()
    event_status, event_attempts, _, _, sms_status, sms_attempts, _ = _rows(event_id, notification_id)
    assert event_status == 'dead_letter' and event_attempts == 5
    # one more pass must be a no-op even when forced due again: the event is no
    # longer pending/retry (it's dead_letter), so it must not be picked up again.
    _force_due(event_id)
    process_batch()
    _, event_attempts_after, _, _, _, sms_attempts_after, _ = _rows(event_id, notification_id)
    assert event_attempts_after == 5, 'a dead-lettered event was reprocessed - duplicate processing'
    assert sms_attempts_after == sms_attempts == 5


def test_retry_increments_correctly_in_lockstep_with_the_shared_event():
    event_id, notification_id = _make_event()
    seen = []
    for _ in range(3):
        _force_due(event_id)
        process_batch()
        event_status, event_attempts, _, _, sms_status, sms_attempts, _ = _rows(event_id, notification_id)
        seen.append((event_attempts, sms_attempts))
    assert seen == [(1, 1), (2, 2), (3, 3)], f'retry did not advance monotonically once per due call, got {seen}'


def test_dead_letter_after_five_attempts_for_both_channels():
    event_id, notification_id = _make_event()
    for _ in range(5):
        _force_due(event_id)
        process_batch()
    event_status, event_attempts, push_status, push_attempts, sms_status, sms_attempts, _ = _rows(event_id, notification_id)
    assert event_status == 'dead_letter' and event_attempts == 5
    assert push_status == 'dead_letter' and push_attempts == 5
    assert sms_status == 'dead_letter' and sms_attempts == 5


def test_push_behavior_is_unchanged_by_the_sms_addition():
    event_id, notification_id = _make_event()
    process_batch()
    event_status, event_attempts, push_status, push_attempts, _, _, _ = _rows(event_id, notification_id)
    # push_attempt.status has always mirrored event.status exactly (pre-existing
    # contract) - this must still hold after adding the independent sms path.
    assert push_status == event_status
    assert push_attempts == event_attempts == 1
