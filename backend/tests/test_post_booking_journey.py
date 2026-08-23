import uuid
from datetime import datetime, timedelta, timezone


def login(client, email):
    response = client.post('/auth/dev-login', json={'email': email})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def supplier(client, headers, kind):
    key = f'supplier-{kind}-{uuid.uuid4().hex}'
    response = client.post('/supplier/onboarding', headers={**headers, 'Idempotency-Key': key}, json={'supplier_type': kind, 'display_name': f'تأمین‌کننده {kind}'})
    assert response.status_code == 201
    return response.json()['id']


def test_real_villa_booking_creates_a_trip_and_a_real_timeline_that_cancellation_extends(client):
    supplier_user = login(client, 'supplier@aftab.test')
    customer = login(client, 'employee@aftab.test')
    foreign = login(client, 'employee@faraz.test')
    supplier_id = supplier(client, supplier_user, 'vacation_rental')
    slug = f'villa-{uuid.uuid4().hex}'
    prop = client.post('/supplier/vacation-properties', headers=supplier_user, json={'supplier_id': supplier_id, 'title': 'ویلای سفر واقعی', 'slug': slug, 'city': 'رامسر', 'property_type': 'villa', 'capacity': 4, 'bedrooms': 2, 'details': {}})
    assert prop.status_code == 201
    unit = client.post(f"/supplier/vacation-properties/{prop.json()['id']}/units", headers=supplier_user, json={'title': 'واحد استاندارد', 'capacity': 4, 'available_units': 1, 'nightly_price': 3000000, 'pricing': {'min_stay': 1}})
    assert unit.status_code == 201
    unit_id = unit.json()['id']

    check_in = datetime(2031, 5, 1, 12, 0, tzinfo=timezone.utc)
    booking = client.post(f"/vacation-units/{unit_id}/reservations", headers=customer, json={'check_in': check_in.isoformat(), 'check_out': (check_in + timedelta(days=2)).isoformat(), 'guests': 2, 'command_id': f'villa-real-trip-{uuid.uuid4().hex}'})
    assert booking.status_code == 201
    reservation_id = booking.json()['reservation_id']

    # 1. My Trips: a real Trip row must now exist for this booking, scoped to its own tenant/user.
    trips = client.get('/me/trips', headers=customer)
    assert trips.status_code == 200
    trip = next((row for row in trips.json() if row['destination'] == 'رامسر'), None)
    assert trip is not None, 'real villa booking did not produce a real Trip row'
    assert trip['status'] == 'planned'

    # Cross-tenant isolation: the other tenant must never see this trip.
    foreign_trips = client.get('/me/trips', headers=foreign)
    assert foreign_trips.status_code == 200
    assert all(row['destination'] != 'رامسر' or row.get('id') != trip['id'] for row in foreign_trips.json())

    # 2/3/4. Trip Detail / Timeline / "what changed": a real system-sourced booking_created event.
    timeline = client.get(f"/trips/{trip['id']}/timeline", headers=customer)
    assert timeline.status_code == 200
    events = timeline.json()['events']
    created_events = [e for e in events if e['type'] == 'booking.created']
    assert len(created_events) == 1
    assert created_events[0]['source'] == 'system'
    assert created_events[0]['deep_link'] == f"/manage-booking/{reservation_id}"

    # No cross-tenant read of the trip/timeline by id.
    assert client.get(f"/trips/{trip['id']}/timeline", headers=foreign).status_code == 404

    # 6. Cancellation / Refund: a cancel request must transition the reservation AND extend the
    # same real timeline with a second, distinguishable event (still SYSTEM-sourced, not fabricated).
    cancel = client.post(f"/reservations/{reservation_id}/service-requests", headers={**customer, 'Idempotency-Key': f'cancel-{uuid.uuid4().hex}'}, json={'request_type': 'cancel'})
    assert cancel.status_code == 202
    assert cancel.json()['booking_status'] == 'cancel_requested'

    timeline_after = client.get(f"/trips/{trip['id']}/timeline", headers=customer)
    events_after = timeline_after.json()['events']
    assert len(events_after) == len(events) + 1
    cancel_events = [e for e in events_after if e['type'] == 'reservation.cancel_requested']
    assert len(cancel_events) == 1
    assert cancel_events[0]['source'] == 'system' and cancel_events[0]['requires_action'] is True
