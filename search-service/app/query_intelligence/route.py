"""Origin/destination inference for route-based verticals (flight, train,
bus) using directional tokens (به/از/تا) and the canonical entity corpus
(entities.py, itself backed by the existing autocomplete dataset). Never
invents an origin, and never uses device/IP location -- only what the query
text actually contains. When direction can't be determined confidently, the
result is explicitly marked ambiguous rather than guessed."""
from __future__ import annotations

from ..autocomplete import _fold
from .entities import _INDEX

ROUTE_VERTICALS = frozenset({"flight", "train", "bus"})

_TO_TOKENS = tuple(_fold(t) for t in ("به", "تا"))
_FROM_TOKEN = _fold("از")
_AFTER_TOKEN = _fold("بعد")   # "then" -- marks an additional stop after the main route, e.g. "شیراز بعد کیش"


def _find_entity_spans(folded_text: str) -> list[tuple[int, int, dict]]:
    claimed = [False] * len(folded_text)
    spans: list[tuple[int, int, dict]] = []
    for surface, entity in _INDEX:
        if not surface:
            continue
        idx = folded_text.find(surface)
        if idx == -1:
            continue
        end = idx + len(surface)
        if any(claimed[idx:end]):
            continue
        spans.append((idx, end, entity))
        for i in range(idx, end):
            claimed[i] = True
    spans.sort(key=lambda s: s[0])
    seen: set[str] = set()
    out = []
    for s in spans:
        if s[2]["id"] not in seen:
            out.append(s)
            seen.add(s[2]["id"])
    return out


def _resolve_pair(folded: str, idx1: int, idx2: int, e1: dict, e2: dict) -> tuple[dict, dict] | None:
    """Returns (origin, destination) if a directional token confidently
    orders e1/e2, else None -- never guesses when direction is unclear."""
    between = folded[idx1:idx2]
    from_idx = folded.find(_FROM_TOKEN)
    to_idx = max((folded.find(t) for t in _TO_TOKENS if t in folded), default=-1)
    if from_idx != -1 and to_idx != -1 and from_idx < idx1 < to_idx < idx2:
        return e1, e2
    if any(t in between for t in _TO_TOKENS):
        return e1, e2
    return None


def infer_route(normalized_text: str) -> dict:
    """Returns {"origin": entity|None, "destination": entity|None,
    "intermediate_stops": [entity, ...], "ambiguous": bool, "reason": str|None}."""
    folded = _fold(normalized_text)
    spans = _find_entity_spans(folded)

    if len(spans) == 0:
        return {"origin": None, "destination": None, "intermediate_stops": [], "ambiguous": False, "reason": None}
    if len(spans) == 1:
        return {"origin": None, "destination": None, "intermediate_stops": [], "ambiguous": True, "reason": "single_location_no_direction"}

    if len(spans) == 3:
        # "تهران به شیراز بعد کیش" -- an additional stop after the main
        # route, e.g. via "بعد" (then). Captured as metadata only (the
        # orchestrator still only ever searches origin->destination); never
        # silently treated as a searchable multi-leg itinerary.
        (idx1, _, e1), (idx2, _, e2), (idx3, _, e3) = spans
        pair = _resolve_pair(folded, idx1, idx2, e1, e2)
        after_idx = folded.find(_AFTER_TOKEN)
        if pair and after_idx != -1 and idx2 < after_idx < idx3:
            return {"origin": pair[0], "destination": pair[1], "intermediate_stops": [e3],
                    "ambiguous": False, "reason": None}
        return {"origin": None, "destination": None, "intermediate_stops": [],
                "ambiguous": True, "reason": "multiple_possible_destinations"}

    if len(spans) > 3:
        return {"origin": None, "destination": None, "intermediate_stops": [],
                "ambiguous": True, "reason": "multiple_possible_destinations"}

    (idx1, _, e1), (idx2, _, e2) = spans
    pair = _resolve_pair(folded, idx1, idx2, e1, e2)
    if pair:
        return {"origin": pair[0], "destination": pair[1], "intermediate_stops": [], "ambiguous": False, "reason": None}
    return {"origin": None, "destination": None, "intermediate_stops": [], "ambiguous": True, "reason": "missing_route_direction"}
