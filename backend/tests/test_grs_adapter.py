"""Adapter-core tests - a FakeTransport stands in for the network, exactly the
way ZarinPalAdapter is tested with an injected transport in this codebase.
No test in this file ever reaches a real socket."""
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import pytest
from app.grs_contract import GRSConfig
from app.grs_adapter import GRSAdapter, GRSTransportResponse, GRS_ERROR_TAXONOMY, NON_RETRYABLE_OPERATIONS


@dataclass
class FakeTransport:
    responses: list[GRSTransportResponse] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    raise_exc: Optional[Exception] = None

    def request(self, method, path, *, params=None, json_body=None, timeout):
        self.calls.append({"method": method, "path": path, "params": params, "json_body": json_body})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.responses.pop(0)


@dataclass(frozen=True)
class FakeContext:
    tenant_id: int = 1
    correlation_id: str = "corr-1"
    idempotency_key: str = "idem-1"


ENABLED_CONFIG = GRSConfig(mode="sandbox", base_url="https://grs.example/api", client_token="secret",
                            connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="IRR", webhook_secret="whsec")
DISABLED_CONFIG = GRSConfig(mode="disabled", base_url="", client_token="", connect_timeout_seconds=5,
                             read_timeout_seconds=15, money_unit="", webhook_secret="")


def test_disabled_adapter_fails_closed_without_touching_transport():
    transport = FakeTransport()
    adapter = GRSAdapter(config=DISABLED_CONFIG, transport=transport)
    result = adapter.execute("list_cities", {}, FakeContext())
    assert result["ok"] is False
    assert result["error"]["code"] == "provider_disabled"
    assert transport.calls == []


def test_misconfigured_adapter_fails_closed():
    bad_config = GRSConfig(mode="sandbox", base_url="http://insecure", client_token="", connect_timeout_seconds=5,
                            read_timeout_seconds=15, money_unit="", webhook_secret="")
    transport = FakeTransport()
    adapter = GRSAdapter(config=bad_config, transport=transport)
    result = adapter.execute("list_cities", {}, FakeContext())
    assert result["error"]["code"] == "provider_misconfigured"
    assert transport.calls == []


def test_list_cities_builds_correct_read_only_request():
    transport = FakeTransport(responses=[GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": {"cities": [], "total": 0}}, "application/json")])
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("list_cities", {"count": 50}, FakeContext())
    assert result["ok"] is True
    assert transport.calls[0]["method"] == "GET"
    assert transport.calls[0]["path"] == "/v1/cities"
    assert transport.calls[0]["params"] == {"count": 50}


def test_reserve_room_count_greater_than_one_is_rejected_before_any_call():
    transport = FakeTransport()
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    payload = {"property_id": 1, "check_in": "2026-09-15", "check_out": "2026-09-18",
               "booker_first_name": "a", "booker_last_name": "b", "booker_phone": "x",
               "rooms": [{"room_type_id": 1, "rate_plan_id": 1, "count": 2}]}
    result = adapter.execute("reserve", payload, FakeContext())
    assert result["error"]["code"] == "provider_validation_error"
    assert transport.calls == []  # never even attempted


def test_reserve_success_builds_post_with_full_body():
    transport = FakeTransport(responses=[GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": {"reserve": {"status": "booking", "confirmation_code": "C1"}}}, "application/json")])
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    payload = {"property_id": 1, "check_in": "2026-09-15", "check_out": "2026-09-18",
               "booker_first_name": "a", "booker_last_name": "b", "booker_phone": "x",
               "rooms": [{"room_type_id": 1, "rate_plan_id": 1, "count": 1}]}
    result = adapter.execute("reserve", payload, FakeContext())
    assert result["ok"] is True
    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["path"] == "/v1/reserve"


def test_http_200_with_inventory_error_is_a_business_failure_not_success():
    transport = FakeTransport(responses=[GRSTransportResponse(200, {
        "code": 200, "message": "", "errors": [{"name": "inventory", "message": "Room Ids: 1"}],
        "value": {"reserve": {"state": "offline", "status": "rejected", "confirmation_code": "C1"}},
    }, "application/json")])
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("reserve", {"property_id": 1, "check_in": "x", "check_out": "y",
                                          "booker_first_name": "a", "booker_last_name": "b", "booker_phone": "z",
                                          "rooms": [{"room_type_id": 1, "rate_plan_id": 1, "count": 1}]}, FakeContext())
    assert result["ok"] is False
    assert result["error"]["code"] == "inventory_unavailable"
    assert result["error"]["retryable"] is False


@pytest.mark.parametrize("status,expected_category,expected_retryable", [
    (401, "provider_authentication_failed", False),
    (403, "provider_forbidden", False),
    (422, "provider_validation_error", False),
    (429, "provider_rate_limited", True),   # read-only op
    (500, "provider_unavailable", True),    # read-only op
])
def test_http_error_status_mapping_for_read_only_operation(status, expected_category, expected_retryable):
    transport = FakeTransport(responses=[GRSTransportResponse(status, None, "text/html")])
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("list_cities", {}, FakeContext())
    assert result["error"]["code"] == expected_category
    assert result["error"]["retryable"] is expected_retryable


def test_reserve_5xx_is_never_retryable_even_though_it_would_be_for_a_get():
    transport = FakeTransport(responses=[GRSTransportResponse(500, None, "text/html")])
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    payload = {"property_id": 1, "check_in": "x", "check_out": "y", "booker_first_name": "a",
               "booker_last_name": "b", "booker_phone": "z", "rooms": [{"room_type_id": 1, "rate_plan_id": 1, "count": 1}]}
    result = adapter.execute("reserve", payload, FakeContext())
    assert result["error"]["retryable"] is False


def test_non_json_response_is_a_protocol_error():
    transport = FakeTransport(responses=[GRSTransportResponse(200, None, "text/html")])
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("list_cities", {}, FakeContext())
    assert result["error"]["code"] == "provider_protocol_error"


def test_timeout_maps_to_provider_timeout_and_is_retryable_for_read_only():
    transport = FakeTransport(raise_exc=TimeoutError("boom"))
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("list_cities", {}, FakeContext())
    assert result["error"]["code"] == "provider_timeout"
    assert result["error"]["retryable"] is True


def test_timeout_on_book_is_never_retryable():
    transport = FakeTransport(raise_exc=TimeoutError("boom"))
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("book", {"confirmation_code": "C1"}, FakeContext())
    assert result["error"]["code"] == "provider_timeout"
    assert result["error"]["retryable"] is False


def test_unsupported_operation_never_crashes():
    transport = FakeTransport()
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("not_a_real_operation", {}, FakeContext())
    assert result["ok"] is False
    assert result["error"]["code"] == "provider_protocol_error"


def test_all_non_retryable_operations_are_reservation_lifecycle_writes():
    # sanity check on the policy table itself
    assert "reserve" in NON_RETRYABLE_OPERATIONS
    assert "book" in NON_RETRYABLE_OPERATIONS
    assert "list_cities" not in NON_RETRYABLE_OPERATIONS


def test_error_taxonomy_covers_every_documented_category():
    from app.grs_adapter import _PUBLIC_MESSAGE_FA
    assert set(_PUBLIC_MESSAGE_FA) == GRS_ERROR_TAXONOMY


def test_no_provider_message_leaks_into_public_message():
    transport = FakeTransport(responses=[GRSTransportResponse(500, None, "text/html")])
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=transport)
    result = adapter.execute("list_cities", {}, FakeContext())
    # the public message must be the Persian fixed string, never raw provider text
    assert result["error"]["message"] == "سرویس اقامتگاه موقتاً در دسترس نیست."
