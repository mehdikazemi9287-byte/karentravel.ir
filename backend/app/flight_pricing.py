"""Shared sell-price logic for scheduled ("system") flight suppliers — Mahan (mahan_flight.py) and Niira (nira_flight.py).

* The tenant markup rule comes from `commerce.quote` with ctx {service_type: flight, supplier_id, airline_code, scope,
  flight_type: system, origin, destination}; with no matching rule the sell price equals the supplier net (no invented margin).
* The CAO adult cap (`charter_blocks.cap_for`, per leg and date) is checked on the adult sell price.
* Only DB reads happen here; callers make every supplier network call outside a DB transaction and roll back afterwards.
* Callers send customers only `public_price()` / the indicative sell figure; net, margin and VAT stay internal.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

FLIGHT_TYPE = "system"            # scheduled airline inventory (not charter blocks)


def flight_scope(db: Session, airport_codes: Iterable[str]) -> str:
    """domestic only when every airport is known and in Iran; an unknown airport is never assumed domestic."""
    from .catalog import CatalogAirport
    codes = {c.upper() for c in airport_codes if c}
    countries = {a.id: a.country_code for a in db.scalars(select(CatalogAirport).where(CatalogAirport.id.in_(codes)))} if codes else {}
    return "domestic" if codes and set(countries) == codes and all(c == "IR" for c in countries.values()) else "international"


def pricing_ctx(*, supplier_id: str, airline_code: str, origin: str, destination: str, scope: str) -> dict:
    return {"service_type": "flight", "supplier_id": supplier_id, "airline_code": airline_code, "origin": origin, "destination": destination,
            "scope": scope, "flight_type": FLIGHT_TYPE}


def cap_check(db: Session, tenant_id: int, legs: list[tuple[str, str, date]], adult_sell: Optional[int]) -> dict:
    """CAO adult cap over all legs. A cap on only some legs cannot be split from a combined fare → unverifiable."""
    from .charter_blocks import cap_for
    caps = [cap_for(db, tenant_id, o, d, day) for o, d, day in legs]
    state, total = "none", None
    if any(c[0] is not None for c in caps):
        if not all(c[0] is not None for c in caps):
            state = "unverifiable"
        else:
            total = sum(c[0] for c in caps)
            state = "exceeded" if (adult_sell or 0) > total else "ok"
    return {"cap_state": state, "cap_unit_irr": total, "cap_refs": [c[1] for c in caps if c[1]]}


def sell_quote(db: Session, tenant_id: int, user_id: Optional[int], *, supplier_id: str, airline_code: str, legs: list[tuple[str, str, date]],
               counts: dict, net_unit: dict, net_total: int, cabin: Optional[str] = None) -> dict:
    """Final price of one itinerary: markup on per-passenger net amounts, then the CAO cap, then VAT on the commission.
    Returns internal figures too (net, margin, VAT) — callers must only pass `public_price()` to customers."""
    from .agency_b2b import bps_of, vat_rate_on
    from .commerce import quote as commerce_quote
    scope = flight_scope(db, [x for o, d, _ in legs for x in (o, d)])
    ctx = pricing_ctx(supplier_id=supplier_id, airline_code=airline_code, origin=legs[0][0], destination=legs[0][1], scope=scope)
    fares = {p: {"count": counts[p], "total": net_unit[p]} for p in counts}
    result = commerce_quote(db, tenant_id, ctx, fares, user_id=user_id)
    lines = {ln["pax"]: ln for ln in result["lines"]}
    sell_unit = {p: lines[p]["sell"] for p in counts}
    sell_total = sum(sell_unit[p] * counts[p] for p in counts)
    cap = cap_check(db, tenant_id, legs, sell_unit.get("adult", 0))
    margin = sell_total - net_total
    try:
        rate = vat_rate_on(date.today(), db, tenant_id)
        vat = {"vat_on_commission": bps_of(max(margin, 0), rate.rate_bps), "vat_rate_bps": rate.rate_bps, "vat_reference": rate.legal_reference}
    except Exception:  # an uncovered date is an error in vat_rate_on, never a guess
        vat = {"vat_on_commission": None, "vat_rate_bps": None, "vat_reference": "unavailable"}
    return {"currency": "IRR", "sell_total": sell_total, "sell_unit": sell_unit, "counts": counts, "cabin": cabin, "scope": scope, **cap,
            "net_total": net_total, "net_unit": net_unit, "margin": margin, "rule_id": (result.get("rule") or {}).get("id"), **vat}


def public_price(p: dict) -> dict:
    return {"total_amount": p["sell_total"], "currency": p["currency"], "per_passenger": [{"type": k, "count": p["counts"][k], "unit_amount": p["sell_unit"][k]} for k in p["counts"]]}


def internal_price(p: dict) -> dict:
    return {k: p[k] for k in ("net_total", "net_unit", "sell_total", "margin", "rule_id", "vat_on_commission", "vat_rate_bps", "vat_reference", "cap_state", "cap_unit_irr", "cap_refs")}


class IndicativePricer:
    """Approximate per-adult sell price for search results (indicative, one adult, on the itinerary total so fixed amounts and
    rounding agree with the final quote). The rule is chosen once per (carrier, origin, destination) — a search can return
    dozens of offers. No VAT here; the final quote (revalidate) is authoritative."""

    def __init__(self, db: Session, tenant_id: int, user_id: Optional[int], supplier_id: str, *, group_id=None):
        """group_id: an already-resolved price group (search-service path: no user identity crosses that boundary);
        None → resolved from user_id as before."""
        self.db, self.tenant_id, self.user_id, self.supplier_id = db, tenant_id, user_id, supplier_id
        self._group = {} if group_id is None else {"group_id": group_id}
        self._rules: dict[tuple, object] = {}
        self._scopes: dict[frozenset, str] = {}

    def _scope(self, airports: Iterable[str]) -> str:
        key = frozenset(a.upper() for a in airports)
        if key not in self._scopes:
            self._scopes[key] = flight_scope(self.db, key)
        return self._scopes[key]

    def adult_sell(self, carrier: str, airports: list[str], net_adult: int) -> int:
        from .commerce import apply_rule, choose_rule
        scope = self._scope(airports)
        key = (carrier.upper(), airports[0].upper(), airports[1].upper(), scope)
        if key not in self._rules:
            ctx = pricing_ctx(supplier_id=self.supplier_id, airline_code=carrier, origin=key[1], destination=key[2], scope=scope)
            self._rules[key] = choose_rule(self.db, self.tenant_id, ctx, user_id=self.user_id, **self._group)
        return apply_rule(self._rules[key], {"adult": {"count": 1, "total": int(net_adult)}})["lines"][0]["sell"]

    def cap(self, legs: list[tuple[str, str, date]], adult_sell: int) -> dict:
        return cap_check(self.db, self.tenant_id, legs, adult_sell)
