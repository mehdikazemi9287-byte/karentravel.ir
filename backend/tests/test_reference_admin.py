"""Reference records in the admin panel (completeness, edit, ownership) and the gaps closed in the bundle importer."""
import csv
import json

from sqlalchemy import select

from app.catalog import CatalogAirline, CatalogAirport, CatalogContent, CatalogHotel, CatalogPlace
from app.main import SessionLocal
from scripts.catalog import import_airlines_reference, import_airports_reference
from scripts.catalog import import_checkline_bundle as b
from tests.test_catalog_hotel_content import _token
from tests.test_catalog_master_data import _load
from tests.test_checkline_bundle import _bundle, _clean_catalog_after, _reset  # noqa: F401  (autouse cleanup)

EMBED = '<iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3010.2!2d{lng}!3d{lat}!2m3!1f0" width="600"></iframe>'


def _edit(root, fn):
    for name in ("deep-data-audit-round3.json", "catalog-controls-round3.json"):
        path = f"{root}/evidence-round3/{name}"; data = json.loads(open(path, encoding="utf-8").read()); fn(name, data)
        open(path, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False))


def test_hotels_are_never_dropped_and_positions_are_verified(tmp_path, client):
    _reset(); _load(tmp_path); root = _bundle(tmp_path)

    def more(name, data):
        if name.startswith("deep"):
            data["catalog"] += [{"id": i, "type": "location", "status": "publish", "title": t, "slug": f"h{i}", "meta": {}, "public_body": "<p>متن</p>"} for i, t in ((13, "هتل بدون کشور"), (14, "Malaysia Listed Phuket Hotel"), (15, "Patong Sea Hotel"), (16, "Far Away Hotel"))]
            data["catalog"].append({"id": 5, "type": "country", "status": "publish", "title": "مالزی", "slug": "malaysia", "meta": {}, "public_body": ""})
        else:
            data["catalog_meta"] += [{"id": 5, "type": "country", "title": "مالزی", "meta": {"title-en": ["Malaysia"]}},
                                     {"id": 13, "type": "location", "title": "هتل بدون کشور", "meta": {"address": ["نامشخص"]}},
                                     {"id": 14, "type": "location", "title": "Malaysia Listed Phuket Hotel", "meta": {"country": ["5"], "city": ["4"], "address": ["Patong"], "map-embed": [EMBED.format(lat="7.89", lng="98.30")]}},
                                     {"id": 15, "type": "location", "title": "Patong Sea Hotel", "meta": {"country": ["3"], "city": ["777"], "address": ["Thaweewong Rd, Patong, Phuket 83150"], "latitude": ["98.31"], "longitude": ["7.9"]}},
                                     {"id": 16, "type": "location", "title": "Far Away Hotel", "meta": {"country": ["3"], "city": ["4"], "address": ["Patong"], "map-embed": [EMBED.format(lat="25.25", lng="55.29")]}}]
    _edit(root, more)
    first = b.main(root, False); again = b.main(root, False)
    assert first["hotels"]["quarantined"] == {} and first["hotels"]["needs_review"] == {"country_unresolved": 1, "country_city_conflict": 1} and (again["hotels"]["inserted"], again["hotels"]["updated"]) == (0, 0)
    with SessionLocal() as db:
        unknown, conflict, sea, far = (db.get(CatalogHotel, f"cl-{i}") for i in (13, 14, 15, 16))
        assert (unknown.country_code, unknown.city_id, unknown.status) == ("ZZ", None, "draft") and json.loads(unknown.details_json)["checkline"]["review_note"] == "country_unresolved"
        # the city is the more specific fact: the hotel follows its city's country, stays a draft and says why
        assert (conflict.country_code, conflict.city_id, conflict.status) == ("TH", "cl-city-4", "draft") and json.loads(conflict.details_json)["checkline"]["review_note"] == "country_city_conflict"
        assert (conflict.latitude, conflict.longitude) == (7.89, 98.3) and json.loads(conflict.details_json)["checkline"]["coordinates_basis"] == "source_map_embed"
        # dangling city reference: the address names one bundle city of that country; the swapped latitude/longitude fields are put right by the city check
        details = json.loads(sea.details_json)["checkline"]
        assert sea.city_id == "cl-city-4" and details["place_basis"] == "source_text" and (sea.latitude, sea.longitude, details["coordinates_basis"]) == (7.9, 98.31, "source_fields_swapped") and "review_note" not in details
        assert (far.latitude, far.longitude) == (None, None) and "coordinates_basis" not in json.loads(far.details_json)["checkline"]      # a map centred 4,500 km from the hotel's city is not a position
    assert first["hotels"]["with_coordinates"] == 2 and first["hotels"]["coordinates_unverified"] == 1
    public = client.get("/catalog/hotels", params={"limit": 50}).json()["items"]
    assert "ZZ" not in {h["country_code"] for h in public} and "checkline-13" not in {h["slug"] for h in public} and client.get("/catalog/hotels/checkline-13").status_code == 404
    token = _token(client, "platform-admin@aftab.test")
    listed = client.get("/admin/catalog/hotels", params={"q": "cl-13"}, headers=token).json()["items"]
    assert listed[0]["id"] == "cl-13" and {"شهر", "تصویر", "نوع اتاق"} <= set(listed[0]["missing"]) and client.get("/admin/catalog/hotels/cl-13", headers=token).status_code == 200


