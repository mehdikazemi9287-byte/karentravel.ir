"""Niira NRS airline web-service client (one API for many Iranian airlines) — spec: docs/integrations/NIRA_NRS_WEBSERVICE.md.

Switch: NIRA_MODE = off (default) | sandbox | live.
* off / unknown value  → nothing is built, no network call is ever made.
* sandbox              → only Niira's own test airline A1 (http://a1.nirasoft.ir). Any other host is refused at send time.
* live                 → the airlines listed in NIRA_AIRLINES that have NIRA_<CODE>_USER/PASS (and a host). A1 is refused.

Rules kept on purpose (public repo, credentials travel in the query string):
* `OfficeUser`/`OfficePass` go in the query (NRS design). Full URLs and query strings are never logged, never put in an
  exception, and httpx's own "HTTP Request: GET <url>" log line is redacted by `_QueryRedactFilter` (installed at import).
  Exceptions are raised `from None` so the httpx exception (which carries the request URL) is not chained.
* Timeouts on every call (connect 5 s, read 20 s). Only idempotent reads retry (network/timeout/503); ReservJS, ETIssueJS,
  CancelPNRJS, CancelSeatJS and ETRefundJS are sent exactly once — a lost answer is `ambiguous` and must be reconciled
  with NRSRT/NRSETR, never re-sent blindly.
* Money is parsed as whole IRR integers; anything else is refused (fail closed), never estimated.
* DepartureDate (Gregorian) is always sent, and a returned flight whose date differs from the requested date is dropped.
* ETR `Comission` is internal (finance only): `TicketRecord.public()` leaves it out.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

import httpx

log = logging.getLogger("karenseir.nira")

MODES = ("off", "sandbox", "live")
SANDBOX_AIRLINE = "A1"
SANDBOX_HOST = "a1.nirasoft.ir"
DEFAULT_CGI = "NRSWeb.cgi"
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 20.0
READ_RETRIES = 2
RETRYABLE = {"NETWORK", "TIMEOUT", "UNAVAILABLE"}
MAX_PASSENGERS = 9
MAX_DEPENDANTS_PER_ADULT = 4

# Query parameter names, each kept in one place. The spec writes `Airline`/`Email`; Mahan's NRS deployment was exercised
# with `AirLine`/`EMail`. NOT verified against a Niira host yet — first sandbox call decides (see the spec doc).
P_AIRLINE = "Airline"
P_USER = "OfficeUser"
P_PASS = "OfficePass"
P_EMAIL = "Email"
P_COMMAND = "Command"

# Built-in host table from the spec ("verify against the latest Niira document before enabling"). (host, cgi, scheme)
AIRLINES: dict[str, tuple[str, str, str]] = {
    "EP": ("restapi.iaa.ir", DEFAULT_CGI, "https"),
    "FP": ("api.flypersiaairlines.ir", DEFAULT_CGI, "https"),
    "HH": ("api.taban.aero", "NRSWebWS.cgi", "https"),
    "IV": ("api.caspianairlines.com", DEFAULT_CGI, "https"),
    "I3": ("api.ataair.ir", DEFAULT_CGI, "https"),
    "IRZ": ("api.sahaair.com", DEFAULT_CGI, "https"),
    "J1": ("apps.merajairlines.ir", DEFAULT_CGI, "https"),
    "NV": ("api.karunair.ir", "NRSWEB.cgi", "https"),
    "PA": ("api.parsair.ir", DEFAULT_CGI, "https"),
    "PY": ("api.pouyaair.com", "NRSWEB.cgi", "https"),
    "QB": ("api.qeshm-air.com", DEFAULT_CGI, "https"),
    "VR": ("api.vareshair.ir", "NRSWebWS.cgi", "https"),
    "Y9": ("api.kishairlines.ir", "NRSWEB.cgi", "https"),
    "ZV": ("api.zagrosairlines.com", DEFAULT_CGI, "https"),
    "DZD": ("api.yazdairways.com", DEFAULT_CGI, "https"),
    "IRU": ("api.chabaharairlines.ir", DEFAULT_CGI, "https"),
    "A7": ("api.asajet.ir", DEFAULT_CGI, "https"),
    "RAI": ("api.raimonairways.com", DEFAULT_CGI, "https"),
    "ATS": ("api.atlasairplus.com", DEFAULT_CGI, "https"),
    "TKN": ("api.flykishiran.com", DEFAULT_CGI, "https"),
    "NSN": ("api.nasimairlines.ir", DEFAULT_CGI, "https"),
    "ISP": ("nrs.jskyair.com", DEFAULT_CGI, "https"),
    "MEH": ("api.mehrairways.com", DEFAULT_CGI, "https"),
    "LMB": ("nrs.ladairways.ir", DEFAULT_CGI, "https"),
    "MBL": ("nrs.ladairways.ir", DEFAULT_CGI, "https"),
    "SHR": ("nrs.soroushair.com", DEFAULT_CGI, "https"),
    SANDBOX_AIRLINE: (SANDBOX_HOST, DEFAULT_CGI, "http"),
}
# Codes accepted only with an explicit NIRA_<CODE>_HOST (no default host in the spec). W5 = Mahan on Niira; the existing
# Mahan MRS integration (mahan_mrs.py / MAHAN_MODE) is separate and untouched.
EXPLICIT_HOST_ONLY = {"W5"}
# Office-user prefixes on the owner's account sheet → airline code.
ALIASES = {"VAR": "VR", "JI": "J1", "TBN": "HH"}
NAMES_FA = {"EP": "آسمان", "FP": "فلای‌پرشیا", "HH": "تابان", "IV": "کاسپین", "I3": "آتا", "IRZ": "ساها", "J1": "معراج", "NV": "کارون", "PA": "پارس‌ایر",
            "PY": "پویا", "QB": "قشم‌ایر", "VR": "وارش", "Y9": "کیش‌ایر", "ZV": "زاگرس", "DZD": "یزد", "IRU": "چابهار", "A7": "آسا جت", "RAI": "ریمون",
            "ATS": "اطلس", "TKN": "کیش ایران", "NSN": "نسیم", "ISP": "جی‌اسکای", "MEH": "مهر", "LMB": "لاد", "MBL": "لاد", "SHR": "سروش",
            "A1": "تست نیرا", "W5": "ماهان"}


# ------------------------------------------------------------------------------------------------ redaction
_SECRET_PARAM = re.compile(r"((?:Office)?(?:User|Pass)(?:word)?|pwd|password)(=|\"?\s*:\s*\"?)([^&\s\"',;}<]*)", re.I)


def redact(text: Any, *secrets: str) -> str:
    """Hide OfficeUser=/OfficePass= values and any known secret value in free text (error pages, echoes)."""
    out = _SECRET_PARAM.sub(lambda m: m.group(1) + m.group(2) + "***", str(text))
    for v in secrets:
        if v and len(v) >= 3:
            out = out.replace(v, "***")
    return out


def strip_query(text: str) -> str:
    """Drop every URL query string from a log message (…?a=b&OfficePass=… → …?[redacted])."""
    return re.sub(r"\?[^\s\"']*", "?[redacted]", text)


class _QueryRedactFilter(logging.Filter):
    """httpx logs 'HTTP Request: GET <full url> ...' at INFO — the URL carries OfficePass. Rewrite the record safely."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # never let logging break a request
            msg = str(record.msg)
        record.msg, record.args = redact(strip_query(msg)), None
        return True


