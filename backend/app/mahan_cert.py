"""Mahan MRS certification run (QAA only): the 8 scenarios of TestScenarios_W56 — search, FareQuote, Book; no ticketing.

    MAHAN_ENV=qaa MAHAN_QAA_API_KEY=... python -m app.mahan_cert [--days 1] [--international IKA-BKK] [--only 6,7,8 | --all]

Prints the filled sheet as CSV (same columns as Mahan's sheet) between ==MAHAN-CERT-CSV== markers, plus one line per
step. Every refused Book prints Mahan's full reason and, once per distinct reason, the request body and the raw answer
(==MAHAN-BOOK-FAIL== blocks, no key/password inside) so it can go to Mahan support as is. Refuses to run against Live.

Lessons from QAA runs (1405-08-14/17):
* On IKA-BKK only class R prices as business (Cabin C); others are Y or have no fare — cabins learnt from FareQuote are
  reused across days and scenarios, and `--business-hint` puts the known business RBDs first.
* Book must carry the flight's own DepartureDateTime and a unique document per passenger (DUPLICATE DOC).
* Every Book gets fresh synthetic names: run 3 re-used TESTA/TEST on W5 51 of the same day that already holds
  TL27U, which an airline host may refuse as a duplicate booking (hypothesis; Mahan only said «رزرو انجام نشد.»).
* Child/infant birth dates are derived from the travel date (child 7 y, infant 9 months) so they stay in age range.
* A Book that times out (or loses the connection) may still have created a PNR on QAA: that scenario stops there and
  is reported, it is never retried with fresh names.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import string
import sys
from datetime import date, timedelta
from typing import Optional

from .mahan_mrs import BUSINESS_RBD, Flight, MahanClient, MahanError, docs_text

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
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _today() -> date:
    """The run's "today" (one place, so tests can move the clock)."""
    return date.today()


def log(msg: str) -> None:
    print(msg, flush=True)


def ddmmmyy(d: date) -> str:
    return f"{d.day:02d}{MONTHS[d.month - 1]}{d.year % 100:02d}"


