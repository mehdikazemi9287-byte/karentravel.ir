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


def infer_route(normalized_text: str) -> dict:
    """Returns {"origin": entity|None, "destination": entity|None,
    "ambiguous": bool, "reason": str|None}."""
    folded = _fold(normalized_text)
    spans = _find_entity_spans(folded)

    if len(spans) == 0:
        return {"origin": None, "destination": None, "ambiguous": False, "reason": None}
    if len(spans) == 1:
        return {"origin": None, "destination": None, "ambiguous": True, "reason": "single_location_no_direction"}
    if len(spans) > 2:
        return {"origin": None, "destination": None, "ambiguous": True, "reason": "multiple_possible_destinations"}

    (idx1, _, e1), (idx2, _, e2) = spans
    between = folded[idx1:idx2]
    from_idx = folded.find(_FROM_TOKEN)
    to_idx = max((folded.find(t) for t in _TO_TOKENS if t in folded), default=-1)

    if from_idx != -1 and to_idx != -1 and from_idx < idx1 < to_idx < idx2:
        return {"origin": e1, "destination": e2, "ambiguous": False, "reason": None}
    if any(t in between for t in _TO_TOKENS):
        return {"origin": e1, "destination": e2, "ambiguous": False, "reason": None}
    return {"origin": None, "destination": None, "ambiguous": True, "reason": "missing_route_direction"}
