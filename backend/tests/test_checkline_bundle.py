"""Full-bundle import: content is carried over with provenance, nothing commercial, nothing invented, idempotent, reviewer edits kept."""
import json

from sqlalchemy import delete, select

from app.catalog import (CatalogContent, CatalogHotel, CatalogHotelImage, CatalogHotelMatch, CatalogHotelProviderMapping, CatalogHotelRoomType, CatalogLegacyRoute, CatalogPlace, CatalogTour, CatalogTourDeparture,
                         CatalogTourHotel, CatalogVenue)
from app.main import SessionLocal
from scripts.catalog import import_checkline_bundle as b
from tests.test_catalog_hotel_content import VALID, _token
from tests.test_catalog_master_data import _load


def _bundle(tmp_path):
    root = tmp_path / "bundle"; (root / "evidence-round3").mkdir(parents=True); (root / "round3-technical").mkdir(); (root / "ecosystem-technical").mkdir()
    body = "<h2>معرفی</h2><p>هتلی آرام در مرکز شهر.<br/>نزدیک بازار.</p><script>alert(1)</script><iframe src='x'></iframe>"
    catalog = [
        {"id": 1, "type": "country", "status": "publish", "title": "ایران", "slug": "iran", "meta": {}, "public_body": "<p>کشور ایران</p>"},
        {"id": 3, "type": "country", "status": "publish", "title": "تایلند", "slug": "thailand", "meta": {}, "public_body": "<p>تایلند در جنوب شرق آسیا</p>"},
        {"id": 2, "type": "city", "status": "publish", "title": "شیراز", "slug": "shiraz", "meta": {}, "public_body": "<p>شهر شیراز</p>"},
        {"id": 4, "type": "city", "status": "publish", "title": "پوکت", "slug": "phuket", "meta": {}, "public_body": "<p>جزیرهٔ پوکت</p>"},
        {"id": 10, "type": "location", "status": "publish", "title": "هتل باغ نارنج", "slug": "h10", "meta": {}, "public_body": body},
        {"id": 11, "type": "location", "status": "draft", "title": "هتل پیش‌نویس", "slug": "h11", "meta": {"country": "1", "city": "2", "gallery": ["900"]}, "public_body": "<p>متن</p>"},
        {"id": 12, "type": "location", "status": "publish", "title": "Phuket Bay Hotel", "slug": "h12", "meta": {}, "public_body": ""},
        {"id": 20, "type": "tour", "status": "publish", "title": "تور ۳ شب و ۴ روز شیراز", "slug": "t20", "meta": {}, "public_body": "<p>گشت شیراز</p>"},
        {"id": 21, "type": "tour", "status": "trash", "title": "حذف‌شده", "slug": "t21", "meta": {}, "public_body": ""},
        {"id": 30, "type": "visa", "status": "publish", "title": "ویزای تایلند", "slug": "v30", "meta": {}, "public_body": "<p>مدارک لازم</p>"}]
    meta = [
        {"id": 1, "type": "country", "title": "ایران", "meta": {"title-en": ["Iran"], "capital": ["تهران"], "currency": ["ریال"], "map": [{"lat": "32.4", "lng": "53.6"}]}},
        {"id": 3, "type": "country", "title": "تایلند", "meta": {"title-en": ["Thailand"], "currency": ["بات"], "visa": ["<p>ویزای توریستی</p>"], "map": [{"lat": "15.87", "lng": "100.99"}]}},
        {"id": 2, "type": "city", "title": "شیراز", "meta": {"country": ["1"], "title-en": ["Shiraz"], "time_zone": ["+3:30"]}},
        {"id": 4, "type": "city", "title": "پوکت", "meta": {"country": ["3"], "title-en": ["Phuket"], "map": [{"lat": "7.88", "lng": "98.39"}], "top-image": ["901"]}},
        {"id": 10, "type": "location", "title": "هتل باغ نارنج", "meta": {"country": ["1"], "city": ["2"], "address": ["خیابان زند ۱۲"], "rating": ["4"], "check-in-time": ["14:00"], "check-out-time": ["۱۲:۰۰"], "rules-text": ["<p>ارائهٔ مدرک</p>"], "tel": ["07112345"],
                                                                 "gallery": [["900", "901", "999"]], "services": [["BB"]], "discount-amount": ["15%"], "room-count": ["40"], "facilitice-group-first": [["0", "3"]], "hotel-distance-to-bold-points_0_hdtbp-place": ["حافظیه"],
                                                                 "hotel-distance-to-bold-points_0_hdtbp-distance": ["2"], "hotel-distance-to-bold-points_0_hdtbp-unit": ["km"], "rooms-info_0_room-title": ["دوتخته"], "rooms-info_0_hidden": ["0"],
                                                                 "rooms-info_0_room-facilities": [["wifi", "air_conditioning", "unknown_code"]], "rooms-info_1_room-title": ["مخفی"], "rooms-info_1_hidden": ["1"]}},
        {"id": 12, "type": "location", "title": "Phuket Bay Hotel", "meta": {"country": ["3"], "city": ["4"], "rating": ["5"], "address": ["Patong"]}},
        {"id": 20, "type": "tour", "title": "تور شیراز", "meta": {"cities": [["2"]], "countries": [["1"]], "travel-duration": ["3 شب و 4 روز"], "facilities": [["persian-tour-leader", "transfer-to-hotel", "food"]], "services": ["بیمه"], "start-price_0_start-price-value": ["9000000"],
                                                              "holding-dates_0_hd-capacity": ["30"], "hotels-list_0_hl-hotel-items_0_hl-hotel-select": ["10"], "hotels-list_0_hl-col1-price-list_hlc-prices_0_hlc-price-value": ["8500000"],
                                                              "transport-list-column-titles_0_direction_title": ["هوایی"], "transport-list-column-titles_0_origin_title": ["تهران"], "transport-list-column-titles_0_destination_title": ["شیراز"], "top-image": ["900"]}},
        {"id": 40, "type": "attraction", "title": "حافظیه", "meta": {"city": ["2"], "country": ["1"], "map": [{"lat": "29.62", "lng": "52.55", "address": "Hafezieh"}]}}]
    (root / "evidence-round3/deep-data-audit-round3.json").write_text(json.dumps({"catalog": catalog, "taxonomy": [{"term_taxonomy_id": "7", "taxonomy": "location-category", "name": "هتل های شیراز"}],
        "pages": [{"ID": "50", "post_title": "هتل های شیراز", "post_name": "shiraz-hotels", "post_status": "publish", "body_chars": 10}, {"ID": "51", "post_title": "اقامت و مهاجرت", "post_name": "immigration", "post_status": "publish", "body_chars": 5},
                  {"ID": "52", "post_title": "تور شیراز", "post_name": "shiraz-tour", "post_status": "publish", "body_chars": 0}, {"ID": "53", "post_title": "پیش‌نویس", "post_name": "d", "post_status": "draft", "body_chars": 0}],
        "menu_items": [{"_menu_item_object": "page", "_menu_item_object_id": "50"}]}, ensure_ascii=False), encoding="utf-8")
    (root / "evidence-round3/catalog-controls-round3.json").write_text(json.dumps({"catalog_meta": meta, "catalog_taxonomy": [{"post_id": "10", "term_taxonomy_id": "7"}]}, ensure_ascii=False), encoding="utf-8")
    (root / "round3-technical/media-workbench.json").write_text(json.dumps([{"id": 900, "image": True, "exists": True, "relative_file": "2024/01/نمای هتل.jpg"}, {"id": 901, "image": True, "exists": True, "relative_file": "2024/01/b.jpg"},
                                                                           {"id": 999, "image": True, "exists": False, "relative_file": "2024/01/missing.jpg"}], ensure_ascii=False), encoding="utf-8")
    (root / "ecosystem-technical/country-city-mismatches.json").write_text("[]", encoding="utf-8")
    return str(root)


