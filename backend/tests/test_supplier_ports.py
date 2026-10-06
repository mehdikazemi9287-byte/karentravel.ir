"""Hotel and flight supplier ports: the contract every adapter must meet. Harness classes exist only in tests."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import catalog, flight_port as fp, hotel_rates as hr
from app.hotel_rates import CancellationResult, ContractViolation, ProviderReservation, RateOffer, RateQuery
from tests.test_catalog_hotel_content import VALID, _token
from tests.test_catalog_master_data import _load

NOW = datetime(2027, 1, 1, 12, 0, tzinfo=timezone.utc)
Q = RateQuery("P1", date(2027, 1, 10), date(2027, 1, 12), 2)
OFFER = RateOffer("P1", "of-1", "Double", 900, "USD", True, NOW + timedelta(minutes=30))


class HotelHarness:
    key = "harness"

    def __init__(self, fresh=OFFER, reserved=None, confirmed=None): self.fresh, self.reserved, self.confirmed, self.calls = fresh, reserved, confirmed, []
    def quote(self, query): return [OFFER]
    def recheck(self, offer, query): self.calls.append("recheck"); return self.fresh
    def reserve(self, offer, query, key): self.calls.append("reserve"); return self.reserved or ProviderReservation("R1", offer.provider_offer_ref, "reserved", offer.total_amount, offer.currency, NOW + timedelta(minutes=15))
    def confirm(self, ref, key): self.calls.append("confirm"); return self.confirmed or ProviderReservation(ref, "of-1", "confirmed", 900, "USD")


def test_hotel_query_and_recheck_rules():
    hr.validate_query(date(2027, 1, 10), date(2027, 1, 12), 2, today=date(2027, 1, 1))
    for args in ((date(2026, 12, 31), date(2027, 1, 2), 2), (date(2027, 1, 10), date(2027, 1, 10), 2), (date(2027, 1, 10), date(2027, 3, 10), 2), (date(2027, 1, 10), date(2027, 1, 12), 0)):
        with pytest.raises(ValueError): hr.validate_query(*args, today=date(2027, 1, 1))
    assert hr.recheck_decision(OFFER, OFFER, Q, NOW)["status"] == "ok"
    dearer = RateOffer("P1", "of-1", "Double", 950, "USD", True, NOW + timedelta(minutes=30))
    assert hr.recheck_decision(OFFER, dearer, Q, NOW) == {"status": "price_changed", "previous_amount": 900, "offer": dearer}
    assert hr.recheck_decision(OFFER, RateOffer("P1", "of-1", "Double", 900, "EUR", True, NOW + timedelta(minutes=30)), Q, NOW)["reason"] == "currency_changed"
    assert hr.recheck_decision(OFFER, None, Q, NOW)["status"] == "unavailable" and hr.recheck_decision(OFFER, None, Q, NOW + timedelta(hours=1))["status"] == "expired"
    for broken in (RateOffer("P1", "of-1", "Double", 0, "USD", True, NOW + timedelta(minutes=30)), RateOffer("P9", "of-1", "Double", 900, "USD", True, NOW + timedelta(minutes=30)),
                   RateOffer("P1", "of-1", "Double", 900, "USD", True, NOW - timedelta(minutes=1)), RateOffer("P1", "of-1", "Double", 900, "XXX", True, NOW + timedelta(minutes=30))):
        assert hr.recheck_decision(OFFER, broken, Q, NOW) == {"status": "unavailable", "reason": "contract_violation"}


def test_hotel_reserve_confirm_cancel_contract(monkeypatch):
    with pytest.raises(PermissionError): hr.book_through_port(HotelHarness(), OFFER, Q, "idem-12345", NOW)      # booking flow is off by default
    monkeypatch.setattr(catalog, "BOOKING_FROM_CATALOG_ENABLED", True)
    port = HotelHarness()
    assert hr.book_through_port(port, OFFER, Q, "idem-12345", NOW).status == "confirmed" and port.calls == ["recheck", "reserve", "confirm"]
    with pytest.raises(ValueError): hr.book_through_port(HotelHarness(), OFFER, Q, "", NOW)
    dearer = HotelHarness(fresh=RateOffer("P1", "of-1", "Double", 950, "USD", True, NOW + timedelta(minutes=30)))
    with pytest.raises(ContractViolation): hr.book_through_port(dearer, OFFER, Q, "idem-12345", NOW)
    assert dearer.calls == ["recheck"]                                                                             # a changed price never reaches reserve
    for bad in (ProviderReservation("R1", "of-1", "reserved", 900, "USD", None), ProviderReservation("R1", "of-1", "reserved", 901, "USD", NOW + timedelta(minutes=5)),
                ProviderReservation("R1", "of-2", "reserved", 900, "USD", NOW + timedelta(minutes=5)), ProviderReservation("", "of-1", "reserved", 900, "USD", NOW + timedelta(minutes=5)),
                ProviderReservation("R1", "of-1", "confirmed", 900, "USD", NOW + timedelta(minutes=5)), ProviderReservation("R1", "of-1", "reserved", 900, "USD", NOW - timedelta(minutes=5))):
        with pytest.raises(ContractViolation): hr.book_through_port(HotelHarness(reserved=bad), OFFER, Q, "idem-12345", NOW)
    with pytest.raises(ContractViolation): hr.book_through_port(HotelHarness(confirmed=ProviderReservation("R1", "of-1", "reserved", 900, "USD")), OFFER, Q, "idem-12345", NOW)
    confirmed = ProviderReservation("R1", "of-1", "confirmed", 900, "USD")
    assert hr.check_cancellation(CancellationResult("R1", "cancelled", 600, "USD"), confirmed).refund_amount == 600
    for bad in (CancellationResult("R1", "cancelled", 901, "USD"), CancellationResult("R1", "cancelled", -1, "USD"), CancellationResult("R2", "cancelled", 0, "USD"), CancellationResult("R1", "pending", 0, "USD"), CancellationResult("R1", "cancelled", 0, "EUR")):
        with pytest.raises(ContractViolation): hr.check_cancellation(bad, confirmed)
    hr.check_transition("reserved", "confirmed"); hr.check_transition("confirmed", "cancelled")
    for a, b in (("cancelled", "confirmed"), ("confirmed", "reserved"), ("expired", "confirmed")):
        with pytest.raises(ContractViolation): hr.check_transition(a, b)


def test_room_and_rate_plan_mapping_and_recheck_endpoint(tmp_path, client):
    _load(tmp_path); hr.RATE_SOURCES.clear()
    admin = _token(client, "platform-admin@aftab.test")
    saved = client.put("/admin/catalog/hotels/h1", json={**VALID, "city_id": "ir-shiraz"}, headers=admin).json()
    other = client.put("/admin/catalog/hotels/h2", json={**VALID, "city_id": "ir-shiraz", "name_en": "Other"}, headers=admin).json()
    mapping = client.post("/admin/catalog/hotels/h1/provider-mappings", json={"provider": "harness", "provider_hotel_id": "P1-" + NOW.isoformat()[:4] + "x"}, headers=admin).json()["provider_mappings"][0]
    room, foreign_room = saved["room_types"][0]["id"], other["room_types"][0]["id"]
    assert client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rooms", json={"room_type_id": foreign_room, "provider_room_id": "RM1"}, headers=admin).status_code == 422   # room of another hotel
    assert client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rooms", json={"room_type_id": room, "provider_room_id": "RM1"}, headers=admin).status_code == 201
    assert client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rooms", json={"room_type_id": room, "provider_room_id": "RM1"}, headers=admin).status_code == 409
    plan = client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rate-plans", json={"provider_rate_plan_id": "BAR", "board": "BB", "refundable": True}, headers=admin)
    assert plan.status_code == 201 and plan.json()["amount"] is None
    for bad in ({"provider_rate_plan_id": "X", "board": "ZZ"}, {"provider_rate_plan_id": "X", "price": 10}, {"provider_rate_plan_id": ""}):
        assert client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rate-plans", json=bad, headers=admin).status_code == 422
    assert client.post(f"/admin/catalog/provider-mappings/{mapping['id']}/rooms", json={"room_type_id": room, "provider_room_id": "RM2"}, headers=_token(client, "supplier@aftab.test")).status_code == 403
    assert client.post("/catalog/hotels/test-hotel-one/rates/999999/recheck").status_code == 404
    hr.RATE_SOURCES.clear()


AIRPORTS, AIRLINES = {"THR", "MHD", "IST"}, {"W5", "TK"}
T0 = datetime(2027, 2, 1, 8, 0, tzinfo=timezone.utc)
SEG = fp.FlightSegment("W5", "1041", "THR", "MHD", T0, T0 + timedelta(hours=1, minutes=30))
FQ = fp.FlightSearchQuery("THR", "MHD", T0, {"ADT": 1})
FARE = fp.FareOffer("f-1", (SEG,), 2500000, "IRR", "YOW", True, NOW + timedelta(minutes=20))


def test_flight_search_and_fare_contract():
    fp.validate_search(FQ, AIRPORTS.__contains__, NOW)
    for q in (fp.FlightSearchQuery("THR", "THR", T0, {"ADT": 1}), fp.FlightSearchQuery("THR", "XXX", T0, {"ADT": 1}), fp.FlightSearchQuery("THR", "MHD", NOW - timedelta(days=2), {"ADT": 1}),
              fp.FlightSearchQuery("THR", "MHD", T0, {"ADT": 0, "CHD": 1}), fp.FlightSearchQuery("THR", "MHD", T0, {"ADT": 1, "INF": 2}), fp.FlightSearchQuery("THR", "MHD", T0, {"ADT": 10}),
              fp.FlightSearchQuery("THR", "MHD", T0, {"ADT": 1, "PET": 1}), fp.FlightSearchQuery("THR", "MHD", T0, {"ADT": 1}, return_on=T0 - timedelta(days=1))):
        with pytest.raises(ValueError): fp.validate_search(q, AIRPORTS.__contains__, NOW)
    r = lambda **o: fp.FareOffer(**{**FARE.__dict__, **o})  # noqa: E731
    s = lambda **o: fp.FlightSegment(**{**SEG.__dict__, **o})  # noqa: E731
    bad = [r(total_amount=0), r(total_amount=-1), r(total_amount=10.5), r(currency="XXX"), r(expires_at=NOW - timedelta(seconds=1)), r(expires_at=datetime(2030, 1, 1)), r(provider_offer_ref=""), r(segments=()),
           r(segments=(s(carrier="ZZ"),)), r(segments=(s(destination="XXX"),)), r(segments=(s(arrives_at=T0),)), r(segments=(s(origin="IST"),)), r(segments=(s(departs_at=T0 + timedelta(days=1), arrives_at=T0 + timedelta(days=1, hours=1)),)),
           r(segments=(s(destination="IST"), fp.FlightSegment("TK", "880", "THR", "MHD", T0 + timedelta(hours=5), T0 + timedelta(hours=7))))]
    assert fp.validate_fares(FQ, [FARE, *bad], AIRLINES.__contains__, AIRPORTS.__contains__, NOW) == [FARE]
    assert fp.FLIGHT_SOURCES == {}


def test_flight_revalidate_pnr_issue_void_refund_and_schedule_change():
    assert fp.revalidate_decision(FARE, FARE, NOW)["status"] == "ok"
    assert fp.revalidate_decision(FARE, fp.FareOffer(**{**FARE.__dict__, "total_amount": 2600000}), NOW)["status"] == "price_changed"
    moved = fp.FlightSegment("W5", "1041", "THR", "MHD", T0 + timedelta(hours=4), T0 + timedelta(hours=5, minutes=30))
    assert fp.revalidate_decision(FARE, fp.FareOffer(**{**FARE.__dict__, "segments": (moved,)}), NOW)["status"] == "schedule_changed"
    assert fp.revalidate_decision(FARE, None, NOW)["status"] == "unavailable" and fp.revalidate_decision(FARE, None, NOW + timedelta(hours=1))["status"] == "expired"
    held = fp.Pnr("ABC123", "f-1", "held", 2500000, "IRR", NOW + timedelta(hours=2))
    assert fp.check_pnr(held, FARE, "held", NOW) is held
    for bad in (fp.Pnr("", "f-1", "held", 2500000, "IRR", NOW + timedelta(hours=2)), fp.Pnr("ABC123", "f-2", "held", 2500000, "IRR", NOW + timedelta(hours=2)), fp.Pnr("ABC123", "f-1", "held", 2400000, "IRR", NOW + timedelta(hours=2)),
                fp.Pnr("ABC123", "f-1", "held", 2500000, "IRR", None), fp.Pnr("ABC123", "f-1", "held", 2500000, "IRR", NOW - timedelta(minutes=1)), fp.Pnr("ABC123", "f-1", "ticketed", 2500000, "IRR")):
        with pytest.raises(fp.FlightContractViolation): fp.check_pnr(bad, FARE, "held", NOW)
    with pytest.raises(fp.FlightContractViolation): fp.check_pnr(fp.Pnr("ABC123", "f-1", "ticketed", 2500000, "IRR"), FARE, "ticketed", NOW)   # issued without ticket numbers
    ticketed = fp.check_pnr(fp.Pnr("ABC123", "f-1", "ticketed", 2500000, "IRR", ticket_numbers=("0712345678901",)), FARE, "ticketed", NOW)
    for a, b in (("held", "ticketed"), ("ticketed", "voided"), ("ticketed", "refunded"), ("ticketed", "schedule_changed"), ("schedule_changed", "refunded")): fp.check_transition(a, b)
    for a, b in (("voided", "ticketed"), ("refunded", "voided"), ("held", "refunded"), ("expired", "ticketed")):
        with pytest.raises(fp.FlightContractViolation): fp.check_transition(a, b)
    assert fp.check_refund(2000000, ticketed) == 2000000
    for amount in (2500001, -1, 1.5, True):
        with pytest.raises(fp.FlightContractViolation): fp.check_refund(amount, ticketed)
    change = fp.schedule_change_event(fp.ScheduleChange("ABC123", SEG, moved, NOW))
    assert (change["category"], change["severity"], change["source"], change["requires_action"], change["affected_reference"]) == ("schedule_change", "critical", "provider", True, "ABC123")
    assert change["old_value"]["حرکت"] == T0.isoformat() and change["new_value"]["حرکت"] == (T0 + timedelta(hours=4)).isoformat()
    minor = fp.schedule_change_event(fp.ScheduleChange("ABC123", SEG, fp.FlightSegment("W5", "1041", "THR", "MHD", T0 + timedelta(minutes=20), T0 + timedelta(hours=1, minutes=50)), NOW))
    assert (minor["severity"], minor["requires_action"]) == ("warning", False)
    cancelled = fp.schedule_change_event(fp.ScheduleChange("ABC123", SEG, None, NOW))
    assert (cancelled["category"], cancelled["new_value"], cancelled["severity"]) == ("cancellation", None, "critical")


def test_provider_schedule_change_lands_in_the_trip_change_log(client):
    """The port's event shape is accepted verbatim by the Trip Operations Center: provider → trip_events → customer."""
    from tests.test_platform_ops import _trip
    import uuid
    trip = _trip("employee@aftab.test")
    moved = fp.FlightSegment("W5", "1041", "THR", "MHD", T0 + timedelta(hours=4), T0 + timedelta(hours=5, minutes=30))
    payload = fp.schedule_change_event(fp.ScheduleChange("ABC123", SEG, moved, NOW)); payload.pop("affected_reference")
    created = client.post(f"/operations/trips/{trip}/events", json={**payload, "command_id": "sc-" + uuid.uuid4().hex, "reason": "اعلام تأمین‌کنندهٔ پرواز"}, headers=_token(client, "backoffice@aftab.test"))
    assert created.status_code == 201 and created.json()["source"] == "provider"
    seen = client.get(f"/trips/{trip}/changes", headers=_token(client, "employee@aftab.test")).json()["changes"][0]
    assert seen["old_value"]["حرکت"] == T0.isoformat() and seen["new_value"]["حرکت"] == (T0 + timedelta(hours=4)).isoformat()


