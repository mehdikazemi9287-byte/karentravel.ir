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


def test_vacation_inventory_is_idempotent_tenant_owned_and_overlap_safe(client):
    supplier_user = login(client, 'supplier@aftab.test'); customer = login(client, 'employee@aftab.test'); foreign = login(client, 'employee@faraz.test')
    supplier_id = supplier(client, supplier_user, 'vacation_rental')
    slug = f'villa-{uuid.uuid4().hex}'
    prop = client.post('/supplier/vacation-properties', headers=supplier_user, json={'supplier_id': supplier_id, 'title': 'ویلای ساحلی تست', 'slug': slug, 'city': 'رامسر', 'property_type': 'villa', 'capacity': 6, 'bedrooms': 2, 'details': {'amenities': ['pool', 'parking'], 'policy_verified': True}})
    assert prop.status_code == 201
    unit = client.post(f"/supplier/vacation-properties/{prop.json()['id']}/units", headers=supplier_user, json={'title': 'واحد دربست', 'capacity': 6, 'available_units': 1, 'nightly_price': 9000000})
    assert unit.status_code == 201
    command = f'villa-book-{uuid.uuid4().hex}'; payload = {'check_in': '2030-05-10T12:00:00Z', 'check_out': '2030-05-12T12:00:00Z', 'guests': 4, 'command_id': command}
    booked = client.post(f"/vacation-units/{unit.json()['id']}/reservations", headers=customer, json=payload)
    replay = client.post(f"/vacation-units/{unit.json()['id']}/reservations", headers=customer, json=payload)
    assert booked.status_code == 201 and replay.json()['id'] == booked.json()['id'] and booked.json()['total_amount'] == 18000000 and booked.json()['checkout_url'].startswith('/checkout/')
    collision = client.post(f"/vacation-units/{unit.json()['id']}/reservations", headers=customer, json={**payload, 'command_id': f'collision-{uuid.uuid4().hex}'})
    assert collision.status_code == 409
    assert client.get(f"/vacation-rentals/{prop.json()['id']}", headers=foreign).status_code == 404


def test_tour_departure_prevents_oversell_and_never_issues_unpaid_voucher(client):
    supplier_user = login(client, 'supplier@aftab.test'); customer = login(client, 'employee@aftab.test'); backoffice = login(client, 'backoffice@aftab.test'); foreign = login(client, 'employee@faraz.test')
    supplier_id = supplier(client, supplier_user, 'tour')
    tour = client.post('/supplier/tours', headers=supplier_user, json={'supplier_id': supplier_id, 'title': 'تور فرهنگی شیراز', 'slug': f'shiraz-{uuid.uuid4().hex}', 'origin': 'تهران', 'destination': 'شیراز', 'tour_type': 'cultural', 'details': {'visa_status': 'not_required', 'itinerary': [{'day': 1, 'title': 'حافظیه'}]}})
    departure = client.post(f"/supplier/tours/{tour.json()['id']}/departures", headers=supplier_user, json={'starts_at': '2030-06-10T06:00:00Z', 'ends_at': '2030-06-13T18:00:00Z', 'booking_deadline': '2030-06-08T18:00:00Z', 'capacity': 2, 'base_price': 15000000, 'pricing': {'single_surcharge': 3000000}})
    assert departure.status_code == 201
    command = f'tour-book-{uuid.uuid4().hex}'; booked = client.post(f"/tour-departures/{departure.json()['id']}/reservations", headers=customer, json={'travellers': 2, 'room_type': 'double', 'command_id': command})
    replay = client.post(f"/tour-departures/{departure.json()['id']}/reservations", headers=customer, json={'travellers': 2, 'room_type': 'double', 'command_id': command})
    assert booked.status_code == 201 and booked.json()['voucher'] is None and replay.json()['id'] == booked.json()['id']
    checkout = client.post(f"/reservations/{booked.json()['reservation_id']}/checkout-sessions", headers=customer, json={'command_id': f'checkout-{uuid.uuid4().hex}'})
    assert checkout.status_code == 201 and checkout.json()['reservation']['service_type'] == 'tour'
    visa_product = client.post('/backoffice/visa-products', headers=backoffice, json={'destination_country': 'ترکیه', 'visa_type': 'tourist', 'title': 'بررسی ویزای ترکیه', 'source_url': 'https://example.gov/visa', 'source_verified_at': datetime.now(timezone.utc).isoformat(), 'details': {'visa_status': 'requires_human_review'}})
    visa = client.post(f"/visa-products/{visa_product.json()['id']}/applications", headers=customer, json={'purpose': 'tourism', 'travel_at': '2030-06-10T06:00:00Z', 'tour_reservation_id': booked.json()['id'], 'command_id': f'visa-tour-{uuid.uuid4().hex}'})
    assert visa.status_code == 201 and visa.json()['tour_reservation_id'] == booked.json()['id']
    visa_detail = client.get(f"/visa-applications/{visa.json()['id']}", headers=customer)
    assert visa_detail.status_code == 200 and visa_detail.json()['tour_reservation_id'] == booked.json()['id'] and any(event['event_type'] == 'tour_linked' for event in visa_detail.json()['timeline'])
    assert client.post(f"/tour-departures/{departure.json()['id']}/reservations", headers=customer, json={'travellers': 1, 'room_type': 'double', 'command_id': f'oversell-{uuid.uuid4().hex}'}).status_code == 409
    assert client.get(f"/tour-products/{tour.json()['id']}", headers=foreign).status_code == 404


