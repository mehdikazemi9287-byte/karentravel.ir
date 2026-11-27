"""Niira NRS client: parsing of every documented response shape, error mapping, edtID builder, redaction, retries, date check,
reserve/issue/cancel/refund. TEST FIXTURES ONLY: every NRS answer here is synthetic (fake flights, prices, PNRs, tickets,
users and passwords). HTTP goes through httpx.MockTransport — the real httpx code path runs, no request leaves the process.
"""
import json
import logging
from datetime import date, datetime

import httpx
import pytest

from app import nira_nrs as nn
from app.nira_nrs import NiraClient, NiraError, Passenger

USER, PASS = "TESTWS.USER", "s3cret-not-real-PW"
DAY = date(2030, 1, 15)


def cfg(code="A1", host="a1.nirasoft.ir", scheme="http", cgi="NRSWeb.cgi"):
    return nn.AirlineConfig(code, scheme, host, cgi, USER, PASS)


class Mock:
    """Route by path fragment → list of answers (dict/str body, (status, body) tuple, or an httpx exception); last repeats."""

    def __init__(self, routes):
        self.routes = {k: v if isinstance(v, list) else [v] for k, v in routes.items()}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for frag, answers in self.routes.items():
            if frag in request.url.path:
                a = answers.pop(0) if len(answers) > 1 else answers[0]
                if isinstance(a, Exception):
                    raise a
                status, body = a if isinstance(a, tuple) else (200, a)
                content = body.encode() if isinstance(body, str) else json.dumps(body).encode()
                return httpx.Response(status, content=content)
        return httpx.Response(404, content=b"not found")

    def count(self, frag):
        return sum(1 for r in self.requests if frag in r.url.path)


def client(routes, mode="sandbox", config=None):
    mock = Mock(routes)
    c = NiraClient(mode, config or cfg(), http=httpx.Client(transport=httpx.MockTransport(mock)), sleep=lambda s: None)
    return c, mock


AVAIL = {"AvailableFlights": [
    {"Origin": "THR", "Destination": "MHD", "DepartureDateTime": "2030-01-15 08:30:00", "ArrivalDateTime": "2030-01-15 10:00:00", "FlightNo": "1001",
     "Airline": "A1", "Transit": "", "AircraftTypeCode": "MD88", "ClassRefundStatus": "Y:Refundable",
     "ClassesStatus": [{"FlightClass": "Y", "Cap": "A", "Price": "25000000", "CurrencyCode": "IRR"},
                       {"FlightClass": "M", "Cap": "3", "Price": "21,000,000", "CurrencyCode": "IRR"},
                       {"FlightClass": "B", "Cap": "C", "Price": "19000000", "CurrencyCode": "IRR"},
                       {"FlightClass": "L", "Cap": "X", "Price": "18000000", "CurrencyCode": "IRR"},
                       {"FlightClass": "K", "Cap": "0", "Price": "17000000", "CurrencyCode": "IRR"}]},
    {"Origin": "THR", "Destination": "MHD", "DepartureDateTime": "2030-01-16 07:00:00", "ArrivalDateTime": "2030-01-16 08:30:00", "FlightNo": "1003",
     "ClassesStatus": [{"FlightClass": "Y", "Cap": "A", "Price": "1", "CurrencyCode": "IRR"}]}]}
FARE = {"AdultFare": "20000000", "AdultTotalPrice": "23500000", "AdultTaxes": "LP:2500000,EN_Desc:Airport tax,FA_Desc:عوارض فرودگاه$KU:1000000,EN_Desc:Other,FA_Desc:سایر",
        "ChildFare": "15000000", "ChildTotalPrice": "17000000", "ChildTaxes": "LP:2000000,EN_Desc:Airport tax,FA_Desc:عوارض",
        "InfantFare": "2000000", "InfantTotalPrice": "2000000", "InfantTaxes": "",
        "CRCNRules": [{"Text": "تا ۲۴ ساعت قبل ۳۰٪"}], "BaggageAllowanceWeight": "20", "BaggageAllowancePieces": "1"}
