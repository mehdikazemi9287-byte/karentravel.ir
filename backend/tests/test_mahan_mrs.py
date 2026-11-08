"""Mahan MRS client: request shape (header key, URLs per env), parsing, DOCS, cert scenario passengers."""
from datetime import timedelta
from decimal import Decimal
import json

import httpx
import pytest

from app import mahan_cert as mc
from app.mahan_mrs import MahanClient, MahanError, docs_text, error_text, parse_availability, parse_quote, redact, refund_inputs, seats

# Dates relative to the runner's "today" (mc._today) so the tests never expire: the runner drops flights before today.
OUT_DAY = (mc._today() + timedelta(days=10)).isoformat()
BACK_DAY = (mc._today() + timedelta(days=14)).isoformat()          # default --stay 4

AVAIL = {"AvailableFlights": [{"FlightNo": "1063", "Origin": "THR", "Destination": "MHD", "DepartureDateTime": f"{OUT_DAY} 07:30", "ArrivalDateTime": f"{OUT_DAY} 09:00",
                               "ClassesStatus": [{"FlightClass": "Y", "Cap": "YA", "Price": "35000000", "CurrencyCode": "IRR"}, {"FlightClass": "B", "Cap": "BX", "Price": "-", "CurrencyCode": "IRR"},
                                                 {"FlightClass": "C", "Cap": "C2", "Price": "0", "CurrencyCode": "IRR"}]}]}
QUOTE = {"errorCode": 0, "result": {"Currency": "IRR", "TotalFare": "60000000", "TotalTax": "4000000", "TotalPrice": "64000000", "Coupons": [{"CouponNo": 1}],
         "PassengerBreakdown": [{"AgeType": "AD", "Quantity": 1, "Taxes": [{"TaxType": "YQ", "TaxAmount": "1000000", "TotalTaxAmount": "1000000"}, {"TaxType": "LP", "TotalTaxAmount": "3000000"}]}]}}


class Fake:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, json=None, headers=None):
        self.calls.append((method, url, json, headers))
        for key, (status, body) in self.routes.items():
            if key in url:
                return httpx.Response(status, content=json_dumps(body), headers={"content-type": "application/json"})
        return httpx.Response(404)


def json_dumps(b):
    return json.dumps(b).encode()


def test_parsing_and_helpers():
    f = parse_availability(AVAIL)
    assert len(f) == 1 and f[0].flight_no == "1063"
    assert [c.rbd for c in f[0].open_classes(business=False)] == ["Y"] and [c.rbd for c in f[0].open_classes(business=True)] == ["C"]
    assert f[0].classes[1].price is None and seats("Y5") == 5 and seats("YC") == 0
    assert docs_text("I", "IRN", "0050298750", "IRN", "07JAN86", "F", "16NOV28", "test", "test") == "I/IRN/0050298750/IRN/07JAN86/F/16NOV28/TEST/TEST"
    with pytest.raises(ValueError):
        docs_text("P", "IRN", "X", "IRN", "1986-01-07", "F", "16NOV28", "T", "T")
    assert refund_inputs({"Fare": "100", "TAXES": [{"TaxCode": "LP", "TaxAmount": "5"}, {"TaxCode": "YQ", "TaxAmount": "7"}, {"TaxCode": "KU", "TaxAmount": "3"}]}) == (Decimal(100), Decimal(10), Decimal(5))


def test_office_auth_b64_key_and_sign(monkeypatch):
    import base64
    monkeypatch.setenv("MAHAN_QAA_API_KEY_B64", base64.b64encode(b"k$1$2").decode())
    monkeypatch.setenv("MAHAN_QAA_OFFICE_USER", "THR1.WS")
    monkeypatch.setenv("MAHAN_QAA_OFFICE_PASS", "p@$$w")
    fake = Fake({"AvailabilityFareJS": (200, AVAIL)})
    cli = MahanClient(env="qaa", transport=fake)
    assert cli.key == "k$1$2"
    cli.availability("THR", "KIH", OUT_DAY, 1)
    url = fake.calls[-1][1]
    assert "OfficeUser=THR1.WS" in url and "OfficePass=p%40%24w" in url
    sign = MahanClient(env="qaa", transport=lambda m, u, json=None, headers=None: httpx.Response(200, content=b"SIGN", headers={"content-type": "application/json"}))
    with pytest.raises(MahanError) as e:
        sign.availability("THR", "KIH", OUT_DAY, 1)
    assert e.value.code == "SIGN"


