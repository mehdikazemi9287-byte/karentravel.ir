"""Mahan MRS certification run (QAA only): the 8 scenarios of TestScenarios_W56 — search, FareQuote, Book; no ticketing.

    MAHAN_ENV=qaa MAHAN_QAA_API_KEY=... python -m app.mahan_cert [--days 21] [--domestic THR-MHD] [--international IKA-IST]

Prints the filled sheet as CSV (same columns as Mahan's sheet) between ==MAHAN-CERT-CSV== markers, plus one line per
step so a failure can be sent to Mahan support. Passengers are the synthetic TEST records from Mahan's SSR sample.
Refuses to run against Live.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
from datetime import date, timedelta

from typing import Optional

from .mahan_mrs import Flight, MahanClient, MahanError, docs_text

SCENARIOS = [  # (id, title, scope, round_trip, adults, children, infants, business)
    (1, "Booking for oneway , single segment, 1 adult", "domestic", False, 1, 0, 0, False),
    (2, "Booking for oneway , single segment, 2 adult", "domestic", False, 2, 0, 0, False),
    (3, "Booking for round trip , single segment, 1 adult, 1 child", "domestic", True, 1, 1, 0, False),
    (4, "Booking for oneway , single segment, 1 adult, 1 child, 1 infant", "domestic", False, 1, 1, 1, False),
    (5, "Booking for round trip, 1 adult/Business  class", "international", True, 1, 0, 0, True),
    (6, "Booking for return, single segment, 2 adult/Business  class", "international", True, 2, 0, 0, True),
    (7, "Booking for round trip single segment, 1 adult, 1 child", "international", True, 1, 1, 0, False),
    (8, "Booking for return, single segment, 1 adult, 1 child, 1 infant/Business  class", "international", True, 1, 1, 1, True),
]
COLUMNS = ["ID", "Test Case", "Departure date", "Return date", "Flight no", "Total Fare", "Total Tax", "Base Price", "Total Surcharge", "Payment Amount and Currency", "Booking ReferenceID (PNR)"]


def log(msg: str) -> None:
    print(msg, flush=True)


def _docs(scope: str, gender: str, dob: str, surname: str, given: str) -> str:
    if scope == "domestic":
        return docs_text("I", "IRN", "0050298750", "IRN", dob, gender, "16NOV28", surname, given)
    return docs_text("P", "IRN", "T97648553", "IRN", dob, gender, "16NOV28", surname, given)


def passengers(scope: str, adults: int, children: int, infants: int, segments: list[dict]) -> list[dict]:
    out = []
    names = ["TESTA", "TESTB", "TESTC", "TESTD"]
    for i in range(adults):
        given, gender = names[i], ("F" if i == 0 else "M")
        ssrs = [{"SSRType": "DOCS", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": _docs(scope, gender, "07JAN86", "TEST", given)} for s in segments]
        if i == 0 and infants:
            ssrs += [{"SSRType": "INFT", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": "TESTINFANT/TESTINFANT 10JAN26"} for s in segments]
        out.append({"FirstName": given, "LastName": "TEST", "AgeType": "AD", "Title": "MS" if gender == "F" else "MR", "Parent": "", "SSRs": ssrs})
    for i in range(children):
        given = "TESTCHILD" + "ABCD"[i]
        ssrs = [{"SSRType": "DOCS", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": _docs(scope, "M", "07JAN16", "TEST", given)} for s in segments]
        out.append({"FirstName": given, "LastName": "TEST", "AgeType": "CH", "Title": "MR", "Parent": "", "SSRs": ssrs})
    return out


def candidates(flights: list[Flight], business: bool, need: int) -> list[tuple[Flight, str]]:
    out = []
    for f in flights:
        for c in f.open_classes(business=business):
            if c.seats >= need:
                out.append((f, c.rbd))
    return out


def run_one(cli: MahanClient, sc: tuple, routes: dict, out_day: str, back_day: str, contact: str) -> dict:
    sid, title, scope, rt, ad, ch, inf, biz = sc
    org, dst = routes[scope]
    row = {"ID": sid, "Test Case": title, "Departure date": out_day, "Return date": back_day if rt else ""}
    seat_need = ad + ch
    out_opts = candidates(cli.availability(org, dst, out_day, ad, ch, inf), biz, seat_need)
    back_opts = candidates(cli.availability(dst, org, back_day, ad, ch, inf), biz, seat_need) if rt else [(None, None)]
    log(f"  [{sid}] availability: {len(out_opts)} outbound option(s){f', {len(back_opts)} return option(s)' if rt else ''}")
    if not out_opts or not back_opts:
        raise MahanError(f"no open {'business' if biz else 'economy'} class for {seat_need} seat(s)")
    last_err: Optional[Exception] = None
    for (fo, ro) in out_opts[:4]:
        for (fb, rb) in back_opts[:3]:
            segs = [{"Origin": org, "Destination": dst, "FlightNo": fo.flight_no, "DepartureDate": out_day, "FlightClass": ro}]
            if fb is not None:
                segs.append({"Origin": dst, "Destination": org, "FlightNo": fb.flight_no, "DepartureDate": back_day, "FlightClass": rb})
            quote_segs = [{"Origin": s["Origin"], "Destination": s["Destination"], "FlightClass": s["FlightClass"], "Departure": s["DepartureDate"], "FlightNo": s["FlightNo"]} for s in segs]
            try:
                q = cli.fare_quote(quote_segs, ad, ch, inf)
            except MahanError as exc:
                last_err = exc
                log(f"  [{sid}] FareQuote {'/'.join(s['FlightNo'] + s['FlightClass'] for s in segs)}: {exc}")
                continue
            log(f"  [{sid}] FareQuote {'/'.join(s['FlightNo'] + s['FlightClass'] for s in segs)}: {q.total_price} {q.currency}")
            pnr = cli.book(segs, passengers(scope, ad, ch, inf, segs), contact)
            log(f"  [{sid}] Book: PNR {pnr}")
            base = q.total_fare
            row.update({"Flight no": " / ".join(f"W5{s['FlightNo']} ({s['FlightClass']})" for s in segs), "Total Fare": str(q.total_fare), "Total Tax": str(q.total_tax),
                        "Base Price": str(base), "Total Surcharge": str(q.surcharge), "Payment Amount and Currency": f"{q.total_price} {q.currency}", "Booking ReferenceID (PNR)": pnr})
            return row
    raise MahanError(f"no priceable combination ({last_err})")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--stay", type=int, default=4)
    ap.add_argument("--domestic", default="THR-MHD")
    ap.add_argument("--international", default="IKA-IST")
    ap.add_argument("--only", default="", help="comma-separated scenario ids")
    a = ap.parse_args(argv)
    if (os.environ.get("MAHAN_ENV") or "qaa").lower() != "qaa":
        print("refusing: certification runs only on QAA (MAHAN_ENV=qaa)", file=sys.stderr)
        return 2
    try:
        cli = MahanClient(env="qaa")
    except MahanError as exc:
        print(f"MAHAN-CERT-ERROR {exc}", file=sys.stderr)
        return 2
    routes = {"domestic": tuple(a.domestic.split("-")), "international": tuple(a.international.split("-"))}
    out_day = (date.today() + timedelta(days=a.days)).isoformat()
    back_day = (date.today() + timedelta(days=a.days + a.stay)).isoformat()
    contact = os.environ.get("MAHAN_TEST_CONTACT") or "+989191258009"
    only = {int(x) for x in a.only.split(",") if x.strip()}
    rows = []
    for sc in SCENARIOS:
        if only and sc[0] not in only:
            continue
        log(f"== scenario {sc[0]}: {sc[1]} ({sc[2]})")
        try:
            rows.append(run_one(cli, sc, routes, out_day, back_day, contact))
        except MahanError as exc:
            log(f"  [{sc[0]}] FAILED: {exc}")
            rows.append({"ID": sc[0], "Test Case": sc[1], "Departure date": out_day, "Return date": back_day if sc[3] else "", "Booking ReferenceID (PNR)": f"FAILED: {exc}"})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in COLUMNS})
    print("==MAHAN-CERT-CSV==")
    print(buf.getvalue().strip())
    print("==END==")
    ok = sum(1 for r in rows if not str(r.get("Booking ReferenceID (PNR)", "")).startswith("FAILED"))
    print(f"MAHAN-CERT-DONE {ok}/{len(rows)} booked (no tickets issued)")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "SCENARIOS", "passengers", "candidates"]
