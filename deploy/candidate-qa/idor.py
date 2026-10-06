"""Candidate object-level access sweep: every GET route with path parameters, called with real object ids that belong
to tenant A / customer A, by (1) anonymous, (2) a user of another tenant, (3) same-tenant users whose role has no
reservation/trip read permission. Any 2xx is a finding. Read-only."""
import json, subprocess, urllib.request, urllib.error, collections
A = "http://127.0.0.1:18137"
def sql(q):
    return [l for l in subprocess.run(["docker", "exec", "ks-catalog-scratch-pg", "psql", "-U", "postgres", "-d", "ks_cand37", "-At", "-c", q], capture_output=True, text=True).stdout.split("\n") if l]
def call(path, token=None):
    req = urllib.request.Request(A + path, headers={"Authorization": "Bearer " + token} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r: return r.status
    except urllib.error.HTTPError as e: return e.code
    except Exception: return 0
def tok(email):
    r = urllib.request.Request(A + "/auth/dev-login", method="POST", data=json.dumps({"email": email}).encode(), headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(r))["access_token"]
OWNER = "(select id from users where email='employee@aftab.test')"; TEN = "(select tenant_id from users where email='employee@aftab.test')"
pools = {
 "reservation_id": f"select id from reservations where user_id={OWNER} limit 2", "trip_id": f"select id from trips where user_id={OWNER} limit 2", "case_id": f"select id from support_cases where user_id={OWNER} limit 2",
 "payment_id": f"select id from payment_intents where user_id={OWNER} limit 2", "notification_id": f"select id from notifications where user_id={OWNER} limit 2", "wallet_id": f"select id from wallets where tenant_id={TEN} limit 1",
 "itinerary_id": f"select id from editable_itineraries where tenant_id={TEN} limit 1", "checkout_id": f"select id from checkout_sessions where tenant_id={TEN} limit 1", "agency_id": f"select id from agencies where tenant_id={TEN} limit 2",
 "quote_id": f"select id from agency_quotes where tenant_id={TEN} limit 1", "event_id": f"select id from trip_events where tenant_id={TEN} and visibility='customer' limit 1", "approval_id": f"select id from approval_workflows where tenant_id={TEN} limit 1",
 "application_id": f"select id from visa_applications where tenant_id={TEN} limit 1", "credit_account_id": f"select id from credit_accounts where tenant_id={TEN} limit 1", "supplier_id": f"select id from suppliers where tenant_id={TEN} limit 1",
 "rid": f"select id from enterprise_requests where tenant_id={TEN} limit 1", "org": f"select id from organizations where tenant_id={TEN} limit 1", "organization_id": f"select id from organizations where tenant_id={TEN} limit 1",
 "saved_search_id": f"select id from saved_searches where tenant_id={TEN} limit 1", "offer_id": f"select id from offers where tenant_id={TEN} limit 1", "tour_id": f"select id from tour_products where tenant_id={TEN} limit 1",
 "attempt_id": f"select id from notification_delivery_attempts where tenant_id={TEN} limit 1", "entry_id": f"select id from agency_commission_entries where tenant_id={TEN} limit 1", "mapping_id": "select id::text from catalog_hotel_provider_mappings limit 1",
 "hotel_id": "select '4fb4ffe9-42f6-5d4e-8fcd-fde6c9071e84'", "match_id": "select id::text from catalog_hotel_matches limit 1", "dataset": "select 'payments'", "section": "select 'payments'"}
ids = {k: sql(q) for k, q in pools.items()}
spec = json.load(urllib.request.urlopen(A + "/openapi.json"))
PUBLIC = ("/catalog/", "/public/", "/media/public/", "/destinations/", "/places/", "/vacation-rentals/", "/tour-products/", "/experience-products/", "/visa-products", "/payments/callback", "/notification-receipts", "/vacation-units/", "/offers/", "/leisure-sessions")
actors = {"anon": None, "other_tenant_customer": tok("employee@faraz.test"), "same_tenant_supplier": tok("supplier@aftab.test"), "same_tenant_agency": tok("agency@aftab.test")}
tested, skipped, findings, counts = 0, [], [], collections.Counter()
for path, ops in sorted(spec["paths"].items()):
    if "get" not in ops or "{" not in path or path.startswith(PUBLIC): continue
    params = [seg[1:-1] for seg in path.split("/") if seg.startswith("{")]
    if any(not ids.get(p) for p in params): skipped.append(path); continue
    url = path
    for p in params: url = url.replace("{" + p + "}", ids[p][0])
    required = [x["name"] for x in ops["get"].get("parameters", []) if x.get("required") and x["in"] == "query"]
    if required: url += "?" + "&".join(f"{n}=2027-01-10" if "check" in n else f"{n}=x" for n in required)
    tested += 1
    for name, token in actors.items():
        status = call(url, token); counts[(name, status // 100)] += 1
        legit = name == "same_tenant_agency" and path.startswith("/agency/")          # member of the QA agency
        legit = legit or (name == "same_tenant_supplier" and path.startswith("/supplier/"))
        if 200 <= status < 300 and not legit: findings.append(f"{name} {status} GET {path}")
        if status >= 500 or status == 0: findings.append(f"{name} {status} GET {path} (server error)")
print("routes_tested", tested, "skipped_no_fixture", len(skipped), [s for s in skipped][:14])
print("status classes", {f"{a}:{c}xx": n for (a, c), n in sorted(counts.items())})
print("FINDINGS", len(findings)); [print("  ", f) for f in findings[:30]]