def test_tour_reference_edit_never_becomes_a_product(tmp_path, client):
    from sqlalchemy import delete
    from app.catalog import CatalogTour, CatalogTourDeparture
    from app.main import SessionLocal
    from scripts.catalog import import_checkline_tours
    import json
    _load(tmp_path)
    with SessionLocal() as db:
        db.execute(delete(CatalogTourDeparture)); db.execute(delete(CatalogTour)); db.commit()
    d = tmp_path / "st"; d.mkdir()
    (d / "tours.jsonl").write_text(json.dumps({"raw": {"tour_id": 7, "title": "تور ۷ شب و ۸ روز ارمنستان", "disabled": "0", "soldout": "0"}}, ensure_ascii=False) + "\n" + json.dumps({"raw": {"tour_id": 8, "title": "تور 9 شب و 3 روز", "disabled": "0", "soldout": "0"}}, ensure_ascii=False), encoding="utf-8")
    (d / "departures.jsonl").write_text(json.dumps({"raw": {"tour_id": 7, "row_index": 1, "departure_raw": "1402-08-04", "end_raw": "1402-08-11"}}), encoding="utf-8")
    import_checkline_tours.main(str(d), False)
    admin = _token(client, "backoffice@aftab.test")
    t = client.get("/admin/catalog/tours/cl-tour-7", headers=admin).json()
    assert (t["duration_nights"], t["duration_days"], t["capacity"], t["supplier"], t["price"], t["sellable"]) == (7, 8, None, None, None, False)
    assert client.get("/admin/catalog/tours/cl-tour-8", headers=admin).json()["duration_nights"] is None      # inconsistent title: nothing derived
    body = {"title_fa": "تور ارمنستان", "destination_place_id": "ir-shiraz", "duration_nights": 7, "duration_days": 8, "transport_mode": "flight", "board": "BB", "guide_included": True, "status": "published",
            "itinerary": [{"day_no": 1, "title": "ورود", "place_id": "ir-shiraz"}, {"day_no": 2, "title": "گشت شهری"}], "hotels": [{"hotel_id": "h1", "nights": 7}]}
    for bad in ({"price": 1}, {"capacity": 20}, {"supplier_id": "x"}, {"board": "ZZ"}, {"destination_place_id": "nowhere"}, {"hotels": [{"hotel_id": "nope"}]}, {"itinerary": [{"day_no": 1, "title": "الف"}, {"day_no": 1, "title": "ب"}]},
                {"duration_nights": 9, "duration_days": 3}, {"itinerary": []}, {"departures": [{"starts_on": "2030-01-01"}]}):
        assert client.put("/admin/catalog/tours/cl-tour-7", json={**body, **bad}, headers=admin).status_code == 422, bad
    assert client.put("/admin/catalog/tours/cl-tour-7", json=body, headers=_token(client, "supplier@aftab.test")).status_code == 403
    saved = client.put("/admin/catalog/tours/cl-tour-7", json=body, headers=admin).json()
    assert saved["status"] == "published" and len(saved["itinerary"]) == 2 and saved["hotels"] == [{"hotel_id": "h1", "nights": 7}] and saved["sellable"] is False and saved["latest_departure"] == "2023-10-26"
    assert import_checkline_tours.main(str(d), False)["admin_owned_skipped"] == 1
    public = client.get("/public/tour-products")
    assert public.status_code in (200, 503) and "cl-tour-7" not in public.text