ADULT = Passenger("ADT", "Ali", "Testi", "M", date(1990, 5, 21), "I", "0012345679")


# ---------------------------------------------------------------- parsing
def test_availability_fare_parses_classes_caps_and_drops_other_dates():
    c, mock = client({"AvailabilityFareJS.jsp": AVAIL})
    res = c.availability_fare("THR", "MHD", DAY, 2)
    assert [f.flight_no for f in res.flights] == ["1001"] and res.rejected == ({"flight_no": "1003", "reason": "date_mismatch"},)
    f = res.flights[0]
    assert f.departure == datetime(2030, 1, 15, 8, 30) and f.aircraft == "MD88"
    caps = {k.rbd: (k.state, k.seats, k.more_than_nine, k.price) for k in f.classes}
    assert caps == {"Y": ("open", 9, True, 25000000), "M": ("open", 3, False, 21000000), "B": ("closed", 0, False, 19000000),
                    "L": ("cancelled", 0, False, 18000000), "K": ("closed", 0, False, 17000000)}
    assert [k.rbd for k in f.classes if k.bookable_for(4)] == ["Y"]
    q = dict(mock.requests[0].url.params)
    assert q["DepartureDate"] == "2030-01-15" and q["cbSource"] == "THR" and q["cbAdultQty"] == "2" and q[nn.P_AIRLINE] == "A1"


def test_availability_string_classes_and_route_mismatch():
    data = {"AvailableFlights": [{"Origin": "THR", "Destination": "MHD", "DepartureDateTime": "2030-01-15T09:00", "FlightNo": "77", "ClassesStatus": "YA M4 BC LX"},
                                 {"Origin": "THR", "Destination": "KIH", "DepartureDateTime": "2030-01-15 09:00", "FlightNo": "78", "ClassesStatus": "YA"}]}
    res = nn.parse_availability(data, "A1", "THR", "MHD", DAY)
    assert [(k.rbd, k.state, k.seats) for k in res.flights[0].classes] == [("Y", "open", 9), ("M", "open", 4), ("B", "closed", 0), ("L", "cancelled", 0)]
    assert res.rejected == ({"flight_no": "78", "reason": "route_mismatch"},)


def test_fare_parses_per_passenger_fares_and_tax_strings():
    c, _ = client({"FareJS.jsp": FARE})
    q = c.fare("THR", "MHD", "Y", "1001", DAY)
    assert (q.adult.base, q.adult.total) == (20000000, 23500000)
    assert [(t.code, t.amount, t.en, t.fa) for t in q.adult.taxes] == [("LP", 2500000, "Airport tax", "عوارض فرودگاه"), ("KU", 1000000, "Other", "سایر")]
    assert q.child.total == 17000000 and q.infant.taxes == () and q.baggage_weight == "20"
    with pytest.raises(NiraError) as e:
        nn.parse_taxes("LP:abc,EN_Desc:x")
    assert e.value.code == "BAD_RESPONSE"