_FILTER = _QueryRedactFilter()
for _name in ("httpx", "httpcore"):
    if not any(isinstance(f, _QueryRedactFilter) for f in logging.getLogger(_name).filters):
        logging.getLogger(_name).addFilter(_FILTER)


# ------------------------------------------------------------------------------------------------ errors
class NiraError(RuntimeError):
    """`nrs_text` is the (redacted) reason NRS gave. Never contains a URL, query string, OfficeUser or OfficePass."""

    def __init__(self, code: str, nrs_text: str = "", *, status: Optional[int] = None, ambiguous: bool = False, airline: str = ""):
        self.code, self.nrs_text, self.status, self.ambiguous, self.airline = code, nrs_text, status, ambiguous, airline
        super().__init__(f"{code}" + (f": {nrs_text}" if nrs_text else ""))

    @property
    def category(self) -> str:
        return ERROR_CATEGORY.get(self.code, "provider")

    @property
    def message_fa(self) -> str:
        return MESSAGES_FA.get(self.code, MESSAGES_FA["NRS_ERROR"])

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE


# (upper-case fragment as NRS writes it, code, category). First match wins, so the longer/more specific fragment comes first.
ERROR_TABLE: list[tuple[str, str, str]] = [
    ("PASSPORT DOCS SSR IS MANDATORY", "PASSPORT_MANDATORY", "passenger"),
    ("SSR DOCS IS MANDATORY", "DOCS_MANDATORY", "passenger"),
    ("INVALID DOCS NUMBER", "INVALID_DOCS", "passenger"),
    ("DUPLICATE NATIONAL CODE", "DUPLICATE_NATIONAL_CODES", "passenger"),
    ("INVALID PASSPORT INFORMATION", "INVALID_PASSPORT", "passenger"),
    ("INVALID PASSENGERS CONTACT", "INVALID_CONTACT", "passenger"),
    ("INCORRECT CONTACT", "INVALID_CONTACT", "passenger"),
    ("INVALID PASSENGER NAME", "INVALID_PASSENGER_NAME", "passenger"),
    ("CHILD OR INFANT WITHOUT PARENT", "CHILD_WITHOUT_ADULT", "passenger"),
    ("FLIGHT CLOSED", "FLIGHT_CLOSED", "inventory"),
    ("CLASS CLOSED", "CLASS_CLOSED", "inventory"),
    ("INVALID FLIGHT", "INVALID_FLIGHT", "inventory"),
    ("POINT OF SALES RESTRICTED", "POS_RESTRICTED", "inventory"),
    ("INVALIDDESTINATION", "INVALID_DESTINATION", "inventory"),
    ("NOT ENOUGH CREDIT", "NOT_ENOUGH_CREDIT", "account"),
    ("SALES CHANNEL NOT ALLOWED", "SALES_CHANNEL_NOT_ALLOWED", "account"),
    ("REMOTE USER NOT REGISTERED", "REMOTE_USER_NOT_REGISTERED", "account"),
    ("USER ACCOUNT HAS BEEN EXPIRED", "ACCOUNT_EXPIRED", "account"),
    ("INVALID USER NAME", "INVALID_USER", "account"),
    ("INCORRECT PASSWORD", "INCORRECT_PASSWORD", "account"),
    ("ACCESS DENIED", "ACCESS_DENIED", "account"),
    ("SIGN!", "SIGN", "account"),
    ("PNR IS ALREADY TICKETED", "ALREADY_TICKETED", "ticket"),
    ("PNR IS CANCELLED", "PNR_CANCELLED", "ticket"),
    ("ALREADY CANCELLED", "ALREADY_CANCELLED", "ticket"),
    ("NO ELECTRONIC TICKET LOADED YET", "NO_ETICKET_YET", "ticket"),
    ("TICKET NUMBER NOT FOUND", "TICKET_NOT_FOUND", "ticket"),
    ("INVALID TICKET NUMBER", "INVALID_TICKET", "ticket"),
    ("INCORRECT RETURN FARE", "INCORRECT_RETURN_FARE", "ticket"),
    ("RESERVATION FAILUR", "RESERVATION_FAILURE", "inventory"),
]
ERROR_CATEGORY = {code: cat for _, code, cat in ERROR_TABLE} | {c: "transport" for c in RETRYABLE} | {"BAD_RESPONSE": "provider", "HOST_NOT_ALLOWED": "config"}

