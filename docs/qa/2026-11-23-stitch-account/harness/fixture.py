# Local QA fixture: creates test offers/reservations in the local SQLite dev backend (same calls as e2e/critical-flows.spec.ts).
import httpx, time, json, sys
API = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8130'
c = httpx.Client(base_url=API, timeout=30)
def login(e): r = c.post('/auth/dev-login', json={'email': e}); r.raise_for_status(); return r.json()
sfx = str(int(time.time()))
sup = login('supplier@aftab.test'); H = {'Authorization': 'Bearer ' + sup['access_token']}
r = c.post('/supplier/onboarding', headers={**H, 'Idempotency-Key': 'qa-sup-' + sfx}, json={'supplier_type': 'hotel', 'display_name': 'تأمین‌کننده آزمایشی QA ' + sfx}); r.raise_for_status(); sid = r.json()['id']
policy = {'verified': True, 'source': 'qa-contract', 'verified_at': '2026-11-23T00:00:00Z', 'cancellation': {'refundable': True, 'penalty_amount': 100000}}
rate = {'check_in': '2030-03-01', 'check_out': '2030-03-03', 'room_type': 'دوتخته', 'rate_plan': 'با صبحانه', 'price_basis': 'room_stay', 'occupancy': {'adults': 2, 'children_ages': []}}
stay = {'check_in': rate['check_in'], 'check_out': rate['check_out'], 'rooms': [rate['occupancy']]}
emp = login('employee@aftab.test'); E = {'Authorization': 'Bearer ' + emp['access_token']}
out = {}
for st in ['hotel', 'flight']:
    attrs = {'origin': 'تهران', 'destination': 'شیراز', 'airline': 'هواپیمایی تست قراردادی', 'departure_time': '08:30', 'arrival_time': '10:00', 'duration': '۱ ساعت و ۳۰ دقیقه', 'duration_minutes': 90, 'stops': 0, 'baggage': '۲۰ کیلوگرم'} if st == 'flight' else {'stars': 4, 'city': 'شیراز', 'room_type': 'دوتخته', 'breakfast': True, 'amenities': ['wifi'], 'hotel_rate': rate}
    r = c.post('/supplier/offers', headers=H, json={'supplier_id': sid, 'service_type': st, 'title': ('پرواز آزمایشی تهران شیراز' if st == 'flight' else 'هتل آزمایشی QA'), 'amount': 2_000_000 if st == 'hotel' else 3_500_000, 'available_units': 5, 'valid_minutes': 60, 'policy': policy, 'attributes': attrs, 'fulfillment_mode': 'manual_supplier', 'provider_key': 'manual_supplier'}); r.raise_for_status(); oid = r.json()['id']
    r = c.post(f'/offers/{oid}/price-check', headers=E, json={'units': 1, 'command_id': f'qa-pc-{st}-{sfx}', **({'hotel_stay': stay} if st == 'hotel' else {})}); r.raise_for_status()
    r = c.post('/orchestration/bookings', headers=E, json={'price_check_id': r.json()['id'], 'command_id': f'qa-bk-{st}-{sfx}'}); r.raise_for_status(); out[st] = r.json()['id']
r = c.post('/me/wallets', headers={**E, 'Idempotency-Key': 'qa-w-' + sfx}, json={'currency': 'IRR'}); print('wallet', r.status_code)
print(json.dumps(out))
