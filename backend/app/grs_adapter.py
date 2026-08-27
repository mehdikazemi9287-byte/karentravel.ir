"""
GRS hotel-provider adapter core: HTTP client abstraction, error taxonomy, and
the GRSAdapter itself - implementing the SAME `IntegrationAdapter` Protocol
`ZarinPalAdapter` already implements (key/mode/timeout_seconds/retry_policy +
validate_configuration/health/execute), dispatching every documented GRS
operation through the single existing `execute(operation, payload, context)`
entry point rather than inventing a parallel ~25-method interface.

No call in this module has ever reached the real GRS endpoint - there is no
credential/base URL anywhere in this environment (verified directly against
.env, .env.example, and the live API container's env). Every test exercises
this adapter through an injected fake transport, exactly the way
`ZarinPalAdapter(transport=...)` is already tested in this codebase.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

from .grs_contract import (
    GRSConfig, GRSConfigError, GRSEnvelope, GRSProtocolError,
    parse_grs_envelope, envelope_is_business_failure,
    normalize_reserve_details, normalize_rate_plan_price, normalize_suggestion_room,
)
from .grs_location import GRSLocationQueryMode, build_suggestion_query_params


# ---------------------------------------------------------------------------
# Error taxonomy - the minimum set required, mapped from HTTP status + parsed
# envelope, never showing the raw GRS technical message to a public caller.
# ---------------------------------------------------------------------------
GRS_ERROR_TAXONOMY = {
    "provider_disabled", "provider_misconfigured", "provider_authentication_failed",
    "provider_forbidden", "provider_rate_limited", "provider_timeout",
    "provider_protocol_error", "provider_unavailable", "provider_validation_error",
    "offer_expired", "inventory_unavailable", "rate_unavailable", "capacity_invalid",
    "stay_rule_violation", "reservation_not_found", "reservation_expired",
    "reservation_rejected", "provider_result_unknown", "reconciliation_required",
}

_PUBLIC_MESSAGE_FA = {
    "provider_disabled": "این سرویس در حال حاضر فعال نیست.",
    "provider_misconfigured": "سرویس اقامتگاه به‌درستی پیکربندی نشده است.",
    "provider_authentication_failed": "ارتباط با تأمین‌کننده برقرار نشد.",
    "provider_forbidden": "دسترسی به این عملیات مجاز نیست.",
    "provider_rate_limited": "درخواست‌های زیادی ارسال شده؛ کمی بعد دوباره تلاش کنید.",
    "provider_timeout": "پاسخ تأمین‌کننده به‌موقع نرسید.",
    "provider_protocol_error": "پاسخ نامعتبری از تأمین‌کننده دریافت شد.",
    "provider_unavailable": "سرویس اقامتگاه موقتاً در دسترس نیست.",
    "provider_validation_error": "اطلاعات ارسالی معتبر نیست.",
    "offer_expired": "این پیشنهاد منقضی شده است.",
    "inventory_unavailable": "ظرفیت این اتاق دیگر موجود نیست.",
    "rate_unavailable": "این نرخ دیگر معتبر نیست.",
    "capacity_invalid": "ظرفیت درخواستی معتبر نیست.",
    "stay_rule_violation": "این بازه اقامت مجاز نیست.",
    "reservation_not_found": "رزرو پیدا نشد.",
    "reservation_expired": "مهلت این رزرو به پایان رسیده است.",
    "reservation_rejected": "این رزرو توسط تأمین‌کننده رد شد.",
    "provider_result_unknown": "نتیجه عملیات نامشخص است؛ در حال بررسی است.",
    "reconciliation_required": "این عملیات نیاز به بررسی دستی دارد.",
}

# Which operations must NEVER be blindly retried, even on a retryable-looking
# transport error - per the documented retry policy (section 19).
NON_RETRYABLE_OPERATIONS = {
    "reserve", "extend_hold", "book", "modify_reservation", "accept_modification",
    "cancel_modification", "request_cancellation", "accept_cancellation",
    "reject_cancellation", "request_service", "create_activity", "set_webhook",
}
READ_ONLY_OPERATIONS = {
    "list_cities", "list_facilities", "list_properties", "get_property",
    "list_room_types", "get_available_rooms", "search_suggestions",
    "list_reservations", "get_reservation", "get_reservation_activities",
    "get_webhook",
}


@dataclass(frozen=True)
class GRSErrorResult:
    category: str
    public_message_fa: str
    retryable: bool
    provider_message: str  # kept for internal audit/support only, never shown publicly
    correlation_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": False, "status": "not_sent", "provider": "grs",
            "reason": self.category, "correlation_id": self.correlation_id,
            "error": {
                "code": self.category, "message": self.public_message_fa,
                "retryable": self.retryable, "correlation_id": self.correlation_id,
            },
        }


def map_http_error(*, operation: str, http_status: Optional[int], correlation_id: str, provider_message: str = "") -> GRSErrorResult:
    """Maps a transport-level outcome (HTTP status, or None for a raw
    timeout/connection failure) to the internal taxonomy, honoring the
    documented per-status retry policy and the non-retryable operation list."""
    is_read_only = operation in READ_ONLY_OPERATIONS
    is_never_retry_op = operation in NON_RETRYABLE_OPERATIONS

    def result(category: str, retryable: bool) -> GRSErrorResult:
        retryable = retryable and not is_never_retry_op
        return GRSErrorResult(category, _PUBLIC_MESSAGE_FA[category], retryable, provider_message, correlation_id)

    if http_status is None:
        return result("provider_timeout", retryable=True)
    if http_status in (401, 403):
        return result("provider_authentication_failed" if http_status == 401 else "provider_forbidden", retryable=False)
    if http_status == 404:
        return result("reservation_not_found" if "reservation" in operation or operation in {"get_reservation", "modify_reservation"} else "provider_protocol_error", retryable=False)
    if http_status == 409:
        return result("reservation_rejected", retryable=False)
    if http_status == 422:
        return result("provider_validation_error", retryable=False)
    if http_status == 429:
        return result("provider_rate_limited", retryable=is_read_only)
    if http_status in (500, 502):
        return result("provider_unavailable", retryable=is_read_only)
    if 200 <= http_status < 300:
        raise ValueError("map_http_error should not be called for a successful HTTP status")
    return result("provider_protocol_error", retryable=False)


def map_envelope_business_error(envelope: GRSEnvelope, *, correlation_id: str) -> GRSErrorResult:
    """Maps a documented 'HTTP 200 but actually failed' envelope to the taxonomy."""
    names = {str(err.get("name", "")).strip().lower() for err in envelope.errors}
    if "inventory" in names:
        category = "inventory_unavailable"
    elif "rate" in names:
        category = "rate_unavailable"
    elif "capacity" in names:
        category = "capacity_invalid"
    elif "stay" in names:
        category = "stay_rule_violation"
    else:
        category = "reservation_rejected"
    return GRSErrorResult(category, _PUBLIC_MESSAGE_FA[category], retryable=False, provider_message=envelope.message, correlation_id=correlation_id)


# ---------------------------------------------------------------------------
# HTTP client abstraction - injectable transport, exactly like
# ZarinPalTransport/ZarinPalHttpTransport in app/providers.py.
# ---------------------------------------------------------------------------
class GRSTransport(Protocol):
    def request(self, method: str, path: str, *, params: Optional[Mapping[str, Any]] = None,
                json_body: Optional[Mapping[str, Any]] = None, timeout: tuple[float, float]) -> "GRSTransportResponse": ...


@dataclass(frozen=True)
class GRSTransportResponse:
    status_code: int
    json_body: Optional[Mapping[str, Any]]
    content_type: str


class GRSHttpTransport:
    """Real transport - only ever constructed when GRS_MODE != disabled, which
    never happens in this environment (no base_url/token configured)."""

    def __init__(self, config: GRSConfig) -> None:
        self._config = config

    def request(self, method: str, path: str, *, params=None, json_body=None, timeout):
        import urllib.request
        import urllib.parse

        url = self._config.base_url.rstrip("/") + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        headers = {"Content-Type": "application/json", "Client-Token": self._config.client_token}
        data = json.dumps(dict(json_body)).encode("utf-8") if json_body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        connect_timeout, read_timeout = timeout
        with urllib.request.urlopen(request, timeout=connect_timeout + read_timeout) as response:  # noqa: S310
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            body = None
            if "application/json" in content_type:
                try:
                    body = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body = None
            return GRSTransportResponse(status_code=response.status, json_body=body, content_type=content_type)


# ---------------------------------------------------------------------------
# The adapter itself.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GRSRetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0


class GRSAdapter:
    key = "hotel"

    def __init__(self, *, config: GRSConfig, transport: Optional[GRSTransport] = None) -> None:
        self._config = config
        self.mode = config.mode
        self.timeout_seconds = config.connect_timeout_seconds + config.read_timeout_seconds
        self.retry_policy = GRSRetryPolicy()
        self._transport = transport if transport is not None else GRSHttpTransport(config)

    def validate_configuration(self) -> None:
        self._config.validate()

    def health(self):
        from .providers import ProviderHealth
        try:
            self.validate_configuration()
        except GRSConfigError as exc:
            return ProviderHealth(status="configuration_error", mode=self.mode, detail=str(exc))
        if self.mode == "disabled":
            return ProviderHealth(status="not_connected", mode=self.mode, detail="GRS is disabled")
        return ProviderHealth(status="configured_not_verified", mode=self.mode, detail="Credentials configured; no live call is claimed")

    def execute(self, operation: str, payload: Mapping[str, Any], context) -> Mapping[str, Any]:
        try:
            self.validate_configuration()
        except GRSConfigError as exc:
            return GRSErrorResult("provider_misconfigured", _PUBLIC_MESSAGE_FA["provider_misconfigured"], False, str(exc), context.correlation_id).as_dict()
        if self.mode == "disabled":
            return GRSErrorResult("provider_disabled", _PUBLIC_MESSAGE_FA["provider_disabled"], False, "grs disabled", context.correlation_id).as_dict()

        handler = _OPERATION_HANDLERS.get(operation)
        if handler is None:
            return GRSErrorResult("provider_protocol_error", _PUBLIC_MESSAGE_FA["provider_protocol_error"], False, f"unsupported operation {operation!r}", context.correlation_id).as_dict()

        try:
            method, path, params, json_body = handler(payload, self._config)
        except GRSProtocolError as exc:
            return GRSErrorResult("provider_validation_error", _PUBLIC_MESSAGE_FA["provider_validation_error"], False, str(exc), context.correlation_id).as_dict()

        timeout = (self._config.connect_timeout_seconds, self._config.read_timeout_seconds)
        try:
            response = self._transport.request(method, path, params=params, json_body=json_body, timeout=timeout)
        except TimeoutError:
            return map_http_error(operation=operation, http_status=None, correlation_id=context.correlation_id).as_dict()
        except Exception as exc:  # noqa: BLE001 - transport-layer failures all become provider_timeout/unavailable, never crash
            return GRSErrorResult("provider_unavailable", _PUBLIC_MESSAGE_FA["provider_unavailable"], operation in READ_ONLY_OPERATIONS, str(exc), context.correlation_id).as_dict()

        if not (200 <= response.status_code < 300):
            return map_http_error(operation=operation, http_status=response.status_code, correlation_id=context.correlation_id).as_dict()
        if response.json_body is None:
            return GRSErrorResult("provider_protocol_error", _PUBLIC_MESSAGE_FA["provider_protocol_error"], False, "non-JSON response body", context.correlation_id).as_dict()

        try:
            envelope = parse_grs_envelope(response.json_body)
        except GRSProtocolError as exc:
            return GRSErrorResult("provider_protocol_error", _PUBLIC_MESSAGE_FA["provider_protocol_error"], False, str(exc), context.correlation_id).as_dict()

        if envelope_is_business_failure(envelope):
            return map_envelope_business_error(envelope, correlation_id=context.correlation_id).as_dict()
        if not envelope.raw_ok:
            return GRSErrorResult("provider_protocol_error", _PUBLIC_MESSAGE_FA["provider_protocol_error"], False, envelope.message, context.correlation_id).as_dict()

        return {"ok": True, "status": "succeeded", "provider": "grs", "operation": operation, "correlation_id": context.correlation_id, "value": envelope.value}


# ---------------------------------------------------------------------------
# Per-operation request builders - each returns (method, path, params, json_body).
# Only the documented shapes are built; anything not literally in the contract
# raises GRSProtocolError rather than guessing.
# ---------------------------------------------------------------------------
def _require(payload: Mapping[str, Any], *keys: str) -> None:
    missing = [key for key in keys if payload.get(key) is None]
    if missing:
        raise GRSProtocolError(f"grs: missing required field(s) for this operation: {', '.join(missing)}")


def _h_list_cities(payload, config):
    params = {k: payload[k] for k in ("offset", "count", "filters") if k in payload}
    return "GET", "/v1/cities", params, None


def _h_list_facilities(payload, config):
    params = {k: payload[k] for k in ("offset", "count") if k in payload}
    return "GET", "/v1/facilities", params, None


def _h_list_properties(payload, config):
    params = {k: payload[k] for k in ("page", "count", "filters") if k in payload}
    return "GET", "/v1/properties", params, None


def _h_get_property(payload, config):
    _require(payload, "property_id")
    return "GET", f"/v1/properties/{payload['property_id']}", None, None


def _h_list_room_types(payload, config):
    _require(payload, "property_id")
    return "GET", "/v1/room-types", {"property_id": payload["property_id"]}, None


def _h_get_available_rooms(payload, config):
    _require(payload, "property_id", "check_in", "check_out")
    return "GET", "/v1/available-rooms", {k: payload[k] for k in ("property_id", "check_in", "check_out")}, None


def _h_search_suggestions(payload, config):
    _require(payload, "mode", "check_in", "check_out", "adults_count")
    params = build_suggestion_query_params(
        mode=GRSLocationQueryMode(payload["mode"]), check_in=payload["check_in"], check_out=payload["check_out"],
        adults_count=payload["adults_count"], country_id=payload.get("country_id"), city_id=payload.get("city_id"),
        star=payload.get("star"), rooms_count=payload.get("rooms_count"), children_ages=payload.get("children_ages"),
        page=payload.get("page"), count=payload.get("count"),
    )
    return "GET", "/v1/suggestion", params, None


def _h_list_promotions(payload, config):
    return "GET", "/v1/promotions", ({"filters": payload["filters"]} if "filters" in payload else None), None


def _h_reserve(payload, config):
    _require(payload, "property_id", "check_in", "check_out", "booker_first_name", "booker_last_name", "booker_phone", "rooms")
    for room in payload["rooms"]:
        if room.get("count", 1) != 1:
            raise GRSProtocolError("grs: ReserveRoom.count must be 1 per the documented contract - use multiple room entries instead")
    return "POST", "/v1/reserve", None, dict(payload)


def _h_extend_hold(payload, config):
    _require(payload, "confirmation_code")
    return "POST", f"/v1/extended-expired-time/{payload['confirmation_code']}", None, {}


def _h_book(payload, config):
    _require(payload, "confirmation_code")
    return "POST", "/v1/book", None, {"confirmation_code": payload["confirmation_code"]}


def _h_list_reservations(payload, config):
    params = {k: payload[k] for k in ("count", "page", "filters") if k in payload}
    return "GET", "/v1/reserves", params, None


def _h_get_reservation(payload, config):
    _require(payload, "confirmation_code")
    return "GET", "/v1/reserve-details", {"confirmation_code": payload["confirmation_code"]}, None


def _h_get_reservation_activities(payload, config):
    _require(payload, "confirmation_code")
    return "GET", f"/v1/reserves/{payload['confirmation_code']}/activities", None, None


def _h_modify_reservation(payload, config):
    _require(payload, "confirmation_code", "reserve")
    return "POST", f"/v1/modify/{payload['confirmation_code']}", None, dict(payload["reserve"])


def _h_accept_modification(payload, config):
    _require(payload, "confirmation_code")
    return "POST", f"/v1/accept-modify/{payload['confirmation_code']}", None, {}


def _h_cancel_modification(payload, config):
    _require(payload, "confirmation_code")
    return "POST", f"/v1/cancel-modify/{payload['confirmation_code']}", None, {}


def _h_request_cancellation(payload, config):
    _require(payload, "confirmation_code")
    return "POST", "/v1/cancel", None, {"confirmation_code": payload["confirmation_code"]}


def _h_accept_cancellation(payload, config):
    _require(payload, "confirmation_code")
    return "POST", f"/v1/accept-cancel/{payload['confirmation_code']}", None, {}


def _h_reject_cancellation(payload, config):
    _require(payload, "confirmation_code")
    return "POST", f"/v1/reject-cancel/{payload['confirmation_code']}", None, {}


def _h_request_service(payload, config):
    _require(payload, "confirmation_code", "type", "data")
    return "POST", f"/v1/request-service/{payload['confirmation_code']}", None, {"type": payload["type"], "data": payload["data"], "description": payload.get("description")}


def _h_create_activity(payload, config):
    _require(payload, "confirmation_code", "description")
    return "POST", f"/v1/reserves/{payload['confirmation_code']}/activities/create", None, {"description": payload["description"]}


def _h_get_webhook(payload, config):
    return "GET", "/v1/web-hook", None, None


def _h_set_webhook(payload, config):
    _require(payload, "web_hook")
    return "POST", "/v1/web-hook", None, {"web_hook": payload["web_hook"]}


_OPERATION_HANDLERS = {
    "list_cities": _h_list_cities, "list_facilities": _h_list_facilities, "list_properties": _h_list_properties,
    "get_property": _h_get_property, "list_room_types": _h_list_room_types, "get_available_rooms": _h_get_available_rooms,
    "search_suggestions": _h_search_suggestions, "list_promotions": _h_list_promotions,
    "reserve": _h_reserve, "extend_hold": _h_extend_hold, "book": _h_book,
    "list_reservations": _h_list_reservations, "get_reservation": _h_get_reservation,
    "get_reservation_activities": _h_get_reservation_activities, "modify_reservation": _h_modify_reservation,
    "accept_modification": _h_accept_modification, "cancel_modification": _h_cancel_modification,
    "request_cancellation": _h_request_cancellation, "accept_cancellation": _h_accept_cancellation,
    "reject_cancellation": _h_reject_cancellation, "request_service": _h_request_service,
    "create_activity": _h_create_activity, "get_webhook": _h_get_webhook, "set_webhook": _h_set_webhook,
}
