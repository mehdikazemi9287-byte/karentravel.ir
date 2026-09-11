"""Ranking foundation, extracted from engine.py so ranking is a dedicated,
versioned, testable stage instead of logic scattered inside endpoint handlers.

RANKING_VERSION is part of the search cache key (cache_keys.py) and is
reported in every response's search_metadata -- a future ranking change ships
as a new version, old cached entries never leak under a changed scoring
model, and A/B or rollback comparisons have a stable label to key on.

Scoring stays deterministic and fully explained (ranking_breakdown / offer
sort keys below) on purpose -- no opaque/AI ranking in this phase. Future
factors (provider reliability, corporate eligibility, user preference,
commercial score, popularity, availability confidence) are additional
weighted terms in score_breakdown; they do not change the pipeline shape."""
from __future__ import annotations

RANKING_VERSION = "v1-deterministic"


def score_breakdown(*, final_price: float, review_score: float, refundable: bool,
                     policy_compliant: bool, stale: bool, provider_reliability: float) -> dict[str, float]:
    """Every term is a real, derived signal -- never fabricated or randomized."""
    return {
        "price": round(1_000_000_000 / max(final_price, 1), 4),
        "reviews": review_score * 10,
        "flexibility": 10 if refundable else 0,
        "policy": 5 if policy_compliant else 0,
        "freshness": 0 if stale else 15,
        "provider_reliability": float(provider_reliability),
    }


def score_offer(breakdown: dict[str, float]) -> float:
    return round(sum(breakdown.values()), 4)


# legacy request-level sort aliases -> canonical offer-sort key
LEGACY_SORT = {"lowest_price": "price_asc", "cheapest": "price_asc", "highest_rated": "review_desc"}

OFFER_SORTERS = {
    "price_asc": lambda i: (i["total_amount"], -i["ranking_score"]),
    "price_desc": lambda i: (-i["total_amount"], -i["ranking_score"]),
    "review_desc": lambda i: (-(i["review_score"] or 0), i["total_amount"]),
    "freshness": lambda i: (i["freshness"] != "live", i["last_updated_at"]),
    "recommended": lambda i: (-i["ranking_score"], i["total_amount"]),
}

ENTITY_SORTERS = {
    "lowest_price": lambda i: i["best_offer"]["final_price"],
    "cheapest": lambda i: i["best_offer"]["final_price"],
    "highest_rated": lambda i: -(i["best_offer"]["review_score"] or 0),
    "best_location": lambda i: -float(i["best_offer"]["attributes"].get("location_score", 0)),
    "most_flexible": lambda i: not bool((i["best_offer"].get("cancellation_policy") or {}).get("refundable")),
    "fastest": lambda i: float(i["best_offer"]["attributes"].get("duration_minutes", 10 ** 9)),
}