def test_ticket_record_hides_commission_and_refund_inputs():
    etr = {"TicketNo": "0991234567890", "Fare": "20000000", "TotalPrice": "23500000", "Comission": "600000",
           "TAXES": [{"TaxCode": "LP", "TaxAmount": "2500000"}, {"TaxCode": "KU", "TaxAmount": "700000"}, {"TaxCode": "YQ", "TaxAmount": "300000"}]}
    pen = {"RefundedTaxes": [], "Legs": [{"RefundedFare": "14000000", "Amount": "30", "Mode": "P", "AM": "", "Cancellation": "N"}], "PENALTY": "6000000",
           "RefundedAmount": "17500000"}
    c, mock = client({"NRSETR.jsp": etr, "NRSPenalty.jsp": pen, "ETRefundJS": {"AirNRSRefund": [{"Done": "0", "Desc": "OK"}]}})
    rec = c.retrieve_ticket("0991234567890")
    assert rec.commission == 600000 and "commission" not in json.dumps(rec.public()).lower() and "600000" not in repr(rec)
    amounts = c.prepare_refund("0991234567890")
    assert (amounts.fare, amounts.ku, amounts.lp, amounts.penalty) == (20000000, 1000000, 2500000, 6000000)
    assert c.refund("0991234567890", amounts) == {"done": True, "desc": "OK"}
    sent = dict(mock.requests[-1].url.params)
    assert (sent["Fare"], sent["KU"], sent["LP"], sent["Penalty"]) == ("20000000", "1000000", "2500000", "6000000")
    assert mock.count("NRSPenaltyNow") == 0


def test_refund_incorrect_fare_and_no_retry():
    c, mock = client({"ETRefundJS": {"AirNRSRefund": [{"Done": "-5000", "Desc": "INCORRECT RETURN FARE"}]}})
    with pytest.raises(NiraError) as e:
        c.refund("0991234567890", nn.RefundInputs(1, 0, 0, 0))
    assert e.value.code == "INCORRECT_RETURN_FARE" and mock.count("ETRefundJS") == 1
    c, mock = client({"ETRefundJS": httpx.ReadTimeout("t")})
    with pytest.raises(NiraError) as e:
        c.refund("0991234567890", nn.RefundInputs(1, 0, 0, 0))
    assert e.value.code == "TIMEOUT" and e.value.ambiguous and mock.count("ETRefundJS") == 1


def test_penalty_now_and_penalty_parse():
    c, mock = client({"NRSPenaltyNow.jsp": {"PENALTY": "0", "RefundedAmount": "100", "Legs": []}})
    assert c.penalty_now("0991234567890").penalty == 0 and mock.count("NRSPenaltyNow") == 1


# ---------------------------------------------------------------- reserve / issue / cancel
def test_reserve_success_rechecks_time_and_sends_passengers():
    c, mock = client({"AvailabilityFareJS.jsp": AVAIL, "ReservJS": {"AirReserve": [{"Error": "No Err", "PNR": "abc123"}]}})
    f = c.availability_fare("THR", "MHD", DAY).flights[0]
    infant = Passenger("INF", "Sara", "Testi", "F", date(2029, 6, 1), "I", "0012345687")
    assert c.reserve(f, "Y", [ADULT, infant], "09120000000|02100000000")["pnr"] == "ABC123"
    assert mock.count("AvailabilityFareJS") == 2                             # one search + one re-check before reserve
    req = mock.requests[-1]
    assert req.url.path == "/ws2/cgi-bin/NRSWeb.cgi/ReservJS"
    p = dict(req.url.params)
    assert p["No"] == "2" and p["edtName1"] == "ALI MR" and p["edtName2"] == "SARA MISS" and p["DepartureDate"] == "2030-01-15" and p["FlightClass"] == "Y"
    assert p["edtID1"] == "I__0012345679__21MAY90_M__TESTI_ALI" and p["edtContact"] == "09120000000|02100000000"


def test_reserve_success_word_and_failures():
    for err, code in (("Success", None), ("CLASS CLOSED", "CLASS_CLOSED"), ("NOT ENOUGH CREDIT", "NOT_ENOUGH_CREDIT"), ("Reservation Failur", "RESERVATION_FAILURE"),
                      ("weird", "RESERVATION_FAILURE")):
        c, mock = client({"AvailabilityFareJS.jsp": AVAIL, "ReservJS": {"AirReserve": [{"Error": err, "PNR": "XYZ789" if code is None else ""}]}})
        f = c.availability_fare("THR", "MHD", DAY).flights[0]
        if code is None:
            assert c.reserve(f, "Y", [ADULT], "09120000000")["pnr"] == "XYZ789"
        else:
            with pytest.raises(NiraError) as e:
                c.reserve(f, "Y", [ADULT], "09120000000")
            assert e.value.code == code and mock.count("ReservJS") == 1


