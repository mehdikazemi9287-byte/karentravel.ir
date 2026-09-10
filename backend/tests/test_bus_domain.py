"""Bus: normalized domain contract, fail-closed provider, no fabricated
inventory, and end-to-end through the generic Offer/PriceCheck/Reservation flow."""
import uuid
from datetime import datetime, timedelta, timezone

from app.main import SessionLocal
from app import operations as om
from app.bus_domain import (
    BUS_SERVICE_TYPE, BusProviderPort, BusSearchQuery, DisabledBusProvider,
    NormalizedBusOffer, build_search_query, normalize_offer_row,
)


def login(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _bus_offer(tenant_id, *, origin="تهران", dest="اصفهان", price=850_000, units=30):
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, tenant_id)
        s = om.Supplier(tenant_id=tenant_id, supplier_type="bus", display_name="اتوبوسران تست", status="active")
        db.add(s); db.flush()
        o = om.Offer(tenant_id=tenant_id, supplier_id=s.id, service_type="bus", title="VIP تهران-اصفهان",
                     amount=price, currency="IRR", available_units=units, status="active",
                     attributes_json='{"operator": "شرکت نمونه", "origin_terminal": "%s", "destination_terminal": "%s",'
                     ' "bus_type": "VIP 2+1", "seat_class": "vip", "amenities": ["wifi", "snack"], "taxes": 0, "fees": 0, "discounts": 0}' % (origin, dest),
                     policy_json='{"refundable": true}',
                     valid_until=datetime.now(timezone.utc) + timedelta(hours=6))
        db.add(o); db.commit()
        return o.id


# --- contract shape ---

def test_disabled_provider_satisfies_port_and_fails_closed():
    p = DisabledBusProvider()
    assert isinstance(p, BusProviderPort)              # structural check
    assert p.search(BusSearchQuery("a", "b", "2030-01-01")) == ()
    assert p.recheck("x") is None
    for method in (p.reserve("o", 1, {}), p.confirm("r", {}), p.cancel("r", {})):
        assert method["ok"] is False and "not_configured" in method["reason"]


class _FixtureBusProvider:
    """Test-only reference implementation of BusProviderPort backed by a static
    fixture list -- proves the contract is implementable without a live provider.
    Never registered in production."""
    key = "bus"
    mode = "fixture"
    _FIXTURES = [
        NormalizedBusOffer(offer_ref="fx-1", operator="فیکسچر لاین", origin_terminal="تهران",
                           destination_terminal="اصفهان", depart_at="2030-06-01T08:00:00+03:30",
                           arrive_at="2030-06-01T13:30:00+03:30", bus_type="VIP 2+1", seat_class="vip",
                           seats_available=12, base_price=900_000, currency="IRR",
                           amenities=("wifi",), refundable=True, source="fixture"),
    ]

    def health(self): return {"key": self.key, "mode": self.mode, "status": "fixture"}
    def search(self, query): return [o for o in self._FIXTURES
                                     if query.origin in o.origin_terminal and query.destination in o.destination_terminal]
    def recheck(self, offer_ref): return next((o for o in self._FIXTURES if o.offer_ref == offer_ref), None)
    def reserve(self, offer_ref, passengers, context): return {"ok": True, "reservation_ref": "fx-res-1", "source": "fixture"}
    def confirm(self, reservation_ref, context): return {"ok": True, "source": "fixture"}
    def cancel(self, reservation_ref, context): return {"ok": True, "source": "fixture"}


def test_fixture_provider_via_port():
    p: BusProviderPort = _FixtureBusProvider()
    assert isinstance(p, BusProviderPort)
    got = p.search(BusSearchQuery("تهران", "اصفهان", "2030-06-01"))
    assert len(got) == 1 and got[0].base_price == 900_000
    assert p.reserve("fx-1", 2, {})["ok"] is True


def test_normalize_offer_row_from_attributes():
    oid = _bus_offer(1)
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, 1)
        n = normalize_offer_row(db.get(om.Offer, oid))
    assert n.operator == "شرکت نمونه" and n.seat_class == "vip" and n.bus_type == "VIP 2+1"
    assert n.seats_available == 30 and n.base_price == 850_000 and n.refundable is True
    assert list(n.amenities) == ["wifi", "snack"] and n.source == "internal_supplier"


def test_build_search_query_clamps():
    q = build_search_query({"origin": " تهران ", "destination": "شیراز", "depart_date": "2030-01-01", "passengers": 99, "seat_class": "bogus"})
    assert q.origin == "تهران" and q.passengers == 20 and q.seat_class is None


# --- API ---

def test_bus_provider_status_honest(client):
    me = login(client, "employee@aftab.test")
    r = client.get("/bus/provider-status", headers=me)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_connected" and body["external_blocked"] is True
    assert body["domain_contract"] == "app.bus_domain.BusProviderPort"


def test_bus_search_internal_only_no_fabrication(client):
    me = login(client, "employee@aftab.test")
    _bus_offer(1, origin="تهران", dest="اصفهان", price=850_000)
    r = client.post("/bus/search", headers=me, json={"origin": "تهران", "destination": "اصفهان", "depart_date": "2030-06-01", "passengers": 2})
    assert r.status_code == 200
    body = r.json()
    assert len(body["internal_supplier_offers"]) >= 1
    assert body["external_provider"]["offers"] == []          # never fabricated
    assert body["external_provider"]["status"] == "not_connected"
    assert body["internal_supplier_offers"][0]["seat_class"] == "vip"


def test_bus_search_route_filter(client):
    me = login(client, "employee@aftab.test")
    _bus_offer(1, origin="مشهد", dest="یزد")
    r = client.post("/bus/search", headers=me, json={"origin": "تهران", "destination": "اصفهان", "depart_date": "2030-06-01"})
    assert all("مشهد" not in o["origin_terminal"] for o in r.json()["internal_supplier_offers"])


def test_bus_books_through_generic_flow(client):
    me = login(client, "employee@aftab.test")
    oid = _bus_offer(1, price=850_000, units=30)
    pc = client.post(f"/offers/{oid}/price-check", headers=me, json={"units": 2, "command_id": f"bpc-{uuid.uuid4().hex[:12]}"})
    assert pc.status_code == 201, pc.text
    bk = client.post("/orchestration/bookings", headers=me,
                     json={"price_check_id": pc.json()["id"], "command_id": f"bbk-{uuid.uuid4().hex[:12]}"})
    assert bk.status_code == 201, bk.text
    with SessionLocal() as db:
        res = db.get(om.Reservation, bk.json()["id"])
        assert res.service_type == "bus" and res.status == "reserved"
        assert db.get(om.Offer, oid).available_units == 28


def test_bus_in_unified_search_vertical(client):
    me = login(client, "employee@aftab.test")
    _bus_offer(1, origin="تهران", dest="اصفهان")
    r = client.post("/search/v2", headers=me, json={"verticals": ["bus"], "destination": "اصفهان", "page": 1, "page_size": 10})
    assert r.status_code == 200      # was 422 before bus joined the taxonomy


def test_bus_tenant_isolation(client):
    _bus_offer(1)
    faraz = login(client, "employee@faraz.test")
    assert client.post("/bus/search", headers=faraz,
                       json={"origin": "تهران", "destination": "اصفهان", "depart_date": "2030-06-01"}
                       ).json()["internal_supplier_offers"] == []
