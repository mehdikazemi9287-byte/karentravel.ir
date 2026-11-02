"""Applied markup is stored per booking/service and posted as revenue (the CheckLine 'commission stayed zero' gap)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.commerce import TreasuryEntry
from app.main import SessionLocal
from app.markup_revenue import AppliedMarkup, markup_from_snapshot
from test_checkout_reviews_zarinpal import hotel_terms


def _login(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_markup_from_snapshot():
    assert markup_from_snapshot(None, 2) is None
    assert markup_from_snapshot({"rule_id": "r"}, 2) is None
    up = markup_from_snapshot({"rule_id": "r", "net_unit": 1_000_000, "adjustment": 150_000}, 2)
    assert up == {"rule_id": "r", "net_unit": 1_000_000, "sell_unit": 1_150_000, "units": 2, "net_total": 2_000_000, "sell_total": 2_300_000,
                  "markup_total": 300_000, "effect": "markup"}
    down = markup_from_snapshot({"rule_id": "r", "net_unit": 1_000_000, "adjustment": -50_000}, 1)
    assert down["effect"] == "discount" and down["markup_total"] == -50_000


def _offer(client, suffix, amount):
    supplier = _login(client, "supplier@aftab.test")
    row = client.post("/supplier/onboarding", headers={**supplier, "Idempotency-Key": f"mk-supplier-{suffix}"}, json={"supplier_type": "hotel", "display_name": f"Markup supplier {suffix}"}).json()
    policy = {"verified": True, "source": "contract:test", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 0}}
    offer = client.post("/supplier/offers", headers=supplier, json={"supplier_id": row["id"], "service_type": "hotel", "title": "هتل سود فروش", "amount": amount, "available_units": 3,
                                                                     "valid_minutes": 60, "policy": policy, "attributes": hotel_terms()[0], "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"})
    assert offer.status_code in (200, 201), offer.text
    return row["id"], offer.json()


def test_booking_with_markup_rule_posts_revenue_per_service(client):
    suffix = uuid.uuid4().hex[:10]
    supplier_id, offer = _offer(client, suffix, 2_000_000)
    admin = _login(client, "platform-admin@aftab.test")
    rule = client.post("/commerce/markup-rules", headers=admin, json={"title": f"سود هتل {suffix}", "service_type": "hotel", "supplier_id": supplier_id,
                                                                   "calc": "fixed", "adult": 150_000, "round_to": 0})
    assert rule.status_code == 201, rule.text
    rule_id = rule.json()["id"]
    try:
        emp = _login(client, "employee@aftab.test")
        checked = client.post(f"/offers/{offer['id']}/price-check", headers=emp, json={"hotel_stay": hotel_terms()[1], "units": 1, "command_id": f"mk-price-{suffix}"})
        assert checked.status_code == 201, checked.text
        booking = client.post("/orchestration/bookings", headers=emp, json={"price_check_id": checked.json()["id"], "command_id": f"mk-booking-{suffix}"})
        assert booking.status_code in (200, 201), booking.text
        res_id = booking.json().get("id") or booking.json().get("reservation_id")
        with SessionLocal() as db:
            row = db.scalar(select(AppliedMarkup).where(AppliedMarkup.reservation_id == res_id))
            assert row is not None and row.rule_id == rule_id and row.service_type == "hotel" and row.effect == "markup"
            assert row.markup_total == 150_000 and row.sell_unit - row.net_unit == 150_000 and row.sell_total == checked.json()["amount"]
            entry = db.scalar(select(TreasuryEntry).where(TreasuryEntry.command_id == f"markup:{res_id}"))
            assert entry is not None and entry.account_type == "revenue" and entry.credit == 150_000 and entry.debit == 0
            assert row.treasury_entry_id == entry.id
        report = client.get("/commerce/markup-revenue", params={"service_type": "hotel"}, headers=_login(client, "finance@aftab.test"))
        assert report.status_code == 200, report.text
        hotel = next(g for g in report.json()["by_service"] if g["service_type"] == "hotel" and g["currency"] == row.currency)
        assert hotel["markup"] >= 150_000 and any(i["reservation_id"] == res_id and i["posted"] for i in report.json()["items"])
        assert client.get("/commerce/markup-revenue", headers=emp).status_code == 403
        assert client.get("/commerce/markup-revenue", params={"date_from": "2026-02-01", "date_to": "2026-01-01"}, headers=admin).status_code == 422
        # another tenant never sees it
        faraz = _login(client, "employee@faraz.test")
        assert client.get("/commerce/markup-revenue", headers=faraz).status_code == 403
    finally:
        r = client.get("/commerce/markup-rules", headers=admin).json()["items"]
        mine = next(x for x in r if x["id"] == rule_id)
        client.put(f"/commerce/markup-rules/{rule_id}", json={**{k: v for k, v in mine.items() if k != "id"}, "status": "disabled"}, headers=admin)
