"""Import the magazine articles in content/blog/*.md as published blog posts (idempotent, additive).

Run inside the api container (the image ships this script and content/blog):

  cd /opt/karenseir && docker compose exec api python -m scripts.import_blog_posts            # dry run: shows what would be inserted
  cd /opt/karenseir && docker compose exec api python -m scripts.import_blog_posts --apply    # insert and publish

Options: --tenant <slug> (default: NEXT_PUBLIC_TENANT_SLUG or "aftab-bank", the tenant the public site reads in
lib/blog.ts), --dir <path> (default: content/blog next to this script's parent).

Rules:
- A post whose slug already exists for the tenant is never touched (whatever its status or text): re-running is a no-op.
- Nothing is updated or deleted. Every file is validated with the same rules as the admin editor (PostIn: slug, title,
  excerpt, tags, cover, no HTML; and the no-price/discount rule) before anything is written; one invalid file aborts all.
- File format: a front-matter block between two "---" lines (slug, title, excerpt, category, tags as a comma list,
  cover, cover_alt), then the plain-text body ("## " headings, "- " lists, internal links as [text](/path)).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException  # noqa: E402
from sqlalchemy import select  # noqa: E402

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "content" / "blog"


def parse_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: missing front matter")
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise ValueError(f"{path.name}: front matter is not closed")
    meta: dict[str, str] = {}
    for line in head.split("\n"):
        if line.strip():
            key, colon, value = line.partition(":")
            if not colon:
                raise ValueError(f"{path.name}: bad front-matter line {line!r}")
            meta[key.strip()] = value.strip()
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    return {"slug": meta.get("slug", ""), "title": meta.get("title", ""), "excerpt": meta.get("excerpt", ""), "body": body.strip() + "\n",
            "category": meta.get("category", "guide"), "tags": tags, "cover": meta.get("cover", ""), "cover_alt": meta.get("cover_alt", "")}


def validate(paths: list[Path]):
    from app.blog import PostIn, _no_prices
    posts, errors, seen = [], [], set()
    for path in paths:
        try:
            data = PostIn(**parse_file(path))
            _no_prices(data)
            if data.slug in seen:
                raise ValueError(f"duplicate slug {data.slug}")
            if path.stem != data.slug:
                raise ValueError(f"file name must equal slug ({data.slug}.md)")
            seen.add(data.slug)
            posts.append(data)
        except HTTPException as exc:
            errors.append(f"{path.name}: {exc.detail}")
        except Exception as exc:  # pydantic ValidationError, ValueError
            errors.append(f"{path.name}: {exc}")
    return posts, errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    ap.add_argument("--tenant", default=os.getenv("NEXT_PUBLIC_TENANT_SLUG") or "aftab-bank")
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    args = ap.parse_args()

    paths = sorted(Path(args.dir).glob("*.md"))
    if not paths:
        print(f"no .md files in {args.dir}")
        return 1
    posts, errors = validate(paths)
    if errors:
        print("INVALID — nothing written:")
        for e in errors:
            print("  " + e)
        return 1

    from app.blog import BlogPost
    from app.database import SessionLocal, set_tenant_context
    from app.main import Tenant

    inserted = skipped = 0
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
        if tenant is None:
            print(f"tenant {args.tenant!r} not found — nothing written")
            return 1
        set_tenant_context(db, tenant.id)
        existing = set(db.scalars(select(BlogPost.slug).where(BlogPost.tenant_id == tenant.id)).all())
        now = datetime.now(timezone.utc)
        for data in posts:
            if data.slug in existing:
                print(f"  SKIP   {data.slug} (already exists)")
                skipped += 1
                continue
            print(f"  INSERT {data.slug}")
            inserted += 1
            if args.apply:
                db.add(BlogPost(tenant_id=tenant.id, slug=data.slug, title=data.title, excerpt=data.excerpt, body=data.body, category=data.category,
                                tags_json=json.dumps(data.tags, ensure_ascii=False), cover=data.cover, cover_alt=data.cover_alt,
                                status="published", published_at=now))
                db.flush()
        if args.apply:
            db.commit()
    print(f"\n{'APPLIED' if args.apply else 'DRY-RUN (pass --apply)'}: tenant={args.tenant} {inserted} to insert, {skipped} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
