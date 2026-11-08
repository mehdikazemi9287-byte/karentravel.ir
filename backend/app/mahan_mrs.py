"""Mahan Air (W5) MRS client — API reference v1.3 (AvailabilityFareJS, FareQuote, Book, NRSRT, ETIssueJS, NRSETR,
CancelPNRJS, CancelSeatJS, NRSPenalty/NRSPenaltyNow, ETRefundJS).

Rules taken from the reference and kept here on purpose:
* `X-API-Key` header only; the key never goes into URLs, bodies or logs. QAA and Live keys/URLs are never mixed.
* Availability prices are indicators only — FareQuote is the authoritative price and combinability check.
* Book sells segments in request order; an infant is an `INFT` SSR under the accompanying adult (not a passenger).
* Money is parsed as integers (IRR) or Decimal; never float.
* Issue and refund are financial: after a timeout or inconsistent answer we reconcile (NRSRT/NRSETR), we never blindly retry.
"""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional
from urllib.parse import urlencode

import httpx

ENVS = {
    "qaa": {"ws1": "https://api.mahanair.co.ir/ws1-qaa", "ws2": "https://api.mahanair.co.ir/ws2-qaa", "cgi": "https://api.mahanair.co.ir/ws2-qaa/cgi-bin/NRSWEB.cgi"},
    "live": {"ws1": "https://api.mahanair.co.ir/ws1", "ws2": "https://api.mahanair.co.ir/ws2", "cgi": "https://api.mahanair.co.ir/ws2/cgi-bin/NRSWEB.cgi"},
}
AIRLINE = "W5"
BUSINESS_RBD = set("JCDIZ")


class MahanError(RuntimeError):
    """`payload` is Mahan's raw answer and `request` the body we sent (never contains the key) — for support tickets.

    Warning: `request` (and a Book `payload`) can hold passenger PII — names, document numbers, birth dates, contact.
    Only log or forward it for QAA synthetic passengers; never dump it for real customers.
    """
    def __init__(self, message: str, *, code: Optional[str] = None, status: Optional[int] = None, ambiguous: bool = False,
                 payload: Any = None, request: Any = None):
        super().__init__(message)
        self.code, self.status, self.ambiguous = code, status, ambiguous
        self.payload, self.request = payload, request


_ERR_KEY = re.compile(r"desc|message|error|reason|remark|warning|detail", re.I)
_NOT_ERR_KEY = re.compile(r"success|errorcode", re.I)       # SuccessMessage etc. are not reasons
_SECRET = re.compile(r"((?:office)?pass(?:word)?|pwd|api[_-]?key|x-api-key|secret|token)(\W{0,3}[=:]\W{0,3})([^&\s\"',;}<]+)", re.I)


def redact(text: str, *secrets: str) -> str:
    """Hide OfficePass=/password=/key= values (and any known secret) that Mahan may echo back in an error page."""
    out = _SECRET.sub(lambda m: m.group(1) + m.group(2) + "***", text)
    for v in secrets:
        if v and len(v) >= 3:
            out = out.replace(v, "***")
    return out


def error_text(data: Any) -> str:
    """Every human-readable reason in a Mahan error answer (description_en/fa, Message, Errors[...], nested result messages)."""
    seen: list[str] = []

    def walk(x: Any, key: str = "") -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str) and key and _ERR_KEY.search(key) and not _NOT_ERR_KEY.search(key):
            t = x.strip()
            if t and t not in seen:
                seen.append(t)
    walk(data)
    return " — ".join(seen)


def money(v: Any) -> Optional[Decimal]:
    if v is None or v == "" or v == "-":
        return None
    try:
        return Decimal(str(v).replace(",", "").strip())
    except InvalidOperation:
        return None


def seats(cap: str) -> Optional[int]:
    """Cap token like 'YA', 'Y9', 'YX', 'YC': A = open (9+), digit = seats left, X/C/0 = closed."""
    s = (cap or "").strip().upper()[-1:]
    if s == "A":
        return 9
    if s.isdigit():
        return int(s)
    return 0


@dataclass
class ClassOption:
    rbd: str
    seats: int
    price: Optional[Decimal]
    currency: Optional[str]


