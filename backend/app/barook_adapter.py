"""Barook "Roozeno" credit gateway (CPG v2) adapter — disabled by default.

Source: Barook technical document «Roozeno CPG V09». Flow:
  1. POST {base}/cpg/v2/start-payment  -> token + expireDate
  2. customer is sent to {base}/cpg/redirect/{token}
  3. Barook redirects back (GET) to our redirectUrl with token, externalCode,
     nationalCode, status. This callback is NOT signed: it is never trusted.
  4. POST {base}/cpg/v2/verify-payment -> COMPLETED. Barook auto-releases the
     customer's credit if verify is not called within ~2 hours.

This module is standalone: it is not registered in ``providers.ADAPTERS`` and
does not touch payment intents. Wiring it into checkout is a separate,
approved change to the payment core.

Open points not covered by the document (see docs): refund/cancel after
verify, status inquiry, whether ``/api/authenticate`` is required, and the
exact production base path. Production mode therefore needs an explicit
``BAROOK_BASE_URL``.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .config import read_secret
from .providers import ProviderContext, ProviderError, ProviderHealth, RetryPolicy

PROVIDER = "barook"
SERVICE_SLUG = "ROOZE_NO_PERSON"
TEST_BASE_URL = "https://api.barook.tech/barook"
ALLOWED_HOSTS = {"api.barook.tech", "gateway.barook.ir"}
STATUSES = {"CREATED", "CREATE", "HOLDED", "PENDING", "COMPLETED", "CANCELED", "CLOSED"}
# Per the document a new token may be requested for the same invoice unless it is final.
FINAL_STATUSES = {"COMPLETED", "CANCELED", "CLOSED"}
TOKEN_RE = re.compile(r"[A-Za-z0-9-]{8,128}")
EXTERNAL_CODE_RE = re.compile(r"[A-Za-z0-9_-]{4,64}")
MOBILE_RE = re.compile(r"09[0-9]{9}")


class BarookTransport(Protocol):
    def post_json(self, url: str, payload: Mapping[str, Any], timeout_seconds: float) -> Mapping[str, Any]: ...


class BarookHttpTransport:
    def post_json(self, url: str, payload: Mapping[str, Any], timeout_seconds: float) -> Mapping[str, Any]:
        request = Request(url, data=json.dumps(dict(payload), ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - host is allow-listed
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # 4xx/5xx carry a JSON error body; never echo it (it may contain request data).
            return {"_http_status": exc.code}


def valid_national_code(code: str) -> bool:
    """Iranian national code: 10 digits with the standard check digit."""
    if not re.fullmatch(r"[0-9]{10}", code) or len(set(code)) == 1:
        return False
    total = sum(int(code[i]) * (10 - i) for i in range(9)) % 11
    check = int(code[9])
    return check == total if total < 2 else check == 11 - total


def _ascii_digits(value: Any) -> str:
    return str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


class BarookAdapter:
    key = "payment_barook"
    retry_policy = RetryPolicy(max_attempts=2)

    def __init__(self, *, mode: str, terminal_code: str, password: str, callback_url: str,
                 base_url: str = "", payment_month_count: int | None = None, payment_day_count: int | None = None,
                 branch_code: str = "", transport: BarookTransport | None = None, timeout_seconds: float = 10.0) -> None:
        self.mode = mode
        self.terminal_code = terminal_code.strip()
        self._password = password
        self.callback_url = callback_url.strip()
        self.base_url = (base_url.strip() or (TEST_BASE_URL if mode == "sandbox" else "")).rstrip("/")
        self.payment_month_count = payment_month_count
        self.payment_day_count = payment_day_count
        self.branch_code = branch_code.strip()
        self.transport = transport or BarookHttpTransport()
        self.timeout_seconds = timeout_seconds

    def __repr__(self) -> str:  # never print the password
        return f"BarookAdapter(mode={self.mode!r}, base_url={self.base_url!r})"

    # -- configuration -------------------------------------------------
    def validate_configuration(self) -> None:
        if self.mode not in {"sandbox", "production"}:
            raise RuntimeError("barook: mode must be sandbox or production")
        if not self.terminal_code or not self._password:
            raise RuntimeError("barook: terminal code and password are required")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.query or parsed.fragment:
            raise RuntimeError("barook: BAROOK_BASE_URL must be an HTTPS Barook endpoint")
        if self.mode == "production" and parsed.hostname != "gateway.barook.ir":
            raise RuntimeError("barook: production must use gateway.barook.ir")
        callback = urlparse(self.callback_url)
        if callback.scheme != "https" or not callback.hostname:
            raise RuntimeError("barook: callback URL must be explicit HTTPS")
        months, days = self.payment_month_count, self.payment_day_count
        if (months is None) == (days is None):
            raise RuntimeError("barook: set exactly one of payment month count or day count (from the contract)")
        if (months is not None and months < 1) or (days is not None and days < 1):
            raise RuntimeError("barook: settlement period must be positive")

    def health(self) -> ProviderHealth:
        try:
            self.validate_configuration()
        except RuntimeError as exc:
            return ProviderHealth(status="configuration_error", mode=self.mode, detail=str(exc))
        return ProviderHealth(status="configured_not_verified", mode=self.mode, detail="Credentials configured; no purchase is claimed")

    # -- helpers ---------------------------------------------------------
    def _fail(self, reason: str, message: str, context: ProviderContext, *, status: str = "failed", retryable: bool = False) -> Mapping[str, Any]:
        return {"ok": False, "status": status, "provider": PROVIDER, "reason": reason,
                "error": ProviderError(reason, message, retryable, context.correlation_id).__dict__}

    def _callback_with_state(self, state: str) -> str:
        parts = urlsplit(self.callback_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["state"] = state
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))

    @staticmethod
    def _sale_items(payload: Mapping[str, Any], amount: int) -> list[dict] | None:
        raw = payload.get("items") or [{"name": str(payload.get("description") or "خدمات سفر")[:120], "count": 1, "unit": "عدد", "amount": amount}]
        items, total = [], 0
        for item in raw:
            count, unit_amount = int(item.get("count", 0)), int(item.get("amount", 0))
            name = str(item.get("name", "")).strip()[:120]
            if count <= 0 or unit_amount <= 0 or not name:
                return None
            total += count * unit_amount
            items.append({"name": name, "saleCount": count, "unitType": str(item.get("unit") or "عدد")[:30], "amount": unit_amount})
        return items if total == amount else None

    # -- operations ------------------------------------------------------
    def execute(self, operation: str, payload: Mapping[str, Any], context: ProviderContext) -> Mapping[str, Any]:
        try:
            self.validate_configuration()
        except RuntimeError as exc:
            return self._fail("invalid_configuration", str(exc), context, status="not_sent")
        amount = int(payload.get("amount", 0) or 0)
        if amount <= 0 or payload.get("currency") != "IRR":
            return self._fail("invalid_amount", "Positive IRR amount is required", context, status="not_sent")
        if operation == "initiate":
            return self._initiate(payload, amount, context)
        if operation == "verify":
            return self._verify(payload, amount, context)
        return self._fail("unsupported_operation", "Unsupported operation", context, status="not_sent")

    def _initiate(self, payload: Mapping[str, Any], amount: int, context: ProviderContext) -> Mapping[str, Any]:
        external_code = str(payload.get("external_code") or payload.get("payment_intent_id") or "")
        mobile = _ascii_digits(payload.get("owner_mobile"))
        national_code = _ascii_digits(payload.get("owner_national_code"))
        if not EXTERNAL_CODE_RE.fullmatch(external_code):
            return self._fail("invalid_external_code", "Invoice number is invalid", context, status="not_sent")
        if not MOBILE_RE.fullmatch(mobile):
            return self._fail("invalid_mobile", "Customer mobile is required", context, status="not_sent")
        if not valid_national_code(national_code):
            return self._fail("invalid_national_code", "Customer national code is required", context, status="not_sent")
        items = self._sale_items(payload, amount)
        if items is None:
            return self._fail("items_mismatch", "Sale items must sum to the payable amount", context, status="not_sent")
        body: dict[str, Any] = {
            "terminalCode": self.terminal_code, "password": self._password, "totalAmount": amount,
            "externalCode": external_code, "ownerMobile": mobile, "ownerNationalCode": national_code,
            "redirectUrl": self._callback_with_state(str(payload.get("callback_state", ""))),
            "saleItemDto": items, "businessServiceSlug": SERVICE_SLUG,
            "attributes": {"payment_intent_id": str(payload.get("payment_intent_id", ""))},
        }
        if self.payment_month_count is not None:
            body["paymentMonthCount"] = self.payment_month_count
        else:
            body["paymentDayCount"] = self.payment_day_count
        owner_name = str(payload.get("owner_name") or "").strip()[:120]
        if owner_name:
            body["ownerName"] = owner_name
        if self.branch_code:
            body["branchCode"] = self.branch_code
        response = self.transport.post_json(f"{self.base_url}/cpg/v2/start-payment", body, self.timeout_seconds)
        data = response if isinstance(response, Mapping) else {}
        token = str(data.get("token") or data.get("Token") or "")
        if not TOKEN_RE.fullmatch(token):
            return self._fail("request_rejected", "Barook start-payment was rejected", context)
        return {"ok": True, "status": "initiated", "provider": PROVIDER, "reference": external_code, "authority": token,
                "expires_at": str(data.get("expireDate") or "") or None,
                "redirect_url": f"{self.base_url}/cpg/redirect/{token}"}

    def _verify(self, payload: Mapping[str, Any], amount: int, context: ProviderContext) -> Mapping[str, Any]:
        token = str(payload.get("authority") or payload.get("token") or "")
        external_code = str(payload.get("external_code") or payload.get("payment_intent_id") or "")
        if not TOKEN_RE.fullmatch(token) or not EXTERNAL_CODE_RE.fullmatch(external_code):
            return self._fail("authority_mismatch", "Token or invoice number is invalid", context)
        response = self.transport.post_json(f"{self.base_url}/cpg/v2/verify-payment",
                                            {"terminalCode": self.terminal_code, "password": self._password,
                                             "externalCode": external_code, "token": token}, self.timeout_seconds)
        data = response if isinstance(response, Mapping) else {}
        status = str(data.get("status") or "").upper()
        if str(data.get("externalCode") or "") != external_code:
            return self._fail("verify_rejected", "Barook verification did not match the invoice", context)
        try:
            paid = int(data.get("totalAmount"))
        except (TypeError, ValueError):
            paid = -1
        if paid != amount:
            # Money moved for a different amount: never capture, needs manual reconciliation.
            return self._fail("amount_mismatch", "Barook amount differs from the invoice", context)
        if status != "COMPLETED":
            return self._fail("verify_rejected", f"Barook status is {status or 'unknown'}", context)
        return {"ok": True, "status": "verified", "provider": PROVIDER, "already_verified": False,
                "authority": token, "ref_id": external_code, "amount": amount}


def parse_callback(params: Mapping[str, Any]) -> dict | None:
    """Shape-check Barook's (unsigned) return query. The result is only a hint:
    the caller must look up its own intent and call verify before capturing."""
    token = str(params.get("token") or params.get("Token") or "").strip()
    external_code = str(params.get("externalCode") or "").strip()
    status = str(params.get("status") or "").strip().upper()
    if not TOKEN_RE.fullmatch(token) or not EXTERNAL_CODE_RE.fullmatch(external_code) or status not in STATUSES:
        return None
    return {"token": token, "external_code": external_code, "status": status, "should_verify": status == "PENDING"}


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def configured_barook_adapter() -> BarookAdapter | None:
    """Returns None unless BAROOK_MODE is sandbox/production."""
    mode = os.getenv("BAROOK_MODE", "disabled").strip().lower()
    if mode == "disabled":
        return None
    return BarookAdapter(mode=mode, terminal_code=read_secret("BAROOK_TERMINAL_CODE"), password=read_secret("BAROOK_PASSWORD"),
                         callback_url=os.getenv("BAROOK_CALLBACK_URL", ""), base_url=os.getenv("BAROOK_BASE_URL", ""),
                         payment_month_count=_optional_int("BAROOK_PAYMENT_MONTH_COUNT"),
                         payment_day_count=_optional_int("BAROOK_PAYMENT_DAY_COUNT"),
                         branch_code=os.getenv("BAROOK_BRANCH_CODE", ""))
