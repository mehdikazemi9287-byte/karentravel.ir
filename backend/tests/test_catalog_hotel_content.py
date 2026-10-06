"""Hotel content: source ownership, admin edits, additive importers, auth/validation, no fabricated commercial data."""
import json

from sqlalchemy import delete

from app.catalog import CatalogHotel, CatalogHotelImage, CatalogHotelMatch, CatalogHotelProviderMapping, CatalogHotelRoomType, CatalogPlace
from app.main import SessionLocal
from scripts.catalog import import_checkline
from tests.test_catalog_master_data import HOTELS, _load


def _token(client, email):
    return {"Authorization": f"Bearer {client.post('/auth/dev-login', json={'email': email}).json()['access_token']}"}


def _stage(tmp_path, hotels):
    d = tmp_path / "staged"; d.mkdir(exist_ok=True)
    (d / "hotels.jsonl").write_text("\n".join(json.dumps({"raw": h}, ensure_ascii=False) for h in hotels), encoding="utf-8")
    geo = [{"id": 1, "type": "country", "title": "ایران", "english_title": "Iran"}, {"id": 2, "type": "city", "title": "شیراز", "english_title": "Shiraz", "country_id": "1"},
           {"id": 3, "type": "country", "title": "تایلند", "english_title": "Thailand"}]
    (d / "geography.jsonl").write_text("\n".join(json.dumps({"raw": g}, ensure_ascii=False) for g in geo), encoding="utf-8")
    return str(d)


CL = [{"hotel_id": 901, "title": "هتل نمونه چک‌لاین (Sample Checkline Hotel)", "country_id": "1", "country": "ایران", "city_id": "2", "city": "شیراز", "rating_current_unverified": "4",
       "address_current": "خیابان زند", "check_in_current": "۱۴:۰۰", "check_out_current": "2:00 عصر - هر زمان"},
      {"hotel_id": 902, "title": "Bangkok Test", "country_id": "3", "country": "تایلند", "city_id": "", "city": "بانکوک", "rating_current_unverified": ""}]
