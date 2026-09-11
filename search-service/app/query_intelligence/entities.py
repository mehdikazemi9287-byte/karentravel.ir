"""Location entity resolution -- reuses the EXISTING canonical autocomplete
entity corpus (app.autocomplete.ENTITIES) rather than a second, disconnected
city/airport dataset, per the Phase 4 requirement. Any change to that corpus
(e.g. the Phase 2 fix that completed it to 11 entities) is picked up here
automatically since this module imports the same list, not a copy."""
from __future__ import annotations

from ..autocomplete import ENTITIES, _fold

# Pre-index once at import time: every (folded surface form) -> entity, for
# every title/code/city/alias. Longest surface forms are tried first so
# "فرودگاه امام خمینی" resolves to the airport, not a shorter city collision.
_INDEX: list[tuple[str, dict]] = []
for _e in ENTITIES:
    for _surface in [_e["title"], _e.get("code", ""), *_e.get("aliases", [])]:
        if _surface:
            _INDEX.append((_fold(_surface), _e))
_INDEX.sort(key=lambda t: -len(t[0]))


def resolve_locations(normalized_text: str) -> list[dict]:
    """Returns distinct entities (by id) whose surface form appears in the
    normalized text, longest-match-first so overlapping names (e.g. a city
    name inside an airport name) resolve to the more specific entity only."""
    folded = _fold(normalized_text)
    found: list[dict] = []
    seen_ids: set[str] = set()
    consumed = folded
    for surface, entity in _INDEX:
        if entity["id"] in seen_ids:
            continue
        if surface and surface in consumed:
            found.append(entity)
            seen_ids.add(entity["id"])
            consumed = consumed.replace(surface, " ", 1)   # avoid re-matching a shorter alias of the same span
    return found