def test_reserve_refuses_schedule_change_and_never_retries_timeout():
    moved = json.loads(json.dumps(AVAIL))
    moved["AvailableFlights"][0]["DepartureDateTime"] = "2030-01-15 11:45:00"
    c, mock = client({"AvailabilityFareJS.jsp": [AVAIL, moved], "ReservJS": {"AirReserve": [{"Error": "No Err", "PNR": "ABC123"}]}})
    f = c.availability_fare("THR", "MHD", DAY).flights[0]
    with pytest.raises(NiraError) as e:
        c.reserve(f, "Y", [ADULT], "09120000000")
    assert e.value.code == "SCHEDULE_CHANGED" and mock.count("ReservJS") == 0
    c, mock = client({"AvailabilityFareJS.jsp": AVAIL, "ReservJS": httpx.ReadTimeout("t")})
    f = c.availability_fare("THR", "MHD", DAY).flights[0]
    with pytest.raises(NiraError) as e:
        c.reserve(f, "Y", [ADULT], "09120000000")
    assert e.value.ambiguous and mock.count("ReservJS") == 1


def test_issue_is_idempotent_and_single_call():
    ans = {"AirNRSTICKETS": [{"Tickets": "ALI MR=0991234567890 SARA MISS=0991234567891"}]}
    c, mock = client({"ETIssueJS": ans})
    first, second = c.issue("ABC123", "ops@example.test"), c.issue("ABC123", "ops@example.test")
    assert first == second == [("ALI MR", "0991234567890"), ("SARA MISS", "0991234567891")] and mock.count("ETIssueJS") == 2
    assert dict(mock.requests[0].url.params)[nn.P_EMAIL] == "ops@example.test"
    c, mock = client({"ETIssueJS": {"AirNRSTICKETS": [{"ALI MR": "0991234567890"}]}})
    assert c.issue("ABC123", "x@example.test") == [("ALI MR", "0991234567890")]
    c, mock = client({"ETIssueJS": httpx.ConnectError("x")})
    with pytest.raises(NiraError):
        c.issue("ABC123", "x@example.test")
    assert mock.count("ETIssueJS") == 1                                      # issue is never retried
    c, _ = client({"ETIssueJS": {"AirNRSTICKETS": []}})
    with pytest.raises(NiraError) as e:
        c.issue("ABC123", "x@example.test")
    assert e.value.code == "ISSUE_NO_TICKETS" and e.value.ambiguous


def test_cancel_pnr_and_seat():
    c, _ = client({"CancelPNRJS": [{"AirCancelPNR": [{"Error": "No Error COMMAND PNR CANCELLED"}]}, {"AirCancelPNR": [{"Error": "Already Cancelled"}]}]})
    assert c.cancel_pnr("ABC123") == "cancelled" and c.cancel_pnr("ABC123") == "already_cancelled"
    c, _ = client({"CancelPNRJS": {"AirCancelPNR": [{"Error": "PNR Is Cancelled"}]}})
    with pytest.raises(NiraError) as e:
        c.cancel_pnr("ABC123")
    assert e.value.code == "PNR_CANCELLED"
    c, mock = client({"CancelSeatJS": {"AirCancelSeat": [{"Done": "true", "NewSplittedPNR": "NEW111"}]}})
    assert c.cancel_seat("ABC123", "ALI", "TESTI", DAY, "1001") == {"done": True, "new_pnr": "NEW111"}
    assert dict(mock.requests[0].url.params)["DepartureDate"] == "2030-01-15"


