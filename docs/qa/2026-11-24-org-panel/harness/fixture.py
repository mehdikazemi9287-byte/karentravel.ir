# Local QA fixture only (dev SQLite backend, ENVIRONMENT=development). Builds test data for the organization-panel screenshots
# through the same APIs the app uses; the only direct DB write is one test `customer` account (no API creates one in a seed tenant).
# The only direct DB writes are two test accounts. Usage: python -I fixture.py <api-origin> <sqlite-file>
import httpx, json, sqlite3, sys, time, uuid
API, DB = sys.argv[1], sys.argv[2]
c = httpx.Client(base_url=API, timeout=30)
def login(e): r = c.post('/auth/dev-login', json={'email': e}); r.raise_for_status(); return {'Authorization': 'Bearer ' + r.json()['access_token']}
def ok(r): assert r.status_code < 300, (r.request.url, r.status_code, r.text[:300]); return r.json()
cid = lambda: str(uuid.uuid4())
sfx = str(int(time.time()))[-6:]
DUAL = 'dual-qa@aftab.test'
db = sqlite3.connect(DB); t = db.execute("select id from tenants where slug='aftab-bank'").fetchone()[0]
db.execute("insert or ignore into users (tenant_id,email,name,role) values (?,?,?,?)", (t, DUAL, 'مدیر آزمون QA', 'customer'))
# second finance user: the credit line is maker-checker (a different credit:fund user approves)
db.execute("insert or ignore into users (tenant_id,email,name,role) values (?,?,?,?)", (t, 'finance-checker-qa@aftab.test', 'کارشناس مالی دوم QA', 'finance_operator')); db.commit()
admin, oadm, emp, dual, fin, sup = (login(e) for e in ['tenant-admin@aftab.test', 'org-admin@aftab.test', 'employee@aftab.test', DUAL, 'finance@aftab.test', 'supplier@aftab.test'])
org = ok(c.post('/enterprise/organizations', headers=admin, json={'name': 'سازمان آزمایشی QA ' + sfx}))['id']
member = ok(c.post('/enterprise/organizations', headers=admin, json={'name': 'سازمان عضویت QA ' + sfx}))['id']
for e in ['org-admin@aftab.test', 'employee@aftab.test', DUAL]: rows = ok(c.post(f'/enterprise/organizations/{org}/members', headers=admin, json={'email': e}))
ok(c.post(f'/enterprise/organizations/{member}/members', headers=admin, json={'email': DUAL}))
ids = {r['email']: r['id'] for r in rows}
ok(c.put(f'/enterprise/organizations/{org}/grants', headers=oadm, json={'command_id': cid(), 'user_id': ids[DUAL], 'permissions': ['requests.read_all', 'roles.manage', 'policy.manage', 'requests.approve']}))
ok(c.put(f'/enterprise/organizations/{org}/policy', headers=oadm, json={'command_id': cid(), 'rules': {'allowed_services': ['hotel', 'flight'], 'maximum_budget': 60_000_000, 'approval_required': True, 'approver_ids': [ids[DUAL]]}}))
def req(title, use, origin, dest, start, end, n, svc, budget):
    return ok(c.post(f'/enterprise/organizations/{org}/requests', headers=emp, json={'command_id': cid(), 'title': title, 'use_case': use, 'purpose': 'آزمون QA — داده آزمایشی', 'origin': origin, 'destination': dest, 'starts_at': start, 'ends_at': end, 'headcount': n, 'services': [svc], 'budget_amount': budget}))['id']
