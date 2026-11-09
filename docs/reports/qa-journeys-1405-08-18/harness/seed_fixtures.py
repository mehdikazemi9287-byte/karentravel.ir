"""QA harness fixture seeder for the LOCAL Karen Travel stack only.

Every row created here is QA/demo data, labelled "[QA-DEMO]". Nothing here is a
real supplier, price or availability. Writes fixtures.json for the Playwright
journeys. Run with the backend's own env (env.sh) and venv python.
"""
import json, os, sys, uuid
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, os.getenv("QA_BACKEND", "/home/claude/qawt/backend"))
import httpx
from sqlalchemy import select
from app.main import SessionLocal, Tenant, User
from app.database import set_tenant_context

API = os.getenv("QA_API", "http://127.0.0.1:8000")
c = httpx.Client(base_url=API, timeout=30)
out = {}


def tok(email):
    r = c.post("/auth/dev-login", json={"email": email}); r.raise_for_status(); return r.json()


def H(t, idem=None):
    h = {"Authorization": "Bearer " + t["access_token"]}
    if idem: h["Idempotency-Key"] = idem
    return h


def ok(r, *codes):
    if r.status_code not in (codes or (200, 201)):
        print("FAIL", r.request.method, r.request.url, r.status_code, r.text[:400]); raise SystemExit(1)
    return r.json()

# --- system tenants (public catalog + consumer) seeded directly, as production bootstrap would
with SessionLocal() as db:
    pub = db.scalar(select(Tenant).where(Tenant.slug == "karenseir-public"))
    if pub is None:
        pub = Tenant(slug="karenseir-public", name="کارن‌سیر — کاتالوگ عمومی", primary_color="#0B6E4F"); db.add(pub); db.flush()
    set_tenant_context(db, pub.id)
    if not db.scalar(select(User).where(User.tenant_id == pub.id, User.role == "public_search_identity")):
        db.add(User(tenant_id=pub.id, email="system+public-search@karenseir.internal", name="KarenSeir Public Search", role="public_search_identity"))
    con = db.scalar(select(Tenant).where(Tenant.slug == "karenseir-consumer"))
    if con is None:
        con = Tenant(slug="karenseir-consumer", name="مشتریان کارن تراول", primary_color="#0E7490"); db.add(con); db.flush()
    set_tenant_context(db, con.id)
    for email, name, mob in [("qa-customer@consumer.qa", "[QA-DEMO] مشتری عادی", "+989120000001"), ("qa-student@consumer.qa", "[QA-DEMO] دانشجو", "+989120000002"), ("qa-elder@consumer.qa", "[QA-DEMO] سالمند", "+989120000003")]:
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(tenant_id=con.id, email=email, name=name, role="customer", mobile_e164=mob))
    db.commit()
    pub_id, con_id = pub.id, con.id

now = datetime.now(timezone.utc)
policy = {"verified": True, "source": "qa-demo-contract", "verified_at": now.isoformat(), "cancellation": {"refundable": True, "penalty_amount": 100000, "description": "[QA-DEMO] استرداد با جریمه ۱۰۰٬۰۰۰ ریال"}}