@dataclass
class Flight:
    flight_no: str
    origin: str
    destination: str
    departure: str            # as returned (local, no timezone)
    arrival: Optional[str]
    pair_code: Optional[str]
    classes: list[ClassOption] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    def open_classes(self, business: Optional[bool] = None) -> list[ClassOption]:
        out = [c for c in self.classes if c.seats > 0]
        if business is not None:
            out = [c for c in out if (c.rbd in BUSINESS_RBD) == business]
        return out


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        for kk in (k, k.lower(), k[0].lower() + k[1:]):
            if isinstance(d, dict) and kk in d and d[kk] not in (None, ""):
                return d[kk]
    return None


def _flight_rows(payload: Any) -> list[dict]:
    """Availability responses wrap the flight list under different names; find dicts that carry ClassesStatus."""
    found: list[dict] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            if any(k in x for k in ("ClassesStatus", "classesStatus")):
                found.append(x)
                return
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(payload)
    return found


def parse_availability(payload: Any) -> list[Flight]:
    if not isinstance(payload, (dict, list)):
        raise MahanError("Availability: unexpected answer", code="BAD_RESPONSE", payload=payload)
    flights = []
    for row in _flight_rows(payload):
        classes = []
        for c in _first(row, "ClassesStatus") or []:
            if not isinstance(c, dict):
                continue
            rbd = str(_first(c, "FlightClass") or "").strip().upper()
            cap = str(_first(c, "Cap") or "")
            if not rbd:
                rbd = cap[:1].upper()
            if not rbd:
                continue
            classes.append(ClassOption(rbd=rbd, seats=seats(cap), price=money(_first(c, "Price")), currency=_first(c, "CurrencyCode")))
        dep = _first(row, "DepartureDateTime", "DepartureDT", "DepartureDate", "Departure")
        flights.append(Flight(flight_no=str(_first(row, "FlightNo") or "").strip(), origin=str(_first(row, "Origin", "Source") or "").strip(),
                              destination=str(_first(row, "Destination", "Target") or "").strip(), departure=str(dep or ""),
                              arrival=_first(row, "ArrivalDateTime", "ArrivalDT", "Arrival"), pair_code=_first(row, "PairCode"), classes=classes, raw=row))
    return [f for f in flights if f.flight_no]


@dataclass
class Quote:
    currency: str
    total_fare: Decimal
    total_tax: Decimal
    total_price: Decimal
    surcharge: Decimal
    coupons: list[dict]
    breakdown: list[dict]
    cabin: str = ""
    raw: dict = field(default_factory=dict, repr=False)


def parse_quote(payload: Any) -> Quote:
    if not isinstance(payload, dict):
        raise MahanError("FareQuote: unexpected answer", code="BAD_RESPONSE", payload=payload)
    if str(payload.get("errorCode", "0")) not in ("0", "0.0"):
        raise MahanError(error_text(payload) or "FareQuote failed", code=str(payload.get("errorCode")), payload=payload)
    r = payload.get("result") or {}
    if not isinstance(r, dict):
        raise MahanError("FareQuote: unexpected answer", code="BAD_RESPONSE", payload=payload)
    surcharge = Decimal(0)
    for b in r.get("PassengerBreakdown") or []:
        for t in b.get("Taxes") or []:
            if str(t.get("TaxType", "")).upper() in ("YQ", "YR"):
                surcharge += money(t.get("TotalTaxAmount")) or money(t.get("TaxAmount")) or Decimal(0)
    tf, tt, tp = money(r.get("TotalFare")), money(r.get("TotalTax")), money(r.get("TotalPrice"))
    if tf is None or tp is None:
        raise MahanError("FareQuote without totals")
    return Quote(currency=r.get("Currency") or "IRR", total_fare=tf, total_tax=tt or Decimal(0), total_price=tp, surcharge=surcharge,
                 coupons=r.get("Coupons") or [], breakdown=r.get("PassengerBreakdown") or [], cabin=str(r.get("Cabin") or ""), raw=payload)


def docs_text(doc_type: str, country: str, number: str, nationality: str, dob: str, gender: str, expiry: str, surname: str, given: str) -> str:
    """DOCS FreeText: {I|P}/{country}/{docNo}/{nationality}/{DOB DDMMMYY}/{M|F}/{expiry DDMMMYY}/{surname}/{given}."""
    if doc_type not in ("I", "P") or gender not in ("M", "F"):
        raise ValueError("DOCS type or gender invalid")
    for v in (dob, expiry):
        if not re.fullmatch(r"\d{2}[A-Z]{3}\d{2}", v):
            raise ValueError("DOCS dates must be DDMMMYY")
    return "/".join([doc_type, country, number, nationality, dob, gender, expiry, surname.upper(), given.upper()])


