"""Partner management, agency quote -> booking attribution, commission ledger, accounting views, supplier hotel self-service."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import operations as m
from app.main import AuditEvent, SessionLocal, User
from tests.test_catalog_hotel_content import VALID, _token
from tests.test_catalog_master_data import _load
from tests.test_platform_ops import _uid

NOW = datetime.now(timezone.utc)


def _offer(tid, amount=5000000, valid=timedelta(days=5), units=3, status="active"):
    with SessionLocal() as db:
        s = m.Supplier(tenant_id=tid, supplier_type="hotel", display_name="sup-" + uuid.uuid4().hex[:8]); db.add(s); db.flush()
        o = m.Offer(tenant_id=tid, supplier_id=s.id, service_type="hotel", title="اتاق دوتخته آزمون " + uuid.uuid4().hex[:8], amount=amount, currency="IRR", available_units=units, status=status, valid_until=NOW + valid); db.add(o); db.commit()
        return o.id, s.id


def test_partner_admin_quote_booking_commission_and_accounting(client):
    admin, agent, cust, fin = (_token(client, e) for e in ("tenant-admin@aftab.test", "agency@aftab.test", "employee@aftab.test", "finance@aftab.test"))
    agent_id, tid = _uid("agency@aftab.test"); cust_id, _ = _uid("employee@aftab.test"); other_id, otid = _uid("employee@faraz.test")
    name = "آژانس " + uuid.uuid4().hex[:6]
    # --- management: only tenant administration
    assert client.post("/admin/partners/agencies", json={"display_name": name, "commission_bps": 400}, headers=agent).status_code == 403
    assert client.get("/admin/partners", headers=cust).status_code == 403 and client.get("/admin/partners").status_code in (401, 403)
    agency = client.post("/admin/partners/agencies", json={"display_name": name, "commission_bps": 400}, headers=admin).json()["id"]
    assert client.post("/admin/partners/agencies", json={"display_name": name}, headers=admin).status_code == 409
    assert client.post("/admin/partners/agencies", json={"display_name": "x", "commission_bps": 9000}, headers=admin).status_code == 422
    with SessionLocal() as db:
        if db.scalar(select(m.LicensedEntity.id).where(m.LicensedEntity.tenant_id == tid, m.LicensedEntity.status == "active")) is None:
            db.add(m.LicensedEntity(tenant_id=tid, legal_name="نهاد آزمون", status="active")); db.commit()
    channel = client.post(f"/admin/partners/agencies/{agency}/sales-channel", json={"name": "ch-" + uuid.uuid4().hex[:8]}, headers=admin).json()["sales_channel_id"]
    assert client.post(f"/admin/partners/agencies/{agency}/sales-channel", json={"name": "second"}, headers=admin).status_code == 409
    assert client.post(f"/agency/{agency}/members", json={"user_id": agent_id}, headers=admin).status_code == 201
    listed = client.get("/admin/partners", headers=admin).json()
    mine = next(a for a in listed["agencies"] if a["id"] == agency)
    assert mine["sales_channel_id"] == channel and mine["members"][0]["user_id"] == agent_id and any(c["id"] == channel and c["type"] == "AGENCY" and c["agency_id"] == agency for c in listed["sales_channels"])
    # --- quote: only a real, valid, priced offer; price is the offer's own
    offer, _ = _offer(tid); expired, _ = _offer(tid, valid=timedelta(days=-1)); free, _ = _offer(tid, amount=0); foreign, _ = _offer(otid)
    with SessionLocal() as db:
        titles = {o.id: o.title for o in db.scalars(select(m.Offer).where(m.Offer.id.in_((offer, expired))))}
    find = lambda oid: [o["id"] for o in client.get(f"/agency/{agency}/offers", params={"q": titles[oid]}, headers=agent).json()["items"]]  # noqa: E731
    assert find(offer) == [offer] and find(expired) == []
    for bad in ({"offer_id": expired, "customer_user_id": cust_id}, {"offer_id": free, "customer_user_id": cust_id}, {"offer_id": foreign, "customer_user_id": cust_id}, {"offer_id": offer, "customer_user_id": other_id},
                {"offer_id": offer, "customer_user_id": agent_id}, {"offer_id": offer, "customer_user_id": cust_id, "amount": 1}):
        assert client.post(f"/agency/{agency}/quotes", json=bad, headers=agent).status_code == 422, bad
    assert client.post(f"/agency/{agency}/quotes", json={"offer_id": offer, "customer_user_id": cust_id}, headers=cust).status_code == 403
    quote = client.post(f"/agency/{agency}/quotes", json={"offer_id": offer, "customer_user_id": cust_id, "note": "پیشنهاد ویژه"}, headers=agent).json()
    assert (quote["amount"], quote["currency"], quote["status"]) == (5000000, "IRR", "sent")
    # --- the agency channel cannot be used without an accepted quote (attribution cannot be self-assigned)
    with SessionLocal() as db:
        from app.main import _resolve_transaction_provenance
        from fastapi import HTTPException
        user = db.get(User, cust_id)
        try: _resolve_transaction_provenance(db, user, None, channel); blocked = False
        except HTTPException as exc: blocked = exc.status_code == 403
    assert blocked
    seen = client.get("/me/agency-quotes", headers=cust).json()["items"][0]
    assert seen["id"] == quote["id"] and seen["booking"] is None and "customer_user_id" not in seen
    assert client.post(f"/me/agency-quotes/{quote['id']}/decision", json={"decision": "accept"}, headers=_token(client, "welfare@aftab.test")).status_code == 404   # not the addressee
    assert client.post(f"/me/agency-quotes/{quote['id']}/decision", json={"decision": "maybe"}, headers=cust).status_code == 422
    assert client.post(f"/me/agency-quotes/{quote['id']}/decision", json={"decision": "accept"}, headers=cust).json()["status"] == "accepted"
    assert client.post(f"/me/agency-quotes/{quote['id']}/decision", json={"decision": "decline"}, headers=cust).status_code == 409
    assert client.get("/me/agency-quotes", headers=cust).json()["items"][0]["booking"] == {"offer_id": offer, "sales_channel_id": channel}
    with SessionLocal() as db:
        from app.main import _resolve_transaction_provenance
        assert _resolve_transaction_provenance(db, db.get(User, cust_id), None, channel)[1] == channel                                                              # now allowed
        r = m.Reservation(tenant_id=tid, user_id=cust_id, service_type="hotel", status="confirmed", sales_channel_id=channel, confirmed_at=datetime.now(timezone.utc), price_snapshot_json=json.dumps({"total_amount": 5000000, "currency": "IRR"}))
        stranger = m.Reservation(tenant_id=tid, user_id=_uid("welfare@aftab.test")[0], service_type="hotel", status="confirmed", sales_channel_id=channel, confirmed_at=datetime.now(timezone.utc), price_snapshot_json=json.dumps({"total_amount": 1}))
        db.add_all([r, stranger]); db.flush()
        db.add(m.Invoice(tenant_id=tid, reservation_id=r.id, user_id=cust_id, invoice_number="T-" + uuid.uuid4().hex[:10], command_id="t-" + uuid.uuid4().hex, subtotal_amount=4600000, tax_amount=400000, total_amount=5000000))
        db.add(m.PaymentIntent(tenant_id=tid, reservation_id=r.id, user_id=cust_id, command_id="t-" + uuid.uuid4().hex, amount=5000000, status="captured", captured_amount=3000000)); db.commit(); rid, sid = r.id, stranger.id
    assert client.post(f"/agency/{agency}/quotes/{quote['id']}/link-booking", json={"reservation_id": sid}, headers=agent).status_code == 422       # another customer's booking
    assert client.post(f"/agency/{agency}/quotes/{quote['id']}/link-booking", json={"reservation_id": rid}, headers=agent).json()["status"] == "booked"
    # --- commission ledger: posted once by finance, strict flow
    assert client.post("/finance/commissions/accrue", json={"reservation_id": rid}, headers=agent).status_code == 403
    pending = client.get("/finance/commissions", headers=fin).json()["not_posted"]
    assert any(p["reservation_id"] == rid and p["amount"] == 200000 for p in pending)
    entry = client.post("/finance/commissions/accrue", json={"reservation_id": rid}, headers=fin).json()
    assert (entry["amount"], entry["commission_bps"], entry["status"]) == (200000, 400, "accrued")
    assert client.post("/finance/commissions/accrue", json={"reservation_id": rid}, headers=fin).status_code == 409
    assert client.post(f"/finance/commissions/{entry['id']}/settle", json={"external_reference": "TRX-1"}, headers=fin).status_code == 409             # must be approved first
    assert client.post(f"/finance/commissions/{entry['id']}/approve", headers=fin).json()["status"] == "approved"
    assert client.post(f"/finance/commissions/{entry['id']}/settle", json={"external_reference": "TRX-1"}, headers=fin).json()["status"] == "settled"
    assert client.post(f"/finance/commissions/{entry['id']}/reverse", json={"reason": "اشتباه"}, headers=fin).status_code == 409                       # settled is final
    ledger = client.get(f"/agency/{agency}/commission-ledger", headers=agent).json()
    assert ledger["totals"] == [{"status": "settled", "currency": "IRR", "amount": 200000}] and ledger["items"][0]["external_reference"] == "TRX-1"
    assert client.get(f"/agency/{agency}/commission-ledger", headers=cust).status_code == 403
    # --- accounting: stated formulas over stored rows
    acc = client.get("/finance/accounting", headers=fin).json()
    row = next(x for x in acc["receivables"]["items"] if x["reservation_id"] == rid)
    assert (row["invoiced"], row["captured"], row["outstanding"], row["tax"]) == (5000000, 3000000, 2000000, 400000) and acc["approved_chart_of_accounts"] is False
    assert any(c["agency_id"] == agency and c["status"] == "settled" and c["amount"] == 200000 for c in acc["commissions"]["items"]) and acc["tax_summary"]["items"]
    assert client.get("/finance/accounting", headers=agent).status_code == 403
    # --- credit link and member removal
    with SessionLocal() as db:
        acct = m.CreditAccount(tenant_id=tid, currency="IRR", limit_amount=90000000); db.add(acct); db.commit(); aid = acct.id
    assert client.get(f"/agency/{agency}/credit", headers=agent).json()["linked"] is False
    assert client.put(f"/admin/partners/agencies/{agency}/credit-account", json={"credit_account_id": aid}, headers=admin).status_code == 200
    credit = client.get(f"/agency/{agency}/credit", headers=agent).json()
    assert credit["linked"] is True and credit["limit_amount"] == 90000000 and isinstance(credit["balances"], dict)
    assert client.delete(f"/admin/partners/agencies/{agency}/members/{agent_id}", headers=admin).json() == {"removed": True}
    assert client.get(f"/agency/{agency}/quotes", headers=agent).status_code == 404
    with SessionLocal() as db:
        actions = {a.action for a in db.scalars(select(AuditEvent).where(AuditEvent.entity.in_(("agency", "agency_quote", "commission"))))}
    assert {"agency.created", "agency.sales_channel_created", "agency_quote.sent", "agency_quote.accepted", "agency_quote.booked", "commission.accrued", "commission.approved", "commission.settled", "agency.member_removed"} <= actions


def test_quote_expiry_price_change_and_cancel(client):
    admin, agent, cust = (_token(client, e) for e in ("tenant-admin@aftab.test", "agency@aftab.test", "employee@aftab.test"))
    agent_id, tid = _uid("agency@aftab.test"); cust_id, _ = _uid("employee@aftab.test")
    agency = client.post("/admin/partners/agencies", json={"display_name": "آژانس " + uuid.uuid4().hex[:6], "commission_bps": 100}, headers=admin).json()["id"]
    client.post(f"/agency/{agency}/members", json={"user_id": agent_id}, headers=admin)
    offer, _ = _offer(tid)
    assert client.post(f"/agency/{agency}/quotes", json={"offer_id": offer, "customer_user_id": cust_id}, headers=agent).status_code == 409      # no sales channel yet
    client.post(f"/admin/partners/agencies/{agency}/sales-channel", json={"name": "ch-" + uuid.uuid4().hex[:8]}, headers=admin)
    q1 = client.post(f"/agency/{agency}/quotes", json={"offer_id": offer, "customer_user_id": cust_id}, headers=agent).json()["id"]
    with SessionLocal() as db:
        db.get(m.Offer, offer).amount = 5500000; db.commit()
    assert client.post(f"/me/agency-quotes/{q1}/decision", json={"decision": "accept"}, headers=cust).status_code == 409                          # supplier price changed: never accepted at the old price
    assert next(q for q in client.get(f"/agency/{agency}/quotes", headers=agent).json()["items"] if q["id"] == q1)["status"] == "expired"
    q2 = client.post(f"/agency/{agency}/quotes", json={"offer_id": offer, "customer_user_id": cust_id}, headers=agent).json()
    assert q2["amount"] == 5500000
    with SessionLocal() as db:
        db.get(m.AgencyQuote, q2["id"]).valid_until = datetime.now(timezone.utc) - timedelta(minutes=1); db.commit()
    assert client.post(f"/me/agency-quotes/{q2['id']}/decision", json={"decision": "accept"}, headers=cust).status_code == 409
    q3 = client.post(f"/agency/{agency}/quotes", json={"offer_id": offer, "customer_user_id": cust_id}, headers=agent).json()["id"]
    assert client.post(f"/agency/{agency}/quotes/{q3}/cancel", headers=agent).json()["status"] == "cancelled"
    assert client.post(f"/agency/{agency}/quotes/{q3}/cancel", headers=agent).status_code == 409
    assert client.post(f"/me/agency-quotes/{q3}/decision", json={"decision": "accept"}, headers=cust).status_code == 409


def test_supplier_hotel_assignment_and_self_service_mapping(tmp_path, client):
    _load(tmp_path)
    admin, sup, padmin = _token(client, "tenant-admin@aftab.test"), _token(client, "supplier@aftab.test"), _token(client, "platform-admin@aftab.test")
    sup_id, tid = _uid("supplier@aftab.test")
    supplier = client.post("/admin/partners/suppliers", json={"display_name": "تأمین‌کننده " + uuid.uuid4().hex[:6], "supplier_type": "hotel"}, headers=admin).json()["id"]
    assert client.post("/admin/partners/suppliers", json={"display_name": "x", "supplier_type": "spaceship"}, headers=admin).status_code == 422
    assert client.post(f"/admin/partners/suppliers/{supplier}/members", json={"user_id": _uid("employee@aftab.test")[0]}, headers=admin).status_code == 422
    assert client.post(f"/admin/partners/suppliers/{supplier}/members", json={"user_id": sup_id}, headers=admin).status_code == 201
    assert client.post(f"/admin/partners/suppliers/{supplier}/hotels", json={"hotel_id": "nope"}, headers=admin).status_code == 422
    assert client.post(f"/admin/partners/suppliers/{supplier}/hotels", json={"hotel_id": "h1"}, headers=admin).status_code == 201
    assert client.post(f"/admin/partners/suppliers/{supplier}/hotels", json={"hotel_id": "h1"}, headers=sup).status_code == 403
    mine = client.get("/supplier/hotels", headers=sup).json()["items"]
    assert [h["hotel_id"] for h in mine if h["hotel_id"] in ("h1", "h2")] == ["h1"] and mine[0]["rate_available"] is False
    ref = "SUP-" + uuid.uuid4().hex[:8]
    assert client.post("/supplier/hotels/h2/provider-mappings", json={"provider": "grs", "provider_hotel_id": ref}, headers=sup).status_code == 404   # not assigned to me
    proposed = client.post("/supplier/hotels/h1/provider-mappings", json={"provider": "grs", "provider_hotel_id": ref}, headers=sup)
    assert proposed.status_code == 201 and proposed.json()["status"] == "unverified"
    assert client.post("/supplier/hotels/h1/provider-mappings", json={"provider": "grs", "provider_hotel_id": ref}, headers=sup).status_code == 409
    assert client.post(f"/admin/catalog/provider-mappings/{proposed.json()['id']}/verify", headers=sup).status_code == 403                             # a supplier cannot verify its own id
    detail = client.get("/admin/catalog/hotels/h1", headers=padmin).json()
    mapping = next(x for x in detail["provider_mappings"] if x["provider_hotel_id"] == ref)
    assert mapping["status"] == "unverified" and mapping["rooms"] == [] and mapping["rate_plans"] == []
    client.put("/admin/catalog/hotels/h1", json={**VALID, "city_id": "ir-shiraz"}, headers=padmin)
    room = client.get("/admin/catalog/hotels/h1", headers=padmin).json()["room_types"][0]["id"]
    client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rooms", json={"room_type_id": room, "provider_room_id": ref + "-R1"}, headers=padmin)
    client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rate-plans", json={"provider_rate_plan_id": ref + "-BAR", "board": "BB", "refundable": True}, headers=padmin)
    after = next(x for x in client.get("/admin/catalog/hotels/h1", headers=padmin).json()["provider_mappings"] if x["id"] == mapping["id"])
    assert after["rooms"][0]["provider_room_id"] == ref + "-R1" and after["rate_plans"][0] == {"id": after["rate_plans"][0]["id"], "provider_rate_plan_id": ref + "-BAR", "board": "BB", "refundable": True}
    assert client.delete(f"/admin/partners/suppliers/{supplier}/hotels/h1", headers=admin).json() == {"removed": True}
    assert "h1" not in [h["hotel_id"] for h in client.get("/supplier/hotels", headers=sup).json()["items"]]
    assert client.delete(f"/admin/partners/suppliers/{supplier}/members/{sup_id}", headers=admin).json() == {"removed": True}
