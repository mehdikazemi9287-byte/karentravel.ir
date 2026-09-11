"""Deterministic turn classifier (master prompt sec 4). Schema-validated
action categories only -- no free-form model output ever executes a tool.
This classifies the ACTION TYPE of a turn (new search / refine / select a
prior result / ask about one / start booking prep / reset / blocked); it
never re-parses dates/passengers/cabin/budget -- that stays in Search's
Query Planner exclusively (sec 12/13)."""
from __future__ import annotations

import re
import unicodedata

NEW_SEARCH = "NEW_SEARCH"
REFINE_SEARCH = "REFINE_SEARCH"
SELECT_RESULT = "SELECT_RESULT"
ASK_ABOUT_RESULT = "ASK_ABOUT_RESULT"
START_BOOKING_PREP = "START_BOOKING_PREP"
UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
CANCEL_CURRENT_FLOW = "CANCEL_CURRENT_FLOW"
BLOCKED_FINANCIAL_ACTION = "BLOCKED_FINANCIAL_ACTION"


def _fold(s: str) -> str:
    t = unicodedata.normalize("NFKC", s or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.translate(str.maketrans({"‌": " ", "‍": " "}))
    return " ".join(t.casefold().split())


_RESET_PHRASES = ("از اول", "یه سفر دیگه", "یک سفر دیگه", "این رو بیخیال", "بیخیالش", "جستجوی جدید", "start over", "new search")
_PAYMENT_PHRASES = ("پولشو", "پول رو", "پرداخت کن", "پرداختش کن", "بخرش", "بخر", "pay for it", "make the payment")
_BOOKING_PHRASES = ("رزروش کن", "رزرو کن", "رزروش رو انجام", "book it", "reserve it")
_ORDINAL_WORDS = {
    "اولی": 1, "اول": 1, "دومی": 2, "دوم": 2, "سومی": 3, "سوم": 3,
    "چهارمی": 4, "چهارم": 4, "پنجمی": 5, "پنجم": 5,
    "آخر": -1, "آخری": -1, "آخرین": -1, "گزینه آخر": -1,
}
_CHEAPEST_REF = ("ارزون ترین", "ارزان ترین", "ارزون‌ترین", "ارزان‌ترین")
_BEST_REF = ("بهترین",)
_QUESTION_MARKERS = ("چیه", "چیست", "کجا", "ساعت", "چند", "داره", "دارد", "؟", "?")


def _find_ordinal(folded: str) -> int | None:
    for phrase, idx in sorted(_ORDINAL_WORDS.items(), key=lambda kv: -len(kv[0])):
        if _fold(phrase) in folded:
            return idx
    if any(p in folded for p in _CHEAPEST_REF):
        return -2   # sentinel: cheapest
    if any(p in folded for p in _BEST_REF):
        return 1    # "بهترین" -> first/top of the (already-ranked) result set
    return None


def classify(text: str, *, has_active_plan: bool, has_result_set: bool) -> dict:
    """Returns {"action": ..., "ordinal_ref": int|None}. ordinal_ref is only
    meaningful for SELECT_RESULT/ASK_ABOUT_RESULT: a positive display_index
    (1-based), -1 for "last", -2 for "cheapest"."""
    folded = _fold(text)

    if any(_fold(p) in folded for p in _RESET_PHRASES):
        return {"action": CANCEL_CURRENT_FLOW, "ordinal_ref": None}

    if any(_fold(p) in folded for p in _PAYMENT_PHRASES):
        return {"action": BLOCKED_FINANCIAL_ACTION, "ordinal_ref": None}

    ordinal = _find_ordinal(folded)
    if ordinal is not None and has_result_set:
        if any(_fold(p) in folded for p in _QUESTION_MARKERS):
            return {"action": ASK_ABOUT_RESULT, "ordinal_ref": ordinal}
        return {"action": SELECT_RESULT, "ordinal_ref": ordinal}

    if any(_fold(p) in folded for p in _BOOKING_PHRASES):
        return {"action": START_BOOKING_PREP, "ordinal_ref": None}

    if ordinal is not None and not has_result_set:
        # a reference with nothing to reference against -- never guess
        return {"action": UNSUPPORTED_ACTION, "ordinal_ref": None}

    # No structural marker matched -- let the caller try Search's planner
    # (NEW_SEARCH if it resolves standalone, REFINE_SEARCH if it only
    # resolves once carried context is added). The classifier does not
    # itself distinguish these two; that decision genuinely depends on
    # whether Search's planner can parse the bare text, which only Search
    # knows (sec 12: Search remains source of truth for query planning).
    return {"action": REFINE_SEARCH if has_active_plan else NEW_SEARCH, "ordinal_ref": None}
