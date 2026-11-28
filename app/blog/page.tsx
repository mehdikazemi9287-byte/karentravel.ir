import type {Metadata} from 'next';
import {Shell} from '../root-pages';
import {BlogListView} from '../../components/blog/BlogViews';
import {BlogListClient} from '../../components/blog/BlogClient';
import {serverBlog, type BlogList} from '../../lib/blog';
import {seoFor} from '../../lib/seo-pages';

export const dynamic = 'force-dynamic';
export const metadata = seoFor('/blog');

export default async function Page({searchParams}: {searchParams: Promise<{category?: string; tag?: string; page?: string}>}) {
  const sp = await searchParams;
  const category = sp.category && /^[a-z]{2,24}$/.test(sp.category) ? sp.category : undefined;
  const tag = sp.tag ? sp.tag.slice(0, 30) : undefined;
  const page = Math.max(1, Math.min(200, Number(sp.page) || 1));
  const path = '/blog?' + new URLSearchParams({...(category ? {category} : {}), ...(tag ? {tag} : {}), page: String(page)}).toString();
  const data = await serverBlog<BlogList>(path);
  return <Shell>{data ? <BlogListView data={data} category={category} tag={tag}/> : <BlogListClient path={path} category={category} tag={tag}/>}</Shell>;
}