MESSAGES_FA = {
    "PASSPORT_MANDATORY": "برای پرواز خارجی اطلاعات گذرنامهٔ مسافر لازم است.",
    "DOCS_MANDATORY": "اطلاعات مدرک شناسایی مسافر (کد ملی یا گذرنامه) لازم است.",
    "INVALID_DOCS": "شمارهٔ مدرک شناسایی مسافر نامعتبر است.",
    "DUPLICATE_NATIONAL_CODES": "کد ملی تکراری در فهرست مسافران وجود دارد.",
    "INVALID_PASSPORT": "اطلاعات گذرنامهٔ مسافر نامعتبر است.",
    "INVALID_CONTACT": "شمارهٔ تماس مسافر نامعتبر است.",
    "INVALID_PASSENGER_NAME": "نام مسافر را ایرلاین نپذیرفت؛ نام لاتین را بررسی کنید.",
    "CHILD_WITHOUT_ADULT": "کودک یا نوزاد بدون همراه بزرگسال قابل رزرو نیست.",
    "FLIGHT_CLOSED": "فروش این پرواز بسته شده است.",
    "CLASS_CLOSED": "ظرفیت این کلاس پروازی تمام شده است.",
    "INVALID_FLIGHT": "این پرواز معتبر نیست یا تغییر کرده است.",
    "POS_RESTRICTED": "فروش این پرواز از این کانال مجاز نیست.",
    "INVALID_DESTINATION": "این مسیر را ایرلاین نمی‌شناسد.",
    "RESERVATION_FAILURE": "رزرو انجام نشد؛ دوباره جست‌وجو کنید.",
    "NOT_ENOUGH_CREDIT": "اعتبار حساب نزد ایرلاین کافی نیست.",
    "SALES_CHANNEL_NOT_ALLOWED": "کاربر وب‌سرویس این ایرلاین برای فروش آنلاین تعریف نشده است (یوزر WS لازم است).",
    "REMOTE_USER_NOT_REGISTERED": "کاربر وب‌سرویس نزد ایرلاین ثبت نشده است.",
    "ACCOUNT_EXPIRED": "حساب کاربری نزد ایرلاین منقضی شده است.",
    "INVALID_USER": "نام کاربری وب‌سرویس ایرلاین نامعتبر است.",
    "INCORRECT_PASSWORD": "رمز وب‌سرویس ایرلاین نادرست است.",
    "ACCESS_DENIED": "ایرلاین دسترسی را رد کرد (ممکن است IP سرور در فهرست مجاز نباشد).",
    "SIGN": "ایرلاین ورود را نپذیرفت.",
    "ALREADY_TICKETED": "برای این رزرو قبلاً بلیت صادر شده است.",
    "PNR_CANCELLED": "این رزرو باطل شده است.",
    "ALREADY_CANCELLED": "این رزرو قبلاً باطل شده است.",
    "NO_ETICKET_YET": "بلیت الکترونیکی هنوز صادر نشده است.",
    "TICKET_NOT_FOUND": "شمارهٔ بلیت پیدا نشد.",
    "INVALID_TICKET": "شمارهٔ بلیت نامعتبر است.",
    "INCORRECT_RETURN_FARE": "مبلغ استرداد را ایرلاین نپذیرفت؛ مبالغ دوباره محاسبه شود.",
    "SCHEDULE_CHANGED": "ساعت یا تاریخ پرواز تغییر کرده است؛ دوباره جست‌وجو کنید.",
    "DATE_MISMATCH": "تاریخ پرواز اعلامی ایرلاین با تاریخ درخواستی یکسان نیست.",
    "TIMEOUT": "پاسخ ایرلاین به‌موقع نرسید.",
    "NETWORK": "ارتباط با ایرلاین برقرار نشد.",
    "UNAVAILABLE": "سرویس ایرلاین موقتاً در دسترس نیست.",
    "HOST_NOT_ALLOWED": "این آدرس برای حالت فعلی اتصال نیرا مجاز نیست.",
    "BAD_RESPONSE": "پاسخ ایرلاین قابل خواندن نبود.",
    "ISSUE_NO_TICKETS": "شمارهٔ بلیت از ایرلاین نرسید؛ وضعیت رزرو باید بررسی شود.",
    "NRS_ERROR": "ایرلاین درخواست را نپذیرفت.",
}

_SUCCESS_TEXT = re.compile(r"^\s*(no\s*err(or)?\b|success\b|ok\s*$)", re.I)
_ERR_KEY = re.compile(r"^(error|err|errors|errormessage|errordesc|message|msg|desc|description_en)$", re.I)   # error fields only, not rule texts


def map_error(text: str) -> Optional[str]:
    up = (text or "").upper()
    for frag, code, _ in ERROR_TABLE:
        if frag in up:
            return code
    return None


def _texts(data: Any, key: str = "") -> list[str]:
    """Every string under an error-like key (Error, Desc, Message …), plus a bare string answer."""
    if isinstance(data, str):
        return [data] if (not key or _ERR_KEY.search(key)) else []
    out: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            out += _texts(v, str(k)) if isinstance(v, (dict, list)) or _ERR_KEY.search(str(k)) else []
    elif isinstance(data, list):
        for v in data:
            out += _texts(v, key)
    return out


def raise_for_nrs(data: Any, airline: str = "", allow: tuple[str, ...] = ()) -> None:
    """Raise the typed error for the first known NRS error string in the answer (codes in `allow` are not errors here)."""
    for t in _texts(data):
        if _SUCCESS_TEXT.match(t):
            continue
        code = map_error(t)
        if code and code not in allow:
            raise NiraError(code, redact(t)[:300], airline=airline)


# ------------------------------------------------------------------------------------------------ parsing helpers
def to_int(v: Any) -> Optional[int]:
    """Whole IRR amount from an NRS number/string ("1,250,000", "1250000.0"). None when absent or not a whole number."""
    if v is None or isinstance(v, bool):
        return None
    s = str(v).replace(",", "").strip()
    if not s or s == "-":
        return None
    m = re.fullmatch(r"(-?\d+)(?:\.0+)?", s)
    return int(m.group(1)) if m else None


def _get(d: Any, *keys: str) -> Any:
    """Case-insensitive key lookup (NRS deployments differ in key casing)."""
    if not isinstance(d, dict):
        return None
    low = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        v = low.get(k.lower())
        if v not in (None, ""):
            return v
    return None


