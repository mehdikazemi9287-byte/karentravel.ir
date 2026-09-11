"""Result-set compaction, ordinal resolution, and state hashing.

Token discipline (sec 22 of the master prompt): raw Search payloads never
get stored/re-sent wholesale -- only a compact reference list (entity_id,
offer_id, display_index, price, currency, title, vertical) survives into
conversation state. Ordinal/result resolution is pure code, never an LLM
call, per the mandatory architecture target."""
from __future__ import annotations

import hashlib
import json
import time
import uuid


def compact_result_set(search_response: dict, *, vertical: str) -> dict:
    entities = search_response.get("entities", [])
    items = []
    for idx, e in enumerate(entities, start=1):
        best = e.get("best_offer") or {}
        items.append({
            "display_index": idx,
            "entity_id": e.get("entity_id"),
            "offer_id": best.get("offer_id") or best.get("id"),
            "title": e.get("title"),
            "price": best.get("final_price"),
            "currency": best.get("currency"),
            "provider_count": e.get("provider_count"),
        })
    return {
        "result_set_id": str(uuid.uuid4()),
        "search_request_id": search_response.get("search_metadata", {}).get("correlation_id"),
        "vertical": vertical,
        "timestamp": time.time(),
        "items": items,
    }


def resolve_ordinal(result_set: dict | None, ordinal_ref: int) -> dict | None:
    """ordinal_ref: 1-based index, -1 = last, -2 = cheapest. Returns the
    compact item dict or None if it can't be resolved -- never guesses."""
    if not result_set or not result_set.get("items"):
        return None
    items = result_set["items"]
    if ordinal_ref == -1:
        return items[-1]
    if ordinal_ref == -2:
        priced = [i for i in items if i.get("price") is not None]
        return min(priced, key=lambda i: i["price"]) if priced else None
    if 1 <= ordinal_ref <= len(items):
        return items[ordinal_ref - 1]
    return None   # out of range -- never clamp/guess


def result_set_is_fresh(result_set: dict | None, *, max_age_seconds: float = 1800) -> bool:
    """Conservative Assistant-level staleness rule -- explicitly NOT a
    provider-availability signal (Search's own freshness/TTL semantics on
    each offer remain authoritative for that; this only governs whether the
    Assistant still considers a conversational reference like "دومی"
    resolvable at all)."""
    if not result_set:
        return False
    return (time.time() - result_set.get("timestamp", 0)) <= max_age_seconds


def state_hash(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def revalidate_price(selected_item: dict, fresh_search_response: dict) -> dict:
    """Compares a previously-selected item's price against a freshly
    re-fetched Search response (Phase 3 sec 11). Never silently substitutes
    another offer -- reports the material facts and lets the caller decide.
    Returns {"changed": bool, "available": bool, "old_price": ..., "new_price": ...,
    "new_item": <fresh compact item or None>}."""
    entities = fresh_search_response.get("entities", [])
    match = next((e for e in entities if e.get("entity_id") == selected_item.get("entity_id")), None)
    if not match:
        return {"changed": True, "available": False, "old_price": selected_item.get("price"),
                "new_price": None, "new_item": None}
    best = match.get("best_offer") or {}
    new_price = best.get("final_price")
    old_price = selected_item.get("price")
    new_item = {**selected_item, "price": new_price, "currency": best.get("currency"),
                "offer_id": best.get("offer_id") or best.get("id")}
    return {"changed": new_price != old_price, "available": True,
            "old_price": old_price, "new_price": new_price, "new_item": new_item}
