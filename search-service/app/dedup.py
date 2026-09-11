"""Explicit deduplication stage.

Identity is entity_id (see engine.normalize_offer: an explicit
attrs["entity_id"] when a provider supplies one, otherwise a deterministic
hash of service_type + normalized title + normalized city). Offers sharing an
entity_id are grouped as one sellable entity with multiple provider/price
options; offers that do not share an entity_id are always kept separate.

This stays conservative on purpose: identity confidence must come from an
explicit signal (same id, or same normalized title+city+vertical), never a
fuzzy/similarity guess. A false merge would silently hide a distinct, real
offer -- worse than showing two rows that a human could tell apart. Fuzzy
cross-provider matching is a future, explicitly opt-in enhancement, not a
default behavior.

Grouping is deterministic: dict insertion order follows input order, and
group ordering is decided later by the ranking stage, not by dedup."""
from __future__ import annotations


def group_by_entity(offers: list[dict]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for o in offers:
        g = groups.setdefault(o["entity_id"], {
            "entity_id": o["entity_id"], "title": o["title"], "service_type": o["service_type"], "offers": [],
        })
        g["offers"].append(o)
    return groups
