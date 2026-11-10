"""Blog (وبلاگ): travel guides and articles written by the tenant's editors.

Posts have a draft → published flow. Bodies are plain text with a tiny, safe subset of formatting (paragraphs,
"## " sub-headings and "- " bullet lines); no HTML is accepted or rendered, so nothing an editor types can run as
script. Like the rest of the site content, a post cannot carry prices or discount figures: those come only from real
offers. Cover images reuse the site media library (``media:<id>``) or a built-in site image.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin
from .site_cms import PRICE_WORDS, SiteMediaAsset

CATEGORIES = {
    "guide": "راهنمای مقصد",
    "places": "جاهای دیدنی",
    "events": "رویدادها و فستیوال‌ها",
    "tips": "نکته‌های سفر",
    "visa": "ویزا و مدارک",
    "news": "اخبار کارن تراول",
}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IMAGE = r"^(/images/[A-Za-z0-9_./-]+|media:[0-9a-f-]{36})$"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BlogPost(OperationalMixin, Base):
    __tablename__ = "blog_posts"
    slug: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(160))
    excerpt: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(24), default="guide", index=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    cover: Mapped[str] = mapped_column(String(200), default="")
    cover_alt: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)  # draft | published
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_blog_post_slug"),)


class PostIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    slug: str = Field(min_length=3, max_length=120)
    title: str = Field(min_length=3, max_length=160)
    excerpt: str = Field(default="", max_length=300)
    body: str = Field(min_length=20, max_length=40000)
    category: str = "guide"
    tags: list[str] = Field(default_factory=list, max_length=8)
    cover: str = Field(default="", max_length=200)
    cover_alt: str = Field(default="", max_length=160)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.lower()
        if not SLUG.fullmatch(v):
            raise ValueError("نامک فقط حروف کوچک لاتین، عدد و خط تیره (مثل shiraz-travel-guide)")
        return v

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError("دسته‌ی مطلب نامعتبر است")
        return v

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            t = " ".join(t.split())
            if t and len(t) <= 30 and t not in out:
                out.append(t)
        return out

    @field_validator("cover")
    @classmethod
    def _cover(cls, v: str) -> str:
        if v and not re.fullmatch(IMAGE, v):
            raise ValueError("تصویر شاخص باید از کتابخانه‌ی رسانه انتخاب شود")
        return v

    @field_validator("body")
    @classmethod
    def _body(cls, v: str) -> str:
        if re.search(r"<\s*/?\s*[a-zA-Z]", v):
            raise ValueError("متن مطلب نباید برچسب HTML داشته باشد")
        return v.replace("\r\n", "\n")


def _no_prices(p: PostIn) -> None:
    text = " ".join([p.title, p.excerpt, p.body, *p.tags])
    for line in text.split("\n"):
        if any(ch.isdigit() for ch in line) and any(w in line for w in PRICE_WORDS):
            raise HTTPException(status_code=422, detail="قیمت و درصد تخفیف در مطلب وبلاگ ثبت نمی‌شود؛ قیمت فقط از نتیجه‌ی استعلام نمایش داده می‌شود")


def _summary(p: BlogPost) -> dict:
    return {"id": p.id, "slug": p.slug, "title": p.title, "excerpt": p.excerpt, "category": p.category, "category_label": CATEGORIES.get(p.category, ""),
            "tags": json.loads(p.tags_json or "[]"), "cover": p.cover, "cover_alt": p.cover_alt, "status": p.status,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
            "reading_minutes": max(1, round(len(p.body.split()) / 200))}


def _full(p: BlogPost) -> dict:
    return _summary(p) | {"body": p.body}


def blog_router(get_db, current_user, role_has_permission, public_tenant: Callable, audit: Optional[Callable] = None) -> APIRouter:
    api = APIRouter(tags=["blog"])

    def editor(user=Depends(current_user)):
        if user.role not in ("platform_admin", "tenant_admin", "backoffice_expert") and not role_has_permission(user.role, "tenant:manage"):
            raise HTTPException(status_code=403, detail="نوشتن و انتشار مطلب وبلاگ فقط برای مدیران مجموعه است")
        return user

    def _get(db: Session, tenant_id: int, post_id: str) -> BlogPost:
        p = db.scalar(select(BlogPost).where(BlogPost.id == post_id, BlogPost.tenant_id == tenant_id))
        if p is None:
            raise HTTPException(status_code=404, detail="مطلب یافت نشد")
        return p

    def _apply(db: Session, user, p: BlogPost, data: PostIn) -> None:
        _no_prices(data)
        if data.cover.startswith("media:"):
            found = db.scalar(select(SiteMediaAsset.id).where(SiteMediaAsset.tenant_id == user.tenant_id, SiteMediaAsset.id == data.cover[6:]))
            if found is None:
                raise HTTPException(status_code=422, detail="تصویر انتخاب‌شده در کتابخانه‌ی رسانه پیدا نشد")
        clash = db.scalar(select(BlogPost.id).where(BlogPost.tenant_id == user.tenant_id, BlogPost.slug == data.slug, BlogPost.id != (p.id or "")))
        if clash:
            raise HTTPException(status_code=409, detail="مطلب دیگری با این نامک وجود دارد")
        p.slug, p.title, p.excerpt, p.body, p.category = data.slug, data.title, data.excerpt, data.body, data.category
        p.tags_json, p.cover, p.cover_alt, p.updated_by = json.dumps(data.tags, ensure_ascii=False), data.cover, data.cover_alt, user.id

    @api.get("/blog/meta")
    def meta(user=Depends(editor)):
        return {"categories": [{"key": k, "label": v} for k, v in CATEGORIES.items()]}

    @api.get("/blog/posts")
    def list_posts(user=Depends(editor), db: Session = Depends(get_db)):
        rows = db.scalars(select(BlogPost).where(BlogPost.tenant_id == user.tenant_id).order_by(BlogPost.created_at.desc()).limit(500)).all()
        return {"items": [_summary(p) for p in rows]}

    @api.get("/blog/posts/{post_id}")
    def get_post(post_id: str, user=Depends(editor), db: Session = Depends(get_db)):
        return _full(_get(db, user.tenant_id, post_id))

    @api.post("/blog/posts", status_code=201)
    def create(data: PostIn, user=Depends(editor), db: Session = Depends(get_db)):
        p = BlogPost(tenant_id=user.tenant_id, status="draft", author_id=user.id)
        _apply(db, user, p, data)
        db.add(p)
        if audit:
            audit(db, user, "blog.created", "blog_post", {"slug": data.slug})
        db.commit()
        return _full(p)

    @api.put("/blog/posts/{post_id}")
    def update(post_id: str, data: PostIn, user=Depends(editor), db: Session = Depends(get_db)):
        p = _get(db, user.tenant_id, post_id)
        _apply(db, user, p, data)
        if audit:
            audit(db, user, "blog.updated", "blog_post", {"slug": data.slug})
        db.commit()
        return _full(p)

    @api.post("/blog/posts/{post_id}/publish")
    def publish(post_id: str, user=Depends(editor), db: Session = Depends(get_db)):
        p = _get(db, user.tenant_id, post_id)
        _no_prices(PostIn(slug=p.slug, title=p.title, excerpt=p.excerpt, body=p.body, category=p.category, tags=json.loads(p.tags_json or "[]"), cover=p.cover, cover_alt=p.cover_alt))
        p.status = "published"
        p.published_at = p.published_at or utcnow()
        if audit:
            audit(db, user, "blog.published", "blog_post", {"slug": p.slug})
        db.commit()
        return _full(p)

    @api.post("/blog/posts/{post_id}/unpublish")
    def unpublish(post_id: str, user=Depends(editor), db: Session = Depends(get_db)):
        p = _get(db, user.tenant_id, post_id)
        p.status = "draft"
        if audit:
            audit(db, user, "blog.unpublished", "blog_post", {"slug": p.slug})
        db.commit()
        return _full(p)

    # ---- public ----
    @api.get("/public/tenants/{tenant_slug}/blog")
    def public_list(tenant_slug: str, response: Response, category: Optional[str] = None, tag: Optional[str] = Query(default=None, max_length=30),
                    page: int = Query(default=1, ge=1, le=200), db: Session = Depends(get_db)):
        tenant = public_tenant(db, tenant_slug)
        q = select(BlogPost).where(BlogPost.tenant_id == tenant.id, BlogPost.status == "published")
        if category:
            if category not in CATEGORIES:
                raise HTTPException(status_code=404, detail="این دسته وجود ندارد")
            q = q.where(BlogPost.category == category)
        rows = db.scalars(q.order_by(BlogPost.published_at.desc(), BlogPost.id)).all()
        if tag:
            rows = [p for p in rows if tag in json.loads(p.tags_json or "[]")]
        size = 12
        total = len(rows)
        response.headers["Cache-Control"] = "public, max-age=60"
        return {"items": [_summary(p) for p in rows[(page - 1) * size: page * size]], "total": total, "page": page, "pages": max(1, -(-total // size)),
                "categories": [{"key": k, "label": v} for k, v in CATEGORIES.items()]}

    @api.get("/public/tenants/{tenant_slug}/blog/{slug}")
    def public_post(tenant_slug: str, slug: str, response: Response, db: Session = Depends(get_db)):
        tenant = public_tenant(db, tenant_slug)
        p = db.scalar(select(BlogPost).where(BlogPost.tenant_id == tenant.id, BlogPost.slug == slug.lower(), BlogPost.status == "published"))
        if p is None:
            raise HTTPException(status_code=404, detail="مطلب یافت نشد")
        related = db.scalars(select(BlogPost).where(BlogPost.tenant_id == tenant.id, BlogPost.status == "published", BlogPost.category == p.category, BlogPost.id != p.id)
                             .order_by(BlogPost.published_at.desc()).limit(3)).all()
        response.headers["Cache-Control"] = "public, max-age=60"
        return _full(p) | {"related": [_summary(r) for r in related]}

    @api.get("/public/tenants/{tenant_slug}/blog-sitemap")
    def public_sitemap(tenant_slug: str, db: Session = Depends(get_db)):
        tenant = public_tenant(db, tenant_slug)
        rows = db.execute(select(BlogPost.slug, func.coalesce(BlogPost.updated_at, BlogPost.published_at)).where(BlogPost.tenant_id == tenant.id, BlogPost.status == "published")).all()
        return {"items": [{"path": f"/blog/{s}", "modified": m.isoformat() if m else None} for s, m in rows]}

    return api


__all__ = ["blog_router", "BlogPost", "CATEGORIES"]
