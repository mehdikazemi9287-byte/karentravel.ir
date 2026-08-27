"""Pure unit tests for the GRS location/query-builder scaffold - contract-derived
examples only, no live network access, no DB."""
import pytest
from app.grs_location import (
    GRSLocationQueryMode, GRSContractGuessError,
    build_suggestion_query_params, parse_grs_city_entry, resolve_location_mapping,
)

# Exact example from the GRS Agency API Document v1.18.4 (as supplied), unmodified.
DOCUMENTED_CITY_ENTRY = {
    "id": 3, "name": "شیراز", "province_id": 2, "province_name": "فارس",
    "country_id": 1, "country_name": "ایران",
}


def test_country_id_mode_matches_v1_18_4_documented_shape():
    params = build_suggestion_query_params(
        mode=GRSLocationQueryMode.COUNTRY_ID, check_in="2026-09-15", check_out="2026-09-18",
        adults_count=2, country_id=1,
    )
    assert params["country_id"] == 1
    assert "city_id" not in params
    assert "filters[0][name]" not in params


def test_city_id_mode_matches_postman_v1_17_0_example_shape():
    params = build_suggestion_query_params(
        mode=GRSLocationQueryMode.CITY_ID, check_in="2019-03-20", check_out="2019-03-22",
        adults_count=1, city_id=38,
    )
    assert params["city_id"] == 38
    assert "country_id" not in params


def test_star_filter_mode_matches_postman_filters_array_example():
    params = build_suggestion_query_params(
        mode=GRSLocationQueryMode.STAR_FILTER, check_in="2019-03-20", check_out="2019-03-22",
        adults_count=1, star=3,
    )
    assert params["filters[0][operand]"] == "IsEqualTo"
    assert params["filters[0][name]"] == "star"
    assert params["filters[0][value]"] == 3


def test_mode_without_its_required_field_refuses_to_guess():
    with pytest.raises(GRSContractGuessError):
        build_suggestion_query_params(mode=GRSLocationQueryMode.COUNTRY_ID, check_in="x", check_out="y", adults_count=1)
    with pytest.raises(GRSContractGuessError):
        build_suggestion_query_params(mode=GRSLocationQueryMode.CITY_ID, check_in="x", check_out="y", adults_count=1)


def test_missing_check_in_out_refused():
    with pytest.raises(GRSContractGuessError):
        build_suggestion_query_params(mode=GRSLocationQueryMode.COUNTRY_ID, check_in="", check_out="", adults_count=1, country_id=1)


def test_children_ages_expand_to_indexed_params():
    params = build_suggestion_query_params(
        mode=GRSLocationQueryMode.COUNTRY_ID, check_in="2026-09-15", check_out="2026-09-18",
        adults_count=2, country_id=1, children_ages=[4, 9],
    )
    assert params["children[0]"] == 4
    assert params["children[1]"] == 9


def test_parse_documented_city_entry():
    record = parse_grs_city_entry(DOCUMENTED_CITY_ENTRY)
    assert record.provider_id == 3
    assert record.name == "شیراز"
    assert record.country_name == "ایران"


def test_parse_city_entry_missing_required_field_refuses_to_guess():
    with pytest.raises(GRSContractGuessError):
        parse_grs_city_entry({"name": "شیراز"})  # missing documented-required "id"


def test_resolve_mapped_city():
    result = resolve_location_mapping(
        DOCUMENTED_CITY_ENTRY,
        existing_provider_ids_to_destination_id={3: "dest-shiraz-uuid"},
        seen_provider_ids=set(),
    )
    assert result.outcome == "mapped"
    assert result.destination_id == "dest-shiraz-uuid"


def test_resolve_unmapped_city_is_flagged_not_dropped():
    result = resolve_location_mapping(
        DOCUMENTED_CITY_ENTRY, existing_provider_ids_to_destination_id={}, seen_provider_ids=set(),
    )
    assert result.outcome == "unmapped"
    assert result.record is not None  # never discarded
    assert result.destination_id is None


def test_resolve_duplicate_within_same_fetch():
    result = resolve_location_mapping(
        DOCUMENTED_CITY_ENTRY,
        existing_provider_ids_to_destination_id={3: "dest-shiraz-uuid"},
        seen_provider_ids={3},
    )
    assert result.outcome == "duplicate"


def test_resolve_null_entry_is_invalid_not_silently_skipped():
    result = resolve_location_mapping(None, existing_provider_ids_to_destination_id={}, seen_provider_ids=set())
    assert result.outcome == "invalid"
    assert "null" in result.reason


def test_resolve_malformed_entry_is_invalid_with_reason():
    result = resolve_location_mapping({"name": "no id here"}, existing_provider_ids_to_destination_id={}, seen_provider_ids=set())
    assert result.outcome == "invalid"
    assert result.record is None


def test_resolve_tolerates_missing_optional_province_country_fields():
    minimal = {"id": 99, "name": "ناشناخته"}
    result = resolve_location_mapping(minimal, existing_provider_ids_to_destination_id={}, seen_provider_ids=set())
    assert result.outcome == "unmapped"
    assert result.record.province_id is None
    assert result.record.country_id is None
