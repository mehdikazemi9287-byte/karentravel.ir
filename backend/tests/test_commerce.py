import uuid

from app.commerce import valid_card, valid_sheba, normalize_sheba


def _h(client, email):
    return {"Authorization": f"Bearer {client.post('/auth/dev-login', json={'email': email}).json()['access_token']}"}


def _uid(client, h):
    return client.get("/me/profile", headers=h).json()["user_id"]


def test_bank_identifier_checksums():
    assert valid_card("6219861034529007") and not valid_card("6219861034529008")
    assert valid_sheba("IR062960000000100324200001") and valid_sheba("۰۶۲۹۶۰۰۰۰۰۰۰۱۰۰۳۲۴۲۰۰۰۰۱")
    assert not valid_sheba("IR062960000000100324200002")
    assert normalize_sheba("06 2960 0000 0010 0324 2000 01") == "IR062960000000100324200001"


def test_markup_rule_specificity_and_pax_math(client):
    admin = _h(client, "platform-admin@aftab.test")
    code = "g" + uuid.uuid4().hex[:6]
    g = client.post("/commerce/groups", json={"code": code, "name": "همکاران"}, headers=admin)
    assert g.status_code == 201, g.text
    gid = g.json()["id"]
    emp = _h(client, "employee@aftab.test")
    emp_id = _uid(client, emp)
    assert client.put(f"/commerce/groups/{gid}/members", json={"user_ids": [emp_id]}, headers=admin).json()["assigned"] == 1
    base = {"service_type": "flight", "calc": "percent", "adult": 500, "child": 500, "infant": 100, "round_to": 1000}
    general = client.post("/commerce/markup-rules", json={**base, "title": "عمومی پرواز"}, headers=admin)
    assert general.status_code == 201
    r = client.post("/commerce/markup-rules", json={**base, "title": "همکار مشهد", "group_id": gid, "origin": "thr", "destination": "MHD",
                                                    "effect": "discount", "adult": 300, "child": 300}, headers=admin)
    assert r.status_code == 201 and r.json()["origin"] == "THR"
    fares = {"adult": {"count": 2, "total": 10_000_000}, "child": {"count": 1, "total": 7_500_000}}
    p = client.post("/commerce/markup-rules/preview", json={"service_type": "flight", "user_id": emp_id, "origin": "THR", "destination": "MHD", "fares": fares}, headers=admin).json()
    assert p["rule"]["title"] == "همکار مشهد" and p["lines"][0]["sell"] == 9_700_000 and p["sell_total"] == 2 * 9_700_000 + 7_275_000
    other = client.post("/commerce/markup-rules/preview", json={"service_type": "flight", "origin": "THR", "destination": "KIH", "fares": fares}, headers=admin).json()
    assert other["rule"]["title"] == "عمومی پرواز" and other["lines"][0]["sell"] == 10_500_000 and other["margin"] > 0
    assert client.post("/commerce/markup-rules", json={**base, "title": "x", "service_type": "spaceship"}, headers=admin).status_code == 422
    assert client.get("/commerce/markup-rules", headers=emp).status_code == 403
    # the shared test database must not keep active rules that would reprice other journeys
    for rule in client.get("/commerce/markup-rules", headers=admin).json()["items"]:
        assert client.put(f"/commerce/markup-rules/{rule['id']}", json={**{k: v for k, v in rule.items() if k != "id"}, "status": "disabled"}, headers=admin).status_code == 200


def test_penalty_tiers(client):
    admin = _h(client, "platform-admin@aftab.test")
    code = "P" + uuid.uuid4().hex[:5]
    r = client.post("/commerce/penalty-rules", json={"code": code, "title": "سیستمی داخلی", "service_type": "flight", "tiers": [
        {"until_minutes": 4320, "adult": 3000, "child": 3000, "infant": 1000},
        {"until_minutes": 180, "adult": 5000, "child": 5000, "infant": 1000},
        {"until_minutes": 0, "adult": 8000, "child": 8000, "infant": 1000}]}, headers=admin)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    fares = {"adult": {"count": 1, "total": 10_000_000}}
    calc = lambda mins: client.post(f"/commerce/penalty-rules/{rid}/calculate", json={"minutes_before": mins, "fares": fares}, headers=admin).json()
    assert calc(10000)["penalty_total"] == 3_000_000 and calc(1000)["penalty_total"] == 5_000_000 and calc(60)["penalty_total"] == 8_000_000
    assert client.post("/commerce/penalty-rules", json={"code": code, "title": "dup", "service_type": "flight", "tiers": [{"until_minutes": 0}]}, headers=admin).status_code == 409