def _reset():
    with SessionLocal() as db:
        for model in (CatalogHotelMatch, CatalogHotelProviderMapping, CatalogHotelImage, CatalogHotelRoomType, CatalogTourHotel, CatalogTourDeparture, CatalogTour, CatalogContent, CatalogLegacyRoute, CatalogHotel): db.execute(delete(model))
        db.execute(delete(CatalogVenue).where(CatalogVenue.source == "checkline")); db.execute(delete(CatalogPlace).where(CatalogPlace.source.in_(("checkline", "iso3166-1")))); db.commit()


import pytest


@pytest.fixture(autouse=True)
def _clean_catalog_after():
    """The importers are additive by design, so rows of this source would otherwise leak into other tests' reference counts."""
    yield
    _reset()


def test_bundle_import_keeps_publication_untouched_without_the_publish_flag(tmp_path, client):
    _reset(); _load(tmp_path); root = _bundle(tmp_path)
    first = b.main(root, False, publish=False)
    assert first["hotels"]["inserted"] == 3 and first["hotels"]["published"] == 0
    with SessionLocal() as db:
        assert {h.status for h in db.scalars(select(CatalogHotel).where(CatalogHotel.source == "checkline"))} == {"draft"} and db.get(CatalogTour, "cl-tour-20").status == "draft"
        db.get(CatalogHotel, "cl-10").status = "published"; db.commit()                      # a reviewer published one
    again = b.main(root, False, publish=False)
    with SessionLocal() as db:
        assert db.get(CatalogHotel, "cl-10").status == "published" and db.get(CatalogHotel, "cl-12").status == "draft" and again["hotels"]["updated"] == 0
    assert client.get("/catalog/tours").json()["total"] == 0 and client.get("/catalog/hotels/checkline-10").status_code == 200