def test_retrieve_pnr_and_credit_command():
    c, mock = client({"NRSRT.jsp": {"PNR": "ABC123", "Status": "HK"}, "NRSCommand.jsp": "CREDIT 1000000 BLOCKED 0"})
    assert c.retrieve_pnr("ABC123")["Status"] == "HK"
    assert "CREDIT" in c.credit_balance() and dict(mock.requests[-1].url.params)[nn.P_COMMAND] == "CRD"


# ---------------------------------------------------------------- errors
@pytest.mark.parametrize("text,code", [
    ("FLIGHT CLOSED", "FLIGHT_CLOSED"), ("CLASS CLOSED", "CLASS_CLOSED"), ("INVALID FLIGHT", "INVALID_FLIGHT"), ("POINT OF SALES RESTRICTED", "POS_RESTRICTED"),
    ("NOT ENOUGH CREDIT", "NOT_ENOUGH_CREDIT"), ("SSR DOCS IS MANDATORY FOR PASSENGER 1", "DOCS_MANDATORY"), ("INVALID DOCS NUMBER(S)", "INVALID_DOCS"),
    ("DUPLICATE NATIONAL CODES", "DUPLICATE_NATIONAL_CODES"), ("INVALID PASSPORT INFORMATION", "INVALID_PASSPORT"),
    ("PASSPORT DOCS SSR IS MANDATORY FOR INTERNATIONAL FLIGHTS", "PASSPORT_MANDATORY"), ("Access Denied", "ACCESS_DENIED"),
    ("User Account has been expired", "ACCOUNT_EXPIRED"), ("Invalid User Name", "INVALID_USER"), ("Incorrect Password", "INCORRECT_PASSWORD"),
    ("Sales Channel not Allowed", "SALES_CHANNEL_NOT_ALLOWED"), ("REMOTE USER NOT REGISTERED", "REMOTE_USER_NOT_REGISTERED"), ("SIGN!", "SIGN"),
    ("Invalid Passenger Name", "INVALID_PASSENGER_NAME"), ("Invalid Passengers Contact", "INVALID_CONTACT"), ("InCorrect Contact", "INVALID_CONTACT"),
    ("Invalid Ticket Number", "INVALID_TICKET"), ("Ticket Number not Found", "TICKET_NOT_FOUND"), ("PNR is already Ticketed", "ALREADY_TICKETED"),
    ("PNR Is Cancelled", "PNR_CANCELLED"), ("Already Cancelled", "ALREADY_CANCELLED"), ("NO ELECTRONIC TICKET LOADED YET", "NO_ETICKET_YET"),
    ("Reservation Failur", "RESERVATION_FAILURE"), ("Child or Infant without parents", "CHILD_WITHOUT_ADULT"), ("INVALIDDESTINATION", "INVALID_DESTINATION")])
def test_documented_errors_map_to_typed_codes_with_persian_messages(text, code):
    assert nn.map_error(text) == code
    c, _ = client({"AvailabilityFareJS.jsp": {"AvailableFlights": [], "Error": text}})
    with pytest.raises(NiraError) as e:
        c.availability_fare("THR", "MHD", DAY)
    assert e.value.code == code and e.value.message_fa and e.value.message_fa != nn.MESSAGES_FA["NRS_ERROR"]


def test_plain_text_and_http_errors():
    c, _ = client({"AvailabilityFareJS.jsp": "Sales Channel not Allowed"})
    with pytest.raises(NiraError) as e:
        c.availability_fare("THR", "MHD", DAY)
    assert e.value.code == "SALES_CHANNEL_NOT_ALLOWED" and e.value.category == "account"
    c, _ = client({"AvailabilityFareJS.jsp": (500, "<html>boom</html>")})
    with pytest.raises(NiraError) as e:
        c.availability_fare("THR", "MHD", DAY)
    assert e.value.code == "NRS_ERROR" and e.value.status == 500


