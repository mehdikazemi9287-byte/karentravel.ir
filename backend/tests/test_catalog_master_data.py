"""Master catalog: reference data only, public read API, no commercial fields."""
import gzip
import json

from app.catalog import CATALOG_TABLES, normalize_text
from app.main import SessionLocal
from scripts.catalog import import_catalog

COMMERCIAL = ("price", "amount", "rate", "inventory", "availab", "capacity", "discount", "review", "rating", "seat", "room")
PLACES = [
    {"id": "ir", "kind": "country", "country_code": "IR", "name_fa": "ایران", "name_en": "Iran", "search_text": "ایران iran"},
    {"id": "ir-07", "kind": "region", "parent_id": "ir", "country_code": "IR", "name_fa": "استان فارس", "name_en": "Fars Province", "search_text": "استان فارس fars province"},
    {"id": "ir-shiraz", "kind": "city", "parent_id": "ir-07", "country_code": "IR", "name_fa": "شیراز", "name_en": "Shiraz", "hotel_count": 2, "search_text": "شیراز shiraz"},
    {"id": "tr", "kind": "country", "country_code": "TR", "name_fa": "ترکیه", "name_en": "Turkey", "search_text": "ترکیه turkey"},
]
HOTELS = [
    {"id": "h1", "slug": "test-hotel-one", "country_code": "IR", "region_id": "ir-07", "city_id": "ir-shiraz", "name_fa": "هتل آزمون یک", "name_en": "Test Hotel One", "hotel_type": "hotel", "stars": 5,
     "latitude": 29.6, "longitude": 52.5, "amenities_json": '["wifi", "pool"]', "quality": 9, "search_text": normalize_text("هتل آزمون یک Test Hotel One شیراز Shiraz ایران"), "source": "test", "source_ref": "node/1"},
    {"id": "h2", "slug": "test-hostel-two", "country_code": "IR", "region_id": "ir-07", "city_id": "ir-shiraz", "name_fa": "هاستل آزمون دو", "hotel_type": "hostel", "stars": None,
     "latitude": 29.61, "longitude": 52.51, "amenities_json": "[]", "quality": 1, "search_text": normalize_text("هاستل آزمون دو شیراز"), "source": "test", "source_ref": "node/2"},
    {"id": "h3", "slug": "test-otel-three", "country_code": "TR", "name_en": "Test Otel Three", "hotel_type": "hotel", "stars": 4, "latitude": 41.0, "longitude": 28.9, "amenities_json": '["wifi"]',
     "quality": 5, "search_text": "test otel three", "source": "test", "source_ref": "node/3"},
]
AIRPORTS = [{"id": "SYZ", "icao_code": "OISS", "name_fa": "فرودگاه شیراز", "name_en": "Shiraz International Airport", "city_id": "ir-shiraz", "country_code": "IR", "latitude": 29.5, "longitude": 52.6,
             "timezone": "Asia/Tehran", "scope": "international", "search_text": "فرودگاه شیراز shiraz syz", "source": "test"}]
AIRLINES = [{"id": "Q1", "iata_code": "W5", "icao_code": "IRM", "name_fa": "هواپیمایی ماهان", "name_en": "Mahan Air", "country_code": "IR", "search_text": "هواپیمایی ماهان mahan air w5", "source": "test"}]
VENUES = [{"id": "v1", "kind": "restaurant", "name_fa": "رستوران آزمون", "city_id": "ir-shiraz", "region_id": "ir-07", "latitude": 29.6, "longitude": 52.5, "search_text": "رستوران ازمون شیراز", "source": "test"}]


def _load(tmp_path):
    data = {"places": PLACES, "hotels": HOTELS, "airlines": AIRLINES, "airports": AIRPORTS, "rail_operators": [], "rail_stations": [], "venues": VENUES}
    for name, rows in data.items():
        with gzip.open(tmp_path / f"{name}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False)
    return import_catalog.main(str(tmp_path), False)


def test_catalog_tables_are_global_and_carry_no_commercial_columns():
    for table in CATALOG_TABLES:
        assert "tenant_id" not in table.c
        assert not [c.name for c in table.c if any(word in c.name for word in COMMERCIAL)], table.name


def test_import_is_idempotent_and_removes_stale_rows(tmp_path, client):
    first = _load(tmp_path)
    assert first["hotels"]["inserted"] + first["hotels"]["updated"] == 3
    second = _load(tmp_path)
    assert second["hotels"] == {"inserted": 0, "updated": 3, "removed": 0}
    with SessionLocal() as db:
        from app.catalog import CatalogHotel
        assert db.query(CatalogHotel).count() == 3


def test_hotel_listing_filters_facets_detail_and_price_is_never_fabricated(tmp_path, client):
    _load(tmp_path)
    body = client.get("/catalog/hotels").json()
    assert body["total"] == 3 and body["items"][0]["slug"] == "test-hotel-one"
    assert all(item["price"] is None and item["price_status"] == "inquiry" for item in body["items"])
    assert client.get("/catalog/hotels", params={"country": "IR", "stars": 5}).json()["total"] == 1
    assert client.get("/catalog/hotels", params={"city": "ir-shiraz", "hotel_type": "hostel,chalet"}).json()["items"][0]["slug"] == "test-hostel-two"
    assert client.get("/catalog/hotels", params={"amenity": "wifi,pool"}).json()["total"] == 1
    assert client.get("/catalog/hotels", params={"q": "هتل شيراز"}).json()["total"] == 2  # Arabic ي folds to Persian ی; the word «هتل» is ignored
    facets = client.get("/catalog/hotels/facets", params={"country": "IR"}).json()
    assert {c["code"] for c in facets["countries"]} == {"IR", "TR"} and facets["cities"][0] == {"id": "ir-shiraz", "name": "شیراز", "count": 2}
    assert facets["stars"] == [{"value": 5, "count": 1}]
    detail = client.get("/catalog/hotels/test-hotel-one").json()
    assert detail["name_en"] == "Test Hotel One" and detail["price"] is None and detail["nearby_airports"][0]["iata"] == "SYZ"
    assert detail["provenance"]["source"] == "test"
    assert client.get("/catalog/hotels/missing").status_code == 404


def test_reference_lists_places_and_suggest(tmp_path, client):
    _load(tmp_path)
    assert client.get("/catalog/airlines", params={"q": "ماهان"}).json()["items"][0]["iata"] == "W5"
    assert client.get("/catalog/airports", params={"country": "IR"}).json()["items"][0]["icao"] == "OISS"
    venues = client.get("/catalog/venues", params={"kind": "restaurant,cafe", "city": "ir-shiraz"}).json()
    assert venues["total"] == 1 and venues["items"][0]["price"] is None
    place = client.get("/catalog/places/ir-shiraz").json()
    assert place["hotels"] == 2 and place["airports"][0]["iata"] == "SYZ" and place["venue_counts"] == {"restaurant": 1}
    suggest = client.get("/catalog/suggest", params={"q": "هتل شیراز"}).json()
    assert suggest["commercial_data"] is False
    assert [i["id"] for i in suggest["items"] if i["type"] == "city"] == ["ir-shiraz"]
    assert {i["type"] for i in suggest["items"]} >= {"city", "airport"}
    assert client.get("/catalog/suggest", params={"q": "a"}).status_code == 422
    summary = client.get("/catalog/summary").json()
    assert summary["commercial_data"] is False and summary["hotels_by_country"] == {"IR": 2, "TR": 1}
