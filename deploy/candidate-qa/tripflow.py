"""Candidate flow through the HTTP API only (used for the least-privilege proof and browser fixtures)."""
import json, sys, urllib.request, urllib.error, uuid
A = "http://127.0.0.1:18137"; TRIP = sys.argv[1]
def call(method, path, body=None, token=None):
    req = urllib.request.Request(A + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={"content-type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
tok = lambda email: call("POST", "/auth/dev-login", {"email": email})[1]["access_token"]
ops, cust = tok("backoffice@aftab.test"), tok("employee@aftab.test")
ev = lambda **o: {"command_id": "flow-" + uuid.uuid4().hex, "category": "schedule_change", "severity": "critical", "source": "supplier", "old_value": {"پرواز": "W5 1041", "حرکت": "۱۴۰۵/۰۸/۰۱ ساعت ۰۸:۰۰"}, "new_value": {"پرواز": "W5 1041", "حرکت": "۱۴۰۵/۰۸/۰۱ ساعت ۱۴:۳۰"}, "reason": "اعلام ایرلاین", "requires_action": True, **o}
s1, e1 = call("POST", f"/operations/trips/{TRIP}/events", ev(), ops)
s2, e2 = call("POST", f"/operations/trips/{TRIP}/events", ev(category="hotel_change", severity="warning", old_value={"هتل": "هتل الف"}, new_value={"هتل": "هتل ب"}, requires_action=False, reason="تغییر از سوی تأمین‌کننده"), ops)
s3, e3 = call("POST", f"/operations/trips/{TRIP}/events", ev(category="supplier_issue", old_value=None, new_value={"وضعیت": "در انتظار پاسخ تأمین‌کننده"}, visibility="internal", reason="پیگیری داخلی"), ops)
s4, ch = call("GET", f"/trips/{TRIP}/changes", token=cust)
s5, ack = call("POST", f"/trips/{TRIP}/events/{e2['id']}/acknowledge", token=cust)
s6, center = call("GET", "/operations/trip-events?unacknowledged=true", token=ops)
s7, dl = call("GET", f"/operations/notification-deliveries?trip_event_id={e1['id']}", token=ops)
print("record", s1, s2, s3, "| customer changes", s4, len(ch.get("changes", [])), "unack", ch.get("unacknowledged"), "| ack", s5, ack.get("acknowledged"), "| center", s6, center.get("summary"), "| deliveries", s7, sorted(d["channel"] + ":" + d["delivery_status"] for d in dl.get("items", [])))