def test_reads_retry_transport_errors_only():
    c, mock = client({"AvailabilityFareJS.jsp": [httpx.ConnectError("x"), (503, "busy"), AVAIL]})
    assert len(c.availability_fare("THR", "MHD", DAY).flights) == 1 and mock.count("AvailabilityFareJS") == 3
    c, mock = client({"AvailabilityFareJS.jsp": {"Error": "Access Denied"}})
    with pytest.raises(NiraError):
        c.availability_fare("THR", "MHD", DAY)
    assert mock.count("AvailabilityFareJS") == 1


# ---------------------------------------------------------------- passengers
def test_edt_id_builder_and_composition_rules():
    assert nn.edt_id(ADULT) == "I__0012345679__21MAY90_M__TESTI_ALI"
    full = Passenger("ADT", "Maryam", "Testi", "F", date(1995, 1, 28), "P", "X1234567", issued_by="IRN", birth_country="IRN", expiry=date(2031, 3, 2), title="MRS")
    assert nn.edt_id(full) == "P_IRN_X1234567_IRN_28JAN95_F_02MAR31_TESTI_MARYAM" and nn.title_for(full) == "MRS"
    with pytest.raises(ValueError):
        nn.edt_id(Passenger("ADT", "Ali", "Testi", "M", date(1990, 1, 1), "I", "0012345678"))        # bad check digit
    with pytest.raises(ValueError):
        nn.edt_id(Passenger("ADT", "Ali", "Testi", "M", date(1990, 1, 1), "P", "X1234567"))          # passport without country/expiry
    child = Passenger("CHD", "Reza", "Testi", "M", date(2022, 1, 1), "I", "0012345687")
    with pytest.raises(ValueError):
        nn.reserve_params([child, ADULT], DAY)                                                       # first must be an adult
    with pytest.raises(ValueError):
        nn.reserve_params([ADULT] + [child] * 5, DAY)                                                # > 4 dependants per adult
    with pytest.raises(ValueError):
        nn.reserve_params([ADULT] * 10, DAY)
    with pytest.raises(ValueError):
        nn.reserve_params([ADULT, ADULT], DAY)                                                       # duplicate national ID
    p = nn.reserve_params([ADULT, child], DAY)
    assert p["No"] == 2 and p["edtAge1"] == 39 and p["edtName2"] == "REZA MR"
    assert nn.ddmmmyy(date(1995, 1, 28)) == "28JAN95"


