/* Blog presentation, shared by the server pages and the browser fallback. Text is rendered as text only. */
import Link from 'next/link';
import {blogImage, faDate, parseBody, type BlogList, type BlogPost, type BlogSummary} from '../../lib/blog';

const fa = (n: number) => n.toLocaleString('fa-IR');

export function BlogCard({p}: {p: BlogSummary}) {
  return <Link className="blog-card" href={`/blog/${p.slug}`}>
    {p.cover && <>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={blogImage(p.cover)} alt={p.cover_alt || ''} loading="lazy"/></>}
    <div><span className="blog-cat">{p.category_label}</span><h2>{p.title}</h2>{p.excerpt && <p>{p.excerpt}</p>}
      <small>{faDate(p.published_at)} · {fa(p.reading_minutes)} دقیقه مطالعه</small></div>
  </Link>;
}

export function BlogListView({data, category, tag}: {data: BlogList; category?: string; tag?: string}) {
  const q = (page: number) => '/blog?' + new URLSearchParams({...(category ? {category} : {}), ...(tag ? {tag} : {}), ...(page > 1 ? {page: String(page)} : {})}).toString();
  return <section className="container customer-page blog-page">
    <span className="eyebrow">مجله‌ی سفر کارن تراول</span>
    <h1>{tag ? `مطالب «${tag}»` : 'راهنما و نکته‌های سفر'}</h1>
    <p>راهنمای مقصدها، نکته‌های سفر، ویزا و مدارک، و خبرهای کارن تراول.</p>
    <nav className="tour-collection-nav" aria-label="دسته‌های وبلاگ">
      <Link href="/blog" aria-current={!category && !tag ? 'page' : undefined}>همه</Link>
      {data.categories.map(c => <Link key={c.key} href={`/blog?category=${c.key}`} aria-current={category === c.key ? 'page' : undefined}>{c.label}</Link>)}
    </nav>
    {data.items.length ? <div className="blog-grid">{data.items.map(p => <BlogCard key={p.id} p={p}/>)}</div>
      : <p className="blog-empty" role="status">هنوز مطلبی در این بخش منتشر نشده است.</p>}
    {data.pages > 1 && <nav className="blog-pages" aria-label="صفحه‌ها">
      {data.page > 1 && <Link href={q(data.page - 1)}>صفحه‌ی قبل</Link>}
      <span>صفحه‌ی {fa(data.page)} از {fa(data.pages)}</span>
      {data.page < data.pages && <Link href={q(data.page + 1)}>صفحه‌ی بعد</Link>}
    </nav>}
  </section>;
}

export function BlogArticle({p, site}: {p: BlogPost; site: string}) {
  const ld = {'@context': 'https://schema.org', '@type': 'BlogPosting', headline: p.title, description: p.excerpt || undefined,
    datePublished: p.published_at, dateModified: p.updated_at || p.published_at, image: p.cover ? [p.cover.startsWith('/') ? site + p.cover : blogImage(p.cover)] : undefined,
    mainEntityOfPage: `${site}/blog/${p.slug}`, publisher: {'@type': 'Organization', name: 'کارن تراول'}, inLanguage: 'fa-IR'};
  return <article className="container customer-page blog-article">
    <nav className="blog-crumbs" aria-label="مسیر"><Link href="/">کارن تراول</Link> / <Link href="/blog">وبلاگ</Link> / <Link href={`/blog?category=${p.category}`}>{p.category_label}</Link></nav>
    <h1>{p.title}</h1>
    <p className="blog-meta">{faDate(p.published_at)} · {fa(p.reading_minutes)} دقیقه مطالعه</p>
    {p.cover && <>{/* eslint-disable-next-line @next/next/no-img-element */}<img className="blog-cover" src={blogImage(p.cover)} alt={p.cover_alt || ''}/></>}
    {p.excerpt && <p className="blog-lead">{p.excerpt}</p>}
    <div className="blog-body">{parseBody(p.body).map((b, i) => b.kind === 'h' ? <h2 key={i}>{b.text}</h2>
      : b.kind === 'ul' ? <ul key={i}>{b.items!.map((x, j) => <li key={j}>{x}</li>)}</ul> : <p key={i}>{b.text}</p>)}</div>
    {p.tags.length > 0 && <p className="blog-tags">{p.tags.map(t => <Link key={t} href={`/blog?tag=${encodeURIComponent(t)}`}>#{t}</Link>)}</p>}
    <aside className="blog-cta panel"><b>برای این سفر کمک می‌خواهید؟</b><p>مقصد و زمان سفرتان را بگویید تا کارشناسان کارن تراول گزینه‌های موجود را پیشنهاد دهند.</p>
      <Link className="button primary" href="/tours">دیدن تورها</Link> <Link className="button secondary" href="/support">مشاوره‌ی سفر</Link></aside>
    {p.related.length > 0 && <section className="blog-related"><h2>مطالب مرتبط</h2><div className="blog-grid">{p.related.map(r => <BlogCard key={r.id} p={r}/>)}</div></section>}
    <script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(ld).replace(/</g, '\\u003c')}}/>
  </article>;
}