VALID = {"name_fa": "هتل ویرایش‌شده", "name_en": "Edited Hotel", "country_code": "IR", "city_id": "ir-shiraz", "hotel_type": "hotel", "stars": 4, "stars_status": "verified",
         "address": "شیراز، خیابان زند", "amenities": ["wifi", "elevator"], "description": "متن معرفی", "rules_text": "ارائهٔ مدرک شناسایی الزامی است.", "checkin_time": "14:00",
         "checkout_time": "12:00", "children_policy": "allowed", "pets_policy": "not_allowed", "smoking_policy": "not_allowed", "status": "published",
         "images": [{"url": "https://upload.wikimedia.org/x.jpg", "author": "A. Author", "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                     "source_url": "https://commons.wikimedia.org/wiki/File:x.jpg"}],
         "room_types": [{"name_fa": "اتاق دوتخته", "bed_type": "double", "max_adults": 2, "max_children": 1, "view": "city", "amenities": ["wifi"]}]}


def _reset():
    with SessionLocal() as db:
        for model in (CatalogHotelMatch, CatalogHotelProviderMapping, CatalogHotelImage, CatalogHotelRoomType, CatalogHotel): db.execute(delete(model))
        db.execute(delete(CatalogPlace).where(CatalogPlace.source.in_(("checkline", "iso3166-1")))); db.commit()


def test_checkline_import_is_draft_idempotent_and_never_guesses(tmp_path, client):
    _reset(); _load(tmp_path); staged = _stage(tmp_path, CL)
    first = import_checkline.main(staged, False)
    assert first["inserted"] == 2 and first["quarantined"] == {} and first["countries_added"] == ["TH"] and first["city_unresolved"] == 1
    second = import_checkline.main(staged, False)
    assert (second["inserted"], second["updated"], second["unchanged"], second["countries_added"]) == (0, 0, 2, [])
    with SessionLocal() as db:
        row = db.get(CatalogHotel, "cl-901")
        assert db.query(CatalogHotel).filter(CatalogHotel.source == "checkline").count() == 2
        thailand, bangkok = db.get(CatalogPlace, "th"), db.get(CatalogHotel, "cl-902")
        assert (thailand.kind, thailand.source, thailand.source_ref, thailand.latitude) == ("country", "iso3166-1", "TH", None)
        assert bangkok.country_code == "TH" and bangkok.city_id is None and bangkok.stars is None  # no city row in the source: unresolved, not invented
        assert (row.status, row.city_id, row.stars, row.stars_status, row.checkin_time, row.checkout_time) == ("draft", "ir-shiraz", 4, "source_reported", "14:00", None)
        assert row.latitude is None and row.image_url is None and row.amenities_json == "[]" and row.name_en == "Sample Checkline Hotel"
    # drafts are invisible publicly
    assert client.get("/catalog/hotels/cl-901").status_code == 404
    assert client.get("/catalog/hotels", params={"q": "چک‌لاین"}).json()["total"] == 0


def test_osm_reimport_keeps_checkline_and_admin_edits_and_never_deletes(tmp_path, client):
    _reset(); _load(tmp_path); import_checkline.main(_stage(tmp_path, CL), False)
    admin = _token(client, "platform-admin@aftab.test")
    assert client.put("/admin/catalog/hotels/h2", json={**VALID, "name_fa": "هاستل ویرایش دستی"}, headers=admin).status_code == 200
    # OSM input now lacks h3 and tries to overwrite h2 and to claim the CheckLine id
    import gzip
    rows = [HOTELS[0], {**HOTELS[1], "name_fa": "بازنویسی OSM"}, {**HOTELS[0], "id": "cl-901", "slug": "hijack"}]
    with gzip.open(tmp_path / "hotels.json.gz", "wt", encoding="utf-8") as fh: json.dump(rows, fh, ensure_ascii=False)
    from scripts.catalog import import_catalog
    report = import_catalog.main(str(tmp_path), False)["hotels"]
    assert report["removed"] == 0 and report["kept_absent"] == 1 and report["protected_skipped"] == 2 and report["inserted"] == 0
    again = import_catalog.main(str(tmp_path), False)["hotels"]
    assert (again["inserted"], again["updated"], again["removed"]) == (0, 0, 0)
    with SessionLocal() as db:
        assert db.get(CatalogHotel, "h3") is not None
        assert db.get(CatalogHotel, "h2").name_fa == "هاستل ویرایش دستی"
        assert db.get(CatalogHotel, "cl-901").source == "checkline" and db.get(CatalogHotel, "cl-901").slug == "checkline-901"
        assert db.query(CatalogHotelImage).filter_by(hotel_id="h2").count() == 1
    # CheckLine re-import leaves an admin-edited CheckLine hotel alone
    assert client.put("/admin/catalog/hotels/cl-901", json=VALID, headers=admin).status_code == 200
    rerun = import_checkline.main(_stage(tmp_path, CL), False)
    assert rerun["admin_owned_skipped"] == 1 and rerun["inserted"] == 0
    with SessionLocal() as db:
        assert db.get(CatalogHotel, "cl-901").name_fa == "هتل ویرایش‌شده"


def test_admin_api_auth_validation_roundtrip_and_public_view(tmp_path, client):
    _reset(); _load(tmp_path); import_checkline.main(_stage(tmp_path, CL), False)
    assert client.get("/admin/catalog/hotels").status_code in (401, 403)
    assert client.put("/admin/catalog/hotels/cl-901", json=VALID).status_code in (401, 403)
    assert client.put("/admin/catalog/hotels/cl-901", json=VALID, headers=_token(client, "employee@aftab.test")).status_code == 403
    assert client.put("/admin/catalog/hotels/cl-901", json=VALID, headers=_token(client, "supplier@aftab.test")).status_code == 403
    admin = _token(client, "backoffice@aftab.test")
    for bad in ({"price": 100}, {"nightly_price": 1}, {"amenities": ["jacuzzi_unknown"]}, {"checkin_time": "2pm"}, {"city_id": "tr"}, {"stars_status": None},
                {"images": [{**VALID["images"][0], "license": ""}]}, {"images": [{"url": "https://x.test/a.jpg"}]}, {"room_types": [{"name_fa": "اتاق", "price": 5}]},
                {"pets_policy": "maybe"}, {"latitude": 29.6}, {"website": "javascript:alert(1)"}):
        assert client.put("/admin/catalog/hotels/cl-901", json={**VALID, **bad}, headers=admin).status_code == 422, bad
    with SessionLocal() as db:
        assert db.get(CatalogHotel, "cl-901").updated_by is None  # rejected saves wrote nothing
    assert client.put("/admin/catalog/hotels/nope", json=VALID, headers=admin).status_code == 404
    saved = client.put("/admin/catalog/hotels/cl-901", json=VALID, headers=admin).json()
    assert saved["admin_owned"] and saved["status"] == "published" and saved["room_types"][0]["bed_type_fa"] == "دوتخته دبل"
    reopened = client.get("/admin/catalog/hotels/cl-901", headers=admin).json()
    assert reopened["amenity_keys"] == ["wifi", "elevator"] and reopened["images"][0]["license"] == "CC BY-SA 4.0" and reopened["rules_text"] == VALID["rules_text"]
    assert reopened["price"] is None
    public = client.get("/catalog/hotels/checkline-901").json()
    assert public["price"] is None and public["price_status"] == "inquiry" and len(public["images"]) == 1 and public["room_types"][0]["max_adults"] == 2
    assert not any("price" in key or "avail" in key for key in public["room_types"][0])
    assert {p["key"]: p["value"] for p in public["policies"]} == {"children_policy": "allowed", "pets_policy": "not_allowed", "smoking_policy": "not_allowed"}
    assert client.get("/catalog/hotels", params={"amenity": "elevator"}).json()["total"] == 1
    assert client.get("/catalog/hotels", params={"policy": "pets_policy:not_allowed", "city": "ir-shiraz", "stars": 4}).json()["items"][0]["id"] == "cl-901"
    assert any(p["key"] == "children_policy:allowed" for p in client.get("/catalog/hotels/facets").json()["policies"])
    # replacing content removes old children rows; hiding removes it from public search
    assert client.put("/admin/catalog/hotels/cl-901", json={**VALID, "images": [], "room_types": [], "status": "hidden"}, headers=admin).status_code == 200
    with SessionLocal() as db:
        assert db.query(CatalogHotelImage).filter_by(hotel_id="cl-901").count() == 0 and db.query(CatalogHotelRoomType).filter_by(hotel_id="cl-901").count() == 0
    assert client.get("/catalog/hotels/checkline-901").status_code == 404
    created = client.post("/admin/catalog/hotels", json={**VALID, "name_en": "Brand New"}, headers=admin)
    assert created.status_code == 201 and created.json()["provenance"]["source"] == "karenseir"


def test_duplicates_are_linked_only_on_address_evidence_and_reviewer_decides_the_rest(tmp_path, client):
    _reset(); _load(tmp_path)
    with SessionLocal() as db:  # canonical reference records the CheckLine rows may collide with
        h1, h2 = db.get(CatalogHotel, "h1"), db.get(CatalogHotel, "h2")
        h1.name_en, h1.address = "Zand Palace", "Zand Boulevard 12, Shiraz"
        h2.name_en, h2.name_fa, h2.address = "Eram Garden Inn", None, None
        db.commit()
    base = {"country_id": "1", "country": "ایران", "city_id": "2", "city": "شیراز", "rating_current_unverified": "3"}
    staged = _stage(tmp_path, [{**base, "hotel_id": 911, "title": "Zand Palace Hotel", "address_current": "No 12 Zand Boulevard"},      # name + city + address -> linked
                               {**base, "hotel_id": 912, "title": "Eram Garden Inn", "address_current": "Eram street 5"},                # name + city only -> proposed
                               {**base, "hotel_id": 913, "title": "Zand Palace", "address_current": "Airport road 40"},                  # same name, different address -> proposed
                               {**base, "hotel_id": 914, "title": "Unrelated Lodge", "address_current": "No 12 Zand Boulevard"}])        # same address, different name -> nothing
    report = import_checkline.main(staged, False)
    assert report["inserted"] == 4
    with SessionLocal() as db:
        assert (db.get(CatalogHotel, "cl-911").duplicate_of, db.get(CatalogHotel, "cl-911").match_basis) == ("h1", "name+city+address")
        assert db.get(CatalogHotel, "cl-912").duplicate_of is None and db.get(CatalogHotel, "cl-913").duplicate_of is None and db.get(CatalogHotel, "cl-914").duplicate_of is None
        pairs = {(m.hotel_id, m.candidate_id): (m.basis, m.status) for m in db.query(CatalogHotelMatch)}
        assert pairs[("cl-912", "h2")] == ("name+city", "proposed") and pairs[("cl-913", "h1")] == ("name+city", "proposed") and not any(k[0] == "cl-914" for k in pairs)
        assert db.query(CatalogHotel).count() == 7  # nothing merged away or deleted
        match_id = db.query(CatalogHotelMatch).filter_by(hotel_id="cl-912").one().id
        reject_id = db.query(CatalogHotelMatch).filter_by(hotel_id="cl-913").one().id
    admin = _token(client, "platform-admin@aftab.test")
    assert client.post(f"/admin/catalog/matches/{match_id}", json={"decision": "confirm", "merge_fields": True}).status_code in (401, 403)
    assert client.post(f"/admin/catalog/matches/{match_id}", json={"decision": "merge"}, headers=admin).status_code == 422
    assert client.post("/admin/catalog/hotels/cl-911/status", json={"status": "published"}, headers=admin).status_code == 422  # a linked duplicate is never public
    confirmed = client.post(f"/admin/catalog/matches/{match_id}", json={"decision": "confirm", "merge_fields": True}, headers=admin).json()
    assert confirmed["duplicate_of"]["id"] == "h2"
    assert client.post(f"/admin/catalog/matches/{reject_id}", json={"decision": "reject"}, headers=admin).status_code == 200
    with SessionLocal() as db:
        canonical = db.get(CatalogHotel, "h2")
        assert canonical.address == "Eram street 5" and canonical.stars == 3 and canonical.stars_status == "source_reported" and canonical.hotel_type == "hostel"  # only empty fields were filled
        assert canonical.updated_by is not None and db.get(CatalogHotel, "h1").address == "Zand Boulevard 12, Shiraz"
    rerun = import_checkline.main(staged, False)
    assert rerun["inserted"] == 0 and rerun["matches"]["kept_decisions"] == 2
    with SessionLocal() as db:
        assert db.query(CatalogHotelMatch).filter_by(id=reject_id).one().status == "rejected" and db.get(CatalogHotel, "cl-913").duplicate_of is None
        assert db.query(CatalogHotelMatch).count() == 3
    history = client.get("/admin/catalog/hotels/cl-912/history", headers=admin).json()
    assert history[0]["action"] == "catalog_hotel.match_confirmed" and history[0]["actor"]


def test_state_flags_publish_unpublish_and_verification(tmp_path, client):
    _reset(); _load(tmp_path); import_checkline.main(_stage(tmp_path, CL), False)
    admin = _token(client, "backoffice@aftab.test")
    draft = client.get("/admin/catalog/hotels/cl-901", headers=admin).json()
    assert draft["state"] == {"catalogued": True, "content_complete": False, "rate_available": False, "bookable": False, "published": False, "source": "checkline", "last_verified_at": None}
    assert client.post("/admin/catalog/hotels/cl-902/status", json={"status": "published"}, headers=admin).status_code == 422  # no city
    assert client.post("/admin/catalog/hotels/cl-901/status", json={"status": "published"}, headers=_token(client, "employee@aftab.test")).status_code == 403
    assert client.post("/admin/catalog/hotels/cl-901/status", json={"status": "published"}, headers=admin).json()["state"]["published"] is True
    public = client.get("/catalog/hotels/checkline-901").json()
    assert public["state"]["bookable"] is False and public["state"]["rate_available"] is False and public["price"] is None and public["state"]["content_complete"] is False
    assert client.post("/admin/catalog/hotels/cl-901/status", json={"status": "hidden"}, headers=admin).status_code == 200
    assert client.get("/catalog/hotels/checkline-901").status_code == 404
    saved = client.put("/admin/catalog/hotels/cl-901", json={**VALID, "mark_verified": True}, headers=admin).json()
    assert saved["state"]["content_complete"] is True and saved["state"]["last_verified_at"] and saved["state"]["bookable"] is False
    assert client.put("/admin/catalog/hotels/cl-901", json={**VALID, "images": []}, headers=admin).json()["state"]["content_complete"] is False
    listed = client.get("/admin/catalog/hotels", params={"review": "no_city", "source": "checkline"}, headers=admin).json()
    assert [i["id"] for i in listed["items"]] == ["cl-902"]
    mapping = {"provider": "grs", "provider_hotel_id": "H-1"}
    assert client.post("/admin/catalog/hotels/cl-901/provider-mappings", json=mapping, headers=admin).json()["provider_mappings"][0]["status"] == "unverified"
    assert client.post("/admin/catalog/hotels/cl-902/provider-mappings", json=mapping, headers=admin).status_code == 409
    assert client.get("/admin/catalog/hotels/cl-901", headers=admin).json()["state"]["rate_available"] is False  # an unverified mapping is not a rate
    actions = [e["action"] for e in client.get("/admin/catalog/hotels/cl-901/history", headers=admin).json()]
    assert "catalog_hotel.status_changed" in actions and "catalog_hotel.updated" in actions and "catalog_hotel.provider_mapping_added" in actions
