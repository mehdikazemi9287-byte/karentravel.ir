"""Rate port contract (no fabricated price, ever) and the non-commercial tour catalog."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app import hotel_rates
from app.catalog import CatalogHotelProviderMapping, CatalogTour, CatalogTourDeparture, TOUR_TABLES
from app.hotel_rates import RateOffer, RateQuery, RateSourceError, validate_offers
from app.main import SessionLocal
from scripts.catalog import import_checkline_tours
from scripts.catalog.import_checkline_tours import jalali_to_gregorian
from tests.test_catalog_hotel_content import _token
from tests.test_catalog_master_data import _load

SOON = datetime.now(timezone.utc) + timedelta(minutes=20)
DATES = {"checkin": "2027-01-10", "checkout": "2027-01-12"}


class ContractHarnessSource:
    """Test-only stand-in used to exercise the port's rules. It is never registered outside a test."""
    key = "harness"

    def __init__(self, offers=None, error=False): self.offers, self.error, self.queries = offers or [], error, []

    def quote(self, query: RateQuery):
        self.queries.append(query)
        if self.error: raise RateSourceError("timeout")
        return self.offers


@pytest.fixture()
def harness():
    hotel_rates.RATE_SOURCES.clear()
    yield hotel_rates.RATE_SOURCES
    hotel_rates.RATE_SOURCES.clear()
    with SessionLocal() as db:
        db.execute(delete(CatalogHotelProviderMapping)); db.commit()


def test_offer_contract_drops_anything_that_is_not_a_real_quote():
    q = RateQuery("P1", date(2027, 1, 10), date(2027, 1, 12), 2)
    good = RateOffer("P1", "ref-1", "Double", 1200, "USD", True, SOON)
    bad = [RateOffer("P1", "r", "Double", 0, "USD", True, SOON), RateOffer("P1", "r", "Double", -5, "USD", True, SOON), RateOffer("P2", "r", "Double", 10, "USD", True, SOON),
           RateOffer("P1", "r", "Double", 10, "XXX", True, SOON), RateOffer("P1", "", "Double", 10, "USD", True, SOON), RateOffer("P1", "r", "Double", 10, "USD", True, SOON - timedelta(hours=1)),
           RateOffer("P1", "r", "Double", 10, "USD", True, datetime(2030, 1, 1)), RateOffer("P1", "r", "Double", True, "USD", True, SOON), RateOffer("P1", "r", "Double", 10.5, "USD", True, SOON)]
    assert validate_offers(q, [good, *bad]) == [good]


def test_rates_need_published_hotel_verified_mapping_and_registered_source(tmp_path, client, harness):
    _load(tmp_path)
    admin = _token(client, "platform-admin@aftab.test")
    slug, base = "test-hotel-one", "/catalog/hotels/test-hotel-one"
    assert client.get(f"{base}/rates", params=DATES).json() == {"hotel_id": "h1", **DATES, "status": "no_rate_source", "offers": [], "price": None}
    assert client.get(f"{base}/rates", params={"checkin": "2027-01-12", "checkout": "2027-01-10"}).status_code == 422
    assert client.get("/catalog/hotels/missing/rates", params=DATES).status_code == 404
    mapping = client.post("/admin/catalog/hotels/h1/provider-mappings", json={"provider": "harness", "provider_hotel_id": "P1"}, headers=admin).json()["provider_mappings"][0]
    source = ContractHarnessSource([RateOffer("P1", "ref-9", "Double", 900, "USD", None, SOON), RateOffer("P1", "ref-0", "Double", 0, "USD", None, SOON)])
    harness["harness"] = source
    assert client.get(f"{base}/rates", params=DATES).json()["status"] == "no_rate_source" and source.queries == []  # unverified mapping: the supplier is not even asked
    assert client.get(base).json()["state"]["rate_available"] is False
    assert client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/verify", headers=_token(client, "employee@aftab.test")).status_code == 403
    assert client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/verify", headers=admin).json()["provider_mappings"][0]["status"] == "verified"
    quoted = client.get(f"{base}/rates", params={**DATES, "adults": 2}).json()
    assert quoted["status"] == "ok" and quoted["price"] is None and [o["total_amount"] for o in quoted["offers"]] == [900]  # the zero-priced offer never reaches a customer
    assert source.queries[0] == RateQuery("P1", date(2027, 1, 10), date(2027, 1, 12), 2, 0)
    state = client.get(base).json()["state"]
    assert state["rate_available"] is True and state["bookable"] is False and client.get(base).json()["price"] is None
    assert client.get("/catalog/hotels", params={"q": "هتل آزمون یک"}).json()["items"][0]["state"]["rate_available"] is True
    assert client.get("/catalog/hotels/test-hostel-two").json()["state"]["rate_available"] is False
    harness["harness"] = ContractHarnessSource(error=True)
    assert client.get(f"{base}/rates", params=DATES).json() == {"hotel_id": "h1", **DATES, "status": "rate_source_unavailable", "offers": [], "price": None}
    harness["harness"] = ContractHarnessSource([])
    assert client.get(f"{base}/rates", params=DATES).json()["status"] == "no_availability"
    harness.clear()
    assert client.get(base).json()["state"]["rate_available"] is False and client.get(f"{base}/rates", params=DATES).json()["status"] == "no_rate_source"