class MahanClient:
    def __init__(self, env: Optional[str] = None, api_key: Optional[str] = None, transport: Optional[Callable[..., httpx.Response]] = None, timeout: float = 30):
        self.env = (env or os.environ.get("MAHAN_ENV") or "qaa").lower()
        if self.env not in ENVS:
            raise ValueError("MAHAN_ENV must be qaa or live")
        prefix = "MAHAN_QAA_" if self.env == "qaa" else "MAHAN_"
        b64 = os.environ.get(prefix + "API_KEY_B64")
        self.key = (api_key or (base64.b64decode(b64).decode() if b64 else os.environ.get(prefix + "API_KEY")) or "").strip()
        if not self.key:
            raise MahanError("کلید وب‌سرویس ماهان تنظیم نشده است", code="NO_KEY")
        # The JSP/CGI query methods (AvailabilityFareJS, NRSRT, ETIssueJS, ...) authenticate with the office user/password
        # (verified on QAA: X-API-Key alone answers "SIGN"); the REST methods (FareQuote, Book) with X-API-Key.
        self.office = {"OfficeUser": os.environ.get(prefix + "OFFICE_USER", "").strip(), "OfficePass": os.environ.get(prefix + "OFFICE_PASS", "").strip().replace("$$", "$")}
        self.urls = ENVS[self.env]
        self._send = transport
        self.timeout = timeout

    def _q(self, params: dict) -> str:
        return urlencode({**params, **{k: v for k, v in self.office.items() if v}})

    def _request(self, method: str, url: str, json: Optional[dict] = None) -> Any:
        headers = {"X-API-Key": self.key, "Accept": "application/json"}
        try:
            if self._send is not None:
                r = self._send(method, url, json=json, headers=headers)
            else:
                with httpx.Client(timeout=self.timeout) as c:
                    r = c.request(method, url, json=json, headers=headers)
        except httpx.TimeoutException as exc:
            raise MahanError("پاسخ ماهان به‌موقع نرسید", code="TIMEOUT", ambiguous=True) from exc
        except httpx.HTTPError as exc:
            raise MahanError("ارتباط با ماهان برقرار نشد", code="NETWORK") from exc
        if r.status_code == 503:
            raise MahanError("سرویس ماهان موقتاً در دسترس نیست", code="UNAVAILABLE", status=503)
        text = (r.text or "").strip()
        if r.status_code >= 400:
            safe = redact(text, self.key, self.office.get("OfficePass", ""))
            raise MahanError(f"HTTP {r.status_code}" + (f": {safe[:300]}" if safe else ""), status=r.status_code, payload=safe[:4000], request=json)
        if text in ("SIGN", '"SIGN"'):
            raise MahanError("ماهان ورود را نپذیرفت (نام کاربری/رمز دفتر یا کلید)", code="SIGN")
        try:
            return r.json()
        except ValueError as exc:
            raise MahanError(f"پاسخ ماهان JSON نبود: {text[:80]}", code="BAD_RESPONSE") from exc

    # ---- shopping ----
    def availability(self, origin: str, destination: str, date: str, adults: int, children: int = 0, infants: int = 0) -> list[Flight]:
        q = self._q({"AirLine": AIRLINE, "cbSource": origin, "cbTarget": destination, "cbAdultQty": adults, "cbChildQty": children, "cbInfantQty": infants, "DepartureDate": date})
        return parse_availability(self._request("GET", f"{self.urls['ws1']}/AvailabilityFareJS.jsp?{q}"))

    def fare_quote(self, segments: list[dict], adults: int, children: int = 0, infants: int = 0, currency: Optional[str] = None) -> Quote:
        pax = [{"AgeType": t, "Quantity": n} for t, n in (("AD", adults), ("CH", children), ("IN", infants)) if n]
        body: dict = {"Segments": [{"AirlineCode": AIRLINE, **s} for s in segments], "Passengers": pax, "DiscountCode": ""}
        if currency:
            body["Currency"] = currency
        return parse_quote(self._request("POST", f"{self.urls['ws1']}/AirFare/FareQuote", json=body))

    def book(self, segments: list[dict], passengers: list[dict], contact: str) -> str:
        """Returns the PNR. On refusal the MahanError carries every reason Mahan gave plus `payload`/`request` for support."""
        body = {"Contact": contact, "Segments": [{"AirlineCode": AIRLINE, **s} for s in segments], "Passengers": passengers}
        data = self._request("POST", f"{self.urls['ws2']}/Res/Book", json=body)
        if not isinstance(data, dict):
            raise MahanError("Book: unexpected answer", code="BAD_RESPONSE", payload=data, request=body)
        pnr = (data.get("result") or {}).get("PNR") if isinstance(data.get("result"), dict) else None
        if str(data.get("errorCode", "0")) not in ("0", "0.0") or not pnr:
            raise MahanError(error_text(data) or "Book failed", code=str(data.get("errorCode")), payload=data, request=body)
        return str(pnr)

    # ---- after sale ----
    def retrieve_pnr(self, pnr: str) -> dict:
        return self._request("GET", f"{self.urls['ws1']}/NRSRT.jsp?{self._q({'AirLine': AIRLINE, 'PNR': pnr})}")

    def issue(self, pnr: str, email: str) -> list[str]:
        """Financial. On timeout the caller must reconcile with retrieve_pnr/retrieve_ticket, not call issue again."""
        data = self._request("GET", f"{self.urls['cgi']}/ETIssueJS?{self._q({'AirLine': AIRLINE, 'PNR': pnr, 'EMail': email})}")
        tickets = []
        for row in (data.get("AirNRSTICKETS") or []):
            text = str(row.get("Tickets") or "")
            tickets += [m.group(1) for m in re.finditer(r"=(\d{6,})", text)]
        if not tickets:
            raise MahanError(data.get("Message") or "Issue returned no ticket", code="ISSUE", ambiguous=True)
        return tickets

    def retrieve_ticket(self, ticket_no: str) -> dict:
        return self._request("GET", f"{self.urls['ws1']}/NRSETR.jsp?{self._q({'AirLine': AIRLINE, 'TicketNo': ticket_no})}")

    def cancel_pnr(self, pnr: str) -> str:
        data = self._request("GET", f"{self.urls['cgi']}/CancelPNRJS?{self._q({'AirLine': AIRLINE, 'PNR': pnr})}")
        rows = data.get("AirCancelPNR") or [{}]
        return str(rows[0].get("Error") or "")

    def cancel_seat(self, pnr: str, first: str, last: str, date: str, flight_no: str) -> dict:
        q = self._q({"AirLine": AIRLINE, "PNR": pnr, "PassengerName": first, "PassengerLastName": last, "DepartureDate": date, "FlightNo": flight_no})
        return (self._request("GET", f"{self.urls['cgi']}/CancelSeatJS?{q}").get("AirCancelSeat") or [{}])[0]

    def penalty(self, ticket_no: str, now: bool = True) -> dict:
        return self._request("GET", f"{self.urls['ws1']}/{'NRSPenaltyNow' if now else 'NRSPenalty'}.jsp?{self._q({'AirLine': AIRLINE, 'TicketNo': ticket_no})}")

    def refund(self, ticket_no: str, fare: Decimal, ku: Decimal, lp: Decimal, penalty: Decimal) -> dict:
        """Financial. Values must come from NRSETR (Fare, taxes except LP = KU, LP) and NRSPenalty after seat cancellation."""
        q = self._q({"AirLine": AIRLINE, "TicketNo": ticket_no, "Fare": str(fare), "KU": str(ku), "LP": str(lp), "Penalty": str(penalty)})
        row = (self._request("GET", f"{self.urls['cgi']}/ETRefundJS?{q}").get("AirNRSRefund") or [{}])[0]
        if str(row.get("Done")) != "0":
            raise MahanError(row.get("Desc") or "Refund failed", code=str(row.get("Done")))
        return row


def refund_inputs(etr: dict) -> tuple[Decimal, Decimal, Decimal]:
    """Fare, KU (all taxes except LP) and LP from an NRSETR response, as the reference prescribes."""
    fare = money(etr.get("Fare")) or Decimal(0)
    ku = lp = Decimal(0)
    for t in etr.get("TAXES") or []:
        amount = money(t.get("TaxAmount")) or Decimal(0)
        if str(t.get("TaxCode", "")).upper() == "LP":
            lp += amount
        else:
            ku += amount
    return fare, ku, lp