def test_client_requests(monkeypatch):
    monkeypatch.delenv("MAHAN_QAA_API_KEY", raising=False)
    monkeypatch.delenv("MAHAN_QAA_API_KEY_B64", raising=False)
    with pytest.raises(MahanError):
        MahanClient(env="qaa")
    fake = Fake({"AvailabilityFareJS": (200, AVAIL), "FareQuote": (200, QUOTE), "Res/Book": (200, {"result": {"PNR": "ABC123"}, "errorCode": 0})})
    cli = MahanClient(env="qaa", api_key="k-123", transport=fake)
    cli.availability("THR", "MHD", OUT_DAY, 1)
    m, url, _, h = fake.calls[-1]
    assert m == "GET" and url.startswith("https://api.mahanair.co.ir/ws1-qaa/AvailabilityFareJS.jsp?AirLine=W5&cbSource=THR") and h["X-API-Key"] == "k-123" and "k-123" not in url
    q = cli.fare_quote([{"Origin": "THR", "Destination": "MHD", "FlightClass": "Y", "Departure": OUT_DAY, "FlightNo": "1063"}], 1, 0, 1)
    assert q.total_price == Decimal(64000000) and q.surcharge == Decimal(1000000)
    assert fake.calls[-1][2]["Passengers"] == [{"AgeType": "AD", "Quantity": 1}, {"AgeType": "IN", "Quantity": 1}] and fake.calls[-1][2]["Segments"][0]["AirlineCode"] == "W5"
    assert cli.book([{"Origin": "THR"}], [], "+989121234567") == "ABC123" and fake.calls[-1][1] == "https://api.mahanair.co.ir/ws2-qaa/Res/Book"
    bad = MahanClient(env="qaa", api_key="k", transport=Fake({"FareQuote": (200, {"errorCode": 1, "description_en": "FARE NOT FOUND"})}))
    with pytest.raises(MahanError, match="FARE NOT FOUND"):
        bad.fare_quote([{}], 1)
    down = MahanClient(env="qaa", api_key="k", transport=Fake({"FareQuote": (503, {})}))
    with pytest.raises(MahanError) as e:
        down.fare_quote([{}], 1)
    assert e.value.code == "UNAVAILABLE"


def test_cert_passengers_and_runner(monkeypatch, capsys):
    segs = [{"FlightNo": "1063", "DepartureDate": OUT_DAY}, {"FlightNo": "1064", "DepartureDate": BACK_DAY}]
    p = mc.passengers("domestic", 1, 1, 1, segs)
    assert [x["AgeType"] for x in p] == ["AD", "CH"]                      # infant is an INFT SSR, not a passenger
    assert sum(1 for s in p[0]["SSRs"] if s["SSRType"] == "INFT") == 2 and p[0]["SSRs"][0]["FreeText"].startswith("I/IRN/")
    two = mc.passengers("international", 2, 0, 0, segs)
    docs = [x["SSRs"][0]["FreeText"].split("/")[2] for x in two]
    assert docs[0] != docs[1] and all(d.startswith("T") and len(d) == 9 for d in docs)
    assert two[0]["SSRs"][0]["FreeText"] == two[0]["SSRs"][-1]["FreeText"]          # same document on every segment
    import random as _r
    nc = mc.national_code(_r.Random(1))
    assert len(nc) == 10 and int(nc[9]) == (lambda r: r if r < 2 else 11 - r)(sum(int(nc[i]) * (10 - i) for i in range(9)) % 11)
    monkeypatch.setenv("MAHAN_ENV", "live")
    assert mc.main([]) == 2                                                  # never against Live
    monkeypatch.setenv("MAHAN_ENV", "qaa")
    monkeypatch.setenv("MAHAN_QAA_API_KEY", "k")
    def send(method, url, json=None, headers=None):
        if "AvailabilityFareJS" in url:
            return httpx.Response(200, content=json_dumps(AVAIL), headers={"content-type": "application/json"})
        if "FareQuote" in url:
            biz = json["Segments"][0]["FlightClass"] == "C"
            q = {**QUOTE, "result": {**QUOTE["result"], "Cabin": "C" if biz else "Y"}}
            return httpx.Response(200, content=json_dumps(q), headers={"content-type": "application/json"})
        return httpx.Response(200, content=json_dumps({"result": {"PNR": "PNR777"}, "errorCode": 0}), headers={"content-type": "application/json"})
    monkeypatch.setattr(mc, "MahanClient", lambda env: MahanClient(env=env, api_key="k", transport=send))
    assert mc.main(["--only", "1,5"]) == 0
    out = capsys.readouterr().out
    assert "PNR777" in out and "64000000 IRR" in out and "MAHAN-CERT-DONE 2/2" in out
    assert "W5 1063 (C)" not in out and "W51063 (C)" in out and "W51063 (Y)" in out   # scenario 5 business = class C, scenario 1 economy = Y
    assert mc.is_business("C+C") and not mc.is_business("Y") and not mc.is_business("")


