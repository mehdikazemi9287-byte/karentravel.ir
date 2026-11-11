import type {Metadata} from 'next';
import {notFound} from 'next/navigation';
import {Shell} from '../../page';
import {BlogArticle} from '../../../components/blog/BlogViews';
import {BlogPostClient} from '../../../components/blog/BlogClient';
import {blogImage, serverBlog, type BlogPost} from '../../../lib/blog';

export const dynamic = 'force-dynamic';
const site = () => (process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000').replace(/\/$/, '');
const clean = (s: string) => (/^[a-z0-9-]{3,120}$/.test(s) ? s : '');

export async function generateMetadata({params}: {params: Promise<{slug: string}>}): Promise<Metadata> {
  const slug = clean((await params).slug);
  const p = slug ? await serverBlog<BlogPost>(`/blog/${slug}`) : null;
  if (!p) return {title: 'وبلاگ کارن تراول'};
  const image = p.cover ? (p.cover.startsWith('/') ? site() + p.cover : blogImage(p.cover)) : undefined;
  return {title: p.title, description: p.excerpt || undefined, alternates: {canonical: `/blog/${p.slug}`},
    openGraph: {type: 'article', title: p.title, description: p.excerpt || undefined, publishedTime: p.published_at ?? undefined, images: image ? [image] : undefined, locale: 'fa_IR'}};
}

export default async function Page({params}: {params: Promise<{slug: string}>}) {
  const slug = clean((await params).slug);
  if (!slug) notFound();
  const p = await serverBlog<BlogPost>(`/blog/${slug}`);
  if (p === null) notFound();
  return <Shell>{p ? <BlogArticle p={p} site={site()}/> : <BlogPostClient slug={slug} site={site()}/>}</Shell>;
}
