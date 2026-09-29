"""Notification worker must not silently require booking/financial privileges."""
from app import outbox_worker as worker


def test_default_worker_does_not_open_booking_database(monkeypatch):
    monkeypatch.delenv('RESERVATION_REAPER_ENABLED', raising=False)
    def forbidden_session():
        raise AssertionError('Outbox role must never enter reservation reaper by default')
    monkeypatch.setattr(worker, 'SessionLocal', forbidden_session)
    assert worker.sweep_reservations_once() == 0
    assert worker.worker_health()['reservation_reaper'] == 'disabled'


def test_reaper_requires_exact_explicit_opt_in(monkeypatch):
    for value in ('0', '', 'true', 'yes'):
        monkeypatch.setenv('RESERVATION_REAPER_ENABLED', value)
        assert not worker.reservation_reaper_enabled()
    monkeypatch.setenv('RESERVATION_REAPER_ENABLED', '1')
    assert worker.reservation_reaper_enabled()
    assert worker.worker_health()['reservation_reaper'] == 'enabled'