def scrub(value: Any, secrets: tuple[str, ...]) -> Any:
    """Known secret values removed from every string (keys included) of a parsed answer, before anything reads it."""
    if isinstance(value, dict):
        return {scrub(k, secrets): scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    if isinstance(value, str):
        return redact(value, *secrets)
    return value


def _rows(data: Any, *wrappers: str) -> list[dict]:
    v = _get(data, *wrappers)
    if isinstance(v, dict):
        return [v]
    return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []


@dataclass(frozen=True)
class Tax:
    code: str
    amount: int
    en: str = ""
    fa: str = ""


_TAX_PART = re.compile(r"^\s*([A-Za-z0-9]{1,4})\s*:\s*(-?[\d,]+(?:\.0+)?)\s*(?:,\s*EN_Desc\s*:(.*?))?\s*(?:,\s*FA_Desc\s*:(.*))?\s*$", re.S)


def parse_taxes(value: Any) -> list[Tax]:
    """`CODE:amount,EN_Desc:..,FA_Desc:..$CODE:amount,...` — or a list of {TaxCode, TaxAmount} (ETR). A malformed part
    raises BAD_RESPONSE: a tax we cannot read would make totals and refunds wrong."""
    if value in (None, ""):
        return []
    if isinstance(value, list):
        out = []
        for t in value:
            if isinstance(t, str):
                out += parse_taxes(t)
                continue
            code, amount = str(_get(t, "TaxCode", "Code") or "").strip().upper(), to_int(_get(t, "TaxAmount", "Amount"))
            if not code or amount is None:
                raise NiraError("BAD_RESPONSE", "tax entry without code or whole amount")
            out.append(Tax(code, amount, str(_get(t, "EN_Desc", "TaxDesc") or ""), str(_get(t, "FA_Desc") or "")))
        return out
    out = []
    for part in str(value).split("$"):
        if not part.strip():
            continue
        m = _TAX_PART.match(part)
        if not m or to_int(m.group(2)) is None:
            raise NiraError("BAD_RESPONSE", "unreadable tax string")
        out.append(Tax(m.group(1).upper(), to_int(m.group(2)) or 0, (m.group(3) or "").strip(), (m.group(4) or "").strip()))
    return out


def parse_cap(cap: Any) -> tuple[str, int, bool]:
    """(state, seats, more_than_nine). Last character of the cap: A = more than 9, 0-9 = exact seats (0 = closed),
    C = closed (full), X = cancelled. Anything else is treated as closed (fail closed)."""
    s = str(cap or "").strip().upper()[-1:]
    if s == "A":
        return "open", 9, True
    if s.isdigit():
        return ("open" if int(s) > 0 else "closed"), int(s), False
    if s == "X":
        return "cancelled", 0, False
    return "closed", 0, False


@dataclass(frozen=True)
class ClassAvail:
    rbd: str
    state: str
    seats: int
    more_than_nine: bool
    price: Optional[int] = None
    currency: Optional[str] = None

    def bookable_for(self, seated: int) -> bool:
        return self.state == "open" and (self.more_than_nine or self.seats >= seated)


@dataclass(frozen=True)
class Flight:
    airline: str
    flight_no: str
    origin: str
    destination: str
    departure: datetime          # airport-local wall time as NRS returns it (naive)
    arrival: Optional[datetime]
    classes: tuple[ClassAvail, ...]
    transit: str = ""
    aircraft: str = ""
    refund_status: Any = None


def parse_local(value: Any) -> Optional[datetime]:
    s = str(value or "").strip().replace("T", " ").replace("/", "-")
    if not s:
        return None
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16)):
        try:
            return datetime.strptime(s[:n], fmt)
        except ValueError:
            continue
    return None                                               # a date without a time is not a departure time


def _classes(raw: Any) -> list[ClassAvail]:
    out: list[ClassAvail] = []
    if isinstance(raw, str):                                  # AvailabilityJS: "YA M4 BC" style tokens
        for tok in re.split(r"[\s,;/|]+", raw.strip()):
            if len(tok) >= 2:
                state, seats, plus = parse_cap(tok[-1])
                out.append(ClassAvail(tok[:-1].upper(), state, seats, plus))
        return out
    for c in raw or []:
        if not isinstance(c, dict):
            continue
        cap = str(_get(c, "Cap") or "")
        rbd = str(_get(c, "FlightClass") or "").strip().upper() or cap[:-1].upper()
        if not rbd:
            continue
        state, seats, plus = parse_cap(cap)
        out.append(ClassAvail(rbd, state, seats, plus, to_int(_get(c, "Price")), (str(_get(c, "CurrencyCode") or "") or None)))
    return out


@dataclass(frozen=True)
class Availability:
    flights: tuple[Flight, ...]
    rejected: tuple[dict, ...]   # [{"flight_no", "reason"}] — dropped, never repaired


def parse_availability(data: Any, airline: str, origin: str, destination: str, day: date) -> Availability:
    if not isinstance(data, (dict, list)):
        raise NiraError("BAD_RESPONSE", "availability answer is not JSON", airline=airline)
    raise_for_nrs(data, airline)
    rows = _rows(data, "AvailableFlights") if isinstance(data, dict) else [r for r in data if isinstance(r, dict)]
    flights, rejected = [], []
    for r in rows:
        fn = str(_get(r, "FlightNo") or "").strip()
        o, d = str(_get(r, "Origin") or "").strip().upper(), str(_get(r, "Destination") or "").strip().upper()
        dep, arr = parse_local(_get(r, "DepartureDateTime")), parse_local(_get(r, "ArrivalDateTime"))
        reason = None
        if not fn:
            reason = "no_flight_no"
        elif dep is None:
            reason = "no_departure_time"
        elif dep.date() != day:
            reason = "date_mismatch"                          # spec: the returned date must equal the requested date
        elif o != origin or d != destination:
            reason = "route_mismatch"
        if reason:
            rejected.append({"flight_no": fn, "reason": reason})
            continue
        flights.append(Flight(airline=str(_get(r, "Airline") or airline).strip().upper(), flight_no=fn, origin=o, destination=d, departure=dep, arrival=arr,
                              classes=tuple(_classes(_get(r, "ClassesStatus"))), transit=str(_get(r, "Transit") or ""),
                              aircraft=str(_get(r, "AircraftTypeCode") or ""), refund_status=_get(r, "ClassRefundStatus")))
    return Availability(tuple(flights), tuple(rejected))


@dataclass(frozen=True)
class PaxFare:
    base: int
    total: int
    taxes: tuple[Tax, ...]


@dataclass(frozen=True)
class FareQuote:
    adult: Optional[PaxFare]
    child: Optional[PaxFare]
    infant: Optional[PaxFare]
    rules: Any
    baggage_weight: Any
    baggage_pieces: Any


def parse_fare(data: Any, airline: str = "") -> FareQuote:
    if not isinstance(data, dict):
        raise NiraError("BAD_RESPONSE", "fare answer is not JSON", airline=airline)
    raise_for_nrs(data, airline)
    row = (_rows(data, "Fare", "Fares", "AirFare") or [data])[0]

    def pax(prefix: str) -> Optional[PaxFare]:
        base, total = to_int(_get(row, prefix + "Fare")), to_int(_get(row, prefix + "TotalPrice"))
        if base is None and total is None:
            return None
        if base is None or total is None or base < 0 or total <= 0:
            raise NiraError("BAD_RESPONSE", f"{prefix} fare without whole base and total", airline=airline)
        return PaxFare(base, total, tuple(parse_taxes(_get(row, prefix + "Taxes"))))
    q = FareQuote(pax("Adult"), pax("Child"), pax("Infant"), _get(row, "CRCNRules"), _get(row, "BaggageAllowanceWeight"), _get(row, "BaggageAllowancePieces"))
    if q.adult is None:
        raise NiraError("BAD_RESPONSE", "fare without adult price", airline=airline)
    return q