def test_book_refusal_keeps_every_reason_and_the_request():
    refusal = {"errorCode": 1, "description_fa": "رزرو انجام نشد.", "description_en": "", "result": {"Errors": [{"Message": "DUPLICATE NAME ON FLIGHT"}]}}
    cli = MahanClient(env="qaa", api_key="secret-key", transport=Fake({"Res/Book": (200, refusal)}))
    with pytest.raises(MahanError) as e:
        cli.book([{"Origin": "IKA", "FlightNo": "51"}], [{"FirstName": "TESTA"}], "+989121234567")
    assert "رزرو انجام نشد." in str(e.value) and "DUPLICATE NAME ON FLIGHT" in str(e.value) and e.value.code == "1"
    assert e.value.payload == refusal and e.value.request["Passengers"] == [{"FirstName": "TESTA"}] and "secret-key" not in json.dumps(e.value.request)
    bad = MahanClient(env="qaa", api_key="k", transport=Fake({"Res/Book": (400, {"title": "Passengers[1].Title is invalid"})}))
    with pytest.raises(MahanError, match="Title is invalid") as e:
        bad.book([{}], [{}], "+98")
    assert e.value.status == 400 and e.value.request is not None


def test_cert_passengers_unique_names_and_ages():
    from datetime import date
    segs = [{"FlightNo": "51", "DepartureDate": "2026-11-20"}, {"FlightNo": "50", "DepartureDate": "2026-11-24"}]
    p = mc.passengers("international", 1, 1, 1, segs, tag="QWER", travel=date(2026, 11, 20))
    assert p[0]["FirstName"] == "TESTQWERA" and p[1]["FirstName"] == "TESTCHDQWERA" and p[1]["Title"] == "MR"
    assert p[1]["SSRs"][0]["FreeText"].split("/")[4] == "20NOV19"                      # child 7 years old
    inft = [s["FreeText"] for s in p[0]["SSRs"] if s["SSRType"] == "INFT"]
    assert inft == ["TEST/TESTINFQWERA 20FEB26"] * 2                                     # infant 9 months old
    iata = mc.passengers("international", 1, 1, 1, segs, tag="QWER", travel=date(2026, 11, 20), variant="iata")
    inf_docs = [s["FreeText"] for s in iata[0]["SSRs"] if s["SSRType"] == "DOCS" and "/FI/" in s["FreeText"]]
    assert len(inf_docs) == 2 and inf_docs[0].endswith("/TEST/TESTINFQWERA") and iata[1]["Title"] == "MSTR"
    docs = {s["FreeText"].split("/")[2] for x in iata for s in x["SSRs"] if s["SSRType"] == "DOCS"}
    assert len(docs) == 3                                                                # adult, infant, child: all different