def years_before(d: date, years: int = 0, months: int = 0) -> date:
    m = d.year * 12 + d.month - 1 - years * 12 - months
    return date(m // 12, m % 12 + 1, min(d.day, 28))


def national_code(rng: random.Random) -> str:
    """A synthetic 10-digit Iranian national code with a valid check digit (Mahan rejects a document repeated on a flight)."""
    d = [rng.randint(0, 9) for _ in range(9)]
    r = sum(x * (10 - i) for i, x in enumerate(d)) % 11
    return "".join(map(str, d)) + str(r if r < 2 else 11 - r)


def _doc_no(scope: str, rng: random.Random) -> tuple[str, str]:
    return ("I", national_code(rng)) if scope == "domestic" else ("P", f"T{rng.randint(10000000, 99999999)}")


def _docs(scope: str, gender: str, dob: str, surname: str, given: str, rng: random.Random) -> str:
    kind, no = _doc_no(scope, rng)
    return docs_text(kind, "IRN", no, "IRN", dob, gender, "16NOV28", surname, given)


def name_tag(rng: random.Random, n: int = 4) -> str:
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def passengers(scope: str, adults: int, children: int, infants: int, segments: list[dict], rng: Optional[random.Random] = None,
               tag: str = "", travel: Optional[date] = None, variant: str = "base") -> list[dict]:
    """Each passenger gets its own synthetic document (same on every segment) and, with `tag`, a name unique to this run.

    variant "base": the shape that booked TL27U (adult DOCS; infant = INFT SSR under the first adult; child Title MR).
    variant "iata": also an infant DOCS on the adult (gender FI per IATA) and child Title MSTR — tried when "base" is refused.
    """
    rng = rng or random.Random()
    travel = travel or _today()
    child_dob, infant_dob = ddmmmyy(years_before(travel, 7)), ddmmmyy(years_before(travel, 0, 9))
    out = []
    for i in range(adults):
        given, gender = f"TEST{tag}{'ABCD'[i]}", ("F" if i == 0 else "M")
        doc = _docs(scope, gender, "07JAN86", "TEST", given, rng)
        ssrs = [{"SSRType": "DOCS", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": doc} for s in segments]
        if i < infants:
            inf_given = f"TESTINF{tag}{'ABCD'[i]}"
            ssrs += [{"SSRType": "INFT", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": f"TEST/{inf_given} {infant_dob}"} for s in segments]
            if variant == "iata":
                inf_doc = _docs(scope, "F", infant_dob, "TEST", inf_given, rng).replace(f"/{infant_dob}/F/", f"/{infant_dob}/FI/")
                ssrs += [{"SSRType": "DOCS", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": inf_doc} for s in segments]
        out.append({"FirstName": given, "LastName": "TEST", "AgeType": "AD", "Title": "MS" if gender == "F" else "MR", "Parent": "", "SSRs": ssrs})
    for i in range(children):
        given = f"TESTCHD{tag}{'ABCD'[i]}"
        doc = _docs(scope, "M", child_dob, "TEST", given, rng)
        ssrs = [{"SSRType": "DOCS", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": doc} for s in segments]
        out.append({"FirstName": given, "LastName": "TEST", "AgeType": "CH", "Title": "MSTR" if variant == "iata" else "MR", "Parent": "", "SSRs": ssrs})
    return out


def candidates(flights: list[Flight], need: int) -> list[tuple[Flight, str]]:
    """Every open class with enough seats (infants sit on laps); cabin is decided by FareQuote's Cabin, not the RBD."""
    return [(f, c.rbd) for f in flights for c in f.classes if c.seats >= need]


def flight_day(f: Optional[Flight], asked: str) -> str:
    """Book needs the flight's own departure date (DepartureDateTime), which can differ from the searched day."""
    d = (getattr(f, "departure", "") or "")[:10]
    return d if len(d) == 10 and d[4] == "-" else asked


def is_business(cabin: str) -> bool:
    c = cabin.upper()
    return "BUS" in c or any(part.strip() in ("C", "J", "F", "BUSINESS") for part in c.replace("/", "+").split("+"))


class Learnt:
    """What QAA told us so far, shared by all scenarios of a run: cabin per (origin, destination, RBD), and RBD pairs
    without fare per (origin, destination, adults, children, infants, RBDs) — a no-fare on one route/passenger mix says
    nothing about another."""

    def __init__(self, business_hint: str = ""):
        self.cabin: dict[tuple[str, str, str], bool] = {}
        self.nofare: dict[tuple, int] = {}
        self.hint = [x.strip().upper() for x in business_hint.split(",") if x.strip()]

    def record(self, segs: list[dict], cabin: str) -> None:
        parts = [p.strip() for p in cabin.replace("/", "+").split("+")]
        if len(parts) == len(segs):
            for s, p in zip(segs, parts):
                self.cabin[(s["Origin"], s["Destination"], s["FlightClass"])] = is_business(p)

    def wrong_cabin(self, org: str, dst: str, rbd: str, biz: bool) -> bool:
        known = self.cabin.get((org, dst, rbd))
        return known is not None and known != biz

    def rank(self, org: str, dst: str, rbd: str, biz: bool) -> int:
        known = self.cabin.get((org, dst, rbd))
        if known is not None:
            return 0 if known == biz else 9
        if biz:
            return 1 if rbd in self.hint else 2 if rbd in BUSINESS_RBD else 3
        return 3 if rbd in self.hint or rbd in BUSINESS_RBD else 2


def nofare_key(org: str, dst: str, ad: int, ch: int, inf: int, rbds: tuple) -> tuple:
    return (org, dst, ad, ch, inf, rbds)


def dump_failure(sid: int, label: str, variant: str, exc: MahanError) -> None:
    log(f"==MAHAN-BOOK-FAIL== scenario {sid} {label} variant={variant} code={getattr(exc, 'code', None)}")
    log("request: " + json.dumps(getattr(exc, "request", None), ensure_ascii=False))
    log("answer:  " + json.dumps(getattr(exc, "payload", None), ensure_ascii=False))
    log("==END-BOOK-FAIL==")


def run_one(cli: MahanClient, sc: tuple, routes: dict, days: list[str], stay: int, contact: str, learnt: Optional[Learnt] = None,
            max_quotes: int = 60, max_books: int = 8, rng: Optional[random.Random] = None) -> dict:
    sid, title, scope, rt, ad, ch, inf, biz = sc
    org, dst = routes[scope]
    need = ad + ch
    learnt = learnt or Learnt()
    rng = rng or random.Random()
    variants = ["base", "iata"] if (ch or inf) else ["base"]
    quotes = books = 0
    tried: set[str] = set()
    reasons: list[str] = []
    dumped: set[tuple[str, str]] = set()
    last_err: Optional[Exception] = None
    cab = "business" if biz else "economy"
    for out_day in days:
        back_day = (date.fromisoformat(out_day) + timedelta(days=stay)).isoformat()
        try:
            out_opts = candidates(cli.availability(org, dst, out_day, ad, ch, inf), need)
            back_opts = (candidates(cli.availability(dst, org, back_day, ad, ch, inf), need) if rt else [(None, None)]) if out_opts else []
        except MahanError as exc:
            log(f"  [{sid}] {out_day}: availability failed: {exc}")
            continue
        out_opts = [o for o in out_opts if not learnt.wrong_cabin(org, dst, o[1], biz) and flight_day(o[0], out_day) >= _today().isoformat()]
        if rt:
            back_opts = [b for b in back_opts if not learnt.wrong_cabin(dst, org, b[1], biz)]
        if not out_opts or not back_opts:
            continue
        log(f"  [{sid}] {out_day}: {len(out_opts)} outbound class option(s){f', {len(back_opts)} return' if rt else ''}")
        pairs = []
        for o in out_opts:
            for b in back_opts:
                if b[0] is not None and flight_day(b[0], back_day) < flight_day(o[0], out_day):   # return before outbound
                    continue
                pairs.append((o, b))
        pairs.sort(key=lambda p: (0 if p[1][1] is None or p[0][1] == p[1][1] else 1, learnt.rank(org, dst, p[0][1], biz),
                                  learnt.rank(dst, org, p[1][1], biz) if p[1][1] else 0))
        for ((fo, ro), (fb, rb)) in pairs:
            if quotes >= max_quotes or books >= max_books:
                raise MahanError(f"no bookable {cab} combination after {quotes} quotes / {books} books ({' | '.join(reasons) or last_err})")
            segs = [{"Origin": org, "Destination": dst, "FlightNo": str(fo.flight_no), "DepartureDate": flight_day(fo, out_day), "FlightClass": ro}]
            if fb is not None:
                segs.append({"Origin": dst, "Destination": org, "FlightNo": str(fb.flight_no), "DepartureDate": flight_day(fb, back_day), "FlightClass": rb})
            label = " / ".join(f"W5{s['FlightNo']}{s['FlightClass']} {s['DepartureDate']}" for s in segs)
            nf = nofare_key(org, dst, ad, ch, inf, tuple(s["FlightClass"] for s in segs))
            if label in tried or learnt.nofare.get(nf, 0) >= 2:
                continue
            tried.add(label)
            quotes += 1
            try:
                q = cli.fare_quote([{"Origin": s["Origin"], "Destination": s["Destination"], "FlightClass": s["FlightClass"], "Departure": s["DepartureDate"], "FlightNo": s["FlightNo"]} for s in segs], ad, ch, inf)
            except MahanError as exc:
                last_err = exc
                learnt.nofare[nf] = learnt.nofare.get(nf, 0) + 1
                log(f"  [{sid}] FareQuote {label}: {exc}")
                continue
            learnt.record(segs, q.cabin)
            if is_business(q.cabin) != biz:
                log(f"  [{sid}] FareQuote {label}: cabin {q.cabin or '?'} — not {cab}, next")
                continue
            log(f"  [{sid}] FareQuote {label}: {q.total_price} {q.currency} (cabin {q.cabin})")
            travel = date.fromisoformat(segs[0]["DepartureDate"])
            for variant in variants:
                if books >= max_books:
                    break
                books += 1
                try:
                    pnr = cli.book(segs, passengers(scope, ad, ch, inf, segs, rng=rng, tag=name_tag(rng), travel=travel, variant=variant), contact)
                except MahanError as exc:
                    last_err = exc
                    reason = f"{exc} [code {getattr(exc, 'code', None)}]"
                    if reason not in reasons:
                        reasons.append(reason)
                    log(f"  [{sid}] Book {label} ({variant}): {reason}")
                    if exc.ambiguous or exc.code in ("TIMEOUT", "NETWORK"):
                        # The answer was lost, not refused: a PNR may exist. Re-booking with fresh names could double-book.
                        msg = f"Book outcome unknown (timeout/network) on {label} ({variant}) — a PNR may exist on QAA; check manually before re-running"
                        log(f"  [{sid}] {msg}")
                        dump_failure(sid, label, variant, exc)
                        raise MahanError(msg, code="BOOK_UNKNOWN", ambiguous=True, request=exc.request) from exc
                    if (str(exc), variant) not in dumped:
                        dumped.add((str(exc), variant))
                        dump_failure(sid, label, variant, exc)
                    continue
                log(f"  [{sid}] Book ({variant}): PNR {pnr}")
                return {"ID": sid, "Test Case": title, "Departure date": segs[0]["DepartureDate"], "Return date": segs[1]["DepartureDate"] if len(segs) > 1 else "",
                        "Flight no": " / ".join(f"W5{s['FlightNo']} ({s['FlightClass']})" for s in segs), "Total Fare": str(q.total_fare), "Total Tax": str(q.total_tax),
                        "Base Price": str(q.total_fare), "Total Surcharge": str(q.surcharge), "Payment Amount and Currency": f"{q.total_price} {q.currency}", "Booking ReferenceID (PNR)": pnr}
    raise MahanError(f"no bookable {cab} combination in the date window after {quotes} quotes / {books} books ({' | '.join(reasons) or last_err})")


def main(argv: Optional[list[str]] = None, default_only: str = "") -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1, help="first departure day = today + DAYS")
    ap.add_argument("--window", type=int, default=30, help="how many departure days to try")
    ap.add_argument("--stay", type=int, default=4)
    ap.add_argument("--domestic", default="THR-KIH")
    ap.add_argument("--international", default="IKA-BKK", help="QAA has priced flights only on IKA-BKK (1405-08-14)")
    ap.add_argument("--business-hint", default="R", help="RBDs tried first for business (R = Cabin C on IKA-BKK in QAA)")
    ap.add_argument("--max-quotes", type=int, default=60)
    ap.add_argument("--max-books", type=int, default=8, help="Book attempts per scenario")
    ap.add_argument("--only", default=None, help=f"comma-separated scenario ids (default: {default_only or 'all'})")
    ap.add_argument("--all", action="store_true", help="run all 8 scenarios")
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
    days = [(_today() + timedelta(days=a.days + i)).isoformat() for i in range(a.window)]
    contact = os.environ.get("MAHAN_TEST_CONTACT") or "+989191258009"
    only_s = "" if a.all else (a.only if a.only is not None else default_only)
    try:
        only = {int(x) for x in only_s.split(",") if x.strip()}
    except ValueError:
        ap.error(f"--only: comma-separated scenario ids expected, got {only_s!r}")
    if only - {sc[0] for sc in SCENARIOS}:
        ap.error(f"--only: unknown scenario id(s) {sorted(only - {sc[0] for sc in SCENARIOS})} (valid: 1-{len(SCENARIOS)})")
    learnt, rng = Learnt(a.business_hint), random.Random()
    log(f"MAHAN-CERT QAA {_today().isoformat()} days {days[0]}..{days[-1]} routes {routes} scenarios {sorted(only) or 'all'}")
    rows = []
    for sc in SCENARIOS:
        if only and sc[0] not in only:
            continue
        log(f"== scenario {sc[0]}: {sc[1]} ({sc[2]})")
        try:
            rows.append(run_one(cli, sc, routes, days, a.stay, contact, learnt, a.max_quotes, a.max_books, rng))
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


__all__ = ["main", "SCENARIOS", "passengers", "candidates", "is_business", "Learnt", "run_one"]