def test_bundle_import_carries_content_and_never_commercial_data(tmp_path, client):
    _reset(); _load(tmp_path); root = _bundle(tmp_path)
    first = b.main(root, False)
    assert first["hotels"]["inserted"] == 3 and first["hotels"]["published"] == 2 and first["hotels"]["bad_image_refs"] == 1 and first["places"]["countries_added"] == 1 and first["places"]["cities_added"] == 1
    again = b.main(root, False)
    assert (again["hotels"]["inserted"], again["hotels"]["updated"], again["hotels"]["unchanged"], again["tours"]["inserted"], again["tours"]["updated"], again["places"]["countries_added"], again["places"]["cities_added"]) == (0, 0, 3, 0, 0, 0, 0)
    with SessionLocal() as db:
        h = db.get(CatalogHotel, "cl-10")
        assert h.description == "معرفی\nهتلی آرام در مرکز شهر.\nنزدیک بازار." and "alert" not in h.description and (h.city_id, h.stars, h.stars_status, h.checkin_time, h.checkout_time, h.phone) == ("ir-shiraz", 4, "source_reported", "14:00", "12:00", "07112345")
        assert h.latitude is None and json.loads(h.amenities_json) == ["breakfast"] and h.status == "published"
        details = json.loads(h.details_json)["checkline"]
        assert details["room_count"] == "40" and details["nearby"] == [{"place": "حافظیه", "distance": "2", "unit": "km"}] and details["board_plans"] == ["صبحانه"] and details["categories"] == ["هتل های شیراز"]
        assert "discount" not in h.details_json and "15%" not in h.details_json and "facilit" not in h.details_json                      # no discount, no unlabeled facility codes
        rooms = db.scalars(select(CatalogHotelRoomType).where(CatalogHotelRoomType.hotel_id == "cl-10")).all()
        assert [(r.name_fa, json.loads(r.amenities_json)) for r in rooms] == [("دوتخته", ["wifi", "air_conditioning"])] and rooms[0].image_url is None                    # hidden room skipped, unknown code dropped
        images = db.scalars(select(CatalogHotelImage).where(CatalogHotelImage.hotel_id == "cl-10").order_by(CatalogHotelImage.sort_order)).all()
        assert [i.url for i in images] == ["https://checkline.travel/wp-content/uploads/2024/01/%D9%86%D9%85%D8%A7%DB%8C%20%D9%87%D8%AA%D9%84.jpg", "https://checkline.travel/wp-content/uploads/2024/01/b.jpg"] and all("rights unverified" in i.license for i in images)
        assert db.get(CatalogHotel, "cl-11").status == "draft" and db.get(CatalogHotel, "cl-12").city_id == "cl-city-4"
        th, phuket, shiraz = db.get(CatalogPlace, "th"), db.get(CatalogPlace, "cl-city-4"), db.get(CatalogPlace, "ir-shiraz")
        assert (th.source, th.latitude, th.description) == ("iso3166-1", 15.87, "تایلند در جنوب شرق آسیا") and json.loads(th.details_json)["checkline"]["visa_note"] == "ویزای توریستی"
        assert (phuket.latitude, phuket.longitude, phuket.name_en, phuket.hotel_count) == (7.88, 98.39, "Phuket", 1) and phuket.image_url.endswith("/2024/01/b.jpg")
        assert shiraz.source != "checkline" and shiraz.description == "شهر شیراز" and json.loads(shiraz.details_json)["checkline"]["time_zone"] == "+3:30"   # existing place: only empty fields filled
        tour = db.get(CatalogTour, "cl-tour-20")
        assert (tour.destination_place_id, tour.duration_nights, tour.duration_days, tour.transport_mode, tour.guide_included, tour.transfer_included, tour.status) == ("ir-shiraz", 3, 4, "flight", True, True, "published")
        assert "9000000" not in tour.details_json
        assert "8500000" not in tour.details_json and not any(k in tour.details_json for k in ("price", "capacity", "start-price"))
        assert [x.hotel_id for x in db.scalars(select(CatalogTourHotel).where(CatalogTourHotel.tour_id == "cl-tour-20"))] == ["cl-10"] and db.get(CatalogTour, "cl-tour-21") is None
        assert db.get(CatalogVenue, "cl-attr-40").latitude == 29.62 and db.get(CatalogContent, "cl-visa-30").body == "مدارک لازم"
        routes = {r.legacy_path: r.target_path for r in db.scalars(select(CatalogLegacyRoute))}
        assert routes == {"/shiraz-hotels/": "/hotels?country=IR&city=ir-shiraz", "/immigration/": None, "/shiraz-tour/": "/tours/search?destination=ir-shiraz"}
    # ---- the content is reachable through the public API: search -> results -> detail, with no price and not bookable
    listing = client.get("/catalog/hotels", params={"city": "ir-shiraz", "q": "باغ نارنج"}).json()
    assert listing["total"] == 1 and listing["items"][0]["price"] is None and listing["items"][0]["state"]["bookable"] is False and listing["items"][0]["image_url"]
    detail = client.get("/catalog/hotels/checkline-10").json()
    assert detail["description"].startswith("معرفی") and detail["details"]["nearby"][0]["place"] == "حافظیه" and len(detail["images"]) == 2 and detail["room_types"][0]["name_fa"] == "دوتخته" and detail["price"] is None
    assert client.get("/catalog/hotels/checkline-11").status_code == 404
    assert any(i["type"] == "hotel" and i["href"] == "/hotels/checkline-10" for i in client.get("/catalog/suggest", params={"q": "باغ نارنج"}).json()["items"])
    assert any(i["type"] == "tour" and i["href"] == "/tours/t20" for i in client.get("/catalog/suggest", params={"q": "شیراز"}).json()["items"])
    tours = client.get("/catalog/tours", params={"destination": "ir-shiraz"}).json()
    assert tours["total"] == 1 and tours["sellable"] is False and tours["items"][0]["price"] is None and tours["items"][0]["image_url"] and tours["destinations"][0]["id"] == "ir-shiraz"
    t = client.get("/catalog/tours/cl-tour-20").json()
    assert t["sellable"] is False and t["price"] is None and t["details"]["inclusions"] == ["راهنمای فارسی‌زبان", "ترانسفر هتل", "وعدهٔ غذایی"] and t["hotels"] == [{"id": "cl-10", "name": "هتل باغ نارنج", "stars": 4, "slug": "checkline-10", "nights": None}]
    assert t["details"]["transport_legs"][0]["origin"] == "تهران" and "price" not in json.dumps(t["details"]) and client.get("/catalog/tours/cl-tour-21").status_code == 404
    place = client.get("/catalog/places/ir-shiraz").json()
    assert place["description"] == "شهر شیراز" and place["details"]["time_zone"] == "+3:30" and place["reference_tours"][0]["id"] == "cl-tour-20"
    assert client.get("/catalog/places/th").json()["details"]["visa_note"] == "ویزای توریستی"
    assert client.get("/catalog/content", params={"kind": "visa"}).json()["items"][0]["title"] == "ویزای تایلند" and client.get("/catalog/content/cl-visa-30").json()["body"] == "مدارک لازم"
    assert client.get("/catalog/legacy-route", params={"path": "shiraz-hotels"}).json()["target_path"] == "/hotels?country=IR&city=ir-shiraz" and client.get("/catalog/legacy-route", params={"path": "nope"}).status_code == 404
    assert client.get("/catalog/legacy-routes").json() == {"total": 3, "mapped": 2, "items": client.get("/catalog/legacy-routes").json()["items"]}