def test_reference_admin_lists_edits_and_keeps_edits_through_reimports(tmp_path, client):
    _reset(); _load(tmp_path); root = _bundle(tmp_path); b.main(root, False)
    token = _token(client, "platform-admin@aftab.test")
    assert client.get("/admin/catalog/reference/places").status_code in (401, 403) and client.get("/admin/catalog/reference/prices", headers=token).status_code == 404
    summary = client.get("/admin/catalog/completeness", headers=token).json()
    assert set(summary) == {"places", "airlines", "airports", "attractions", "visa", "hotels", "tours"} and all(0 <= v["complete"] <= v["total"] for v in summary.values())
    cities = client.get("/admin/catalog/reference/places", params={"q": "پوکت", "type": "city", "country": "th"}, headers=token).json()
    assert [r["id"] for r in cities["items"]] == ["cl-city-4"] and cities["items"][0]["parent"] == "تایلند" and 0 < cities["items"][0]["completeness"]["percent"] <= 100
    incomplete = client.get("/admin/catalog/reference/places", params={"incomplete": True, "limit": 100}, headers=token).json()
    assert incomplete["total"] >= 1 and all(r["completeness"]["missing"] for r in incomplete["items"])
    detail = client.get("/admin/catalog/reference/places/cl-city-4", headers=token).json()
    assert detail["values"]["name_en"] == "Phuket" and detail["relations"]["hotels"] == 1 and detail["admin_owned"] is False and {f["key"] for f in detail["fields"]} >= {"description", "latitude", "image_url"}
    url = "/admin/catalog/reference/places/cl-city-4"
    assert client.put(url, json={"values": {"price": 1}}, headers=token).status_code == 422 and client.put(url, json={"values": {"latitude": 95}}, headers=token).status_code == 422
    assert client.put(url, json={"values": {"latitude": None}}, headers=token).status_code == 422                                    # latitude and longitude go together
    assert client.put(url, json={"values": {"image_url": "http://insecure.example/a.jpg"}}, headers=token).status_code == 422
    saved = client.put(url, json={"values": {"description": "جزیره‌ای در جنوب تایلند؛ متن بازبینی‌شده."}}, headers=token).json()
    assert saved["admin_owned"] is True and saved["values"]["description"].startswith("جزیره‌ای") and saved["values"]["name_en"] == "Phuket"
    visa = client.get("/admin/catalog/reference/visa", headers=token).json()
    assert {r["id"] for r in visa["items"]} == {"cl-visa-30", "cl-visa-country-th"}
    assert client.put("/admin/catalog/reference/visa/cl-visa-30", json={"values": {"body": ""}}, headers=token).status_code == 422
    assert client.put("/admin/catalog/reference/visa/cl-visa-30", json={"values": {"body": "مدارک لازم — بازبینی‌شده", "status": "draft"}}, headers=token).status_code == 200
    assert client.get("/catalog/visa").json()["articles"] == []                                                                      # a draft guide is not public
    attraction = client.get("/admin/catalog/reference/attractions", params={"q": "حافظیه"}, headers=token).json()["items"][0]
    assert attraction["id"] == "cl-attr-40" and "توضیح" in attraction["completeness"]["missing"]
    assert client.put("/admin/catalog/reference/attractions/cl-attr-40", json={"values": {"city_id": "ir"}}, headers=token).status_code == 422   # a country is not a city
    tours = client.get("/admin/catalog/tours", headers=token).json()["items"]
    assert tours[0]["missing"] == ["شرایط لغو"] and tours[0]["admin_owned"] is False
    # the bundle importer and the reference importer both leave the panel edits alone
    b.main(root, False); _load(tmp_path)
    with SessionLocal() as db:
        assert db.get(CatalogPlace, "cl-city-4").description.startswith("جزیره‌ای") and (db.get(CatalogContent, "cl-visa-30").body, db.get(CatalogContent, "cl-visa-30").status) == ("مدارک لازم — بازبینی‌شده", "draft")


