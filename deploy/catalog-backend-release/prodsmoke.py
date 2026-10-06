"""Read-only production smoke: anonymous GET of every parameterless route + guard check of write routes with an empty body.
Usage: prodsmoke.py <out.json> [before.json]   (second form compares against a saved snapshot)"""
import json, sys, urllib.request, urllib.error
A = "http://127.0.0.1:8000"
def call(method, path, body=None):
    req = urllib.request.Request(A + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: raw, status = r.read(), r.status
    except urllib.error.HTTPError as e: raw, status = e.read(), e.code
    except Exception as e: return 0, str(e)[:50]
    try: return status, json.loads(raw) if raw else None
    except Exception: return status, "<non-json>"
def shape(v, d=0):
    if isinstance(v, dict): return {k: shape(x, d + 1) for k, x in sorted(v.items())} if d < 6 else "{}"
    if isinstance(v, list): return [shape(v[0], d + 1)] if v else []
    return type(v).__name__ if v is not None else "null"
def missing(old, new, path=""):
    out = []
    if isinstance(old, dict):
        if not isinstance(new, dict): return [f"{path}: object -> other"]
        for k, v in old.items(): out += [f"{path}.{k}: missing"] if k not in new else missing(v, new[k], f"{path}.{k}")
    elif isinstance(old, list):
        if not isinstance(new, list): return [f"{path}: list -> other"]
        if old and new: out += missing(old[0], new[0], path + "[]")
    elif old != new and "null" not in (old, new): out.append(f"{path}: {old} -> {new}")
    return out
before = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
spec = before["spec_ops"] if before else None
live = json.load(urllib.request.urlopen(A + "/openapi.json"))
ops = spec or sorted([m.upper(), p] for p, v in live["paths"].items() for m in v if m in ("get", "post", "put", "patch", "delete") and not (m == "get" and ("{" in p or any(x.get("required") and x["in"] == "query" for x in v[m].get("parameters", [])))))
snap = {"spec_ops": ops, "results": {}}
for method, path in ops:
    if method != "GET" and any(w in path for w in ("otp", "sms", "register", "voice", "assistant", "dev-login", "webhook", "callback")): continue  # never trigger a message or a provider callback on production
    p = "/".join("1" if seg.startswith("{") else seg for seg in path.split("/"))
    status, body = call(method, p, None if method == "GET" else {})
    snap["results"][f"{method} {path}"] = [status, shape(body) if method == "GET" and status < 400 else None]
json.dump(snap, open(sys.argv[1], "w"))
r = snap["results"]; print("routes", len(r), "2xx", sum(1 for s, _ in r.values() if 200 <= s < 300), "4xx", sum(1 for s, _ in r.values() if 400 <= s < 500), "5xx/0", [k for k, (s, _) in r.items() if s >= 500 or s == 0])
print("anon 2xx on non-GET:", [k for k, (s, _) in r.items() if not k.startswith("GET") and 200 <= s < 300])
if before:
    bad = [f"{k}: {before['results'][k][0]} -> {r[k][0]}" for k in before["results"] if k in r and before["results"][k][0] != r[k][0]]
    bad += [f"{k}: {m[:3]}" for k in before["results"] if k in r and before["results"][k][0] == r[k][0] and before["results"][k][1] is not None for m in [missing(before["results"][k][1], r[k][1])] if m]
    bad += [f"{k}: gone" for k in before["results"] if k not in r]
    print("COMPARE_WITH_BEFORE:", "IDENTICAL" if not bad else bad[:20]); sys.exit(1 if bad else 0)
