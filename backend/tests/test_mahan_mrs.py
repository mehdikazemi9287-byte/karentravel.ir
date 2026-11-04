"""Mahan MRS client: request shape (header key, URLs per env), parsing, DOCS, cert scenario passengers."""
from decimal import Decimal
import json

import httpx
import pytest

from app import mahan_cert as mc
from app.mahan_mrs import MahanClient, MahanError, docs_text, parse_availability, refund_inputs, seats

AVAIL = {"AvailableFlights": [{"FlightNo": "1063", "Origin": "THR", "Destination": "MHD", "DepartureDateTime": "2026-12-01 07:30", "ArrivalDateTime": "2026-12-01 09:00",
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


def test_client_requests(monkeypatch):
    monkeypatch.delenv("MAHAN_QAA_API_KEY", raising=False)
    with pytest.raises(MahanError):
        MahanClient(env="qaa")
    fake = Fake({"AvailabilityFareJS": (200, AVAIL), "FareQuote": (200, QUOTE), "Res/Book": (200, {"result": {"PNR": "ABC123"}, "errorCode": 0})})
    cli = MahanClient(env="qaa", api_key="k-123", transport=fake)
    cli.availability("THR", "MHD", "2026-12-01", 1)
    m, url, _, h = fake.calls[-1]
    assert m == "GET" and url.startswith("https://api.mahanair.co.ir/ws1-qaa/AvailabilityFareJS.jsp?AirLine=W5&cbSource=THR") and h["X-API-Key"] == "k-123" and "k-123" not in url
    q = cli.fare_quote([{"Origin": "THR", "Destination": "MHD", "FlightClass": "Y", "Departure": "2026-12-01", "FlightNo": "1063"}], 1, 0, 1)
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
    segs = [{"FlightNo": "1063", "DepartureDate": "2026-12-01"}, {"FlightNo": "1064", "DepartureDate": "2026-12-05"}]
    p = mc.passengers("domestic", 1, 1, 1, segs)
    assert [x["AgeType"] for x in p] == ["AD", "CH"]                      # infant is an INFT SSR, not a passenger
    assert sum(1 for s in p[0]["SSRs"] if s["SSRType"] == "INFT") == 2 and p[0]["SSRs"][0]["FreeText"].startswith("I/IRN/0050298750")
    assert mc.passengers("international", 2, 0, 0, segs[:1])[1]["SSRs"][0]["FreeText"].startswith("P/IRN/T97648553")
    monkeypatch.setenv("MAHAN_ENV", "live")
    assert mc.main([]) == 2                                                  # never against Live
    monkeypatch.setenv("MAHAN_ENV", "qaa")
    monkeypatch.setenv("MAHAN_QAA_API_KEY", "k")
    fake = Fake({"AvailabilityFareJS": (200, AVAIL), "FareQuote": (200, QUOTE), "Res/Book": (200, {"result": {"PNR": "PNR777"}, "errorCode": 0})})
    monkeypatch.setattr(mc, "MahanClient", lambda env: MahanClient(env=env, api_key="k", transport=fake))
    assert mc.main(["--only", "1,5"]) == 0
    out = capsys.readouterr().out
    assert "PNR777" in out and "64000000 IRR" in out and "MAHAN-CERT-DONE 2/2" in out
