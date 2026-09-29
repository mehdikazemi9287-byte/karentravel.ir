import json
import uuid
from copy import deepcopy
from sqlalchemy import select
from app.main import SessionLocal
from app import operations as models
from test_checkout_reviews_zarinpal import auth, login, reservation_fixture, hotel_terms


def test_hotel_allocation_snapshot_and_fail_closed_contract(client):
    employee, _, _, offer = reservation_fixture(client, uuid.uuid4().hex)
    attrs, stay = hotel_terms(2)
    stay['rooms'] *= 2
    with SessionLocal() as db:
        row = db.get(models.Offer, offer['id']); row.attributes_json = json.dumps(attrs); db.commit()
    headers = auth(employee); url = f"/offers/{offer['id']}/price-check"
    payload = {'units': 2, 'hotel_stay': stay, 'command_id': uuid.uuid4().hex, 'expected_final_price': 1}
    assert client.post(url, headers=headers, json=payload).status_code == 409
    payload['expected_final_price'] = 4_000_000
    checked = client.post(url, headers=headers, json=payload)
    assert checked.status_code == 201, checked.text
    assert checked.json()['amount'] == 4_000_000
    assert client.post(url, headers=headers, json=payload).json()['id'] == checked.json()['id']
    changed = deepcopy(payload); changed['hotel_stay']['rooms'][0]['adults'] = 1
    assert client.post(url, headers=headers, json=changed).status_code == 409
    changed['command_id'] = uuid.uuid4().hex
    assert client.post(url, headers=headers, json=changed).status_code == 409
    malformed = deepcopy(payload); malformed['hotel_stay']['rooms'][0]['children_ages'] = [True]
    assert client.post(url, headers=headers, json=malformed).status_code == 422
    omitted = {'units': 2, 'command_id': uuid.uuid4().hex}
    assert client.post(url, headers=headers, json=omitted).status_code == 422
    command = {'price_check_id': checked.json()['id'], 'command_id': uuid.uuid4().hex}
    other = login(client, 'employee@faraz.test')
    assert client.post('/orchestration/bookings', headers=auth(other), json=command).status_code == 409
    booked = client.post('/orchestration/bookings', headers=headers, json=command)
    assert booked.status_code == 201, booked.text
    assert client.post('/orchestration/bookings', headers=headers, json=command).json()['id'] == booked.json()['id']
    with SessionLocal() as db:
        row = db.get(models.Reservation, booked.json()['id'])
        assert json.loads(row.price_snapshot_json)['hotel_stay'] == stay
        item = db.scalar(select(models.BookingItem).where(models.BookingItem.reservation_id == row.id))
        assert json.loads(item.snapshot_json)['hotel_stay'] == stay
        assert db.get(models.Offer, offer['id']).available_units == 0
    checkout = client.post(f"/reservations/{booked.json()['id']}/checkout-sessions", headers=headers, json={'command_id': uuid.uuid4().hex}).json()
    travellers = [client.post('/me/travellers', headers=headers, json={'full_name': f'Mock Hotel Guest {i}'}).json()['id'] for i in range(4)]
    step = f"/checkout-sessions/{checkout['id']}/steps/traveller"
    assert client.put(step, headers=headers, json={'command_id': uuid.uuid4().hex, 'traveller_ids': travellers[:1]}).status_code == 422
    assert client.put(step, headers=headers, json={'command_id': uuid.uuid4().hex, 'traveller_ids': travellers}).status_code == 200


def test_hotel_changed_or_missing_terms_cannot_hold(client):
    user, _, _, offer = reservation_fixture(client, uuid.uuid4().hex)
    attrs, stay = hotel_terms(); headers = auth(user)
    url = f"/offers/{offer['id']}/price-check"
    checked = client.post(url, headers=headers, json={'units': 1, 'hotel_stay': stay, 'command_id': uuid.uuid4().hex}).json()
    with SessionLocal() as db:
        row = db.get(models.Offer, offer['id']); row.attributes_json = '{}'; db.commit()
    assert client.post('/orchestration/bookings', headers=headers, json={'price_check_id': checked['id'], 'command_id': uuid.uuid4().hex}).status_code == 409
    assert client.post(url, headers=headers, json={'units': 1, 'hotel_stay': stay, 'command_id': uuid.uuid4().hex}).status_code == 409
    with SessionLocal() as db:
        assert db.get(models.Offer, offer['id']).available_units == 2
        assert db.get(models.PriceCheck, checked['id']).consumed_at is None


def test_hotel_exact_child_rate_dates_and_room_quantity(client):
    user, _, _, offer = reservation_fixture(client, uuid.uuid4().hex)
    attrs, stay = hotel_terms(1)
    attrs['hotel_rate']['occupancy']['children_ages'] = [7, 2]
    stay['rooms'][0]['children_ages'] = [2, 7]
    with SessionLocal() as db:
        row = db.get(models.Offer, offer['id']); row.attributes_json = json.dumps(attrs); db.commit()
    headers = auth(user); url = f"/offers/{offer['id']}/price-check"
    def check(selection, units=1):
        return client.post(url, headers=headers, json={'units': units, 'hotel_stay': selection, 'command_id': uuid.uuid4().hex})
    assert check(stay).status_code == 201
    wrong = deepcopy(stay); wrong['rooms'][0]['children_ages'] = [3, 7]
    assert check(wrong).status_code == 409
    wrong = deepcopy(stay); wrong['check_out'] = wrong['check_in']
    assert check(wrong).status_code == 422
    wrong = deepcopy(stay); wrong['check_out'] = '2099-12-31'
    assert check(wrong).status_code == 409
    assert check(stay, 2).status_code == 409
    wrong = deepcopy(stay); wrong['rooms'][0]['children_ages'] = [18]
    assert check(wrong).status_code == 422


def test_postgres_hotel_duplicate_quote_and_last_rooms(client):
    from concurrent.futures import ThreadPoolExecutor
    from app.main import engine
    import pytest
    if engine.dialect.name != 'postgresql':
        pytest.skip('Row-lock concurrency requires isolated PostgreSQL')
    user, _, _, offer = reservation_fixture(client, uuid.uuid4().hex)
    _, stay = hotel_terms(); stay['rooms'] *= 2
    headers = auth(user)
    payload = {'units': 2, 'hotel_stay': stay, 'command_id': uuid.uuid4().hex}
    def quote(_):
        return client.post(f"/offers/{offer['id']}/price-check", headers=headers, json=payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        quotes = list(pool.map(quote, range(2)))
    assert [r.status_code for r in quotes] == [201, 201]
    assert quotes[0].json()['id'] == quotes[1].json()['id']
    independent = client.post(f"/offers/{offer['id']}/price-check", headers=headers, json={**payload, 'command_id': uuid.uuid4().hex})
    assert independent.status_code == 201
    quote_ids = [quotes[0].json()['id'], independent.json()['id']]
    def reserve(index):
        return client.post('/orchestration/bookings', headers=headers, json={'price_check_id': quote_ids[index], 'command_id': uuid.uuid4().hex})
    with ThreadPoolExecutor(max_workers=2) as pool:
        reservations = list(pool.map(reserve, range(2)))
    assert sorted(r.status_code for r in reservations) == [201, 409]
    with SessionLocal() as db:
        rows = db.scalars(select(models.Reservation).where(models.Reservation.price_check_id.in_(quote_ids))).all()
        assert len(rows) == 1
        assert db.get(models.Offer, offer['id']).available_units == 0