def test_bundle_reimport_keeps_reviewer_edits_and_other_sources(tmp_path, client):
    _reset(); _load(tmp_path); root = _bundle(tmp_path); b.main(root, False)
    admin = _token(client, "platform-admin@aftab.test")
    edited = client.put("/admin/catalog/hotels/cl-10", json={**VALID, "name_fa": "نام بازبینی‌شده", "description": "متن بازبین", "status": "hidden"}, headers=admin)
    assert edited.status_code == 200
    with SessionLocal() as db:
        osm_before = (db.get(CatalogHotel, "h1").description, db.get(CatalogHotel, "h1").name_fa)
    report = b.main(root, False)
    with SessionLocal() as db:
        h = db.get(CatalogHotel, "cl-10")
        assert (h.name_fa, h.description, h.status) == ("نام بازبینی‌شده", "متن بازبین", "hidden") and db.query(CatalogHotelImage).filter_by(hotel_id="cl-10").count() == 1     # reviewer's single image kept
        assert (db.get(CatalogHotel, "h1").description, db.get(CatalogHotel, "h1").name_fa) == osm_before and db.query(CatalogHotel).filter(CatalogHotel.source == "checkline").count() == 3
    assert report["hotels"]["inserted"] == 0 and client.get("/catalog/hotels/checkline-10").status_code == 404


def test_reference_reimport_never_erases_what_the_bundle_filled(tmp_path, client):
    """The OSM-derived importer owns its rows but has no description for Shiraz; the bundle filled it. A re-import must keep it."""
    from scripts.catalog import import_catalog
    _reset(); _load(tmp_path); root = _bundle(tmp_path); b.main(root, False)
    with SessionLocal() as db:
        before = (db.get(CatalogPlace, "ir-shiraz").description, db.get(CatalogPlace, "ir-shiraz").details_json)
    report = import_catalog.main(str(tmp_path), False)
    with SessionLocal() as db:
        after = (db.get(CatalogPlace, "ir-shiraz").description, db.get(CatalogPlace, "ir-shiraz").details_json)
    assert before[0] == "شهر شیراز" and after == before and report["places"]["updated"] == 0
