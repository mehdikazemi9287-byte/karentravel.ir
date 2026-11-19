"""Stitch round 6: tour package-builder add-ons, public 360/route projection, host experience portal."""
import uuid, json
from datetime import datetime, timedelta, timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture, login, auth
import test_leisure_commerce as lc

ADDONS = [{"code": "vegan-menu", "title": "منوی گیاهی", "price": 450000, "unit": "person", "category": "food"},
          {"code": "private-van", "title": "ون اختصاصی", "price": 1700000, "unit": "booking", "category": "transport"},
          {"code": "BAD CODE", "title": "x", "price": 1}, {"code": "neg", "title": "منفی", "price": -5}]


def make_tour(client):
    employee, _, traveller, offer = reservation_fixture(client, uuid.uuid4().hex); supplier = login(client, 'supplier@aftab.test')
    with SessionLocal() as db:
        o = db.get(m.Offer, offer['id']); sid = o.supplier_id; policy = json.loads(o.policy_json)
    details = {'cancellation_policy': policy, 'itinerary': [{'title': 'پرواز تهران به یزد', 'day': 1, 'mode': 'flight', 'lat': 31.9, 'lng': 54.3, 'place': 'یزد'}, {'title': 'کویر بافق', 'day': 2, 'lat': 999, 'lng': 55.1}],
               'media_360': [{'url': 'https://cdn.example.test/yazd-360.jpg', 'title': 'بادگیر', 'hotspots': [{'label': 'بادگیر هتل داد', 'yaw': 40}]}, {'url': 'javascript:alert(1)'}],
               'narration': {'title': 'راز شب‌های بافق', 'guide': 'استاد کاشانی', 'audio_url': 'http://insecure.test/a.mp3'}}
    tour = client.post('/supplier/tours', headers=auth(supplier), json={'supplier_id': sid, 'title': 'Mock QA 360 Tour', 'slug': 'qa-' + uuid.uuid4().hex, 'origin': 'تهران', 'destination': 'یزد', 'tour_type': 'cultural', 'details': details}).json()
    now = datetime.now(timezone.utc)
    dep = client.post('/supplier/tours/' + tour['id'] + '/departures', headers=auth(supplier), json={'starts_at': (now + timedelta(days=10)).isoformat(), 'ends_at': (now + timedelta(days=14)).isoformat(), 'booking_deadline': (now + timedelta(days=9)).isoformat(), 'capacity': 5, 'base_price': 1000000, 'pricing': {'addons': ADDONS}}).json()
    return employee, tour, dep


def test_addons_priced_by_organiser_only(client):
    employee, tour, dep = make_tour(client); url = '/tour-departures/' + dep['id']
    detail = client.get('/tour-products/' + tour['id'], headers=auth(employee)).json()
    codes = [a['code'] for a in detail['departures'][0]['addons']]; assert codes == ['vegan-menu', 'private-van']
    q = client.get(url + '/quote?travellers=2&addons=vegan-menu,private-van', headers=auth(employee)).json()
    assert q['base_amount'] == 2000000 and q['total_amount'] == 2000000 + 2 * 450000 + 1700000
    assert client.get(url + '/quote?travellers=2&addons=spa', headers=auth(employee)).status_code == 409
    r = client.post(url + '/reservations', headers=auth(employee), json={'travellers': 2, 'room_type': 'double', 'addons': ['vegan-menu'], 'expected_total_amount': 2900000, 'command_id': uuid.uuid4().hex})
    assert r.status_code == 201, r.text and r.json()['total_amount'] == 2900000
    with SessionLocal() as db:
        item = db.query(m.BookingItem).filter(m.BookingItem.reservation_id == r.json()['reservation_id']).one()
        assert json.loads(item.snapshot_json)['package_addons'][0]['amount'] == 900000
    assert client.post(url + '/reservations', headers=auth(employee), json={'travellers': 1, 'addons': ['vegan-menu'], 'expected_total_amount': 1000000, 'command_id': uuid.uuid4().hex}).status_code == 409


def test_public_projection_sanitises_media_and_route(client):
    from app.main import _public_tour_projection
    employee, tour, _ = make_tour(client)
    pub = _public_tour_projection(client.get('/tour-products/' + tour['id'], headers=auth(employee)).json())
    assert pub['details']['media_360'] == [{'url': 'https://cdn.example.test/yazd-360.jpg', 'title': 'بادگیر', 'hotspots': [{'label': 'بادگیر هتل داد', 'yaw': 40.0}]}]
    assert pub['details']['narration']['audio_url'] is None
    it = pub['details']['itinerary']; assert it[0]['lat'] == 31.9 and it[0]['mode'] == 'flight' and 'lat' not in it[1]
    assert all('price' not in a for a in pub['departures'][0]['addons'])


def test_host_portal_counts_only_own_data(client):
    sup = login(client, 'supplier@aftab.test'); headers = auth(sup)
    sid = lc.supplier(client, headers, 'pool_sport'); place = lc.make_place(client, headers, sid); product = lc.make_product(client, headers, place['id'])
    ticket = lc.make_ticket_type(client, headers, product['id']); session = lc.make_session(client, headers, product['id'], capacity=4, starts_in_hours=5)
    with SessionLocal() as db:
        db.get(m.ExperienceProduct, product['id']).status = 'published'; db.commit()
    customer = auth(login(client, 'employee@aftab.test'))
    checked = lc.price_check(client, customer, session['id'], [{'ticket_type_id': ticket['id'], 'quantity': 2}]); assert checked.status_code == 201, checked.text
    assert lc.book(client, customer, checked.json()['id']).status_code == 201
    portal = client.get('/supplier/experience-portal', headers=headers).json()
    mine = [s for s in portal['sessions'] if s['id'] == session['id']][0]
    assert mine['seats_sold'] == 2 and any(a['session_id'] == session['id'] and a['guests'] == 2 for a in portal['arrivals'])
    assert portal['payout']['status'] in ('configured', 'not_configured')
    assert client.get('/supplier/experience-portal', headers=customer).status_code in (401, 403)
