"""Panels Phase 2 — charter seat blocks: BAND_ALEF gate, CAO price cap, staff review/publish into the normal checkout,
domestic-charter flag (D8), allocations to agencies (seat quotas) consumed by the receiving agency's credit booking,
seller money view without the customer price, adapters that make no network call."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import charter_blocks as C
from app import operations as m
from app.charter_quotas import SeatQuota
from app.main import SessionLocal

from test_agency_b2b import _user, activate, fund, key, login, make_agency, price_check


def block_body(**over) -> dict:
    dep = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=15)
    body = {"airline_code": "QB", "airline_name": "قشم ایر", "flight_number": f"{uuid.uuid4().int % 9000 + 1000}", "aircraft": "Airbus A320",
            "origin": "IKA", "destination": "IST", "origin_city": "تهران", "destination_city": "استانبول", "route_scope": "international",
            "departure_at": dep.isoformat(), "arrival_at": (dep + timedelta(hours=3, minutes=30)).isoformat(), "seats_total": 10,
            "net_adult_irr": 39_800_000, "net_child_irr": 29_850_000, "net_infant_irr": 3_980_000, "release_at": (dep - timedelta(days=2)).isoformat(),
            "refund_tiers": [{"hours_before": 72, "penalty_bps": 2000}, {"hours_before": 3, "penalty_bps": 5000}], "submit": True}
    body.update(over)
    return body


@pytest.fixture()
def charter(client):
    owner, ops, fin1, fin2 = _user("agency_partner"), _user("backoffice_expert"), _user("finance_operator"), _user("finance_operator")
    a = make_agency(owner)
    w = {"agency_id": a, "owner_email": owner, "owner": login(client, owner), "ops": login(client, ops), "fin1": login(client, fin1), "fin2": login(client, fin2)}
    return w


def test_band_alef_required_and_block_lifecycle(client, charter, monkeypatch):
    a, owner, ops = charter["agency_id"], charter["owner"], charter["ops"]
    r = client.post(f"/agency/{a}/charter/blocks", json=block_body(), headers=owner)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "AGENCY_NOT_ACTIVE"
    activate(client, owner, ops, a, licence_type="BAND_BE")  # a tour licence does not allow flights
    r = client.post(f"/agency/{a}/charter/blocks", json=block_body(), headers=owner)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "LICENCE_REQUIRED"


def test_publish_allocate_and_sell_on_credit(client, charter, monkeypatch):
    monkeypatch.delenv("CHARTER_DOMESTIC_SALE", raising=False)
    a, owner, ops = charter["agency_id"], charter["owner"], charter["ops"]
    activate(client, owner, ops, a)
    assert client.post(f"/agency/{a}/charter/blocks", json=block_body(release_at=datetime.now(timezone.utc).isoformat()), headers=owner).status_code == 422
    assert client.post(f"/agency/{a}/charter/blocks", json=block_body(source="parto"), headers=owner).status_code == 422  # external source needs its reference
    b = client.post(f"/agency/{a}/charter/blocks", json=block_body(source="parto", external_ref="PRT-77812"), headers=owner)
    assert b.status_code == 201, b.text
    blk = b.json()
    assert blk["status"] == "submitted" and blk["tax_role"] == "PRINCIPAL" and blk["accountant_confirmed"] is False and blk["price_cap_status"] == "not_configured"
    # the charterer cannot publish; staff can, with a contract fee
    assert client.post(f"/staff/charter/blocks/{blk['id']}/decision", json={"decision": "approve"}, headers=owner).status_code == 403
    assert client.post(f"/staff/charter/blocks/{blk['id']}/decision", json={"decision": "reject"}, headers=ops).status_code == 422  # reason required
    pub = client.post(f"/staff/charter/blocks/{blk['id']}/decision", json={"decision": "approve", "platform_fee_bps": 300}, headers=ops)
    assert pub.status_code == 200, pub.text
    pub = pub.json()
    assert pub["status"] == "published" and pub["seats"]["public_available"] == 10
    with SessionLocal() as db:
        offer = db.get(m.Offer, db.get(C.CharterBlock, blk["id"]).offer_id)
        assert offer.status == "active" and offer.service_type == "flight" and offer.amount == 39_800_000
        agency_name = db.get(m.Agency, a).display_name
        assert agency_name not in offer.title and agency_name not in offer.attributes_json  # R-PUB-1: no agency identity on the public offer
        supplier = db.get(m.Supplier, offer.supplier_id)
        assert agency_name not in supplier.display_name
    # allocate 4 seats to a partner agency
    buyer_owner = _user("agency_partner")
    buyer = make_agency(buyer_owner)
    bh = login(client, buyer_owner)
    assert client.post(f"/agency/{a}/charter/blocks/{blk['id']}/allocations", json={"agency_id": buyer, "seats": 4}, headers=owner).status_code == 422  # not active yet
    activate(client, bh, ops, buyer, licence_type="BAND_BE")
    assert client.post(f"/agency/{a}/charter/blocks/{blk['id']}/allocations", json={"agency_id": buyer, "seats": 11}, headers=owner).status_code == 409
    al = client.post(f"/agency/{a}/charter/blocks/{blk['id']}/allocations", json={"agency_id": buyer, "seats": 4}, headers=owner)
    assert al.status_code == 201, al.text
    detail = client.get(f"/agency/{a}/charter/blocks/{blk['id']}", headers=owner).json()
    assert detail["seats"]["allocated_held"] == 4 and detail["seats"]["public_available"] == 6 and detail["allocations"][0]["agency_id"] == buyer
    got = client.get(f"/agency/{buyer}/charter/allocations-received", headers=bh).json()["items"]
    assert got[0]["seats"] == 4 and got[0]["offer_id"]
    # the partner agency books 2 seats on its credit: the seats come out of its allocation, not out of public sale
    fund(client, charter["fin1"], charter["fin2"], buyer, limit=200_000_000)
    pc = price_check(client, bh, got[0]["offer_id"], units=2)
    r = client.post(f"/agency/{buyer}/credit-bookings", headers=bh, json={"price_check_id": pc["id"], "command_id": f"cb-{uuid.uuid4().hex}"})
    assert r.status_code == 201, r.text
    detail = client.get(f"/agency/{a}/charter/blocks/{blk['id']}", headers=owner).json()
    assert detail["seats"]["sold"] == 2 and detail["seats"]["allocated_held"] == 2 and detail["seats"]["public_available"] == 6
    # seller view: own rate, platform fee and its VAT, net payable — never the customer price
    money = detail["money"]
    assert money["view"] == "agency_seller" and money["gross_at_agency_rate_irr"] == 79_600_000
    assert money["platform_fee_irr"] == 2_388_000 and money["vat_on_fee_irr"] == 238_800 and money["net_payable_irr"] == 79_600_000 - 2_388_000 - 238_800
    assert "customer_price" not in str(detail)
    # the charterer releases the remaining allocation back to public sale
    rel = client.post(f"/agency/{a}/charter/blocks/{blk['id']}/allocations/{al.json()['id']}/release", json={}, headers=owner).json()
    assert rel["released_now"] == 2 and rel["status"] == "released"
    assert client.get(f"/agency/{a}/charter/blocks/{blk['id']}", headers=owner).json()["seats"]["public_available"] == 8
    audit = client.get(f"/staff/charter/blocks/{blk['id']}/audit", headers=ops).json()["items"]
    assert [x["action"] for x in audit][:3] == ["charter.block.created", "charter.block.published", "charter.block.allocated"]
    # another agency never sees this block
    assert client.get(f"/agency/{a}/charter/blocks/{blk['id']}", headers=bh).status_code == 404
    assert client.get(f"/agency/{buyer}/charter/blocks/{blk['id']}", headers=bh).status_code == 404


def test_domestic_charter_is_saved_but_not_published_while_flag_off(client, charter, monkeypatch):
    monkeypatch.delenv("CHARTER_DOMESTIC_SALE", raising=False)
    a, owner, ops = charter["agency_id"], charter["owner"], charter["ops"]
    activate(client, owner, ops, a)
    b = client.post(f"/agency/{a}/charter/blocks", json=block_body(route_scope="domestic", origin="THR", destination="KIH", destination_city="کیش"), headers=owner).json()
    assert b["status"] == "submitted" and b["domestic_sale_disabled"] is True
    r = client.post(f"/staff/charter/blocks/{b['id']}/decision", json={"decision": "approve"}, headers=ops)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "CHARTER_DOMESTIC_DISABLED"
    monkeypatch.setenv("CHARTER_DOMESTIC_SALE", "1")
    assert client.post(f"/staff/charter/blocks/{b['id']}/decision", json={"decision": "approve"}, headers=ops).json()["status"] == "published"


def test_block_above_cao_cap_is_refused(client, charter):
    a, owner, ops = charter["agency_id"], charter["owner"], charter["ops"]
    activate(client, owner, ops, a)
    admin = login(client, _user("tenant_admin"))
    body = block_body(origin="MHD", destination="BGW")
    day = datetime.fromisoformat(body["departure_at"]).date()
    client.post("/staff/charter/price-caps", headers=admin, json={"origin": "MHD", "destination": "BGW", "valid_from": (day - timedelta(days=1)).isoformat(),
                                                                   "valid_to": (day + timedelta(days=1)).isoformat(), "cap_unit_irr": 35_000_000, "legal_reference": "اطلاعیهٔ آزمون"})
    r = client.post(f"/agency/{a}/charter/blocks", json=body, headers=owner)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PRICE_CAP_EXCEEDED" and r.json()["detail"]["price_cap_unit_irr"] == 35_000_000
    ok = client.post(f"/agency/{a}/charter/blocks", json={**body, "net_adult_irr": 35_000_000}, headers=owner)
    assert ok.status_code == 201 and ok.json()["price_cap_unit_irr"] == 35_000_000


def test_sources_are_stubs_without_network():
    for key_, src in C.SOURCES.items():
        assert src.status() == "not_contracted"
        with pytest.raises(C.NotContracted):
            src.fetch_blocks("x")


def test_staff_list_needs_staff(client, charter):
    assert client.get("/staff/charter/blocks", headers=charter["owner"]).status_code == 403
    assert client.get("/staff/charter/blocks", headers=charter["ops"]).status_code == 200
    assert client.get("/charter/sources", headers=charter["owner"]).json()["domestic_charter_sale"] in (True, False)
