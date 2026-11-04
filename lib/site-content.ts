'use client';
/* Published site content (CMS slots). The built-in defaults below are what the site shows for any slot never
   published; an editor's published version replaces a slot as a whole. No price, rating or availability lives here. */
import { resolveApiBase } from './api/karenseir-client';
import {useEffect, useState} from 'react';

export type CmsCard = {title: string; title2?: string; meta?: string; href: string; image: string};
export type SiteContent = {
  announcement: {active: boolean; text: string; href: string};
  hero: {title: string; title2: string; subtitle: string; subtitle2: string; image: string; image_alt: string; minis: CmsCard[]};
  bento: {title: string; title2: string; tiles: CmsCard[]};
  trips: {title: string; items: CmsCard[]};
  assistant: {title: string; prompts: string[]};
  compare: {title: string; items: CmsCard[]};
  organization: {title: string; items: string[]};
  footer: {tagline: string; copyright: string};
};

const A = '/images/approved-figma/';
export const DEFAULT_CONTENT: SiteContent = {
  announcement: {active: false, text: '', href: ''},
  hero: {title: 'سفر را', title2: 'زندگی کن', subtitle: 'از اولین جست‌وجو تا آخرین خاطره،', subtitle2: 'همه‌چیز در کارن‌سیر کنار هم است.',
    image: A + 'refHeroTop.jpg', image_alt: 'مسافری که از زیر طاقی آجری به بام‌های شهر نگاه می‌کند',
    minis: [{title: 'شیراز', href: '/destinations/shiraz', image: A + 'imgThumb2.jpg'}, {title: 'کیش', href: '/destinations/kish', image: A + 'imgThumb3.jpg'}]},
  bento: {title: 'کجای ایران', title2: 'صدایت می‌زند؟', tiles: [
    {title: 'قشم', href: '/destinations/qeshm', image: A + 'tile-qeshm-cliffs.jpg'}, {title: 'شیراز', href: '/destinations/shiraz', image: A + 'tile-shiraz-garden.jpg'},
    {title: 'ماسوله', href: '/destinations/masuleh', image: A + 'imgTileMasuleh.jpg'}, {title: 'اصفهان', href: '/destinations/isfahan', image: A + 'imgTileIsfahan.jpg'}]},
  trips: {title: 'سفرهای انتخاب‌شده برای تو', items: [
    {href: '/destinations/masuleh', image: A + 'refTripNorth.jpg', title: 'مسیر سبز', title2: 'شمال', meta: '۳ روز و ۲ شب'},
    {href: '/destinations/qeshm', image: A + 'refTripQeshm.jpg', title: 'آرامش در', title2: 'جزیره قشم', meta: '۴ روز و ۳ شب'},
    {href: '/destinations/shiraz', image: A + 'refTripShiraz.jpg', title: 'سه روز در', title2: 'شیراز', meta: '۳ روز و ۲ شب'}]},
  assistant: {title: 'همراه هوشمند کارن‌سیر', prompts: ['با ۲۰ میلیون کجا برم؟', 'سفر خانوادگی ۴ روزه', 'بهترین مقصد پاییزی']},
  compare: {title: 'دو انتخاب داری؟ کنار هم ببین', items: [
    {title: 'هتل زندیه شیراز', image: A + 'imgThumb1.jpg', href: '/hotels/zandiyeh-hotel-w999233441'},
    {title: 'هتل عباسی اصفهان', image: A + 'imgThumb.jpg', href: '/hotels/abbasi-hotel-r4769549'}]},
  organization: {title: 'سفر سازمانی، بدون پیچیدگی', items: ['اعتبار کارکنان', 'تأیید مرحله‌ای', 'گزارش مالی']},
  footer: {tagline: 'سفر، قصه‌ی ماست. کارن‌سیر، همراه هر سفر توست.', copyright: '© کارن‌سیر. همهٔ حقوق محفوظ است.'},
};

export const tenantSlug = () => process.env.NEXT_PUBLIC_TENANT_SLUG || 'aftab-bank';
const apiBase = () => resolveApiBase(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000');

/** `media:<id>` → public media URL; site paths are returned as they are. */
export function imageSrc(ref: string): string {
  return ref.startsWith('media:') ? `${apiBase()}/public/tenants/${encodeURIComponent(tenantSlug())}/media/${ref.slice(6)}` : ref;
}

let cache: Partial<SiteContent> | null = null;
let pending: Promise<Partial<SiteContent>> | null = null;
const listeners = new Set<(c: Partial<SiteContent>) => void>();

function load(): Promise<Partial<SiteContent>> {
  if (cache) return Promise.resolve(cache);
  pending ??= fetch(`${apiBase()}/public/tenants/${encodeURIComponent(tenantSlug())}/site-content`)
    .then(r => (r.ok ? r.json() : {}))
    .catch(() => ({}))
    .then((c: Partial<SiteContent>) => {cache = c; listeners.forEach(fn => fn(c)); return c;});
  return pending;
}

/** Call after publishing so open pages show the new content without a reload. */
export function invalidateSiteContent() {cache = null; pending = null; void load();}

/** Published content merged over the defaults; renders the defaults first, then swaps in published slots. */
export function useSiteContent(): SiteContent {
  const [published, setPublished] = useState<Partial<SiteContent>>(cache ?? {});
  useEffect(() => {listeners.add(setPublished); void load().then(setPublished); return () => {listeners.delete(setPublished);};}, []);
  return {...DEFAULT_CONTENT, ...published} as SiteContent;
}
