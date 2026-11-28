import type { MetadataRoute } from 'next';
import { siteUrl } from '../lib/seo';
import { PUBLIC_PAGES } from '../lib/seo-pages';
export const dynamic = "force-dynamic";
// Catalogue pages come from the API; if it cannot be reached the fixed entries are still served.
async function blogPaths():Promise<string[]>{const api=process.env.API_INTERNAL_URL||process.env.NEXT_PUBLIC_API_URL;if(!api)return [];try{const res=await fetch(`${api.replace(/\/$/,'')}/public/tenants/${encodeURIComponent(process.env.NEXT_PUBLIC_TENANT_SLUG||'aftab-bank')}/blog-sitemap`,{signal:AbortSignal.timeout(8000),next:{revalidate:3600}});if(!res.ok)return [];const items=(await res.json()).items;return Array.isArray(items)?items.map((i:{path?:unknown})=>i.path).filter((p:unknown):p is string=>typeof p==='string'&&p.startsWith('/blog/')):[]}catch{return []}}
async function cataloguePaths():Promise<string[]>{const api=process.env.API_INTERNAL_URL||process.env.NEXT_PUBLIC_API_URL;if(!api)return [];try{const res=await fetch(`${api.replace(/\/$/,'')}/catalog/sitemap`,{signal:AbortSignal.timeout(8000),next:{revalidate:3600}});if(!res.ok)return [];const paths=(await res.json()).paths;return Array.isArray(paths)?paths.filter((p:unknown):p is string=>typeof p==='string'&&p.startsWith('/')):[]}catch{return []}}
// Only indexable public pages: every fixed entry has its own canonical and no noindex (tests/seo/seo-check.mjs checks this).
export default async function sitemap():Promise<MetadataRoute.Sitemap>{
  const base=siteUrl();const modified=new Date('2026-11-28T00:00:00Z');
  const fixed=PUBLIC_PAGES.filter(p=>!p.noindex).map(p=>({url:p.path==='/'?base:base+p.path,lastModified:modified,changeFrequency:p.changeFrequency,priority:p.priority}));
  const seen=new Set(PUBLIC_PAGES.map(p=>p.path));
  const dynamicPaths=[...await blogPaths(),...await cataloguePaths()].map(p=>p.split('?')[0].replace(/\/+$/,'')).filter(p=>p&&!seen.has(p)&&(seen.add(p),true));
  return [...fixed,...dynamicPaths.map(path=>({url:base+encodeURI(path),changeFrequency:'weekly' as const,priority:.6}))];
}