def test_runtime_has_no_rate_source_registered():
    import importlib
    assert importlib.reload(hotel_rates).RATE_SOURCES == {}


def test_jalali_dates_convert_only_when_valid():
    assert jalali_to_gregorian("1402-08-04") == date(2023, 10, 26) and jalali_to_gregorian("۱۴۰۳-۰۱-۰۱") == date(2024, 3, 20) and jalali_to_gregorian("1403-12-30") == date(2025, 3, 20)
    assert jalali_to_gregorian("1405-07-14") == date(2026, 10, 6)
    assert all(jalali_to_gregorian(x) is None for x in ("1402-12-30", "1402-13-01", "1402-07-31", "2023-10-26", "", None, "آبان ۱۴۰۲"))


def test_tour_catalog_is_reference_only(tmp_path, client):
    for table in TOUR_TABLES:
        assert "tenant_id" not in table.c and not [c.name for c in table.c if any(w in c.name for w in ("price", "amount", "capacity", "remaining", "inventory", "supplier", "currency"))]
    with SessionLocal() as db:
        db.execute(delete(CatalogTourDeparture)); db.execute(delete(CatalogTour)); db.commit()
    d = tmp_path / "staged"; d.mkdir()
    (d / "tours.jsonl").write_text("\n".join(json.dumps({"raw": t}, ensure_ascii=False) for t in [{"tour_id": 1, "title": "تور ارمنستان", "disabled": "1", "soldout": "1"}, {"tour_id": 2, "title": "تور شیراز", "disabled": "0", "soldout": "0"}]), encoding="utf-8")
    (d / "departures.jsonl").write_text("\n".join(json.dumps({"raw": r}) for r in [{"tour_id": 1, "row_index": 1, "departure_raw": "1402-08-04", "end_raw": "1402-08-11"},
                                                                                     {"tour_id": 1, "row_index": 2, "departure_raw": "1402-12-30", "end_raw": "1403-01-05"},
                                                                                     {"tour_id": 9, "row_index": 1, "departure_raw": "1402-08-04", "end_raw": "1402-08-11"}]), encoding="utf-8")
    first = import_checkline_tours.main(str(d), False)
    assert (first["tours_inserted"], first["departures_inserted"], first["departures_invalid_date"], first["departures_without_tour"]) == (2, 2, 1, 1)
    second = import_checkline_tours.main(str(d), False)
    assert (second["tours_inserted"], second["tours_unchanged"], second["departures_inserted"], second["departures_unchanged"]) == (0, 2, 0, 2)
    admin = _token(client, "backoffice@aftab.test")
    assert client.get("/admin/catalog/tours").status_code in (401, 403) and client.get("/admin/catalog/tours", headers=_token(client, "supplier@aftab.test")).status_code == 403
    listed = client.get("/admin/catalog/tours", headers=admin).json()
    assert listed["total"] == 2 and all(i["status"] == "draft" and i["sellable"] is False and i["price"] is None for i in listed["items"])
    detail = client.get("/admin/catalog/tours/cl-tour-1", headers=admin).json()
    assert detail["source_soldout"] is True and detail["latest_departure"] == "2023-10-26"
    assert detail["departures"] == [{"starts_jalali": "1402-08-04", "ends_jalali": "1402-08-11", "starts_on": "2023-10-26", "ends_on": "2023-11-02"},
                                    {"starts_jalali": "1402-12-30", "ends_jalali": "1403-01-05", "starts_on": None, "ends_on": None}]
    before = client.get("/public/tour-products")
    assert before.status_code in (200, 503) and (before.status_code == 503 or all("cl-tour" not in json.dumps(i) for i in before.json()))  # the reference catalog never leaks into sellable tours
