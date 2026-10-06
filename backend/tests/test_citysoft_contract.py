"""Citysoft contract: built strictly from the documented field paths of the bundle; no network, no credential, not registered."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import citysoft_contract as c, flight_port as fp, hotel_rates as hr
from app.hotel_rates import RateQuery, RateSourceError

NOW = datetime(2027, 1, 1, 9, 0, tzinfo=timezone.utc)
FQ = fp.FlightSearchQuery("THR", "MHD", datetime(2027, 2, 1, tzinfo=timezone.utc), {"ADT": 2, "CHD": 0})
HQ = RateQuery("CN-778", date(2027, 2, 1), date(2027, 2, 3), 2, 1)
FLIGHTS = {"Success": True, "Items": [
    {"AirItinerary": [{"SessionId": "S1", "CombinationId": 3, "RecommendationId": 1, "SubsystemId": 7, "SubsystemName": "x"}], "AirItineraryPricingInfo": {"ItinTotalFare": {"TotalFare": 25000000, "BaseFare": 2, "Currency": "IRR"}},
     "OriginDestinationInformation": {"OriginDestinationOption": [{"FlightSegment": [{"DepartureDateTime": "2027-02-01T08:00:00+03:30", "ArrivalDateTime": "2027-02-01T09:30:00+03:30", "FlightNumber": 1041, "ResBookDesigCode": "Y",
        "DepartureAirport": {"LocationCode": "THR"}, "ArrivalAirport": {"LocationCode": "MHD"}, "MarketingAirline": {"Code": "W5"}}]}]}},
    {"AirItinerary": [{"SessionId": "S1", "CombinationId": 4, "RecommendationId": 1, "SubsystemId": 7}], "AirItineraryPricingInfo": {"ItinTotalFare": {"TotalFare": 0, "Currency": "IRR"}},
     "OriginDestinationInformation": {"OriginDestinationOption": [{"FlightSegment": [{"DepartureDateTime": "2027-02-01T08:00:00+03:30", "ArrivalDateTime": "2027-02-01T09:30:00+03:30", "FlightNumber": 1, "ResBookDesigCode": "Y",
        "DepartureAirport": {"LocationCode": "THR"}, "ArrivalAirport": {"LocationCode": "MHD"}, "MarketingAirline": {"Code": "W5"}}]}]}},
    {"AirItinerary": [{"SessionId": "S1", "CombinationId": 5, "RecommendationId": 1, "SubsystemId": 7}], "AirItineraryPricingInfo": {"ItinTotalFare": {"TotalFare": 9000000, "Currency": "IRR"}},
     "OriginDestinationInformation": {"OriginDestinationOption": [{"FlightSegment": [{"DepartureDateTime": "2027-02-01T08:00:00", "ArrivalDateTime": "2027-02-01T09:30:00", "FlightNumber": 2, "ResBookDesigCode": "Y",
        "DepartureAirport": {"LocationCode": "THR"}, "ArrivalAirport": {"LocationCode": "MHD"}, "MarketingAirline": {"Code": "W5"}}]}]}}]}
ROOMS = {"Success": True, "Items": [{"HotelInfo": {"CitynetCode": "CN-778", "HotelName": "x"}, "expiredAt": "2027-01-01T09:20:00+00:00", "Combinations": [
    {"HotelItinerary": {"SessionId": "H1", "CombinationId": 1, "RecommendationId": 1, "SubsystemId": 2}, "Rooms": [{"RoomTypeName": "Double", "HotelItineraryPricingInfo": {"ItinTotalFare": {"Total": 30000000, "Currency": "IRR"}}},
                                                                                                    {"RoomTypeName": "Single", "HotelItineraryPricingInfo": {"ItinTotalFare": {"Total": 20000000, "Currency": "IRR"}}}]},
    {"HotelItinerary": {"SessionId": "H1", "CombinationId": 2, "RecommendationId": 1, "SubsystemId": 2}, "Rooms": [{"RoomTypeName": "Free", "HotelItineraryPricingInfo": {"ItinTotalFare": {"Total": 0, "Currency": "IRR"}}}]},
    {"HotelItinerary": {"SessionId": "H1", "CombinationId": 3, "RecommendationId": 1, "SubsystemId": 2}, "Rooms": [{"RoomTypeName": "Mixed", "HotelItineraryPricingInfo": {"ItinTotalFare": {"Total": 5, "Currency": "IRR"}}},
                                                                                                    {"RoomTypeName": "Mixed", "HotelItineraryPricingInfo": {"ItinTotalFare": {"Total": 5, "Currency": "USD"}}}]}]},
    {"HotelInfo": {"CitynetCode": "OTHER"}, "Combinations": [{"HotelItinerary": {"SessionId": "H9", "CombinationId": 1, "RecommendationId": 1, "SubsystemId": 2}, "Rooms": [{"RoomTypeName": "X", "HotelItineraryPricingInfo": {"ItinTotalFare": {"Total": 10, "Currency": "IRR"}}}]}]}]}


def test_operations_cover_the_documented_service_and_map_to_ports():
    ops = c.operations()
    assert len(ops) == 26 and all((o["method"], o["path"]) in c.OPERATIONS for o in ops)
    capability = {o["path"]: o["capability"] for o in ops}
    assert (capability["/flights/search"], capability["/hotels/rooms"], capability["/bookingengine/book"], capability["/airportlist"], capability["/ledgers"]) == ("flight.search", "hotel.rate", "booking.reserve", "reference.airports", "finance.ledger")
    assert next(o for o in ops if o["path"] == "/authenticate")["required_parameters"] == ["username", "password"]


def test_requests_and_parsers_use_only_documented_fields():
    assert c.paths_of(c.flight_search_request(FQ)) <= c.documented("POST", "/flights/search", "request")
    assert c.paths_of(c.hotel_rooms_request(HQ)) <= c.documented("POST", "/hotels/rooms", "request")
    assert c.paths_of(FLIGHTS) <= c.documented("POST", "/flights/search", "response") and c.paths_of(ROOMS) <= c.documented("POST", "/hotels/rooms", "response") | c.documented("POST", "/hotels/search", "response")
    request = c.flight_search_request(FQ)
    assert request["TravelerInfoSummary"]["AirTravelerAvail"]["PassengerTypeQuantity"] == [{"Code": "ADT", "Quantity": 2}] and request["OriginDestinationInformations"][0]["DepartureDateTime"] == "2027-02-01"
    assert c.hotel_rooms_request(HQ)["RoomGuests"] == [{"AdultCount": 2, "ChildAge": [0]}]


def test_parsed_offers_pass_or_fail_the_port_contract_never_get_repaired():
    fares = c.parse_flight_search(FLIGHTS, offer_ttl=timedelta(minutes=15), now=NOW)
    assert [f.provider_offer_ref for f in fares] == ["S1:3:1:7", "S1:4:1:7"]                         # the item without a stated time zone is not guessed
    assert c.parse_flight_search(FLIGHTS, offer_ttl=timedelta(minutes=15), now=NOW, zone=__import__("zoneinfo").ZoneInfo("Asia/Tehran"))[-1].segments[0].departs_at.utcoffset() == timedelta(hours=3, minutes=30)
    valid = fp.validate_fares(FQ, fares, {"W5"}.__contains__, {"THR", "MHD"}.__contains__, NOW)
    assert [f.total_amount for f in valid] == [25000000] and valid[0].segments[0].flight_number == "1041" and valid[0].expires_at == NOW + timedelta(minutes=15)   # zero fare dropped by the port
    offers = c.parse_hotel_rooms(ROOMS, HQ, offer_ttl=timedelta(minutes=15), now=NOW)
    assert [(o.provider_offer_ref, o.total_amount, o.room_name) for o in offers] == [("H1:1:1:2", 50000000, "Double + Single"), ("H1:2:1:2", 0, "Free")]   # mixed currencies and other hotels never become an offer
    assert [o.total_amount for o in hr.validate_offers(HQ, offers, NOW)] == [50000000] and offers[0].expires_at == datetime(2027, 1, 1, 9, 20, tzinfo=timezone.utc)
    assert c.parse_flight_search({"Success": False, "Items": FLIGHTS["Items"]}, offer_ttl=timedelta(minutes=1)) == [] and c.parse_hotel_rooms({"Items": []}, HQ, offer_ttl=timedelta(minutes=1)) == []


def test_adapter_fails_closed_and_is_not_registered():
    with pytest.raises(RateSourceError): c.CitysoftAdapter(transport=None).quote(HQ)
    with pytest.raises(RateSourceError): c.CitysoftAdapter(transport=lambda *a: {}, username="u", password="p").quote(HQ)                 # no offer validity configured
    calls = []
    def transport(method, path, body, token):
        calls.append((method, path, token))
        return {"Success": True, "token": "T"} if path == "/authenticate" else ROOMS if path == "/hotels/rooms" else FLIGHTS
    adapter = c.CitysoftAdapter(transport=transport, username="u", password="p", offer_ttl_seconds=900)
    assert len(adapter.quote(HQ)) == 2 and len(adapter.search(FQ)) == 2 and calls == [("POST", "/authenticate", None), ("POST", "/hotels/rooms", "T"), ("POST", "/flights/search", "T")]
    with pytest.raises(RateSourceError): c.CitysoftAdapter(transport=lambda *a: {"Success": False}, username="u", password="p", offer_ttl_seconds=900).quote(HQ)
    assert c.KEY not in hr.RATE_SOURCES and c.KEY not in fp.FLIGHT_SOURCES