def seed_catalog(supplier_email, tag):
    s = tok(supplier_email)
    sup = ok(c.post("/supplier/onboarding", headers=H(s, f"qa-sup-{tag}-{uuid.uuid4()}"), json={"supplier_type": "multi_service", "display_name": f"[QA-DEMO] تأمین‌کننده {tag}"}), 201)
    offers = {}
    def offer(key, **body):
        body.setdefault("policy", policy); body.setdefault("fulfillment_mode", "manual_supplier"); body.setdefault("provider_key", "manual_supplier"); body.setdefault("valid_minutes", 43200)
        offers[key] = ok(c.post("/supplier/offers", headers=H(s), json={"supplier_id": sup["id"], **body}), 201)["id"]
    for i, amt in enumerate([21_000_000, 18_500_000, 26_000_000]):
        offer(f"flight{i}", service_type="flight", title=f"[QA-DEMO] پرواز تهران شیراز {i+1}", amount=amt, available_units=9,
              attributes={"origin": "تهران", "destination": "شیراز", "airline": "[QA-DEMO] ایرلاین آزمایشی", "departure_time": f"0{7+i}:30", "arrival_time": f"0{8+i}:50", "duration": "۱ ساعت و ۲۰ دقیقه", "duration_minutes": 80 + i, "stops": 0, "baggage": "۲۰ کیلوگرم", "rating": 4.2, "organization_policy_compliant": True, "entity_id": f"qa-flight-{tag}-{i}"})
    dep = (now + timedelta(days=12)).replace(microsecond=0)
    for i, amt in enumerate([4_800_000, 3_900_000]):
        offer(f"train{i}", service_type="train", title=f"[QA-DEMO] قطار تهران مشهد {i+1}", amount=amt, available_units=20,
              attributes={"origin": "تهران", "destination": "مشهد", "rail_operator": "[QA-DEMO] رجا آزمایشی", "train_number": f"QA-{300+i}", "seat_class": "کوپه ۴ تخته" if i == 0 else "سالنی اقتصادی", "departure_time": (dep + timedelta(hours=i*3)).isoformat(), "arrival_time": (dep + timedelta(hours=11 + i*3)).isoformat(), "duration_minutes": 660, "entity_id": f"qa-train-{tag}-{i}"})
    ci = date.today() + timedelta(days=20)
    offer("hotel", service_type="hotel", title="[QA-DEMO] هتل آزمایشی شیراز", amount=35_000_000, available_units=4,
          attributes={"city": "شیراز", "stars": 4, "rating": 4.4, "review_score": 8.4, "room_type": "دوتخته", "breakfast": True, "amenities": ["wifi"], "entity_id": f"qa-hotel-{tag}",
                      "hotel_rate": {"check_in": ci.isoformat(), "check_out": (ci + timedelta(days=2)).isoformat(), "room_type": "دوتخته", "rate_plan": "BB", "price_basis": "room_stay", "occupancy": {"adults": 2, "children_ages": []}}})
    tour = ok(c.post("/supplier/tours", headers=H(s), json={"supplier_id": sup["id"], "title": f"[QA-DEMO] تور فرهنگی شیراز {tag}", "slug": f"qa-tour-{tag}-{uuid.uuid4().hex[:6]}", "origin": "تهران", "destination": "شیراز", "tour_type": "cultural", "details": {"visa_status": "not_required", "services": ["هتل", "راهنما"], "itinerary": [{"day": 1, "title": "حافظیه"}], "cancellation_policy": policy}}), 201)
    ok(c.post(f"/supplier/tours/{tour['id']}/departures", headers=H(s), json={"starts_at": (now + timedelta(days=30)).isoformat(), "ends_at": (now + timedelta(days=33)).isoformat(), "booking_deadline": (now + timedelta(days=28)).isoformat(), "capacity": 12, "base_price": 15_000_000, "pricing": {"single_surcharge": 3_000_000}}), 201)
    return {"supplier_id": sup["id"], "offers": offers, "tour_id": tour["id"]}

# corporate tenant (aftab-bank) catalog, via the real supplier panel API
out["aftab"] = seed_catalog("supplier@aftab.test", "aftab")

# public + consumer catalogs: supplier users must exist in those tenants
with SessionLocal() as db:
    for tid, email in [(pub_id, "qa-supplier@public.qa"), (con_id, "qa-supplier@consumer.qa")]:
        set_tenant_context(db, tid)
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(tenant_id=tid, email=email, name="[QA-DEMO] تأمین‌کننده", role="supplier"))
    db.commit()
out["public"] = seed_catalog("qa-supplier@public.qa", "public")
out["consumer"] = seed_catalog("qa-supplier@consumer.qa", "consumer")

# organization, members, credit account (limit 50,000,000 IRR) and policy
ta = tok("tenant-admin@aftab.test")
orgs = ok(c.get("/enterprise/organizations", headers=H(ta)))
org = next((o for o in orgs if o["name"].startswith("[QA-DEMO]")), None) or ok(c.post("/enterprise/organizations", headers=H(ta), json={"name": "[QA-DEMO] سازمان آفتاب"}), 201)
for email in ["employee@aftab.test", "org-admin@aftab.test", "welfare@aftab.test"]:
    ok(c.post(f"/enterprise/organizations/{org['id']}/members", headers=H(ta), json={"email": email}), 201)
oa = tok("org-admin@aftab.test")
fin = tok("finance@aftab.test")  # credit:fund is finance-only since PR #52 (H-1)
credit = ok(c.post(f"/organizations/{org['id']}/credit-accounts", headers=H(fin), json={"organization_id": org["id"], "limit_amount": 50_000_000, "command_id": "qa-credit-" + uuid.uuid4().hex}), 201)
out.update({"org_id": org["id"], "credit_account": credit, "public_tenant_id": pub_id, "consumer_tenant_id": con_id})
json.dump(out, open(os.getenv("QA_DIR", "/home/claude/qa-journeys") + "/fixtures.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:1500])
