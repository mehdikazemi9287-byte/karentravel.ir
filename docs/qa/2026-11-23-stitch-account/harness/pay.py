# Local QA only: walk the hotel reservation through checkout and a SANDBOX (test-mode) payment on the local dev backend.
import httpx, sys, uuid, re
from urllib.parse import urlparse, parse_qs
API='http://127.0.0.1:8130'; rid=sys.argv[1]
c=httpx.Client(base_url=API,timeout=30)
tok=c.post('/auth/dev-login',json={'email':'employee@aftab.test'}).json()['access_token']; H={'Authorization':'Bearer '+tok}
tr=[]
for n in ['مسافر آزمایشی یک','مسافر آزمایشی دو']:
    r=c.post('/me/travellers',headers={**H,'Idempotency-Key':str(uuid.uuid4())},json={'full_name':n,'nationality':'IR'}); print('trav',r.status_code,r.text[:120]); tr.append(r.json()['id'])
r=c.post(f'/reservations/{rid}/checkout-sessions',headers=H,json={'command_id':str(uuid.uuid4())}); print('start',r.status_code); cs=r.json()
steps=[('traveller',{'traveller_ids':tr}),('recheck',{}),('policy',{'acknowledged':True}),('funding',{'wallet_amount':0,'credit_amount':0}),('invoice',{}),('payment',{})]
for st,extra in steps:
    r=c.put(f"/checkout-sessions/{cs['id']}/steps/{st}",headers=H,json={'command_id':str(uuid.uuid4()),**extra}); print(st,r.status_code,r.text[:160] if r.status_code>=300 else r.json().get('stage'))
    if r.status_code>=300: sys.exit(1)
    cs=r.json()
pid=cs['payment_intent_id']; print('pid',pid)
r=c.post(f'/payments/{pid}/initiate',headers=H,json={}); print('init',r.status_code,r.text[:200]); url=r.json().get('redirect_url')
u=urlparse(url); q=parse_qs(u.query); auth=u.path.rsplit('/',1)[-1]
r=c.post(f'/payments/sandbox/{auth}/decision',data={'state':q['state'][0],'decision':'success'},headers={'accept':'text/html'}); print('decision',r.status_code,r.headers.get('location'))
loc=r.headers.get('location')
if loc: r=c.get(loc); print('callback',r.status_code,r.headers.get('location'))
r=c.post(f'/payments/{pid}/verify',headers=H,json={}); print('verify',r.status_code,r.text[:300])
