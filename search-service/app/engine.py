"""Search engine: raw offer pool -> normalized / filtered / ranked / deduped /
grouped results. Logic ported from the monolith's search_offers + unified_search
so a strangler swap is result-compatible. No price, availability or provider
response is fabricated: every field is derived from a real offer row."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from .normalization import aware, normalize_text, search_datetime

_LEGACY_SORT = {"lowest_price": "price_asc", "cheapest": "price_asc", "highest_rated": "review_desc"}
_OFFER_SORTERS = {
    "price_asc": lambda i: (i["total_amount"], -i["ranking_score"]),
    "price_desc": lambda i: (-i["total_amount"], -i["ranking_score"]),
    "review_desc": lambda i: (-(i["review_score"] or 0), i["total_amount"]),
    "freshness": lambda i: (i["freshness"] != "live", i["last_updated_at"]),
    "recommended": lambda i: (-i["ranking_score"], i["total_amount"]),
}
_ENTITY_SORTERS = {
    "lowest_price": lambda i: i["best_offer"]["final_price"],
    "cheapest": lambda i: i["best_offer"]["final_price"],
    "highest_rated": lambda i: -(i["best_offer"]["review_score"] or 0),
    "best_location": lambda i: -float(i["best_offer"]["attributes"].get("location_score", 0)),
    "most_flexible": lambda i: not bool((i["best_offer"].get("cancellation_policy") or {}).get("refundable")),
    "fastest": lambda i: float(i["best_offer"]["attributes"].get("duration_minutes", 10 ** 9)),
}
_PUBLIC_SAFE_OFFER_KEYS = frozenset({
    "id", "offer_id", "entity_id", "service_type", "title", "provider", "provider_status",
    "freshness", "freshness_state", "observed_at", "availability_state", "inventory_status",
    "available", "cancellation_policy", "policy_verified", "review_score", "location",
    "attributes", "ranking_explanation",
})


def _f(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def normalize_offer(row: dict, *, query_norm: str, filters: dict, include_stale: bool, now: datetime) -> dict | None:
    attrs = row.get("attributes") or {}
    policy = row.get("policy") or {}
    searchable = normalize_text(" ".join(str(v) for v in [
        row.get("title", ""), attrs.get("city", ""), attrs.get("origin", ""),
        attrs.get("destination", ""), attrs.get("province", ""), attrs.get("airport", ""), attrs.get("poi", ""),
    ]))
    if query_norm and query_norm not in searchable:
        return None
    review_score = float(attrs.get("review_score", attrs.get("rating", 0)) or 0)
    if filters.get("min_review_score") is not None and review_score < filters["min_review_score"]:
        return None
    cancellation = policy.get("cancellation", {}) if policy.get("verified") is True else None
    if filters.get("refundable") is not None and (cancellation or {}).get("refundable") is not filters["refundable"]:
        return None
    have_amenities = {normalize_text(str(a)) for a in attrs.get("amenities", [])}
    if any(normalize_text(a) not in have_amenities for a in filters.get("amenities", []) or []):
        return None
    if filters.get("instant_booking") is not None and bool(
        attrs.get("instant_booking", row.get("fulfillment_mode") == "manual_supplier")
    ) is not filters["instant_booking"]:
        return None
    bounds = filters.get("map_bounds")
    if bounds:
        lat, lng = attrs.get("latitude"), attrs.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)) or not (
            bounds["south"] <= lat <= bounds["north"] and bounds["west"] <= lng <= bounds["east"]
        ):
            return None

    fallback_observed = search_datetime(row.get("updated_at") or row.get("created_at"), now)
    observed_at = search_datetime(attrs.get("observed_at"), fallback_observed)
    ttl_default = 3600 if row.get("fulfillment_mode") == "manual_supplier" else 300
    ttl = max(30, min(_f(attrs.get("freshness_ttl_seconds", ttl_default), ttl_default), 86400))
    stale = observed_at + timedelta(seconds=ttl) <= now
    if stale and not include_stale:
        return None

    taxes = max(0, _f(attrs.get("taxes", 0)))
    fees = max(0, _f(attrs.get("fees", 0)))
    discounts = max(0, _f(attrs.get("discounts", 0)))
    base = _f(row.get("amount", 0))
    final_price = max(0, base + taxes + fees - discounts)
    entity_id = attrs.get("entity_id") or hashlib.sha256(
        f"{row.get('service_type')}:{normalize_text(row.get('title', ''))}:{normalize_text(str(attrs.get('city', '')))}".encode()
    ).hexdigest()[:24]

    result: dict[str, Any] = {
        "id": row.get("id"), "offer_id": row.get("id"), "entity_id": entity_id,
        "service_type": row.get("service_type"), "title": row.get("title"),
        "provider": row.get("provider_key"),
        "provider_status": "supplier_verified" if row.get("fulfillment_mode") == "manual_supplier" else "provider_required",
        "last_updated_at": observed_at.isoformat(), "observed_at": observed_at.isoformat(),
        "availability_checked_at": search_datetime(attrs.get("availability_checked_at"), observed_at).isoformat(),
        "price_checked_at": search_datetime(attrs.get("price_checked_at"), observed_at).isoformat(),
        "freshness_ttl_seconds": ttl, "freshness": "stale" if stale else "live",
        "freshness_state": "STALE" if stale else "LIVE",
        "amount": base, "base_price": base, "taxes": taxes, "fees": fees, "discounts": discounts,
        "total_amount": final_price, "final_price": final_price, "currency": row.get("currency"),
        "available": not stale, "availability_state": "REQUIRES_RECHECK" if stale else "CONFIRMED",
        "inventory_status": "available" if not stale else "stale_unknown",
        "available_units": row.get("available_units") if not stale else None,
        "cancellation_policy": cancellation, "policy_verified": policy.get("verified") is True,
        "quality_score": attrs.get("quality_score", attrs.get("quality")),
        "review_score": review_score or None,
        "location": {k: attrs.get(k) for k in ("city", "province", "latitude", "longitude") if attrs.get(k) is not None},
        "attributes": attrs,
        "valid_until": search_datetime(row.get("valid_until"), now).isoformat(),
    }
    breakdown = {
        "price": round(1_000_000_000 / max(result["total_amount"], 1), 4),
        "reviews": review_score * 10,
        "flexibility": 10 if cancellation and cancellation.get("refundable") else 0,
        "policy": 5 if attrs.get("organization_policy_compliant") else 0,
        "freshness": 0 if stale else 15,
        "provider_reliability": float(attrs.get("provider_reliability", 5)),
    }
    result["ranking_breakdown"] = breakdown
    result["ranking_score"] = round(sum(breakdown.values()), 4)
    result["ranking_explanation"] = [
        label for enabled, label in (
            (not stale, "داده تازه"),
            (review_score >= 8, "امتیاز کاربران بالا"),
            (bool(cancellation and cancellation.get("refundable")), "امکان استرداد"),
            (bool(attrs.get("organization_policy_compliant")), "منطبق با سیاست سازمان"),
        ) if enabled
    ]
    return result


def structured_intent(req) -> dict:
    q = normalize_text(req.query or "")
    intent: dict[str, Any] = {"normalized_query": q, "travellers": req.travellers}
    if req.origin:
        intent["origin"] = req.origin
    if req.destination:
        intent["destination"] = req.destination
    return intent


def assemble(req, pools: dict[str, list[dict]], provider_meta: list[dict], elapsed_ms: float) -> dict:
    now = datetime.now(timezone.utc)
    intent = structured_intent(req)
    query = req.destination or intent.get("destination") or req.query
    query_norm = normalize_text(query or "")
    safe_filters = {k: v for k, v in (req.filters or {}).items() if k in {
        "min_price", "max_price", "min_review_score", "refundable", "amenities", "instant_booking", "map_bounds",
    }}
    legacy_sort = _LEGACY_SORT.get(req.sort, "recommended")

    offers: list[dict] = []
    for vertical, rows in pools.items():
        norm = []
        for row in rows:
            if safe_filters.get("min_price") is not None and _f(row.get("amount")) < safe_filters["min_price"]:
                continue
            if safe_filters.get("max_price") is not None and _f(row.get("amount")) > safe_filters["max_price"]:
                continue
            n = normalize_offer(row, query_norm=query_norm, filters=safe_filters, include_stale=req.include_stale, now=now)
            if n is not None:
                norm.append(n)
        norm.sort(key=_OFFER_SORTERS[legacy_sort])
        offers.extend(norm)

    groups: dict[str, dict] = {}
    for o in offers:
        g = groups.setdefault(o["entity_id"], {"entity_id": o["entity_id"], "title": o["title"], "service_type": o["service_type"], "offers": []})
        g["offers"].append(o)
    entities = []
    for g in groups.values():
        g["offers"].sort(key=lambda i: (i["final_price"], -i["ranking_score"]))
        g["best_offer"] = g["offers"][0]
        g["provider_count"] = len({i["provider"] for i in g["offers"]})
        g["ranking_score"] = max(i["ranking_score"] for i in g["offers"])
        entities.append(g)
    entities.sort(key=_ENTITY_SORTERS.get(req.sort, lambda i: -i["ranking_score"]))

    offset = (req.page - 1) * req.page_size
    page_items = entities[offset:offset + req.page_size]
    if req.public:
        for e in page_items:
            e["offers"] = [{k: v for k, v in o.items() if k in _PUBLIC_SAFE_OFFER_KEYS} for o in e["offers"]]
            e["best_offer"] = {k: v for k, v in e["best_offer"].items() if k in _PUBLIC_SAFE_OFFER_KEYS}

    recovery = [] if entities else [
        {"type": "nearby_dates", "message": "تاریخ‌های ±۱ روز را بررسی کنید", "fabricated_price": False},
        {"type": "fewer_filters", "message": "برخی فیلترها را حذف کنید", "fabricated_price": False},
    ]
    failed = [m for m in provider_meta if m["status"] not in ("available", "not_connected")]
    # provider_diagnostics keyed by the real offer provider (parity with monolith)
    diag = [
        {"provider": key, "status": "available", "offer_count": sum(1 for o in offers if o["provider"] == key)}
        for key in sorted({o["provider"] for o in offers})
    ]
    return {
        "structured_query": intent,
        "entities": page_items,
        "pagination": {"page": req.page, "page_size": req.page_size, "total": len(entities)},
        "freshness_policy": "provider_and_vertical_specific",
        "availability_recheck_required_before_checkout": True,
        "price_recheck_required_before_checkout": True,
        "zero_result_recovery": recovery,
        "provider_diagnostics": diag,
        "provider_fanout": [
            {"provider": m["provider"], "vertical": m.get("vertical"), "status": m["status"], "offer_count": m.get("offer_count", 0)}
            for m in provider_meta
        ],
        "search_metadata": {
            "providers_requested": len(provider_meta),
            "providers_completed": sum(1 for m in provider_meta if m["status"] in ("available", "not_connected")),
            "providers_failed": len(failed),
            "partial_results": bool(failed) and bool(entities),
            "elapsed_ms": elapsed_ms,
            "correlation_id": req.correlation_id,
        },
        "tenant_data_included": not req.public,
        "elapsed_ms": elapsed_ms,
    }