def test_cert_runner_learns_cabin_retries_variant_and_dumps(monkeypatch, capsys):
    avail = {"AvailableFlights": [{"FlightNo": "51", "Origin": "IKA", "Destination": "BKK", "DepartureDateTime": f"{OUT_DAY} 02:00",
                                   "ClassesStatus": [{"FlightClass": c, "Cap": c + "9"} for c in ("BK", "Y", "R")]},
                                  {"FlightNo": "50", "Origin": "BKK", "Destination": "IKA", "DepartureDateTime": f"{BACK_DAY} 10:00",
                                   "ClassesStatus": [{"FlightClass": c, "Cap": c + "9"} for c in ("BK", "Y", "R")]}]}
    quoted, booked = [], []

    def send(method, url, json=None, headers=None):
        ok = lambda b: httpx.Response(200, content=json_dumps(b), headers={"content-type": "application/json"})
        if "AvailabilityFareJS" in url:
            return ok(avail)
        if "FareQuote" in url:
            rbd = json["Segments"][0]["FlightClass"]
            quoted.append(rbd)
            if rbd == "Y":
                return ok({"errorCode": 1, "description_fa": "نرخ یافت نشد."})
            return ok({**QUOTE, "result": {**QUOTE["result"], "Cabin": "C+C" if rbd == "R" else "Y+Y"}})
        child = [p for p in json["Passengers"] if p["AgeType"] == "CH"]
        booked.append([p["FirstName"] for p in json["Passengers"]])
        if child and child[0]["Title"] != "MSTR":
            return ok({"errorCode": 1, "description_fa": "رزرو انجام نشد.", "description_en": "CHILD TITLE INVALID"})
        return ok({"result": {"PNR": f"PNR{len(booked)}"}, "errorCode": 0})

    monkeypatch.setenv("MAHAN_ENV", "qaa")
    monkeypatch.setattr(mc, "MahanClient", lambda env: MahanClient(env=env, api_key="k", transport=send))
    assert mc.main([], default_only="6,7,8") == 0
    out = capsys.readouterr().out
    assert "scenario 5" not in out and "MAHAN-CERT-DONE 3/3" in out
    assert quoted == ["R", "BK", "R"]                          # 6: hint R first; 7: R learnt as business, skipped; 8: R again
    assert "CHILD TITLE INVALID" in out and "==MAHAN-BOOK-FAIL== scenario 7" in out and '"Title": "MR"' in out
    names = [n for b in booked for n in b]
    assert len(names) == len(set(names))                       # fresh names on every Book


def _ok(b):
    return httpx.Response(200, content=json_dumps(b), headers={"content-type": "application/json"})


IKA_BKK = {"AvailableFlights": [{"FlightNo": "51", "Origin": "IKA", "Destination": "BKK", "DepartureDateTime": f"{OUT_DAY} 02:00",
                                 "ClassesStatus": [{"FlightClass": c, "Cap": c + "9"} for c in ("Y", "R")]},
                                {"FlightNo": "50", "Origin": "BKK", "Destination": "IKA", "DepartureDateTime": f"{BACK_DAY} 10:00",
                                 "ClassesStatus": [{"FlightClass": c, "Cap": c + "9"} for c in ("Y", "R")]}]}


def test_cert_stops_on_ambiguous_book(monkeypatch, capsys):
    books = []

    def send(method, url, json=None, headers=None):
        if "AvailabilityFareJS" in url:
            return _ok(IKA_BKK)
        if "FareQuote" in url:
            return _ok({**QUOTE, "result": {**QUOTE["result"], "Cabin": "Y+Y"}})
        books.append(json)
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setenv("MAHAN_ENV", "qaa")
    monkeypatch.setattr(mc, "MahanClient", lambda env: MahanClient(env=env, api_key="k", transport=send))
    assert mc.main(["--only", "7"]) == 1
    out = capsys.readouterr().out
    assert len(books) == 1                                         # never re-booked with fresh names
    assert "Book outcome unknown (timeout/network)" in out and "check manually before re-running" in out
    assert "==MAHAN-BOOK-FAIL== scenario 7" in out and "FAILED: Book outcome unknown" in out