@dataclass(frozen=True)
class TicketRecord:
    ticket_no: str
    fare: int
    total: Optional[int]
    taxes: tuple[Tax, ...]
    commission: Optional[int] = field(default=None, repr=False)   # internal / finance only
    coupons: Any = field(default=None, repr=False)

    def public(self) -> dict:
        """Customer-safe view: no commission, no coupons/history internals."""
        return {"ticket_no": self.ticket_no, "fare": self.fare, "total": self.total, "taxes": [{"code": t.code, "amount": t.amount} for t in self.taxes]}


def parse_ticket(data: Any, ticket_no: str, airline: str = "") -> TicketRecord:
    if not isinstance(data, dict):
        raise NiraError("BAD_RESPONSE", "ETR answer is not JSON", airline=airline)
    raise_for_nrs(data, airline)
    row = (_rows(data, "AirNRSETR", "ETR", "Ticket") or [data])[0]
    fare = to_int(_get(row, "Fare"))
    if fare is None or fare < 0:
        raise NiraError("BAD_RESPONSE", "ETR without whole Fare", airline=airline)
    return TicketRecord(ticket_no=str(_get(row, "TicketNo", "TicketNumber") or ticket_no), fare=fare, total=to_int(_get(row, "TotalPrice")),
                        taxes=tuple(parse_taxes(_get(row, "TAXES", "Taxes"))), commission=to_int(_get(row, "Comission", "Commission")), coupons=_get(row, "COUPONS"))


@dataclass(frozen=True)
class PenaltyResult:
    penalty: int
    refunded_amount: Optional[int]
    legs: tuple[dict, ...]
    refunded_taxes: tuple[Any, ...]


def parse_penalty(data: Any, airline: str = "") -> PenaltyResult:
    if not isinstance(data, dict):
        raise NiraError("BAD_RESPONSE", "penalty answer is not JSON", airline=airline)
    raise_for_nrs(data, airline)
    row = (_rows(data, "AirNRSPenalty", "Penalty") or [data])[0]
    pen = to_int(_get(row, "PENALTY"))
    if pen is None or pen < 0:
        raise NiraError("BAD_RESPONSE", "penalty without whole PENALTY", airline=airline)
    legs = tuple({"refunded_fare": to_int(_get(leg, "RefundedFare")), "amount": to_int(_get(leg, "Amount")), "mode": _get(leg, "Mode"),
                  "am": _get(leg, "AM"), "cancellation": _get(leg, "Cancellation")} for leg in (_get(row, "Legs") or []) if isinstance(leg, dict))
    return PenaltyResult(pen, to_int(_get(row, "RefundedAmount")), legs, tuple(_get(row, "RefundedTaxes") or []))


@dataclass(frozen=True)
class RefundInputs:
    fare: int
    ku: int
    lp: int
    penalty: int


def refund_inputs(ticket: TicketRecord, penalty: PenaltyResult) -> RefundInputs:
    """ETRefund amounts as the spec prescribes: Fare = ETR base fare, LP = airport tax (TaxCode LP), KU = every other ETR tax,
    Penalty = NRSPenalty's PENALTY (computed after the seat was cancelled)."""
    lp = sum(t.amount for t in ticket.taxes if t.code == "LP")
    ku = sum(t.amount for t in ticket.taxes if t.code != "LP")
    if penalty.penalty > ticket.fare + lp + ku:
        raise NiraError("BAD_RESPONSE", "penalty larger than the ticket value")
    return RefundInputs(ticket.fare, ku, lp, penalty.penalty)


# ------------------------------------------------------------------------------------------------ passengers
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_NAME = re.compile(r"^[A-Z][A-Z ]{0,39}$")


def ddmmmyy(d: Optional[date]) -> str:
    return f"{d.day:02d}{MONTHS[d.month - 1]}{d.year % 100:02d}" if d else ""


def national_id_ok(nid: str) -> bool:
    """Iranian national code: 10 digits with the official check digit."""
    if not re.fullmatch(r"\d{10}", nid or "") or len(set(nid)) == 1:
        return False
    s = sum(int(nid[i]) * (10 - i) for i in range(9)) % 11
    return int(nid[9]) == (s if s < 2 else 11 - s)


@dataclass(frozen=True)
class Passenger:
    type: str                      # ADT | CHD | INF
    first_name: str
    last_name: str
    gender: str                    # M | F
    birth_date: date
    document_type: str             # I = Iranian national ID (domestic) | P = passport
    document_number: str
    issued_by: str = ""            # country of issue (passport) — may be empty for I
    birth_country: str = ""
    expiry: Optional[date] = None
    title: str = ""                # optional explicit female title MS | MRS | MISS


def title_for(p: Passenger) -> str:
    if p.gender == "M":
        return "MR"
    if p.title:
        if p.title.upper() not in ("MS", "MRS", "MISS"):
            raise ValueError("female title must be MS, MRS or MISS")
        return p.title.upper()
    return "MS" if p.type == "ADT" else "MISS"


def edt_id(p: Passenger) -> str:
    """`I_{IssuedBy}_{NationalId}_{BirthCountry}_{BirthDate}_{Gender}_{Expire}_{Last}_{First}` (only national ID and birth date
    are mandatory for I); `P_...` with the same order for passports (all fields required)."""
    if p.gender not in ("M", "F"):
        raise ValueError("gender must be M or F")
    last, first = p.last_name.strip().upper(), p.first_name.strip().upper()
    if not _NAME.match(last) or not _NAME.match(first):
        raise ValueError("names must be Latin letters")
    if p.document_type == "I":
        if not national_id_ok(p.document_number):
            raise ValueError("invalid Iranian national ID")
        if p.birth_date is None:
            raise ValueError("birth date is mandatory")
    elif p.document_type == "P":
        if not re.fullmatch(r"[A-Z0-9]{5,20}", (p.document_number or "").upper()) or not p.issued_by or p.expiry is None:
            raise ValueError("passport needs number, issuing country and expiry")
    else:
        raise ValueError("document type must be I or P")
    parts = [p.document_type, p.issued_by.upper(), p.document_number.upper(), p.birth_country.upper(), ddmmmyy(p.birth_date), p.gender,
             ddmmmyy(p.expiry), last, first]
    if any("_" in x for x in parts[1:]):
        raise ValueError("fields may not contain '_'")
    return "_".join(parts)


