"""Pure unit tests for the GRS contract scaffold - no DB, no network, no app context."""
import os
import pytest
from app.grs_contract import (
    GRSConfig, GRSConfigError, GRSProtocolError,
    parse_grs_envelope, envelope_is_business_failure,
    normalize_reserve_details, normalize_rate_plan_price, normalize_suggestion_room,
    map_grs_event_to_internal_transition,
)


def test_config_fails_closed_when_disabled_by_default():
    cfg = GRSConfig(mode="disabled", base_url="", client_token="", connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="", webhook_secret="")
    cfg.validate()  # disabled is always valid
    assert cfg.can_accept_bookable_prices() is False


def test_config_fails_closed_without_money_unit_even_if_enabled():
    cfg = GRSConfig(mode="sandbox", base_url="https://grs.example/api", client_token="secret", connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="", webhook_secret="")
    with pytest.raises(GRSConfigError):
        cfg.validate()
    assert cfg.can_accept_bookable_prices() is False


def test_config_fails_closed_without_https_base_url():
    cfg = GRSConfig(mode="sandbox", base_url="http://insecure.example", client_token="secret", connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="IRR", webhook_secret="")
    with pytest.raises(GRSConfigError):
        cfg.validate()


def test_config_valid_when_fully_specified():
    cfg = GRSConfig(mode="sandbox", base_url="https://grs.example/api", client_token="secret", connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="IRR", webhook_secret="whsec")
    cfg.validate()
    assert cfg.can_accept_bookable_prices() is True


def test_envelope_handles_error_singular_and_errors_plural():
    e1 = parse_grs_envelope({"code": 422, "message": "", "error": [{"name": "check_in", "message": "validation.required"}], "value": None})
    assert e1.errors[0]["name"] == "check_in"
    e2 = parse_grs_envelope({"code": 200, "message": "", "errors": [{"name": "inventory", "message": "Room Ids: 1"}], "value": {"reserve": {"status": "rejected"}}})
    assert e2.errors[0]["name"] == "inventory"


def test_envelope_tolerates_null_error():
    e = parse_grs_envelope({"code": 200, "message": "", "error": None, "errors": None, "value": {}})
    assert e.errors == []
    assert e.raw_ok is True


def test_envelope_rejects_unrecognized_shape():
    with pytest.raises(GRSProtocolError):
        parse_grs_envelope({"unexpected": "shape"})


def test_http_200_with_inventory_error_is_business_failure_not_success():
    envelope = parse_grs_envelope({
        "code": 200, "message": "", "errors": [{"name": "inventory", "message": "Room Ids: 12,13"}],
        "value": {"reserve": {"state": "offline", "status": "rejected", "confirmation_code": "abc"}},
    })
    assert envelope.raw_ok is False  # code==200 but errors present
    assert envelope_is_business_failure(envelope) is True


def test_rejected_reserve_value_without_explicit_error_entry_is_still_business_failure():
    envelope = parse_grs_envelope({"code": 200, "message": "", "error": None, "value": {"reserve": {"status": "rejected"}}})
    assert envelope_is_business_failure(envelope) is True


def test_clean_success_is_not_a_business_failure():
    envelope = parse_grs_envelope({"code": 200, "message": "", "error": None, "value": {"reserve": {"status": "booking"}}})
    assert envelope_is_business_failure(envelope) is False


def test_normalize_reserve_details_typos():
    raw = {"Status": "booked", "Property_confirmation_code": "P1", "total_canellation_fee": 5000}
    norm = normalize_reserve_details(raw)
    assert norm["status"] == "booked"
    assert norm["property_confirmation_code"] == "P1"
    assert norm["total_cancellation_fee"] == 5000


def test_normalize_reserve_details_prefers_correct_spelling_if_both_present():
    raw = {"status": "booked", "Status": "should_not_win"}
    norm = normalize_reserve_details(raw)
    assert norm["status"] == "booked"


def test_normalize_rate_plan_price_typo():
    assert normalize_rate_plan_price({"baby_cot_racke_rate": 100})["baby_cot_rack_rate"] == 100


def test_normalize_suggestion_room_typo():
    assert normalize_suggestion_room({"roome_type_extra": 1})["room_type_extra"] == 1


@pytest.mark.parametrize("status,current,expected_target", [
    ("pending", "pending", "reserved"),
    ("booking", "pending", "reserved"),
    ("rejected", "awaiting_payment", "failed"),  # "failed" is only legal from draft/pending/awaiting_payment
    ("canceling", "reserved", "cancel_requested"),
    ("modify_booking", "confirmed", "change_requested"),
])
def test_clear_mappings_with_a_realistic_current_status(status, current, expected_target):
    decision = map_grs_event_to_internal_transition(current, "online", status)
    assert decision.target_status == expected_target
    assert decision.requires_backoffice_review is False


def test_canceled_maps_to_cancelled_from_cancel_requested():
    decision = map_grs_event_to_internal_transition("cancel_requested", "offline", "canceled")
    assert decision.target_status == "cancelled"


def test_booked_never_auto_confirms():
    decision = map_grs_event_to_internal_transition("reserved", "online", "booked")
    assert decision.target_status is None
    assert "must be driven by KarenSeir's own payment/credit verification" in decision.reason


def test_overbooking_and_suggested_never_forced_into_enum():
    for status in ("overbooking", "suggested"):
        decision = map_grs_event_to_internal_transition("confirmed", "online", status)
        assert decision.target_status is None
        assert decision.requires_backoffice_review is True


def test_ambiguous_refund_never_auto_finalizes():
    decision = map_grs_event_to_internal_transition("confirmed", "online", "refund")
    assert decision.target_status is None
    assert decision.requires_backoffice_review is True


def test_cancellation_rejected_never_silently_reconfirms():
    decision = map_grs_event_to_internal_transition("cancel_requested", "online", "cancellation_rejected")
    assert decision.target_status is None
    assert decision.requires_backoffice_review is True


def test_unknown_status_never_crashes():
    decision = map_grs_event_to_internal_transition("confirmed", "online", "some_new_status_from_provider")
    assert decision.target_status is None
    assert decision.requires_backoffice_review is True


def test_invalid_transition_target_is_rejected_not_applied():
    # "reserved" -> "failed" via "rejected" IS legal (draft/pending/reserved... check table);
    # pick a combo that is NOT legal to prove rejection path: from "draft", "rejected" would
    # try to map to "failed" which IS legal from draft, so instead test an illegal one:
    # from "completed" (terminal, not even in the transitions dict) nothing should apply.
    decision = map_grs_event_to_internal_transition("completed", "online", "canceling")
    assert decision.target_status is None
    assert decision.requires_backoffice_review is True