def test_airport_and_airline_reference_importers_only_add(tmp_path, client):
    _reset(); _load(tmp_path); root = _bundle(tmp_path); b.main(root, False)
    path = tmp_path / "airports.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["id", "ident", "type", "name", "latitude_deg", "longitude_deg", "elevation_ft", "continent", "iso_country", "iso_region", "municipality", "scheduled_service", "icao_code", "iata_code", "gps_code", "local_code", "home_link", "wikipedia_link", "keywords"])
        w.writerow([1, "VTSP", "large_airport", "Phuket International Airport", "8.1132", "98.3169", "", "AS", "TH", "TH-83", "Phuket", "yes", "VTSP", "HKT", "", "", "", "", ""])
        w.writerow([2, "VTXX", "small_airport", "Small Strip", "8.0", "98.0", "", "AS", "TH", "", "Phuket", "yes", "", "XXA", "", "", "", "", ""])       # too small
        w.writerow([3, "EGLL", "large_airport", "London Heathrow Airport", "51.47", "-0.46", "", "EU", "GB", "", "London", "yes", "EGLL", "LHR", "", "", "", "", ""])  # country not in the catalogue
        w.writerow([4, "VTBD", "medium_airport", "No Service", "13.9", "100.6", "", "AS", "TH", "", "Bangkok", "no", "VTBD", "DMK", "", "", "", "", ""])
    with SessionLocal() as db: before = set(db.scalars(select(CatalogAirport.id)))
    first = import_airports_reference.main(str(path), False); again = import_airports_reference.main(str(path), False)
    assert (first["inserted"], first["city_linked"], again["inserted"], again["existing"]) == (1, 1, 0, 1)
    with SessionLocal() as db:
        hkt = db.get(CatalogAirport, "HKT")
        assert set(db.scalars(select(CatalogAirport.id))) == before | {"HKT"} and (hkt.city_id, hkt.country_code, hkt.name_fa, hkt.source) == ("cl-city-4", "TH", None, "ourairports")
    rows = [{"item": "http://www.wikidata.org/entity/Q90000001", "iata": "TG", "icao": "THA", "iso": "TH", "en": "Thai Airways", "fa": "تای ایرویز", "web": "https://www.thaiairways.com/", "links": "90"},
            {"item": "http://www.wikidata.org/entity/Q90000002", "iata": "TG", "icao": "TGC", "iso": "TH", "en": "Thai Cargo", "links": "3"},
            {"item": "http://www.wikidata.org/entity/Q90000003", "iata": "BA", "icao": "BAW", "iso": "GB", "en": "British Airways", "links": "100"}]
    src = tmp_path / "airlines.json"; src.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    first = import_airlines_reference.main(str(src), False); again = import_airlines_reference.main(str(src), False)
    assert (first["inserted"], first["outside_catalogue_countries"], again["inserted"]) == (1, 1, 0)
    with SessionLocal() as db:
        tg = db.scalars(select(CatalogAirline).where(CatalogAirline.iata_code == "TG")).all()
        assert [(a.id, a.name_en, a.logo_url) for a in tg] == [("Q90000001", "Thai Airways", None)]
    token = _token(client, "platform-admin@aftab.test")
    assert client.get("/admin/catalog/reference/airports", params={"q": "HKT"}, headers=token).json()["items"][0]["completeness"]["missing"] == ["نام فارسی", "منطقهٔ زمانی"]
    saved = client.put("/admin/catalog/reference/airports/HKT", json={"values": {"name_fa": "فرودگاه بین‌المللی پوکت", "timezone": "Asia/Bangkok"}}, headers=token).json()
    assert saved["completeness"]["percent"] == 100 and client.get("/admin/catalog/reference/airlines", params={"country": "TH"}, headers=token).json()["total"] == 1
    with SessionLocal() as db:  # rows this test added outside the bundle source
        db.delete(db.get(CatalogAirport, "HKT")); db.delete(db.get(CatalogAirline, "Q90000001")); db.commit()
