'use client';
/* Browser fallback when the server could not reach the API while rendering a blog page. */
import {useEffect, useState} from 'react';
import {resolveApiBase} from '../../lib/api/karenseir-client';
import {blogTenant, type BlogList, type BlogPost} from '../../lib/blog';
import {BlogArticle, BlogListView} from './BlogViews';

function useBlog<T>(path: string) {
  const [s, setS] = useState<{kind: 'loading'} | {kind: 'ready'; data: T} | {kind: 'missing'} | {kind: 'error'}>({kind: 'loading'});
  useEffect(() => {
    let live = true;
    const base = resolveApiBase(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
    fetch(`${base}/public/tenants/${encodeURIComponent(blogTenant())}${path}`)
      .then(async r => {if (!live) return; if (r.status === 404) setS({kind: 'missing'}); else if (r.ok) setS({kind: 'ready', data: await r.json()}); else setS({kind: 'error'});})
      .catch(() => live && setS({kind: 'error'}));
    return () => {live = false;};
  }, [path]);
  return s;
}

export function BlogListClient({path, category, tag}: {path: string; category?: string; tag?: string}) {
  const s = useBlog<BlogList>(path);
  if (s.kind === 'ready') return <BlogListView data={s.data} category={category} tag={tag}/>;
  return <section className="container customer-page blog-page"><h1>راهنما و نکته‌های سفر</h1>
    <p role={s.kind === 'loading' ? 'status' : 'alert'}>{s.kind === 'loading' ? 'در حال دریافت مطالب…' : 'مطالب اکنون دریافت نشد؛ کمی بعد دوباره سر بزنید.'}</p></section>;
}

export function BlogPostClient({slug, site}: {slug: string; site: string}) {
  const s = useBlog<BlogPost>(`/blog/${encodeURIComponent(slug)}`);
  if (s.kind === 'ready') return <BlogArticle p={s.data} site={site}/>;
  return <section className="container customer-page blog-page">
    <p role={s.kind === 'loading' ? 'status' : 'alert'}>{s.kind === 'loading' ? 'در حال دریافت مطلب…' : s.kind === 'missing' ? 'این مطلب پیدا نشد یا دیگر منتشر نیست.' : 'مطلب اکنون دریافت نشد؛ کمی بعد دوباره سر بزنید.'}</p></section>;
}