def test_visa_workflow_is_human_reviewed_and_cruise_fails_closed(client):
    backoffice = login(client, 'backoffice@aftab.test'); customer = login(client, 'employee@aftab.test'); foreign = login(client, 'employee@faraz.test')
    product = client.post('/backoffice/visa-products', headers=backoffice, json={'destination_country': 'فرانسه', 'visa_type': 'tourist', 'title': 'ویزای توریستی فرانسه', 'source_url': 'https://france-visas.gouv.fr/en/web/france-visas/visa-application-guidelines', 'source_verified_at': datetime.now(timezone.utc).isoformat(), 'details': {'documents': ['passport', 'photo', 'insurance'], 'processing_time': 'not_guaranteed'}})
    assert product.status_code == 201
    app = client.post(f"/visa-products/{product.json()['id']}/applications", headers=customer, json={'purpose': 'tourism', 'travel_at': '2030-09-01T00:00:00Z', 'command_id': f'visa-{uuid.uuid4().hex}'})
    assert app.status_code == 201 and app.json()['guarantee'] is False
    applicant = client.post(f"/visa-applications/{app.json()['id']}/applicants", headers=customer, json={'full_name': 'مسافر نمونه', 'passport_country': 'ایران', 'passport_reference': 'P123456789'})
    assert applicant.status_code == 201 and 'passport_reference' not in applicant.json()
    document = client.post(f"/visa-applications/{app.json()['id']}/documents", headers=customer, json={'document_type': 'passport', 'storage_reference': 'private://visa/passport/test'})
    assert document.status_code == 201 and document.json()['status'] == 'uploaded'
    assert client.put(f"/backoffice/visa-documents/{document.json()['id']}", headers=customer, json={'status': 'accepted'}).status_code == 403
    reviewed = client.put(f"/backoffice/visa-documents/{document.json()['id']}", headers=backoffice, json={'status': 'accepted', 'review_note': 'بررسی انسانی'})
    assert reviewed.status_code == 200 and reviewed.json()['source_type'] == 'human_agent'
    detail = client.get(f"/visa-applications/{app.json()['id']}", headers=customer)
    assert detail.status_code == 200 and detail.json()['documents'][0]['status'] == 'accepted' and detail.json()['timeline'][-1]['source_type'] == 'human_agent'
    assert client.get(f"/visa-applications/{app.json()['id']}", headers=foreign).status_code == 404
    assert client.get('/cruises', headers=customer).json()['live_booking'] is False


def test_vacation_seasonal_weekend_min_stay_pricing_and_cancellation_quote(client):
    supplier_user = login(client, 'supplier@aftab.test'); customer = login(client, 'employee@aftab.test')
    supplier_id = supplier(client, supplier_user, 'vacation_rental')
    policy = {'source': 'internal_policy_v1', 'verified': True, 'verified_at': datetime.now(timezone.utc).isoformat(), 'cancellation': {'refundable': True, 'penalty_amount': 2000000}}
    slug = f'villa-{uuid.uuid4().hex}'
    prop = client.post('/supplier/vacation-properties', headers=supplier_user, json={'supplier_id': supplier_id, 'title': 'ویلای فصلی تست', 'slug': slug, 'city': 'کیش', 'property_type': 'villa', 'capacity': 6, 'bedrooms': 2, 'details': {'cancellation_policy': policy}})
    assert prop.status_code == 201
    weekend_night = datetime(2031, 2, 3, 12, 0, tzinfo=timezone.utc)
    pricing = {'min_stay': 2, 'weekend_days': [(weekend_night + timedelta(days=1)).weekday()], 'weekend_price': 5000000, 'seasonal_rates': [{'start': '07-01', 'end': '07-31', 'nightly_price': 9000000}]}
    unit = client.post(f"/supplier/vacation-properties/{prop.json()['id']}/units", headers=supplier_user, json={'title': 'واحد فصلی', 'capacity': 6, 'available_units': 1, 'nightly_price': 4000000, 'pricing': pricing})
    assert unit.status_code == 201 and unit.json()['id']
    unit_id = unit.json()['id']

    too_short = client.post(f"/vacation-units/{unit_id}/reservations", headers=customer, json={'check_in': weekend_night.isoformat(), 'check_out': (weekend_night + timedelta(days=1)).isoformat(), 'guests': 2, 'command_id': f'villa-short-{uuid.uuid4().hex}'})
    assert too_short.status_code == 422

    weekend_stay = client.post(f"/vacation-units/{unit_id}/reservations", headers=customer, json={'check_in': weekend_night.isoformat(), 'check_out': (weekend_night + timedelta(days=2)).isoformat(), 'guests': 2, 'command_id': f'villa-weekend-{uuid.uuid4().hex}'})
    assert weekend_stay.status_code == 201 and weekend_stay.json()['total_amount'] == 4000000 + 5000000
    breakdown = weekend_stay.json()['price_breakdown']
    assert breakdown[0]['rate_source'] == 'base' and breakdown[1]['rate_source'] == 'weekend'

    seasonal_in = datetime(2030, 7, 10, 12, 0, tzinfo=timezone.utc)
    seasonal_stay = client.post(f"/vacation-units/{unit_id}/reservations", headers=customer, json={'check_in': seasonal_in.isoformat(), 'check_out': (seasonal_in + timedelta(days=2)).isoformat(), 'guests': 2, 'command_id': f'villa-season-{uuid.uuid4().hex}'})
    assert seasonal_stay.status_code == 201 and seasonal_stay.json()['total_amount'] == 9000000 * 2
    assert all(night['rate_source'] == 'seasonal' for night in seasonal_stay.json()['price_breakdown'])

    quote = client.get(f"/reservations/{seasonal_stay.json()['reservation_id']}/cancellation-quote", headers=customer)
    assert quote.status_code == 200
    body = quote.json()
    assert body['policy_verified'] is True and body['total_amount'] == 18000000 and body['penalty_amount'] == 2000000 and body['refundable_amount'] == 16000000
