"""Bundle content as site structure: tour slug/filters, travel requirements, destination breadcrumbs/related, de-duplicated images."""
import json

from scripts.catalog import import_checkline_bundle as b
from tests.test_catalog_master_data import _load
from tests.test_checkline_bundle import _bundle, _reset


def test_tour_vertical_visa_and_destination_structure(tmp_path, client):
    _reset(); _load(tmp_path); root = _bundle(tmp_path)
    media = json.loads(open(root + "/round3-technical/media-workbench.json", encoding="utf-8").read())
    media[0]["sha256"] = media[1]["sha256"] = "same-bytes"                      # two library records of one file
    open(root + "/round3-technical/media-workbench.json", "w", encoding="utf-8").write(json.dumps(media, ensure_ascii=False))
    b.main(root, False); again = b.main(root, False)
    assert (again["hotels"]["updated"], again["tours"]["updated"]) == (0, 0)
    hotel = client.get("/catalog/hotels/checkline-10").json()
    assert len(hotel["images"]) == 1 and hotel["request"] == {"mode": "inquiry", "online_booking": False, "reason": hotel["request"]["reason"]} and hotel["seo"]["title"].startswith("هتل باغ نارنج")
    assert {a["key"] for a in hotel["room_types"][0]["amenities"]} == {"wifi", "air_conditioning"} and hotel["state"]["bookable"] is False
    tours = client.get("/catalog/tours").json()
    item = tours["items"][0]
    assert (item["slug"], item["href"]) == ("t20", "/tours/t20") and tours["years"] == [] and client.get("/catalog/tours", params={"nights": "1-3"}).json()["total"] == 1 and client.get("/catalog/tours", params={"nights": "7+"}).json()["total"] == 0
    assert client.get("/catalog/tours", params={"nights": "2"}).status_code == 422 and client.get("/catalog/tours", params={"category": "وجود ندارد"}).json()["total"] == 0
    by_slug, by_id = client.get("/catalog/tours/t20").json(), client.get("/catalog/tours/cl-tour-20").json()
    assert by_slug["id"] == by_id["id"] == "cl-tour-20" and by_slug["origin"] == "تهران" and by_slug["request"]["online_booking"] is False and by_slug["price"] is None and by_slug["travel_requirements"] is None
    assert by_slug["seo"]["title"].startswith("تور ۳ شب و ۴ روز شیراز")
    visa = client.get("/catalog/visa").json()
    assert [c["id"] for c in visa["countries"]] == ["th"] and visa["countries"][0]["visa_note"] == "ویزای توریستی" and visa["articles"][0]["title"] == "ویزای تایلند" and "تضمین نمی‌شود" in visa["disclaimer"]
    assert client.get("/catalog/content/cl-visa-country-th").json()["body"] == "ویزای توریستی"
    shiraz = client.get("/catalog/places/ir-shiraz").json()
    assert shiraz["breadcrumbs"][0] == {"id": "ir", "name": "ایران"} and shiraz["seo"]["title"].startswith("سفر به شیراز") and isinstance(shiraz["related"], list)
    assert client.get("/catalog/places/cl-city-4").json()["breadcrumbs"] == [{"id": "th", "name": "تایلند"}]
