"""
GRS location contract - city_id/country_id resolution.

AUDIT-PHASE SCAFFOLD ONLY. No live call has ever been made against the real GRS
endpoint (no base URL or credential exists anywhere in this environment - verified
via .env, .env.example, and the running API container's actual env, all empty).
Everything here is derived strictly from the documented request/response shapes
already supplied; nothing about GRS's real behavior is guessed or assumed.

Known, unresolved contract contradiction (see GRS Agency API Document v1.18.4
section on /v1/suggestion vs the older Postman Collection v1.17.0 example):
  - v1.18.4 documents `country_id` as the /v1/suggestion location parameter.
  - Postman v1.17.0 shows a real example using `city_id` directly, plus a
    `filters[0][name]=star` style filter array example.
  - The Persian prose in both stays about "city search" throughout, which does
    not disambiguate which parameter shape the live API actually honors.
This module does NOT guess which one is correct. It builds whichever documented
shape the caller explicitly selects (GRSLocationQueryMode), so the eventual live
contract-probe (once a real credential/sandbox exists) can try each shape with
the fewest possible requests and record which one actually returns results -
per the user's own required procedure. Until that probe runs, GRS_LOCATION_QUERY_MODE
must be explicitly set by a human decision informed by the probe, never defaulted
to a guess.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class GRSLocationQueryMode(str, Enum):
    """Which documented /v1/suggestion location-parameter shape to use. Set
    explicitly after a real contract probe - never defaulted to a guess."""
    COUNTRY_ID = "country_id"   # v1.18.4-documented shape
    CITY_ID = "city_id"         # Postman v1.17.0 example shape (undocumented in v1.18.4)
    STAR_FILTER = "filters"     # Postman v1.17.0 filters[]-array example (property search, not suggestion)


class GRSContractGuessError(RuntimeError):
    """Raised when a caller asks this module to build a query shape or resolve
    a location field that is not literally present in the documented contract."""


def build_suggestion_query_params(
    *,
    mode: GRSLocationQueryMode,
    check_in: str,
    check_out: str,
    adults_count: int,
    country_id: Optional[int] = None,
    city_id: Optional[int] = None,
    star: Optional[int] = None,
    rooms_count: Optional[int] = None,
    children_ages: Optional[list[int]] = None,
    page: Optional[int] = None,
    count: Optional[int] = None,
) -> dict[str, Any]:
    """Builds GET /v1/suggestion query params for exactly one documented shape.
    Never mixes shapes, never invents a parameter the contract does not show."""
    if not check_in or not check_out:
        raise GRSContractGuessError("grs: check_in/check_out are required per v1.18.4 (yyyy-mm-dd)")
    params: dict[str, Any] = {
        "check_in": check_in,
        "check_out": check_out,
        "adults_count": adults_count,
    }
    if rooms_count is not None:
        params["rooms_count"] = rooms_count
    if page is not None:
        params["page"] = page
    if count is not None:
        params["count"] = count
    if children_ages:
        for index, age in enumerate(children_ages):
            params[f"children[{index}]"] = age

    if mode is GRSLocationQueryMode.COUNTRY_ID:
        if country_id is None:
            raise GRSContractGuessError("grs: COUNTRY_ID mode requires country_id (v1.18.4-documented shape)")
        params["country_id"] = country_id
    elif mode is GRSLocationQueryMode.CITY_ID:
        if city_id is None:
            raise GRSContractGuessError("grs: CITY_ID mode requires city_id (Postman v1.17.0 example shape, not in v1.18.4 text)")
        params["city_id"] = city_id
    elif mode is GRSLocationQueryMode.STAR_FILTER:
        if star is None:
            raise GRSContractGuessError("grs: STAR_FILTER mode requires a star value (Postman v1.17.0 filters[] example)")
        params["filters[0][operand]"] = "IsEqualTo"
        params["filters[0][name]"] = "star"
        params["filters[0][value]"] = star
    else:  # pragma: no cover - exhaustive Enum
        raise GRSContractGuessError(f"grs: unrecognized location query mode {mode!r}")
    return params


# ---------------------------------------------------------------------------
# City/country mapping - normalizes a documented /v1/cities entry and tracks
# its relationship to KarenSeir's own Destination hierarchy (app/operations.py
# Destination: parent_id/kind/name_fa/name_en/slug tree). No new parallel
# location table is proposed - this is a *mapping* record (provider id <->
# existing Destination id), reusing the existing hierarchy as the source of
# truth for names/slugs/geo, exactly the way ADR/AGENTS.md require ("no
# parallel config/schema").
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GRSCityRecord:
    provider_id: int
    name: str
    province_id: Optional[int]
    province_name: Optional[str]
    country_id: Optional[int]
    country_name: Optional[str]


@dataclass
class LocationMappingResult:
    record: Optional[GRSCityRecord]
    destination_id: Optional[str]  # resolved KarenSeir Destination.id, if any
    outcome: str  # "mapped" | "unmapped" | "duplicate" | "invalid"
    reason: str


def parse_grs_city_entry(raw: Mapping[str, Any]) -> GRSCityRecord:
    """Parses one entry of the documented /v1/cities response shape. Raises on
    anything that does not match the documented shape - never fills in a
    guessed id/name."""
    if "id" not in raw or "name" not in raw:
        raise GRSContractGuessError("grs: /v1/cities entry missing documented required fields id/name")
    return GRSCityRecord(
        provider_id=int(raw["id"]),
        name=str(raw["name"]),
        province_id=raw.get("province_id"),
        province_name=raw.get("province_name"),
        country_id=raw.get("country_id"),
        country_name=raw.get("country_name"),
    )


def resolve_location_mapping(
    raw: Optional[Mapping[str, Any]],
    *,
    existing_provider_ids_to_destination_id: Mapping[int, str],
    seen_provider_ids: set[int],
) -> LocationMappingResult:
    """
    Pure resolver - no DB/network access. The caller supplies the current
    mapping table (existing_provider_ids_to_destination_id) and a running set
    of provider ids already seen in this same batch (seen_provider_ids), so
    duplicates within one /v1/cities page can be detected without a DB round
    trip per entry.

    Handles exactly the cases the contract requires being explicit about:
      - null/missing entry -> "invalid" (never silently skipped without a reason)
      - unmapped provider id (not yet in KarenSeir's mapping table) -> "unmapped"
      - duplicate provider id within the same fetch -> "duplicate"
      - known provider id -> "mapped" to its existing Destination
    "Inactive" is deliberately NOT handled here: the documented /v1/cities shape
    has no active/status field at all, so inactivity can only be inferred by a
    city previously mapped no longer appearing in a fresh full fetch - a
    reconciliation-level concept (last_seen_at bookkeeping), not a per-entry
    parse decision, and out of scope for this pure function.
    """
    if raw is None:
        return LocationMappingResult(record=None, destination_id=None, outcome="invalid", reason="null city entry")
    try:
        record = parse_grs_city_entry(raw)
    except GRSContractGuessError as exc:
        return LocationMappingResult(record=None, destination_id=None, outcome="invalid", reason=str(exc))

    if record.provider_id in seen_provider_ids:
        return LocationMappingResult(
            record=record, destination_id=existing_provider_ids_to_destination_id.get(record.provider_id),
            outcome="duplicate", reason=f"provider_id {record.provider_id} already seen in this fetch",
        )
    destination_id = existing_provider_ids_to_destination_id.get(record.provider_id)
    if destination_id is None:
        return LocationMappingResult(
            record=record, destination_id=None, outcome="unmapped",
            reason=f"provider_id {record.provider_id} ('{record.name}') has no KarenSeir Destination mapping yet - "
            "requires a human/BackOffice mapping decision before this city can be used in a real search",
        )
    return LocationMappingResult(record=record, destination_id=destination_id, outcome="mapped", reason="existing mapping found")
