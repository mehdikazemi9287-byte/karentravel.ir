"""Compatibility gate, part 2: the production API contract (old image) must be preserved by the new image.
Both run on identical throwaway copies of production. Nothing here talks to production."""
import json, subprocess, sys, urllib.request, urllib.error, urllib.parse, uuid
OLD, NEW = "http://127.0.0.1:18134", "http://127.0.0.1:18138"
def call(base, method, path, token=None, body=None, headers=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json", **({"Authorization": "Bearer " + token} if token else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: raw, status = r.read(), r.status
    except urllib.error.HTTPError as e: raw, status = e.read(), e.code
    except Exception as e: return 0, str(e)[:60]
    try: return status, json.loads(raw) if raw else None
    except Exception: return status, "<non-json>"
def shape(v, depth=0):
    if isinstance(v, dict): return {k: shape(x, depth + 1) for k, x in sorted(v.items())} if depth < 6 else "{}"
    if isinstance(v, list): return [shape(v[0], depth + 1)] if v else []
    return type(v).__name__ if v is not None else "null"
def missing(old, new, path=""):
    """keys/structure present in the old response but absent or of another kind in the new one"""
    out = []
    if isinstance(old, dict):
        if not isinstance(new, dict): return [f"{path}: object -> {new if isinstance(new, str) else type(new).__name__}"]
        for k, v in old.items():
            if k not in new: out.append(f"{path}.{k}: missing")
            else: out += missing(v, new[k], f"{path}.{k}")
    elif isinstance(old, list):
        if not isinstance(new, list): return [f"{path}: list -> other"]
        if old and new: out += missing(old[0], new[0], path + "[]")
    elif old != new and "null" not in (old, new): out.append(f"{path}: {old} -> {new}")
    return out
so, sn = (json.load(urllib.request.urlopen(b + "/openapi.json")) for b in (OLD, NEW))
fails, notes = [], []
def resolve(spec, s):
    while isinstance(s, dict) and "$ref" in s: s = spec["components"]["schemas"][s["$ref"].split("/")[-1]]
    return s or {}
# 1. static contract
ops = [(p, m) for p, v in so["paths"].items() for m in v if m in ("get", "post", "put", "patch", "delete")]
for p, m in ops:
    o, n = so["paths"][p][m], sn["paths"].get(p, {}).get(m)
    if n is None: fails.append(f"REMOVED {m.upper()} {p}"); continue
    op_, np_ = ({(x["name"], x["in"]): x.get("required", False) for x in d.get("parameters", [])} for d in (o, n))
    for k in op_:
        if k not in np_: fails.append(f"PARAM_REMOVED {m.upper()} {p} {k}")
    for k, req in np_.items():
        if req and not op_.get(k, False): fails.append(f"PARAM_NOW_REQUIRED {m.upper()} {p} {k}")
    ob, nb = (resolve(s, (d.get("requestBody", {}).get("content", {}).get("application/json", {}) or {}).get("schema")) for s, d in ((so, o), (sn, n)))
    extra_required = set(nb.get("required", [])) - set(ob.get("required", []))
    if extra_required: fails.append(f"BODY_NOW_REQUIRES {m.upper()} {p} {sorted(extra_required)}")
    gone = set(ob.get("properties", {})) - set(nb.get("properties", {}))
    if gone and nb.get("properties"): fails.append(f"BODY_FIELD_REMOVED {m.upper()} {p} {sorted(gone)}")
print("static: old ops", len(ops), "new paths", len(sn["paths"]), "added paths", len(set(sn["paths"]) - set(so["paths"])))
# 2. live behaviour, same data, every seeded/prod role
rows = subprocess.run(["docker", "exec", "ks-catalog-scratch-pg", "psql", "-U", "postgres", "-d", "ks_gate_old", "-At", "-F", "|", "-c", "select distinct on (role, tenant_id) email, role, tenant_id from users order by role, tenant_id, id"], capture_output=True, text=True).stdout.split()
users = {"anon": (None, None)}
for row in rows:
    email, role, tenant = row.split("|")
    to, tn = call(OLD, "POST", "/auth/dev-login", body={"email": email}), call(NEW, "POST", "/auth/dev-login", body={"email": email})
    if to[0] != 200 or tn[0] != 200: fails.append(f"LOGIN {role} old={to[0]} new={tn[0]}"); continue
    if missing(shape(to[1]), shape(tn[1])): fails.append(f"LOGIN_SHAPE {role} {missing(shape(to[1]), shape(tn[1]))}")
    users[f"{role}@t{tenant}"] = (to[1]["access_token"], tn[1]["access_token"])
print("users:", sorted(users))
compared = diffs = 0
def compare(label, method, path, who, body=None, headers=None):
    global compared, diffs
    (so_, bo), (sn_, bn) = call(OLD, method, path, users[who][0], body, headers), call(NEW, method, path, users[who][1], body, headers)
    compared += 1
    problems = [f"status {so_} -> {sn_}"] if so_ != sn_ else (missing(shape(bo), shape(bn)) if so_ < 400 else [])
    if problems: diffs += 1; fails.append(f"LIVE {label} {method} {path} as {who}: {problems[:4]}")
    return so_, bo, bn
gets = sorted(p for p, m in ops if m == "get" and "{" not in p and not any(x.get("required") and x["in"] == "query" for x in so["paths"][p]["get"].get("parameters", [])))
for p in gets:
    for who in users: compare("GET", "GET", p, who)
# parameterised reads the current frontend uses, with real ids from list endpoints
emp = next((u for u in users if u.startswith("employee")), None) or next(u for u in users if u != "anon")
st, hotels, _ = compare("GET", "GET", "/hotels", emp)
for q in ("/search/v2/public?vertical=hotel&destination=" + urllib.parse.quote("تهران"), "/search/v2/public?vertical=flight&origin=THR&destination=MHD&date=2026-11-01", "/public/tour-products", "/public/accommodation?city=" + urllib.parse.quote("تهران")):
    if q.split("?")[0] in so["paths"]: compare("GET", "GET", q, "anon")
for who in users:
    for p, key in (("/bookings", "id"), ("/trips", "id"), ("/notifications", "id")):
        if p in so["paths"] and "get" in so["paths"][p]:
            s, body, _ = compare("GET", "GET", p, who)
            item = (body or [None])[0] if isinstance(body, list) else ((body or {}).get("items") or [None])[0] if isinstance(body, dict) else None
            detail = p + "/{" + [x for x in so["paths"] if x.startswith(p + "/{") and x.count("/") == 2][0].split("{")[1] if any(x.startswith(p + "/{") and x.count("/") == 2 for x in so["paths"]) else None
            if s == 200 and isinstance(item, dict) and key in item and detail and "get" in so["paths"][detail]: compare("GET", "GET", f"{p}/{item[key]}", who)
# existing booking flow on the copies (same request to both)
if isinstance(hotels, list) and hotels:
    idem = "gate-" + uuid.uuid4().hex
    s, bo, bn = compare("BOOKING", "POST", "/bookings", emp, {"hotel_id": hotels[0]["id"], "nights": 1}, {"Idempotency-Key": idem})
    notes.append(f"booking create status={s}")
    compare("BOOKING", "POST", "/bookings", emp, {"hotel_id": hotels[0]["id"], "nights": 1}, {"Idempotency-Key": idem})
    compare("BOOKING", "POST", "/bookings", emp, {"hotel_id": 999999, "nights": 1}, {"Idempotency-Key": "gate-" + uuid.uuid4().hex})
    compare("BOOKING", "POST", "/bookings", "anon", {"hotel_id": hotels[0]["id"], "nights": 1}, {"Idempotency-Key": "gate-" + uuid.uuid4().hex})
    compare("GET", "GET", "/dashboard", emp)
# auth/validation layer of every write route: empty body, anonymous and employee (skips anything that could message a person)
writes = sorted((p, m) for p, m in ops if m != "get" and not any(w in p for w in ("otp", "sms", "register", "voice", "assistant", "dev-login")))
for p, m in writes:
    path = p.replace("{", "").replace("}", "") if "{" not in p else "/".join("1" if seg.startswith("{") else seg for seg in p.split("/"))
    for who in ("anon", emp): compare("WRITE_GUARD", m.upper(), path, who, {})
print("live: GET routes", len(gets), "write routes", len(writes), "comparisons", compared, "differences", diffs)
print("notes:", notes)
print("RESULT:", "PASS" if not fails else f"FAIL ({len(fails)})")
for f in fails[:40]: print("  ", f[:300])
