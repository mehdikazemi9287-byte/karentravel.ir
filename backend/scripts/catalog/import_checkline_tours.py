"""Import staged CheckLine tours as non-commercial reference drafts (additive, idempotent).

  DATABASE_URL=... python scripts/catalog/import_checkline_tours.py <staged_dir> [--dry-run]

A catalog tour is a description of something that was once offered: a title and the dates it ran on. It has
no price, capacity, supplier or tenant and can never be booked. Something sellable exists only when a supplier
creates a tour_products/tour_departures record of its own (with its contract, dates and rates).
Dates: the Jalali text is kept verbatim; a Gregorian date is stored only when the text is a valid calendar date.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select  # noqa: E402

from app.catalog import CatalogTour, CatalogTourDeparture, normalize_text  # noqa: E402
from app.database import SessionLocal  # noqa: E402

SOURCE, LICENSE, RETRIEVED = "checkline", "CheckLine content; rights unverified", "2026-10-06"
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _j2g(jy: int, jm: int, jd: int) -> date:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186)
    gy = 400 * (days // 146097); days %= 146097
    if days > 36524:
        days -= 1; gy += 100 * (days // 36524); days %= 36524
        if days >= 365: days += 1
    gy += 4 * (days // 1461); days %= 1461
    if days > 365:
        gy += (days - 1) // 365; days = (days - 1) % 365
    gd, gm = days + 1, 0
    lengths = [0, 31, 29 if (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    while gm < 13 and gd > lengths[gm]:
        gd -= lengths[gm]; gm += 1
    return date(gy, gm, gd)


def jalali_to_gregorian(text) -> date | None:
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", (text or "").translate(_DIGITS).strip())
    if not m:
        return None
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    if not (1300 <= y <= 1500 and 1 <= mo <= 12 and 1 <= d <= (31 if mo <= 6 else 30)):
        return None
    if mo == 12 and d == 30 and _j2g(y, 12, 30) == _j2g(y + 1, 1, 1):  # Esfand has 30 days only in a leap year
        return None
    return _j2g(y, mo, d)


def main(staged_dir: str, dry_run: bool) -> dict:
    staged = Path(staged_dir)
    tours = [json.loads(line)["raw"] for line in (staged / "tours.jsonl").open(encoding="utf-8")]
    departures = [json.loads(line)["raw"] for line in (staged / "departures.jsonl").open(encoding="utf-8")]
    report = {"tours_input": len(tours), "tours_inserted": 0, "tours_unchanged": 0, "admin_owned_skipped": 0, "departures_input": len(departures), "departures_inserted": 0,
              "departures_unchanged": 0, "departures_invalid_date": 0, "departures_without_tour": 0}
    with SessionLocal() as db:
        known = set()
        for raw in tours:
            tid, title = f"cl-tour-{raw['tour_id']}", (raw.get("title") or "").strip()
            if not title:
                continue
            known.add(tid)
            values = {"title_fa": title[:200], "search_text": normalize_text(title), "source_disabled": str(raw.get("disabled")) == "1", "source_soldout": str(raw.get("soldout")) == "1",
                      "source": SOURCE, "source_ref": f"tour/{raw['tour_id']}", "source_license": LICENSE, "retrieved_on": RETRIEVED}
            row = db.get(CatalogTour, tid)
            if row is None:
                report["tours_inserted"] += 1
                if not dry_run: db.add(CatalogTour(id=tid, status="draft", **values))
            elif row.updated_by is not None:
                report["admin_owned_skipped"] += 1
            elif any(getattr(row, k) != v for k, v in values.items()):
                for k, v in values.items(): setattr(row, k, v)
            else:
                report["tours_unchanged"] += 1
        if not dry_run: db.flush()
        existing = {(d.tour_id, d.source_row) for d in db.scalars(select(CatalogTourDeparture))}
        for raw in departures:
            tid = f"cl-tour-{raw['tour_id']}"
            if tid not in known:
                report["departures_without_tour"] += 1; continue
            starts, ends = jalali_to_gregorian(raw.get("departure_raw")), jalali_to_gregorian(raw.get("end_raw"))
            if starts is None or (ends is not None and ends < starts):
                report["departures_invalid_date"] += 1; starts = ends = None  # keep the raw text, store no computed date
            if (tid, int(raw["row_index"])) in existing:
                report["departures_unchanged"] += 1; continue
            report["departures_inserted"] += 1
            if not dry_run:
                db.add(CatalogTourDeparture(tour_id=tid, source_row=int(raw["row_index"]), starts_jalali=(raw.get("departure_raw") or "")[:20] or None, ends_jalali=(raw.get("end_raw") or "")[:20] or None,
                                            starts_on=starts, ends_on=ends))
        if not dry_run: db.commit()
    print(json.dumps({"dry_run": dry_run, **report}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], "--dry-run" in sys.argv)