r1 = req('مأموریت آزمایشی شیراز', 'business_travel', 'تهران', 'شیراز', '2030-03-01T08:00:00Z', '2030-03-03T18:00:00Z', 1, 'hotel', 40_000_000)
r2 = req('همایش آزمایشی مشهد', 'organizational_event', 'تهران', 'مشهد', '2030-04-10T08:00:00Z', '2030-04-12T18:00:00Z', 3, 'flight', 90_000_000)
r3 = req('سفر آزمایشی تیمی شیراز', 'team_retreat', 'تهران', 'شیراز', '2030-03-01T08:00:00Z', '2030-03-03T18:00:00Z', 1, 'hotel', 20_000_000)
ok(c.post(f'/enterprise/requests/{r3}/decision', headers=dual, json={'command_id': cid(), 'decision': 'approve', 'reason': 'تأیید آزمایشی QA'}))
# a hotel reservation of the requester (same calls as e2e/critical-flows.spec.ts), linked to the approved request, then invoiced at checkout
sid = ok(c.post('/supplier/onboarding', headers={**sup, 'Idempotency-Key': 'qa-org-' + sfx}, json={'supplier_type': 'hotel', 'display_name': 'تأمین‌کننده آزمایشی QA ' + sfx}))['id']
rate = {'check_in': '2030-03-01', 'check_out': '2030-03-03', 'room_type': 'دوتخته', 'rate_plan': 'با صبحانه', 'price_basis': 'room_stay', 'occupancy': {'adults': 1, 'children_ages': []}}
policy = {'verified': True, 'source': 'qa-contract', 'verified_at': '2026-11-24T00:00:00Z', 'cancellation': {'refundable': True, 'penalty_amount': 100000}}
oid = ok(c.post('/supplier/offers', headers=sup, json={'supplier_id': sid, 'service_type': 'hotel', 'title': 'هتل آزمایشی QA', 'amount': 18_000_000, 'available_units': 5, 'valid_minutes': 60, 'policy': policy, 'attributes': {'stars': 4, 'city': 'شیراز', 'room_type': 'دوتخته', 'breakfast': True, 'amenities': ['wifi'], 'hotel_rate': rate}, 'fulfillment_mode': 'manual_supplier', 'provider_key': 'manual_supplier'}))['id']
pc = ok(c.post(f'/offers/{oid}/price-check', headers=emp, json={'units': 1, 'command_id': cid(), 'hotel_stay': {'check_in': rate['check_in'], 'check_out': rate['check_out'], 'rooms': [rate['occupancy']]}}))['id']
res = ok(c.post('/orchestration/bookings', headers=emp, json={'price_check_id': pc, 'command_id': cid()}))['id']
ok(c.post(f'/enterprise/requests/{r3}/bookings', headers=emp, json={'reservation_id': res, 'command_id': cid()}))
tr = ok(c.post('/me/travellers', headers={**emp, 'Idempotency-Key': cid()}, json={'full_name': 'مسافر آزمایشی QA', 'nationality': 'IR'}))['id']
cs = ok(c.post(f'/reservations/{res}/checkout-sessions', headers=emp, json={'command_id': cid()}))
for st, extra in [('traveller', {'traveller_ids': [tr]}), ('recheck', {}), ('policy', {'acknowledged': True}), ('funding', {'wallet_amount': 0, 'credit_amount': 0}), ('invoice', {}), ('payment', {})]:
    cs = ok(c.put(f"/checkout-sessions/{cs['id']}/steps/{st}", headers=emp, json={'command_id': cid(), **extra}))
# SANDBOX (test-mode) payment on the local dev backend, same as docs/qa/2026-11-23-stitch-account/harness/pay.py
from urllib.parse import urlparse, parse_qs
pid = cs['payment_intent_id']; url = ok(c.post(f'/payments/{pid}/initiate', headers=emp, json={})).get('redirect_url')
u = urlparse(url); q = parse_qs(u.query)
r = c.post(f"/payments/sandbox/{u.path.rsplit('/', 1)[-1]}/decision", data={'state': q['state'][0], 'decision': 'success'}, headers={'accept': 'text/html'})
if r.headers.get('location'): c.get(r.headers['location'])
print('sandbox verify', c.post(f'/payments/{pid}/verify', headers=emp, json={}).status_code)
# the contracted (test) supplier fulfils the stay; the backend then issues the invoice that the organization statement lists
r = c.post(f'/reservations/{res}/fulfill', headers=sup, json={'command_id': cid(), 'provider_reference': 'QA-TEST-' + sfx, 'document_reference': 'document://qa-test-voucher-' + sfx}); print('fulfil', r.status_code, r.text[:160])
# organization credit line: maker (finance) + checker (tenant admin), then ledger commands
mk = c.post(f'/organizations/{org}/credit-accounts', headers=fin, json={'organization_id': org, 'limit_amount': 500_000_000, 'currency': 'IRR', 'command_id': cid()}); print('credit maker', mk.status_code)
appr = mk.json().get('approval_request', {}).get('id')
if appr: print('credit checker', c.post(f'/maker-checker/requests/{appr}/approve', headers=login('finance-checker-qa@aftab.test'), json={'note': 'QA'}).status_code)
acct = ok(c.get(f'/enterprise/organizations/{org}/credit', headers=dual))
if acct:
    a = acct[0]['id']
    for kind, amount in [('reserve', 60_000_000), ('capture', 18_000_000)]:
        r = c.post(f'/organization-credit/{a}/commands', headers=fin, json={'command_id': cid(), 'entry_type': kind, 'amount': amount}); print('credit', kind, r.status_code, r.text[:160])
print(json.dumps({'org': org, 'pending_request': r1, 'out_of_policy_request': r2, 'approved_request': r3, 'reservation': res, 'dual': DUAL}))