def test_cert_nofare_is_scoped_to_route_and_passengers():
    learnt = mc.Learnt()
    rejected = set()

    def send(method, url, json=None, headers=None):
        if "AvailabilityFareJS" in url:
            return _ok(IKA_BKK)
        if "FareQuote" in url:
            pax = tuple((p["AgeType"], p["Quantity"]) for p in json["Passengers"])
            rbd = json["Segments"][0]["FlightClass"]
            if pax == (("AD", 2),) or rbd == "R":                  # no fare for 2 adults; R never priced in this fake
                rejected.add((pax, rbd))
                return _ok({"errorCode": 1, "description_en": "FARE NOT FOUND"})
            return _ok({**QUOTE, "result": {**QUOTE["result"], "Cabin": "Y+Y"}})
        return _ok({"result": {"PNR": "PNRX"}, "errorCode": 0})

    cli = MahanClient(env="qaa", api_key="k", transport=send)
    routes = {"international": ("IKA", "BKK"), "domestic": ("THR", "KIH")}
    days = [OUT_DAY, (mc._today() + timedelta(days=11)).isoformat()]
    with pytest.raises(MahanError):
        mc.run_one(cli, (6, "2 adult", "international", True, 2, 0, 0, False), routes, days, 4, "+98", learnt)
    assert learnt.nofare.get(("IKA", "BKK", 2, 0, 0, ("Y", "Y")), 0) >= 1 and all(k[2:5] == (2, 0, 0) for k in learnt.nofare)
    row = mc.run_one(cli, (7, "1 adult 1 child", "international", True, 1, 1, 0, False), routes, days, 4, "+98", learnt)
    assert row["Booking ReferenceID (PNR)"] == "PNRX" and "(Y)" in row["Flight no"]    # 2-adult no-fare did not exclude Y


def test_non_dict_answers_raise_mahan_error():
    for bad in ([1, 2], "oops", None, 7):
        with pytest.raises(MahanError) as e:
            parse_quote(bad)
        assert e.value.code == "BAD_RESPONSE" and e.value.payload == bad
    with pytest.raises(MahanError) as e:
        parse_quote({"errorCode": 0, "result": ["x"]})
    assert e.value.code == "BAD_RESPONSE"
    for bad in ("oops", 7, None):
        with pytest.raises(MahanError) as e:
            parse_availability(bad)
        assert e.value.payload == bad
    assert parse_availability([]) == []
    cli = MahanClient(env="qaa", api_key="k", transport=Fake({"FareQuote": (200, ["not", "a", "dict"])}))
    with pytest.raises(MahanError, match="unexpected answer"):
        cli.fare_quote([{}], 1)


def test_http_error_is_redacted_and_success_message_is_not_a_reason(monkeypatch):
    monkeypatch.setenv("MAHAN_QAA_OFFICE_PASS", "s3cretP")
    page = "Bad request: AvailabilityFareJS.jsp?AirLine=W5&OfficeUser=THR1.WS&OfficePass=s3cretP&cbSource=THR password: hunter2 key=k-999"
    cli = MahanClient(env="qaa", api_key="k-999", transport=lambda m, u, json=None, headers=None: httpx.Response(400, content=page.encode()))
    with pytest.raises(MahanError) as e:
        cli.availability("THR", "KIH", OUT_DAY, 1)
    for leaked in ("s3cretP", "hunter2", "k-999"):
        assert leaked not in str(e.value) and leaked not in e.value.payload
    assert "OfficePass=***" in e.value.payload and "OfficeUser=THR1.WS" in e.value.payload
    assert redact('{"OfficePass": "abc", "Passengers": 2}') == '{"OfficePass": "***", "Passengers": 2}'
    assert error_text({"SuccessMessage": "OK", "errorCode": "1", "Errors": [{"Message": "NO SEAT"}]}) == "NO SEAT"


def test_only_rejects_bad_ids(monkeypatch, capsys):
    monkeypatch.setenv("MAHAN_ENV", "qaa")
    monkeypatch.setattr(mc, "MahanClient", lambda env: MahanClient(env=env, api_key="k", transport=lambda *a, **k: _ok({})))
    for bad in ("6,x", "9"):
        with pytest.raises(SystemExit) as e:
            mc.main(["--only", bad])
        assert e.value.code == 2 and "--only" in capsys.readouterr().err
