"""Text + datetime normalization, ported verbatim from the monolith search
engine so migrated results are byte-comparable."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

_SEARCH_TRANSLATION = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "ؤ": "و", "إ": "ا", "أ": "ا", "ٱ": "ا",
    "‌": " ", "‍": " ",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})
_ALIASES = {
    "tehran": "تهران", "تهرون": "تهران", "thr": "تهران", "shiraz": "شیراز", "syz": "شیراز",
    "mashhad": "مشهد", "mhd": "مشهد", "isfahan": "اصفهان", "esfahan": "اصفهان", "ifn": "اصفهان",
}


def normalize_text(value: str) -> str:
    translated = unicodedata.normalize("NFKC", value or "").translate(_SEARCH_TRANSLATION)
    without_marks = "".join(c for c in translated if unicodedata.category(c) != "Mn")
    without_punct = " ".join(re.sub(r"[^\w\s]", " ", without_marks, flags=re.UNICODE).casefold().split())
    return " ".join(_ALIASES.get(tok, tok) for tok in without_punct.split())


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def search_datetime(value: object, fallback: datetime) -> datetime:
    if isinstance(value, str):
        try:
            return aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return fallback
    if isinstance(value, datetime):
        return aware(value)
    return fallback
