"""D2 (QA 1405-08-18): traveller identity fields, Iranian national-code checksum, per-vertical rules, masking, isolation."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app import operations as models
from app.main import AuditEvent, SessionLocal
from app.traveller_identity import TravellerIdentity, mask_last4, requirement_errors, valid_national_code
from test_checkout_reviews_zarinpal import auth, login, reservation_fixture

VALID = "5260181591"


def future(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()


def test_national_code_checksum_rules():
    assert valid_national_code("0010350829") and valid_national_code(VALID)
    assert valid_national_code("۵۲۶۰۱۸۱۵۹۱")  # Persian digits are normalized
    assert not valid_national_code("0010350828")  # wrong check digit
    assert not valid_national_code("1111111111")  # one repeated digit
    assert not valid_national_code("12345678") and not valid_national_code("abcdefghij") and not valid_national_code(None)
    assert mask_last4("0010350829") == "••••••0829" and mask_last4(None) is None


def test_invalid_identity_is_rejected_in_persian_and_not_saved(client):
    user = login(client, "employee@aftab.test")
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(models.Traveller))
    bad = client.post("/me/travellers", headers=auth(user), json={"full_name": "مسافر کد نادرست", "national_code": "0010350828"})
    assert bad.status_code == 422 and "کد ملی" in bad.json()["detail"]
    cases = [
        ({"passport_number": "P1234567"}, "گذرنامه"),  # number without expiry
        ({"passport_number": "P1234567", "passport_expiry": future(-1)}, "منقضی"),
        ({"national_code": VALID, "nationality": "AF"}, "ایرانی"),
        ({"birth_date": future(3)}, "تولد"),
        ({"birth_date": "1400/01/01"}, "تولد"),
        ({"gender": "x"}, "جنسیت"),
    ]
    for extra, word in cases:
        r = client.post("/me/travellers", headers=auth(user), json={"full_name": "مسافر نامعتبر", **extra})
        assert r.status_code == 422 and word in r.json()["detail"], (extra, r.text)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(models.Traveller)) == before


def test_identity_is_masked_in_lists_and_full_only_for_owner_or_audited_staff(client):
    owner = login(client, "employee@aftab.test")
    created = client.post("/me/travellers", headers=auth(owner), json={
        "full_name": "مسافر هویت کامل", "national_code": "۰۰۱۰۳۵۰۸۲۹", "birth_date": "1990-03-21", "gender": "female",
        "passport_number": "x9876543", "passport_expiry": future(900)})
    assert created.status_code == 201, created.text
    body = created.json(); tid = body["id"]
    assert body["national_code_masked"] == "••••••0829" and body["passport_number_masked"] == "••••6543"
    assert body["nationality"] == "IR" and "national_code" not in body and "passport_number" not in body
    listed = next(t for t in client.get("/me/travellers", headers=auth(owner)).json() if t["id"] == tid)
    assert "0010350829" not in json.dumps(listed) and "X9876543" not in json.dumps(listed)
    full = client.get(f"/me/travellers/{tid}/identity", headers=auth(owner)).json()
    assert full["national_code"] == "0010350829" and full["passport_number"] == "X9876543" and full["birth_date"] == "1990-03-21"
    # partial update keeps the other fields; an empty string clears one
    upd = client.put(f"/me/travellers/{tid}", headers=auth(owner), json={"full_name": "مسافر هویت کامل", "gender": "male"}).json()
    assert upd["gender"] == "male" and upd["has_national_code"] and upd["has_passport"]
    # isolation: another user of the same tenant and a user of another tenant cannot read it
    for other in ("welfare@aftab.test", "employee@faraz.test"):
        assert client.get(f"/me/travellers/{tid}/identity", headers=auth(login(client, other))).status_code == 404
        assert client.put(f"/me/travellers/{tid}", headers=auth(login(client, other)), json={"full_name": "x y z"}).status_code == 404
    assert client.post(f"/ops/travellers/{tid}/identity/reveal", headers=auth(owner), json={"reason": "بررسی صدور بلیت"}).status_code == 403
    assert client.post(f"/ops/travellers/{tid}/identity/reveal", headers=auth(login(client, "employee@faraz.test")), json={"reason": "بررسی صدور بلیت"}).status_code == 403
    staff = login(client, "backoffice@aftab.test")
    assert client.post(f"/ops/travellers/{tid}/identity/reveal", headers=auth(staff), json={}).status_code == 422
    revealed = client.post(f"/ops/travellers/{tid}/identity/reveal", headers=auth(staff), json={"reason": "بررسی صدور بلیت"})
    assert revealed.status_code == 200 and revealed.json()["national_code"] == "0010350829"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "traveller_identity.revealed", AuditEvent.detail.contains(tid))) == 1
    # removing the saved traveller removes its identity row
    assert client.post(f"/me/travellers/{tid}/remove", headers=auth(owner)).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(TravellerIdentity).where(TravellerIdentity.traveller_id == tid)) is None


def _flight_checkout(client, attrs):
    suffix = uuid.uuid4().hex
    user, _, t1, offer = reservation_fixture(client, suffix)
    with SessionLocal() as db:
        row = db.get(models.Offer, offer["id"]); row.service_type = "flight"; row.attributes_json = json.dumps(attrs); db.commit()
    checked = client.post("/offers/" + offer["id"] + "/price-check", headers=auth(user), json={"units": 1, "command_id": "idf-" + suffix, "flight_party": {"adults": 1, "children": 0, "infants": 0}})
    assert checked.status_code == 201, checked.text
    booking = client.post("/orchestration/bookings", headers=auth(user), json={"price_check_id": checked.json()["id"], "command_id": "idb-" + suffix}).json()
    checkout = client.post("/reservations/" + booking["id"] + "/checkout-sessions", headers=auth(user), json={"command_id": "idc-" + suffix}).json()
    req = client.get("/reservations/" + booking["id"] + "/traveller-requirements", headers=auth(user)).json()
    assert req["requirement"] == ("international" if attrs.get("scope") == "international" else "domestic")
    assert client.get("/reservations/" + booking["id"] + "/traveller-requirements", headers=auth(login(client, "employee@faraz.test"))).status_code == 404
    return user, "/checkout-sessions/" + checkout["id"] + "/steps/traveller"


def test_domestic_flight_needs_national_code_or_foreign_passport(client):
    user, step = _flight_checkout(client, {"origin": "THR", "destination": "MHD", "departure_time": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()})
    plain = client.post("/me/travellers", headers=auth(user), json={"full_name": "مسافر بدون مدرک"}).json()
    r = client.put(step, headers=auth(user), json={"command_id": uuid.uuid4().hex, "traveller_ids": [plain["id"]]})
    assert r.status_code == 422 and "کد ملی" in r.json()["detail"] and "مسافر بدون مدرک" in r.json()["detail"]
    foreign = client.post("/me/travellers", headers=auth(user), json={"full_name": "Foreign QA guest", "nationality": "AF"}).json()
    r = client.put(step, headers=auth(user), json={"command_id": uuid.uuid4().hex, "traveller_ids": [foreign["id"]]})
    assert r.status_code == 422 and "گذرنامه" in r.json()["detail"]
    assert client.put("/me/travellers/" + foreign["id"], headers=auth(user), json={"full_name": "Foreign QA guest", "passport_number": "AF123456", "passport_expiry": future(300)}).status_code == 200
    assert client.put(step, headers=auth(user), json={"command_id": uuid.uuid4().hex, "traveller_ids": [foreign["id"]]}).status_code == 200


def test_international_flight_needs_passport_valid_on_travel_date(client):
    depart = datetime.now(timezone.utc) + timedelta(days=60)
    user, step = _flight_checkout(client, {"origin": "IKA", "destination": "IST", "scope": "international", "departure_time": depart.isoformat()})
    t = client.post("/me/travellers", headers=auth(user), json={"full_name": "مسافر پرواز خارجی", "national_code": "0830166130"}).json()
    r = client.put(step, headers=auth(user), json={"command_id": uuid.uuid4().hex, "traveller_ids": [t["id"]]})
    assert r.status_code == 422 and "گذرنامه" in r.json()["detail"]
    client.put("/me/travellers/" + t["id"], headers=auth(user), json={"full_name": "مسافر پرواز خارجی", "passport_number": "B11223344", "passport_expiry": future(30)})
    r = client.put(step, headers=auth(user), json={"command_id": uuid.uuid4().hex, "traveller_ids": [t["id"]]})
    assert r.status_code == 422 and "تاریخ سفر" in r.json()["detail"]
    client.put("/me/travellers/" + t["id"], headers=auth(user), json={"full_name": "مسافر پرواز خارجی", "passport_expiry": future(400)})
    assert client.put(step, headers=auth(user), json={"command_id": uuid.uuid4().hex, "traveller_ids": [t["id"]]}).status_code == 200


def test_requirement_rules_skip_other_verticals():
    t = models.Traveller(id="t-1", tenant_id=1, full_name="x")
    assert requirement_errors("hotel", [t], {}, international=False) == []
    assert requirement_errors("tour", [t], {}, international=True) == []
    assert len(requirement_errors("train", [t], {}, international=False)) == 1
