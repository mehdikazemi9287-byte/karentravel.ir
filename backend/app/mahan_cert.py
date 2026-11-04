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


def candidates(flights: list[Flight], need: int) -> list[tuple[Flight, str]]:
    """Every open class with enough seats; cabin (economy/business) is decided by FareQuote's Cabin, not guessed from the RBD."""
    return [(f, c.rbd) for f in flights for c in f.classes if c.seats >= need]


def flight_day(f: Optional[Flight], asked: str) -> str:
    """Book needs the flight's own departure date (DepartureDateTime), which can differ from the searched day."""
    d = (getattr(f, "departure", "") or "")[:10]
    return d if len(d) == 10 and d[4] == "-" else asked


def is_business(cabin: str) -> bool:
    c = cabin.upper()
    return "BUS" in c or any(part.strip() in ("C", "J", "F", "BUSINESS") for part in c.replace("/", "+").split("+"))


def run_one(cli: MahanClient, sc: tuple, routes: dict, days: list[str], stay: int, contact: str, max_quotes: int = 24) -> dict:
    sid, title, scope, rt, ad, ch, inf, biz = sc
    org, dst = routes[scope]
    need = ad + ch
    quotes = 0
    last_err: Optional[Exception] = None
    for out_day in days:
        back_day = (date.fromisoformat(out_day) + timedelta(days=stay)).isoformat()
        out_opts = candidates(cli.availability(org, dst, out_day, ad, ch, inf), need)
        if not out_opts:
            continue
        back_opts = candidates(cli.availability(dst, org, back_day, ad, ch, inf), need) if rt else [(None, None)]
        if not back_opts:
            continue
        log(f"  [{sid}] {out_day}: {len(out_opts)} outbound class option(s){f', {len(back_opts)} return' if rt else ''}")
        pairs = [(o, b) for o in out_opts for b in back_opts]
        pairs.sort(key=lambda p: 0 if p[1][1] is None or p[0][1] == p[1][1] else 1)   # same RBD both ways prices most often
        for ((fo, ro), (fb, rb)) in pairs:
            if quotes >= max_quotes:
                raise MahanError(f"no priceable {'business' if biz else 'economy'} combination after {quotes} quotes ({last_err})")
            segs = [{"Origin": org, "Destination": dst, "FlightNo": str(fo.flight_no), "DepartureDate": flight_day(fo, out_day), "FlightClass": ro}]
            if fb is not None:
                segs.append({"Origin": dst, "Destination": org, "FlightNo": str(fb.flight_no), "DepartureDate": flight_day(fb, back_day), "FlightClass": rb})
            label = " / ".join(f"W5{s['FlightNo']}{s['FlightClass']} {s['DepartureDate']}" for s in segs)
            quotes += 1
            try:
                q = cli.fare_quote([{"Origin": s["Origin"], "Destination": s["Destination"], "FlightClass": s["FlightClass"], "Departure": s["DepartureDate"], "FlightNo": s["FlightNo"]} for s in segs], ad, ch, inf)
            except MahanError as exc:
                last_err = exc
                log(f"  [{sid}] FareQuote {label}: {exc}")
                continue
            if is_business(q.cabin) != biz:
                log(f"  [{sid}] FareQuote {label}: cabin {q.cabin or '?'} — not {'business' if biz else 'economy'}, next")
                continue
            log(f"  [{sid}] FareQuote {label}: {q.total_price} {q.currency} (cabin {q.cabin})")
            try:
                pnr = cli.book(segs, passengers(scope, ad, ch, inf, segs), contact)
            except MahanError as exc:
                last_err = exc
                log(f"  [{sid}] Book {label}: {exc}")
                continue
            log(f"  [{sid}] Book: PNR {pnr}")
            return {"ID": sid, "Test Case": title, "Departure date": segs[0]["DepartureDate"], "Return date": segs[1]["DepartureDate"] if len(segs) > 1 else "",
                    "Flight no": " / ".join(f"W5{s['FlightNo']} ({s['FlightClass']})" for s in segs), "Total Fare": str(q.total_fare), "Total Tax": str(q.total_tax),
                    "Base Price": str(q.total_fare), "Total Surcharge": str(q.surcharge), "Payment Amount and Currency": f"{q.total_price} {q.currency}", "Booking ReferenceID (PNR)": pnr}
    raise MahanError(f"no priceable {'business' if biz else 'economy'} combination in the date window ({last_err})")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--window", type=int, default=30, help="how many departure days to try")
    ap.add_argument("--stay", type=int, default=4)
    ap.add_argument("--domestic", default="THR-KIH")
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
    days = [(date.today() + timedelta(days=a.days + i)).isoformat() for i in range(a.window)]
    contact = os.environ.get("MAHAN_TEST_CONTACT") or "+989191258009"
    only = {int(x) for x in a.only.split(",") if x.strip()}
    rows = []
    for sc in SCENARIOS:
        if only and sc[0] not in only:
            continue
        log(f"== scenario {sc[0]}: {sc[1]} ({sc[2]})")
        try:
            rows.append(run_one(cli, sc, routes, days, a.stay, contact))
        except MahanError as exc:
            log(f"  [{sc[0]}] FAILED: {exc}")
            rows.append({"ID": sc[0], "Test Case": sc[1], "Booking ReferenceID (PNR)": f"FAILED: {exc}"})
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


__all__ = ["main", "SCENARIOS", "passengers", "candidates", "is_business"]
