"""Deterministic Persian-aware text normalization for Query Intelligence.

Reuses app.normalization.normalize_text (already shipped, already used to
match search offers) instead of a second, competing implementation. It
already handles: ی/ك canonicalization, نیم‌فاصله (ZWNJ) -> space, Persian/
Arabic digit -> Latin digit, NFKC + diacritic stripping, punctuation ->
space, duplicate-whitespace collapse, and a small known city-alias rewrite
(e.g. "tehran" -> "تهران"). It does not stem words, so names are preserved.

The original text is never discarded -- callers keep both original_text and
normalized_text on the SearchPlan."""
from __future__ import annotations

from ..normalization import normalize_text

MAX_QUERY_LENGTH = 300


def normalize_query(text: str) -> str:
    if not text:
        return ""
    return normalize_text(text[:MAX_QUERY_LENGTH])