# ---------------------------------------------------------------- configuration and safety
def test_mode_and_airline_configuration(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("NIRA_"):
            monkeypatch.delenv(k)
    assert nn.nira_mode() == ("off", "off")
    monkeypatch.setenv("NIRA_MODE", "prod")
    assert nn.nira_mode() == ("off", "invalid_mode")
    monkeypatch.setenv("NIRA_AIRLINES", "a1, VAR ,JI,TBN,W5,ZZ")
    assert nn.requested_airlines() == ["A1", "VR", "J1", "HH", "W5", "ZZ"]
    assert nn.airline_config("VR", "sandbox")[1] == "sandbox_only_a1"
    assert nn.airline_config("A1", "live")[1] == "test_airline_in_live"
    assert nn.airline_config("ZZ", "live")[1] == "unknown_airline"
    cfg_, why, missing = nn.airline_config("VR", "live")
    assert cfg_ is None and why == "missing_credentials" and missing == ["NIRA_VR_USER", "NIRA_VR_PASS"]
    assert nn.airline_config("W5", "live")[2] == ["NIRA_W5_HOST", "NIRA_W5_USER", "NIRA_W5_PASS"]
    monkeypatch.setenv("NIRA_VR_USER", USER)
    monkeypatch.setenv("NIRA_VR_PASS", PASS)
    cfg_, why, _ = nn.airline_config("VR", "live")
    assert why == "ok" and cfg_.ws2("ReservJS") == "https://api.vareshair.ir/ws2/cgi-bin/NRSWebWS.cgi/ReservJS" and PASS not in repr(cfg_) and USER not in repr(cfg_)
    monkeypatch.setenv("NIRA_VR_HOST", "http://api.vareshair.ir")
    assert nn.airline_config("VR", "live")[1] == "host_not_allowed"
    monkeypatch.setenv("NIRA_VR_HOST", "https://evil.example/path?x=1")
    assert nn.airline_config("VR", "live")[1] == "invalid_host"
    monkeypatch.delenv("NIRA_VR_HOST")
    monkeypatch.setenv("NIRA_VR_ROUTES", "THR-MHD, mhd-thr")
    cfg_ = nn.airline_config("VR", "live")[0]
    assert cfg_.flies("THR", "MHD") and cfg_.flies("MHD", "THR") and not cfg_.flies("THR", "KIH")
    monkeypatch.setenv("NIRA_A1_USER", USER)
    monkeypatch.setenv("NIRA_A1_PASS", PASS)
    monkeypatch.setenv("NIRA_A1_HOST", "https://api.vareshair.ir")
    assert nn.airline_config("A1", "sandbox")[1] == "host_not_allowed"
    monkeypatch.delenv("NIRA_A1_HOST")
    assert nn.airline_config("A1", "sandbox")[0].ws1("NRSRT.jsp") == "http://a1.nirasoft.ir/ws1/NRSRT.jsp"


def test_sandbox_client_only_reaches_a1_host():
    c, mock = client({"AvailabilityFareJS.jsp": AVAIL}, mode="sandbox", config=cfg("VR", "api.vareshair.ir", "https"))
    with pytest.raises(NiraError) as e:
        c.availability_fare("THR", "MHD", DAY)
    assert e.value.code == "HOST_NOT_ALLOWED" and mock.requests == []
    c, mock = client({"AvailabilityFareJS.jsp": AVAIL}, mode="live", config=cfg())
    with pytest.raises(NiraError):
        c.availability_fare("THR", "MHD", DAY)
    assert mock.requests == []
    with pytest.raises(ValueError):
        NiraClient("off", cfg())


def test_credentials_never_appear_in_logs_or_errors(caplog):
    caplog.set_level(logging.DEBUG)
    echo = f"<html>Login failed OfficeUser={USER}&OfficePass={PASS} Incorrect Password</html>"
    c, mock = client({"AvailabilityFareJS.jsp": [(403, echo)], "ReservJS": httpx.ConnectError(f"cannot reach ?OfficePass={PASS}"),
                      "NRSRT.jsp": f"oops OfficePass={PASS}"})
    errors = []
    for call in (lambda: c.availability_fare("THR", "MHD", DAY), lambda: c._send("ReservJS", c.cfg.ws2("ReservJS"), {}), lambda: c.retrieve_pnr("ABC123")):
        with pytest.raises(NiraError) as e:
            call()
        errors.append(e.value)
    assert errors[0].code == "INCORRECT_PASSWORD" and errors[1].code == "NETWORK"
    # the request really carried the credentials (NRS design) …
    assert dict(mock.requests[0].url.params)[nn.P_PASS] == PASS
    # … but nothing we produce shows them: log records, exception text, repr, chained causes
    blob = "\n".join(r.getMessage() for r in caplog.records) + "\n".join(f"{e!s}{e!r}{e.nrs_text}{e.__cause__!r}{e.__context__!r}" for e in errors) + repr(c)
    assert PASS not in blob and USER not in blob and "OfficePass=s3" not in blob
    assert any(r.name == "httpx" for r in caplog.records), "httpx request log line is produced and must be redacted"
    assert all("?" not in r.getMessage() or "?[redacted]" in r.getMessage() for r in caplog.records if r.name == "httpx")
    assert all(e.__cause__ is None and e.__context__ is None for e in errors)


def test_redact_helper():
    s = nn.redact(f"OfficeUser={USER}&OfficePass={PASS}&x=1 {{\"OfficePass\": \"{PASS}\"}}", PASS)
    assert PASS not in s and USER not in s and "x=1" in s