def _age_years(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def reserve_params(passengers: list[Passenger], departure_day: date) -> dict:
    """edtName{i}/edtLast{i}/edtAge{i}/edtID{i} for i = 1..n. Composition: 1..9 passengers, the first is an adult, at most
    4 children/infants per adult, at most one infant per adult. `edtAge` is sent as whole years on the departure day
    (NOT verified on a Niira host yet — see spec doc)."""
    n = len(passengers)
    adults = sum(1 for p in passengers if p.type == "ADT")
    infants = sum(1 for p in passengers if p.type == "INF")
    if not 1 <= n <= MAX_PASSENGERS or passengers[0].type != "ADT":
        raise ValueError("1-9 passengers and the first must be an adult")
    if any(p.type not in ("ADT", "CHD", "INF") for p in passengers):
        raise ValueError("passenger type must be ADT, CHD or INF")
    if n - adults > MAX_DEPENDANTS_PER_ADULT * adults or infants > adults:
        raise ValueError("too many children/infants per adult")
    nids = [p.document_number for p in passengers if p.document_type == "I"]
    if len(nids) != len(set(nids)):
        raise ValueError("duplicate national ID")
    out: dict[str, Any] = {"No": n}
    for i, p in enumerate(passengers, 1):
        out[f"edtName{i}"] = f"{p.first_name.strip().upper()} {title_for(p)}"
        out[f"edtLast{i}"] = p.last_name.strip().upper()
        out[f"edtAge{i}"] = _age_years(p.birth_date, departure_day)
        out[f"edtID{i}"] = edt_id(p)
    return out


# ------------------------------------------------------------------------------------------------ configuration (env only)
@dataclass(frozen=True)
class AirlineConfig:
    code: str
    scheme: str
    host: str
    cgi: str
    user: str = field(repr=False)
    password: str = field(repr=False)
    routes: Optional[frozenset] = None          # {"THR-MHD", ...}; None = no route table configured

    def base(self) -> str:
        return f"{self.scheme}://{self.host}"

    def ws1(self, method: str) -> str:
        return f"{self.base()}/ws1/{method}"

    def ws2(self, method: str) -> str:
        return f"{self.base()}/ws2/cgi-bin/{self.cgi}/{method}"

    def flies(self, origin: str, destination: str) -> bool:
        return self.routes is None or f"{origin}-{destination}" in self.routes


def nira_mode() -> tuple[str, Optional[str]]:
    raw = (os.getenv("NIRA_MODE") or "off").strip().lower()
    if raw not in MODES:
        return "off", "invalid_mode"
    return raw, ("off" if raw == "off" else None)


def canonical(code: str) -> str:
    c = (code or "").strip().upper()
    return ALIASES.get(c, c)


def requested_airlines() -> list[str]:
    seen: list[str] = []
    for c in (os.getenv("NIRA_AIRLINES") or "").split(","):
        c = canonical(c)
        if c and c not in seen:
            seen.append(c)
    return seen


def _host(raw: str, default_scheme: str) -> Optional[tuple[str, str]]:
    raw = raw.strip()
    parts = urlsplit(raw if "://" in raw else f"{default_scheme}://{raw}")
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment or parts.path not in ("", "/") or parts.username:
        return None
    return parts.scheme, parts.hostname.lower() + (f":{parts.port}" if parts.port else "")


def airline_config(code: str, mode: str) -> tuple[Optional[AirlineConfig], str, list[str]]:
    """(config or None, reason, missing setting NAMES). Never returns or logs a value."""
    if mode == "sandbox" and code != SANDBOX_AIRLINE:
        return None, "sandbox_only_a1", []
    if mode == "live" and code == SANDBOX_AIRLINE:
        return None, "test_airline_in_live", []
    default = AIRLINES.get(code)
    env_host = (os.getenv(f"NIRA_{code}_HOST") or "").strip()
    if default is None and code not in EXPLICIT_HOST_ONLY:
        return None, "unknown_airline", []
    missing = [f"NIRA_{code}_{k}" for k in ("USER", "PASS") if not (os.getenv(f"NIRA_{code}_{k}") or "").strip()]
    if default is None and not env_host:
        missing.insert(0, f"NIRA_{code}_HOST")
    if missing:
        return None, "missing_credentials", missing
    hp = _host(env_host, "https") if env_host else (default[2], default[0])
    if hp is None:
        return None, "invalid_host", []
    scheme, host = hp
    if mode == "sandbox" and (host != SANDBOX_HOST):
        return None, "host_not_allowed", []
    if mode == "live" and (scheme != "https" or host == SANDBOX_HOST):
        return None, "host_not_allowed", []
    cgi = (os.getenv(f"NIRA_{code}_CGI") or (default[1] if default else DEFAULT_CGI)).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.cgi", cgi):
        return None, "invalid_cgi", []
    routes_raw = (os.getenv(f"NIRA_{code}_ROUTES") or "").strip()
    routes = frozenset(r.strip().upper() for r in routes_raw.split(",") if re.fullmatch(r"\s*[A-Za-z]{3}-[A-Za-z]{3}\s*", r)) if routes_raw else None
    return AirlineConfig(code, scheme, host, cgi, os.environ[f"NIRA_{code}_USER"].strip(), os.environ[f"NIRA_{code}_PASS"].strip(), routes), "ok", []


# ------------------------------------------------------------------------------------------------ client
Sender = Callable[[str, dict], httpx.Response]


class NiraClient:
    """One airline on one NRS host. Build with `NiraClient(mode, config)`; `http` lets tests inject an httpx.Client with a
    MockTransport (the real httpx code path, logging included, still runs)."""

    def __init__(self, mode: str, config: AirlineConfig, *, http: Optional[httpx.Client] = None, sleep: Callable[[float], None] = time.sleep,
                 read_retry_codes: frozenset = frozenset(RETRYABLE)):
        if mode not in ("sandbox", "live"):
            raise ValueError("NiraClient needs sandbox or live mode")
        self.mode, self.cfg, self._http, self._sleep, self.read_retry_codes = mode, config, http, sleep, read_retry_codes

    def __repr__(self) -> str:
        return f"NiraClient(mode={self.mode!r}, airline={self.cfg.code!r}, host={self.cfg.host!r})"

    # -- transport
    def _allowed(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").lower()
        expected = self.cfg.host.split(":")[0]
        if host != expected or (self.mode == "sandbox" and host != SANDBOX_HOST) or (self.mode == "live" and (host == SANDBOX_HOST or not url.startswith("https://"))):
            raise NiraError("HOST_NOT_ALLOWED", airline=self.cfg.code)

    def _send(self, op: str, url: str, params: dict, *, text_ok: bool = False) -> Any:
        """Exactly one HTTP GET. No URL/params in logs or errors; secrets redacted from any echoed text."""
        self._allowed(url)
        q = {P_AIRLINE: self.cfg.code, **params, P_USER: self.cfg.user, P_PASS: self.cfg.password}
        secrets = (self.cfg.user, self.cfg.password)
        started = time.monotonic()
        timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)
        failure: Optional[NiraError] = None
        r = None
        try:
            if self._http is not None:
                r = self._http.get(url, params=q, timeout=timeout)
            else:
                with httpx.Client(timeout=timeout, follow_redirects=False) as c:
                    r = c.get(url, params=q)
        except httpx.TimeoutException:
            failure = NiraError("TIMEOUT", airline=self.cfg.code, ambiguous=True)
        except httpx.HTTPError as exc:
            failure = NiraError("NETWORK", f"{type(exc).__name__}", airline=self.cfg.code)
        if failure is not None or r is None:
            # raised outside the except block: no __cause__/__context__ carrying the httpx exception (its request has the URL)
            log.warning("nira %s airline=%s %s", op, self.cfg.code, failure.code if failure else "NETWORK")
            raise failure or NiraError("NETWORK", airline=self.cfg.code)
        log.info("nira %s airline=%s status=%s ms=%d", op, self.cfg.code, r.status_code, int((time.monotonic() - started) * 1000))
        text = (r.text or "").strip()
        if r.status_code == 503:
            raise NiraError("UNAVAILABLE", status=503, airline=self.cfg.code)
        if r.status_code >= 400:
            safe = redact(strip_query(text), *secrets)[:300]
            raise NiraError(map_error(text) or "NRS_ERROR", safe, status=r.status_code, airline=self.cfg.code)
        try:
            data, parsed = r.json(), True
        except ValueError:
            data, parsed = None, False
        if not parsed:
            code = map_error(text)
            if text_ok and not code:
                return redact(strip_query(text), *secrets)                      # NRSCommand answers terminal text
            raise NiraError(code or "BAD_RESPONSE", redact(strip_query(text), *secrets)[:120], airline=self.cfg.code)
        data = scrub(data, secrets)                                              # an NRS echo of the user/password never travels further
        if isinstance(data, str):
            code = map_error(data)
            if code:
                raise NiraError(code, redact(data, *secrets)[:300], airline=self.cfg.code)
        return data

    def _read(self, op: str, url: str, params: dict, **kw: Any) -> Any:
        """Idempotent reads only: retry on network/timeout/503, never on an NRS business answer."""
        for attempt in range(READ_RETRIES + 1):
            try:
                return self._send(op, url, params, **kw)
            except NiraError as exc:
                if exc.code not in self.read_retry_codes or attempt == READ_RETRIES:
                    raise
                self._sleep(min(0.5 * (2 ** attempt), 2.0))
        raise AssertionError("unreachable")

    # -- shopping (reads)
    def _avail(self, method: str, origin: str, destination: str, day: date, adults: int, children: int, infants: int) -> Availability:
        o, d = origin.upper(), destination.upper()
        params = {"cbSource": o, "cbTarget": d, "cbAdultQty": adults, "cbChildQty": children, "cbInfantQty": infants, "DepartureDate": day.isoformat()}
        return parse_availability(self._read(method, self.cfg.ws1(method), params), self.cfg.code, o, d, day)

    def availability_fare(self, origin: str, destination: str, day: date, adults: int = 1, children: int = 0, infants: int = 0) -> Availability:
        return self._avail("AvailabilityFareJS.jsp", origin, destination, day, adults, children, infants)

    def availability(self, origin: str, destination: str, day: date, adults: int = 1, children: int = 0, infants: int = 0) -> Availability:
        return self._avail("AvailabilityJS.jsp", origin, destination, day, adults, children, infants)

    def fare(self, origin: str, destination: str, rbd: str, flight_no: str, day: date) -> FareQuote:
        params = {"Route": f"{origin.upper()}-{destination.upper()}", "RBD": rbd, "FlightNo": flight_no, "DepartureDate": day.isoformat()}
        return parse_fare(self._read("FareJS.jsp", self.cfg.ws1("FareJS.jsp"), params), self.cfg.code)

    def recheck(self, flight: Flight, rbd: str, seated: int) -> Flight:
        """Re-read availability right before a reservation: same flight number, same date AND time, class still bookable."""
        fresh = self.availability_fare(flight.origin, flight.destination, flight.departure.date(), max(seated, 1))
        match = [f for f in fresh.flights if f.flight_no == flight.flight_no]
        if not match or match[0].departure != flight.departure:
            raise NiraError("SCHEDULE_CHANGED", airline=self.cfg.code)
        cls = next((c for c in match[0].classes if c.rbd == rbd), None)
        if cls is None or not cls.bookable_for(seated):
            raise NiraError("CLASS_CLOSED", airline=self.cfg.code)
        return match[0]

    # -- booking (writes: sent once, never retried)
    def reserve(self, flight: Flight, rbd: str, passengers: list[Passenger], contact: str) -> dict:
        """Re-checks the flight time, then ReservJS once. Returns {"pnr", "time_limit"}. A timeout is ambiguous (a PNR may
        exist): reconcile with retrieve_pnr, do not call reserve again."""
        params = reserve_params(passengers, flight.departure.date())                     # validates before any network call
        if not re.fullmatch(r"[0-9+|\- ]{8,80}", contact or ""):
            raise ValueError("contact must be phone number(s) separated by |")
        self.recheck(flight, rbd, sum(1 for p in passengers if p.type != "INF"))
        params.update({"cbSource": flight.origin, "cbTarget": flight.destination, "FlightClass": rbd, "FlightNo": flight.flight_no,
                       "DepartureDate": flight.departure.date().isoformat(), "edtContact": contact})
        data = self._send("ReservJS", self.cfg.ws2("ReservJS"), params)
        row = (_rows(data, "AirReserve") or [{}])[0]
        err, pnr = str(_get(row, "Error") or "").strip(), str(_get(row, "PNR") or "").strip()
        if err.lower() in ("no err", "success"):
            if re.fullmatch(r"[A-Z0-9]{5,8}", pnr.upper()):
                return {"pnr": pnr.upper(), "time_limit": _get(row, "TimeLimit")}
            raise NiraError("RESERVATION_FAILURE", "success without a readable PNR", airline=self.cfg.code, ambiguous=True)   # a PNR may exist
        raise NiraError(map_error(err) or "RESERVATION_FAILURE", redact(err, self.cfg.user, self.cfg.password)[:300], airline=self.cfg.code)

    def issue(self, pnr: str, email: str) -> list[tuple[str, str]]:
        """ETIssueJS once → [(passenger name, ticket no)]. NRS answers a repeated issue for the same PNR with the same ticket
        numbers, so a caller reconciling after a lost answer may call it again deliberately; this method itself never retries."""
        data = self._send("ETIssueJS", self.cfg.ws2("ETIssueJS"), {"PNR": pnr, P_EMAIL: email})
        raise_for_nrs(data, self.cfg.code)
        tickets: list[tuple[str, str]] = []
        for row in _rows(data, "AirNRSTICKETS"):
            for k, v in row.items():
                values = v if isinstance(v, list) else [v]
                for value in values:
                    if isinstance(value, (dict, list)):
                        continue
                    # {"Tickets": "ALI MR=1234567890123 ..."} or {"ALI MR": "1234567890123"} — both read as NAME=TicketNo
                    for m in re.finditer(r"([A-Z][A-Z /.]*?)\s*=\s*(\d{10,14})\b", f"{k}={value}".upper()):
                        tickets.append((m.group(1).strip(), m.group(2)))
        uniq = list(dict.fromkeys(tickets))
        if not uniq:
            raise NiraError("ISSUE_NO_TICKETS", airline=self.cfg.code, ambiguous=True)
        return uniq

    def cancel_pnr(self, pnr: str) -> str:
        """'cancelled' or 'already_cancelled' (both final). Sent once."""
        data = self._send("CancelPNRJS", self.cfg.ws2("CancelPNRJS"), {"PNR": pnr})
        texts = [t for t in _texts(data) if t.strip()]
        if any("ALREADY CANCELLED" in t.upper() for t in texts):
            return "already_cancelled"
        if any(t.strip().upper().startswith("NO ERROR") for t in texts):
            return "cancelled"
        raise_for_nrs(data, self.cfg.code)
        raise NiraError("NRS_ERROR", redact(" ".join(texts))[:300], airline=self.cfg.code)

    def cancel_seat(self, pnr: str, first_name: str, last_name: str, day: date, flight_no: str) -> dict:
        """One passenger. Returns {"done": True, "new_pnr"}. Sent once."""
        data = self._send("CancelSeatJS", self.cfg.ws2("CancelSeatJS"), {"PNR": pnr, "PassengerName": first_name, "PassengerLastName": last_name,
                                                                          "DepartureDate": day.isoformat(), "FlightNo": flight_no})
        row = (_rows(data, "AirCancelSeat", "CancelSeat") or [data if isinstance(data, dict) else {}])[0]
        if str(_get(row, "Done") or "").strip().lower() == "true":
            return {"done": True, "new_pnr": _get(row, "NewSplittedPNR")}
        raise_for_nrs(data, self.cfg.code)
        raise NiraError("NRS_ERROR", "cancel seat not done", airline=self.cfg.code)

    # -- after sale (reads)
    def retrieve_pnr(self, pnr: str) -> dict:
        data = self._read("NRSRT.jsp", self.cfg.ws1("NRSRT.jsp"), {"PNR": pnr})
        if not isinstance(data, dict):
            raise NiraError("BAD_RESPONSE", "RT answer is not JSON", airline=self.cfg.code)
        raise_for_nrs(data, self.cfg.code, allow=("PNR_CANCELLED",))
        return data

    def retrieve_ticket(self, ticket_no: str) -> TicketRecord:
        return parse_ticket(self._read("NRSETR.jsp", self.cfg.ws1("NRSETR.jsp"), {"TicketNo": ticket_no}), ticket_no, self.cfg.code)

    def penalty(self, ticket_no: str) -> PenaltyResult:
        return parse_penalty(self._read("NRSPenalty.jsp", self.cfg.ws1("NRSPenalty.jsp"), {"TicketNo": ticket_no}), self.cfg.code)

    def penalty_now(self, ticket_no: str) -> PenaltyResult:
        """Assumes the seat is cancelled now. Its output is REJECTED by ETRefund if the seat was not cancelled yet."""
        return parse_penalty(self._read("NRSPenaltyNow.jsp", self.cfg.ws1("NRSPenaltyNow.jsp"), {"TicketNo": ticket_no}), self.cfg.code)

    def prepare_refund(self, ticket_no: str) -> RefundInputs:
        """Call only AFTER cancel_pnr/cancel_seat (seat-cancel time is the basis of the penalty)."""
        return refund_inputs(self.retrieve_ticket(ticket_no), self.penalty(ticket_no))

    def refund(self, ticket_no: str, amounts: RefundInputs) -> dict:
        """ETRefundJS once per ticket. Done=0 → success; Done=-5000 → INCORRECT_RETURN_FARE."""
        data = self._send("ETRefundJS", self.cfg.ws2("ETRefundJS"), {"TicketNo": ticket_no, "Fare": amounts.fare, "KU": amounts.ku, "LP": amounts.lp,
                                                                      "Penalty": amounts.penalty})
        row = (_rows(data, "AirNRSRefund") or [{}])[0]
        done, desc = str(_get(row, "Done") if _get(row, "Done") is not None else "").strip(), str(_get(row, "Desc") or "")
        if done == "0":
            return {"done": True, "desc": redact(desc)[:300]}
        if done == "-5000":
            raise NiraError("INCORRECT_RETURN_FARE", redact(desc)[:300], airline=self.cfg.code)
        raise NiraError(map_error(desc) or "NRS_ERROR", redact(desc)[:300], airline=self.cfg.code)

    def credit_balance(self) -> str:
        """NRSCommand `CRD`: remaining credit and blocked amount, as terminal text (internal/finance only)."""
        data = self._read("NRSCommand.jsp", self.cfg.ws1("NRSCommand.jsp"), {P_COMMAND: "CRD"}, text_ok=True)
        raise_for_nrs(data, self.cfg.code)
        return redact(data if isinstance(data, str) else " ".join(str(v) for v in (data.values() if isinstance(data, dict) else data)), self.cfg.user, self.cfg.password)[:2000]
