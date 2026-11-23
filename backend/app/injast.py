"""Injast (اینجاست) — «پرداخت با اینجاست», a second fail-closed hosted payment gateway beside VandaPay.

Source: «Injast Payment Method» (IPM) integration guide v1.05.14 (supplied by the owner, 2026-11-23).

Merchant API (base ``INJAST_API_BASE``, default https://api.injast.life/service/pay; access by server-IP whitelist):
  POST /merchant/invoice               {merchant_id, callback_url, amount (string, IRR), national_id, tracking_code}
                                       -> data.invoice_id            404 USER_NOT_FOUND
  POST /merchant/invoice/confirm-pay   {merchant_id, invoice_id} -> data.status == true
                                       400 INVOICE_ALREADY_VERIFIED · 403 ACCESS_DENIED · 404 NOT_FOUND
  Payment page: {INJAST_PAY_BASE}?invoice_id=…&national_id=…   (default https://pay.injast.life)
  Callback: Injast POSTs JSON {invoice_id, tracking_code, rrn, status, amount, time} to callback_url; a 301/302
  response with Location redirects the customer. Status 1 Failed · 2 Paid · 3 Unknown · 4 Expired · 5 Verified.
  Envelope: {"meta": {"success": bool, "error_code", "error_help", "error_fields"}, "data": …, "message": …}

SECURITY: the guide defines NO callback signature. A callback is therefore only a HINT that something changed.
Money is recorded only after OUR server-to-server confirm-pay succeeds, for the invoice and amount WE stored.
Open questions for Injast are listed in docs/payments/INJAST_INTEGRATION.md.

Configuration (env only):
  INJAST_MODE          disabled (default) | live. Anything else -> disabled. (No sandbox is documented.)
  INJAST_MERCHANT_ID   merchant UUID issued by Injast (*_FILE supported). Required.
  INJAST_API_BASE      https API base (default above).   INJAST_PAY_BASE  https payment page (default above).
  INJAST_CALLBACK_URL  https public URL of /api/payments/injast/callback. Required (checked in main).
  live is refused outside ENVIRONMENT=production unless DEMO_MODE (there is no test merchant).

The HTTP transport is injectable so tests never touch the network.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

log = logging.getLogger("karenseir.injast")

PROVIDER_KEY = "injast"
LABEL = "پرداخت با اینجاست"
DEFAULT_API_BASE = "https://api.injast.life/service/pay"
DEFAULT_PAY_BASE = "https://pay.injast.life"

STATUS_FAILED, STATUS_PAID, STATUS_UNKNOWN, STATUS_EXPIRED, STATUS_VERIFIED = 1, 2, 3, 4, 5
KNOWN_STATUSES = frozenset({1, 2, 3, 4, 5})
ALREADY_VERIFIED = "INVOICE_ALREADY_VERIFIED"

Transport = Callable[[str, str, dict, Optional[bytes], float], "tuple[int, dict]"]

_PERSIAN_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class InjastError(Exception):
    def __init__(self, message: str, *, code: str = "error", status: Optional[int] = None, transient: bool = False):
        super().__init__(message)
        self.code, self.status, self.transient = code, status, transient


def normalize_national_id(value: Any) -> Optional[str]:
    """Iranian national code (کد ملی) -> 10 ASCII digits, or None when invalid.

    Persian/Arabic digits are translated first (never stripped with a /\\D/-style filter); spaces and dashes are
    the only separators allowed. Checksum: s = Σ d[i]·(10-i) for i<9, r = s mod 11; check = r if r < 2 else 11-r.
    """
    if not isinstance(value, str):
        return None
    raw = value.translate(_PERSIAN_ARABIC_DIGITS).strip().replace(" ", "").replace("-", "").replace("‌", "")
    if not re.fullmatch(r"[0-9]{8,10}", raw):
        return None
    code = raw.zfill(10)
    if len(set(code)) == 1:  # 0000000000, 1111111111 … pass the checksum but are not issued
        return None
    total = sum(int(code[i]) * (10 - i) for i in range(9))
    r = total % 11
    check = r if r < 2 else 11 - r
    return code if int(code[9]) == check else None


def _urllib_transport(method: str, url: str, headers: dict, body: Optional[bytes], timeout: float) -> tuple[int, dict]:
    if not url.startswith("https://"):
        raise InjastError("Injast API URL must be https", code="insecure_url")
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https enforced above
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, (exc.read() or b"")
    except Exception as exc:  # network, TLS, timeout
        raise InjastError(f"injast unreachable: {exc.__class__.__name__}", code="unreachable", transient=True) from exc
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        parsed = {}
    return status, parsed if isinstance(parsed, dict) else {}


def _https_base(value: str) -> Optional[str]:
    base = (value or "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment or parsed.username:
        return None
    return base


@dataclass(frozen=True)
class InjastConfig:
    merchant_id: str
    api_base: str = DEFAULT_API_BASE
    pay_base: str = DEFAULT_PAY_BASE
    mode: str = "live"


def config_from_env(environ: Mapping[str, str] = os.environ, *, environment: str = "development",
                    demo_mode: bool = False, secret_reader: Optional[Callable[[str], str]] = None) -> Optional[InjastConfig]:
    """Configuration when Injast is switched ON and fully configured, else ``None`` (fail-closed)."""
    mode = str(environ.get("INJAST_MODE", "disabled") or "disabled").strip().lower()
    if mode == "disabled":
        return None
    if mode != "live":
        log.error("Injast disabled: INJAST_MODE must be disabled or live")
        return None
    read = secret_reader or (lambda name: str(environ.get(name, "") or ""))
    try:
        merchant = (read("INJAST_MERCHANT_ID") or "").strip()
    except RuntimeError:
        log.error("Injast disabled: merchant id file configuration is invalid")
        return None
    try:
        merchant = str(uuid.UUID(merchant))
    except (ValueError, AttributeError):
        log.error("Injast disabled: INJAST_MERCHANT_ID must be the UUID issued by Injast")
        return None
    api_base = _https_base(environ.get("INJAST_API_BASE") or DEFAULT_API_BASE)
    pay_base = _https_base(environ.get("INJAST_PAY_BASE") or DEFAULT_PAY_BASE)
    if not api_base or not pay_base:
        log.error("Injast disabled: INJAST_API_BASE and INJAST_PAY_BASE must be explicit https URLs")
        return None
    if environment != "production" and not demo_mode:
        log.error("Injast disabled: live merchant refused outside production (no Injast sandbox is documented)")
        return None
    return InjastConfig(merchant_id=merchant, api_base=api_base, pay_base=pay_base, mode=mode)


def _uuid_or_none(value: Any) -> Optional[str]:
    try:
        return str(uuid.UUID(str(value))) if isinstance(value, str) else None
    except ValueError:
        return None


class InjastClient:
    def __init__(self, config: InjastConfig, *, transport: Optional[Transport] = None, timeout_seconds: float = 15.0):
        self.config = config
        self._send = transport or _urllib_transport
        self.timeout_seconds = timeout_seconds

    def _post(self, path: str, body: dict) -> dict:
        headers = {"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        status, parsed = self._send("POST", self.config.api_base + path, headers, data, self.timeout_seconds)
        meta = parsed.get("meta") if isinstance(parsed.get("meta"), dict) else {}
        if 200 <= status < 300 and meta.get("success") is True:
            return parsed.get("data") if isinstance(parsed.get("data"), dict) else {}
        if status == 429 or status >= 500 or status == 0:
            raise InjastError(f"injast temporary error HTTP {status}", code=f"http_{status}", status=status, transient=True)
        code = str(meta.get("error_code") or f"http_{status}")[:64]
        raise InjastError(str(parsed.get("message") or f"injast HTTP {status}")[:200], code=code, status=status)

    def create_invoice(self, *, amount_rial: int, national_id: str, tracking_code: str, callback_url: str) -> str:
        if type(amount_rial) is not int or amount_rial <= 0:
            raise InjastError("amount must be a positive integer rial", code="invalid_amount")
        nid = normalize_national_id(national_id)
        if nid is None:
            raise InjastError("invalid national id", code="invalid_national_id")
        if not callback_url.startswith("https://"):
            raise InjastError("callback_url must be https", code="insecure_callback_url")
        if not re.fullmatch(r"[A-Za-z0-9_\-.]{4,64}", tracking_code or ""):
            raise InjastError("invalid tracking code", code="invalid_tracking_code")
        data = self._post("/merchant/invoice", {"merchant_id": self.config.merchant_id, "callback_url": callback_url,
                                                 "amount": str(amount_rial), "national_id": nid, "tracking_code": tracking_code})
        invoice_id = _uuid_or_none(data.get("invoice_id"))
        if invoice_id is None:
            raise InjastError("injast did not return an invoice id", code="bad_response")
        return invoice_id

    def payment_url(self, invoice_id: str, national_id: str) -> str:
        nid = normalize_national_id(national_id)
        inv = _uuid_or_none(invoice_id)
        if nid is None or inv is None:
            raise InjastError("cannot build payment url", code="invalid_payment_url")
        return f"{self.config.pay_base}?{urllib.parse.urlencode({'invoice_id': inv, 'national_id': nid})}"

    def confirm_pay(self, invoice_id: str) -> str:
        """Server-to-server verification. Returns ``confirmed`` or ``already_verified``; raises otherwise."""
        inv = _uuid_or_none(invoice_id)
        if inv is None:
            raise InjastError("invalid invoice id", code="invalid_invoice_id")
        try:
            data = self._post("/merchant/invoice/confirm-pay", {"merchant_id": self.config.merchant_id, "invoice_id": inv})
        except InjastError as exc:
            if exc.code == ALREADY_VERIFIED:
                return "already_verified"
            raise
        if data.get("status") is not True:
            raise InjastError("injast confirm-pay did not confirm", code="not_confirmed")
        return "confirmed"


def parse_callback(raw: bytes) -> Optional[dict]:
    """Strictly typed callback payload, or None. Only these fields are ever read (and logged)."""
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    invoice_id = _uuid_or_none(body.get("invoice_id"))
    tracking = body.get("tracking_code")
    status = body.get("status")
    amount = body.get("amount")
    if isinstance(amount, str) and amount.isdigit():
        amount = int(amount)
    if invoice_id is None or not isinstance(tracking, str) or not re.fullmatch(r"[A-Za-z0-9_\-.]{4,64}", tracking):
        return None
    if type(status) is not int or status not in KNOWN_STATUSES or type(amount) is not int or amount < 0:
        return None
    rrn = body.get("rrn")
    rrn = str(rrn)[:40] if isinstance(rrn, (str, int)) and re.fullmatch(r"[0-9A-Za-z]{1,40}", str(rrn)) else None
    t = body.get("time")
    t = t[:40] if isinstance(t, str) else None
    return {"invoice_id": invoice_id, "tracking_code": tracking, "status": status, "amount": amount, "rrn": rrn, "time": t}
