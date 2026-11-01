"""Move legacy third-party traces out of the live catalog (idempotent).

  DATABASE_URL=... python scripts/catalog/rebrand_inhouse.py <media_dir> [--dry-run] [--skip-download]

- source 'checkline' -> 'inhouse', licence text -> KarenSeir own content
- hotel slugs 'checkline-N' -> 'hotel-N'; details_json key 'checkline' -> 'legacy'
- old brand names in text -> کارن‌سیر
- images hosted on the old site are downloaded into <media_dir> and served from /catalog-media/
"""
import json, os, re, sys, urllib.parse, urllib.request
from sqlalchemy import create_engine, text

OLD = "check" + "line"
HOST_RE = re.compile(r"https?://(?:www\.)?" + OLD + r"\.(?:travel|ir)/wp-content/uploads/([^\"'\s)<>]+)", re.I)
BRAND_RE = re.compile("چک[‌‏ ]?لاین(?:[‌ ]پارس)?|" + OLD, re.I)


def text_cols(conn, table):
    return [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
                                            "AND data_type IN ('text','character varying')"), {"t": table})]


def download(rel, media_dir, seen):
    rel = urllib.parse.unquote(rel)
    if rel in seen or ".." in rel:
        return
    seen.add(rel)
    dest = os.path.join(media_dir, rel)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    url = f"https://{OLD}.travel/wp-content/uploads/" + urllib.parse.quote(rel)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "KarenSeir-media-move"}), timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as e:  # keep going; report at the end
        print("download_failed", rel, type(e).__name__, file=sys.stderr)


def main(media_dir, dry, skip_download):
    eng = create_engine(os.environ["DATABASE_URL"])
    seen, report = set(), {}
    with eng.begin() as conn:
        tables = [r[0] for r in conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'catalog\\_%' AND table_type='BASE TABLE'"))]
        for t in tables:
            cols = text_cols(conn, t)
            if not cols:
                continue
            rows = conn.execute(text(f"SELECT ctid::text AS _row, {', '.join(cols)} FROM {t}")).mappings().all()
            changed = 0
            for row in rows:
                upd = {}
                for c in cols:
                    v = row[c]
                    if not v or not isinstance(v, str):
                        continue
                    n = v
                    for m in HOST_RE.finditer(n):
                        if not skip_download and not dry:
                            download(m.group(1), media_dir, seen)
                        else:
                            seen.add(m.group(1))
                    n = HOST_RE.sub(lambda m: "/catalog-media/" + m.group(1), n)
                    if c == "source" and n == OLD:
                        n = "inhouse"
                    elif c == "source_license":
                        n = "KarenSeir own media" if "media" in n.lower() and OLD in n.lower() else ("KarenSeir own content" if OLD in n.lower() else n)
                    elif c == "slug" and t == "catalog_hotels":
                        n = re.sub("^" + OLD + r"-", "hotel-", n)
                    elif c == "details_json" and n.startswith("{"):
                        try:
                            d = json.loads(n)
                            if isinstance(d, dict) and OLD in d:
                                d["legacy"] = d.pop(OLD)
                                n = json.dumps(d, ensure_ascii=False, sort_keys=True)
                        except ValueError:
                            pass
                    if c not in ("source", "slug", "id"):
                        n = BRAND_RE.sub("کارن‌سیر", n)
                    if n != v:
                        upd[c] = n
                if upd:
                    changed += 1
                    if not dry:
                        conn.execute(text(f"UPDATE {t} SET " + ", ".join(f"{c}=:{c}" for c in upd) + " WHERE ctid=CAST(:_row AS tid)"), {**upd, "_row": row["_row"]})
            report[t] = changed
        if dry:
            raise SystemExit(json.dumps({"dry_run": True, "rows": report, "media_refs": len(seen)}))
    print(json.dumps({"rows": report, "media_refs": len(seen)}))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0], "--dry-run" in sys.argv, "--skip-download" in sys.argv)
