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
    assert up.status_code == 202 and up.json()["status"] == "pending_approval"  # maker-checker (H-1)
    from maker_checker_helpers import approve, ensure_user
    assert client.post(f"/maker-checker/requests/{up.json()['approval_request']['id']}/approve", json={}, headers=admin).status_code == 403  # not the maker
    assert client.post(f"/maker-checker/requests/{up.json()['approval_request']['id']}/approve", json={}, headers=fin).status_code == 403  # no credit:manage
    approved = approve(client, up, _h(client, ensure_user("platform-admin@aftab.test", "platform_admin", "platform-checker")))
    assert approved["result"]["credit"]["limit_amount"] >= 20_000_000
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


# ---------------------------------------------------------------- price group of an organization / agency (PR-2) and the standard set
def _tenant_user(email):
    from sqlalchemy import select
    from app.main import SessionLocal, User
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        return u.tenant_id, u.id


def _group(client, admin, name):
    r = client.post("/commerce/groups", json={"code": "g" + uuid.uuid4().hex[:8], "name": name}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_group_links_resolution_order_and_disable(client):
    from sqlalchemy import select
    from app import operations as m
    from app.commerce import CustomerGroupMember, user_group_id
    from app.main import SessionLocal
    admin = _h(client, "platform-admin@aftab.test")
    tid, uid = _tenant_user("agency@aftab.test")            # a user who is both an org employee and an agency member
    with SessionLocal() as db:
        org = m.Organization(tenant_id=tid, name="سازمان آزمون " + uuid.uuid4().hex[:6], status="active")
        agency = m.Agency(tenant_id=tid, display_name="آژانس آزمون " + uuid.uuid4().hex[:6], status="active")
        db.add_all([org, agency]); db.flush()
        db.add_all([m.EmployeeAssignment(tenant_id=tid, user_id=uid, organization_id=org.id), m.AgencyMembership(tenant_id=tid, user_id=uid, agency_id=agency.id)])
        db.commit()
        org_id, agency_id = org.id, agency.id
    g_org, g_agency, g_direct = _group(client, admin, "گروه سازمان"), _group(client, admin, "گروه آژانس"), _group(client, admin, "گروه مستقیم")

    def resolved():
        with SessionLocal() as db:
            return user_group_id(db, tid, uid)
    before = resolved()
    assert client.post(f"/commerce/groups/{g_agency}/links", json={"party_type": "agency", "party_id": agency_id}, headers=admin).status_code == 201
    assert resolved() == g_agency
    link = client.post(f"/commerce/groups/{g_org}/links", json={"party_type": "organization", "party_id": org_id}, headers=admin)
    assert link.status_code == 201 and link.json()["party_name"].startswith("سازمان آزمون")
    assert resolved() == g_org                                   # organization beats agency
    assert client.put(f"/commerce/groups/{g_direct}/members", json={"user_ids": [uid]}, headers=admin).status_code == 200
    assert resolved() == g_direct                                # direct membership beats both
    with SessionLocal() as db:                                  # disable (never delete) the direct membership: the links apply again
        row = db.scalar(select(CustomerGroupMember).where(CustomerGroupMember.tenant_id == tid, CustomerGroupMember.user_id == uid))
        row.status = "disabled"; db.commit()
    assert resolved() == g_org
    off = client.post(f"/commerce/group-links/{link.json()['id']}/disable", headers=admin)
    assert off.status_code == 200 and off.json()["status"] == "disabled"
    assert resolved() == g_agency                                # disabled link falls through, row kept
    items = client.get(f"/commerce/groups/{g_org}/links", headers=admin).json()["items"]
    assert [(i["party_id"], i["status"]) for i in items] == [(org_id, "disabled")]
    # relinking the same organization reactivates the same row
    again = client.post(f"/commerce/groups/{g_org}/links", json={"party_type": "organization", "party_id": org_id}, headers=admin)
    assert again.json()["id"] == link.json()["id"] and again.json()["status"] == "active" and resolved() == g_org
    # an inactive organization gives no group
    with SessionLocal() as db:
        db.get(m.Organization, org_id).status = "suspended"; db.commit()
    assert resolved() == g_agency
    for lk in client.get(f"/commerce/groups/{g_agency}/links", headers=admin).json()["items"] + client.get(f"/commerce/groups/{g_org}/links", headers=admin).json()["items"]:
        client.post(f"/commerce/group-links/{lk['id']}/disable", headers=admin)
    assert resolved() == before
    assert client.get(f"/commerce/groups/{g_org}/links", headers=_h(client, "employee@aftab.test")).status_code == 403


def test_group_link_never_crosses_tenants(client):
    from app import operations as m
    from app.commerce import user_group_id
    from app.main import SessionLocal
    admin = _h(client, "platform-admin@aftab.test")
    tid_a, _ = _tenant_user("platform-admin@aftab.test")
    tid_b, uid_b = _tenant_user("employee@faraz.test")
    assert tid_a != tid_b
    with SessionLocal() as db:
        org_a = m.Organization(tenant_id=tid_a, name="سازمان الف " + uuid.uuid4().hex[:6], status="active")
        org_b = m.Organization(tenant_id=tid_b, name="سازمان ب " + uuid.uuid4().hex[:6], status="active")
        db.add_all([org_a, org_b]); db.flush()
        # a (corrupt) cross-tenant assignment: tenant-B user pointed at tenant-A organization
        db.add(m.EmployeeAssignment(tenant_id=tid_b, user_id=uid_b, organization_id=org_a.id)); db.commit()
        org_a_id, org_b_id = org_a.id, org_b.id
    g = _group(client, admin, "گروه الف")
    # tenant A cannot link tenant B's organization
    assert client.post(f"/commerce/groups/{g}/links", json={"party_type": "organization", "party_id": org_b_id}, headers=admin).status_code == 404
    ok = client.post(f"/commerce/groups/{g}/links", json={"party_type": "organization", "party_id": org_a_id}, headers=admin)
    assert ok.status_code == 201
    try:
        with SessionLocal() as db:
            assert user_group_id(db, tid_b, uid_b) != g           # the tenant-A link has no effect in tenant B
            assert user_group_id(db, tid_a, uid_b) != g           # nor through tenant A for a user who is not assigned there
    finally:
        client.post(f"/commerce/group-links/{ok.json()['id']}/disable", headers=admin)


def test_standard_groups_are_created_once_without_rules(client):
    admin = _h(client, "platform-admin@aftab.test")
    rules_before = len(client.get("/commerce/markup-rules", headers=admin).json()["items"])
    first = client.post("/commerce/groups/standard-set", headers=admin)
    assert first.status_code == 200, first.text
    names = {g["name"]: g for g in client.get("/commerce/groups", headers=admin).json()["items"]}
    for n in ("عمومی", "سازمانی", "وامی‌پی", "اعتباری وچک", "طبیعت"):
        assert n in names and names[n]["status"] == "active"
    assert sum(1 for g in names.values() if g["is_default"]) <= 1
    second = client.post("/commerce/groups/standard-set", headers=admin).json()
    assert second["created"] == [] and len(second["skipped"]) == 5
    assert len(client.get("/commerce/groups", headers=admin).json()["items"]) == len(names)
    assert len(client.get("/commerce/markup-rules", headers=admin).json()["items"]) == rules_before   # no markup rule invented
    assert client.post("/commerce/groups/standard-set", headers=_h(client, "employee@aftab.test")).status_code == 403


# ---------------------------------------------------------------- flights above the CAO cap are not listed (PR-4)
def test_inventory_search_hides_flight_above_cap(client):
    import json as _json
    from datetime import date, datetime, timedelta, timezone
    from sqlalchemy import update
    from app import operations as m
    from app.charter_blocks import PriceCap
    from app.main import SessionLocal
    tid, uid = _tenant_user("backoffice@aftab.test")
    day = (date.today() + timedelta(days=10)).isoformat()
    tag = "CAPTEST" + uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        sup = m.Supplier(tenant_id=tid, supplier_type="airline", display_name="ت " + tag, status="active")
        db.add(sup); db.flush()
        attrs = {"origin": "SYZ", "destination": "KIH", "departure_time": day + "T08:00:00+03:30", "airline": tag}
        mk = lambda title, amount: m.Offer(tenant_id=tid, supplier_id=sup.id, service_type="flight", title=title, amount=amount, available_units=5, status="active",  # noqa: E731
                                           attributes_json=_json.dumps(attrs), policy_json="{}", valid_until=datetime.now(timezone.utc) + timedelta(days=5))
        low, high = mk(tag + " low", 20_000_000), mk(tag + " high", 40_000_000)
        cap = PriceCap(tenant_id=tid, origin="SYZ", destination="KIH", valid_from=date.today(), valid_to=date.today() + timedelta(days=30),
                       cap_unit_irr=30_000_000, legal_reference="TEST-CAP", created_by_user_id=uid)
        db.add_all([low, high, cap]); db.commit()
        ids, cap_id, high_id = {low.id, high.id}, cap.id, high.id
    try:
        for email, staff in (("employee@aftab.test", False), ("backoffice@aftab.test", True)):
            r = client.post("/search/offers", json={"service_type": "flight", "query": tag}, headers=_h(client, email))
            assert r.status_code == 200, r.text
            mine = [o["title"] for o in r.json() if o["id"] in ids]
            assert mine == [tag + " low"]
            assert (r.headers.get("X-Hidden-Over-Cap") == "1") if staff else ("X-Hidden-Over-Cap" not in r.headers)
        v2 = client.post("/search/v2", json={"query": tag, "verticals": ["flight"]}, headers=_h(client, "employee@aftab.test"))
        assert v2.status_code == 200 and tag + " high" not in _json.dumps(v2.json(), ensure_ascii=False)
        # price-check keeps its 409 for the hidden offer when called by id
        pc = client.post(f"/offers/{high_id}/price-check", json={"units": 1, "command_id": "cap-" + uuid.uuid4().hex}, headers=_h(client, "employee@aftab.test"))
        assert pc.status_code == 409 and pc.json()["detail"]["code"] == "PRICE_CAP_EXCEEDED"
    finally:
        with SessionLocal() as db:                              # test fixture cleanup (shared test DB)
            db.execute(update(PriceCap).where(PriceCap.id == cap_id).values(status="disabled"))
            for o in db.query(m.Offer).filter(m.Offer.id.in_(ids)):
                o.status = "inactive"
            db.commit()