def test_treasury_requests_adjustments_and_subsidiary(client):
    fin = _h(client, "finance@aftab.test")
    admin = _h(client, "platform-admin@aftab.test")
    emp = _h(client, "welfare@aftab.test")
    emp_id = _uid(client, emp)
    # customer deposit request -> finance cannot be bypassed by the customer
    assert client.post("/me/treasury-requests", json={"amount": 5_000_000}, headers=emp).status_code == 422
    req = client.post("/me/treasury-requests", json={"amount": 5_000_000, "tracking_no": "TRK" + uuid.uuid4().hex[:6], "bank_name": "ملت"}, headers=emp)
    assert req.status_code == 201
    assert client.post(f"/commerce/treasury-requests/{req.json()['id']}/decide", json={"approve": True}, headers=emp).status_code == 403
    before = client.get(f"/commerce/users/{emp_id}/account", headers=fin).json()["wallet"]["available"]
    ok = client.post(f"/commerce/treasury-requests/{req.json()['id']}/decide", json={"approve": True, "note": "واریز تأیید شد"}, headers=admin)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    assert client.post(f"/commerce/treasury-requests/{req.json()['id']}/decide", json={"approve": True}, headers=admin).status_code == 409
    acct = client.get(f"/commerce/users/{emp_id}/account", headers=fin).json()
    assert acct["wallet"]["available"] == before + 5_000_000 and acct["statement"][0]["credit"] == 5_000_000
    # admin decrease more than balance is refused; credit limit increase works
    too_much = acct["wallet"]["available"] + 1
    assert client.post(f"/commerce/users/{emp_id}/adjust", json={"target": "wallet", "direction": "decrease", "amount": too_much, "description": "کسر"}, headers=admin).status_code == 409
    up = client.post(f"/commerce/users/{emp_id}/adjust", json={"target": "credit", "direction": "increase", "amount": 20_000_000, "description": "اعتبار همکاری"}, headers=admin)
    assert up.status_code == 201 and up.json()["credit"]["limit_amount"] >= 20_000_000
    assert client.post(f"/commerce/users/{emp_id}/adjust", json={"target": "credit", "direction": "increase", "amount": 1, "description": "تست دسترسی"}, headers=fin).status_code == 403
    book = client.get("/commerce/treasury", params={"counterparty_ref": str(emp_id)}, headers=fin).json()
    assert book["totals"]["credit"] >= 25_000_000
    entry = book["items"][0]
    rev = client.post(f"/commerce/treasury/{entry['id']}/reverse", json={"approve": True, "note": "اشتباه"}, headers=admin)
    assert rev.status_code == 201 and rev.json()["debit"] == entry["credit"]
    assert client.post(f"/commerce/treasury/{entry['id']}/reverse", json={"approve": True}, headers=admin).status_code == 409
    sub = client.get("/commerce/subsidiary", params={"counterparty_type": "user"}, headers=fin).json()
    row = next(i for i in sub["items"] if i["counterparty_ref"] == str(emp_id))
    assert row["remaining"] == row["creditor"] - row["debtor"]
    assert client.get("/commerce/treasury", headers=emp).status_code == 403


def test_bank_account_validation(client):
    emp = _h(client, "employee@aftab.test")
    assert client.put("/me/bank-account", json={"holder_name": "آرمان رضایی", "sheba": "IR062960000000100324200002"}, headers=emp).status_code == 422
    ok = client.put("/me/bank-account", json={"holder_name": "آرمان رضایی", "card_number": "6219-8610-3452-9007", "sheba": "IR062960000000100324200001"}, headers=emp).json()["bank_account"]
    assert ok["card_last4"] == "9007" and ok["card_bank"] == "سامان" and ok["sheba"].startswith("IR06")
    assert client.get("/me/bank-account", headers=emp).json()["bank_account"]["card_last4"] == "9007"


def test_supplier_account_settlement_and_reports(client):
    admin = _h(client, "platform-admin@aftab.test")
    fin = _h(client, "finance@aftab.test")
    sup = client.post("/inventory/suppliers", json={"name": "هتل طرف قرارداد " + uuid.uuid4().hex[:4], "supplier_type": "hotel"}, headers=admin).json()
    assert client.put(f"/commerce/suppliers/{sup['id']}/account", json={"credit_limit": 50_000_000, "sheba": "IR062960000000100324200002"}, headers=admin).status_code == 422
    acc = client.put(f"/commerce/suppliers/{sup['id']}/account", json={"credit_limit": 50_000_000, "payment_terms_days": 14, "sheba": "IR062960000000100324200001"}, headers=admin)
    assert acc.status_code == 200 and acc.json()["sheba"].startswith("IR")
    client.post("/commerce/treasury", json={"counterparty_type": "supplier", "counterparty_ref": sup["id"], "account_type": "payable", "operation": "purchase", "credit": 10_000_000}, headers=admin)
    assert client.post(f"/commerce/suppliers/{sup['id']}/settle", json={"amount": 11_000_000, "tracking_no": "PAY-1"}, headers=admin).status_code == 409
    assert client.post(f"/commerce/suppliers/{sup['id']}/settle", json={"amount": 4_000_000, "tracking_no": "PAY-1", "bank_name": "ملت"}, headers=admin).status_code == 201
    st = client.get(f"/commerce/suppliers/{sup['id']}/statement", headers=fin).json()
    assert st["payable"] == 6_000_000 and st["items"][0]["operation"] == "settlement"
    row = next(s for s in client.get("/commerce/suppliers", headers=fin).json()["items"] if s["id"] == sup["id"])
    assert row["payable"] == 6_000_000 and row["credit_used_pct"] == 12 and not row["over_limit"]
    gw = client.get("/commerce/reports/gateway", headers=fin).json()
    assert "by_status" in gw and isinstance(gw["items"], list)
