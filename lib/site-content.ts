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
  faq: {title: string; intro: string; items: {question: string; answer: string}[]};
  special_tours: {title: string; intro: string; tour_ids: string[]};
  festival: {active: boolean; title: string; intro: string; starts_on: string; ends_on: string; image: string; tour_ids: string[]; terms: string};
  installment: {intro: string; nopay: boolean; vamipay: boolean; dibacard: boolean; organization: boolean; tour_ids: string[]};
};

const A = '/images/approved-figma/';
export const DEFAULT_CONTENT: SiteContent = {
  announcement: {active: false, text: '', href: ''},
  hero: {title: 'سفر را', title2: 'زندگی کن', subtitle: 'از اولین جست‌وجو تا آخرین خاطره،', subtitle2: 'همه‌چیز در کارن تراول کنار هم است.',
    image: A + 'refHeroTop.jpg', image_alt: 'مسافری که از زیر طاقی آجری به بام‌های شهر نگاه می‌کند',
    minis: [{title: 'شیراز', href: '/destinations/shiraz', image: A + 'imgThumb2.jpg'}, {title: 'کیش', href: '/destinations/kish', image: A + 'imgThumb3.jpg'}]},
  bento: {title: 'کجای ایران', title2: 'صدایت می‌زند؟', tiles: [
    {title: 'قشم', href: '/destinations/qeshm', image: A + 'tile-qeshm-cliffs.jpg'}, {title: 'شیراز', href: '/destinations/shiraz', image: A + 'tile-shiraz-garden.jpg'},
    {title: 'ماسوله', href: '/destinations/masuleh', image: A + 'imgTileMasuleh.jpg'}, {title: 'اصفهان', href: '/destinations/isfahan', image: A + 'imgTileIsfahan.jpg'}]},
  trips: {title: 'سفرهای انتخاب‌شده برای تو', items: [
    {href: '/destinations/masuleh', image: A + 'refTripNorth.jpg', title: 'مسیر سبز', title2: 'شمال', meta: '۳ روز و ۲ شب'},
    {href: '/destinations/qeshm', image: A + 'refTripQeshm.jpg', title: 'آرامش در', title2: 'جزیره قشم', meta: '۴ روز و ۳ شب'},
    {href: '/destinations/shiraz', image: A + 'refTripShiraz.jpg', title: 'سه روز در', title2: 'شیراز', meta: '۳ روز و ۲ شب'}]},
  assistant: {title: 'همراه هوشمند کارن تراول', prompts: ['با ۲۰ میلیون کجا برم؟', 'سفر خانوادگی ۴ روزه', 'بهترین مقصد پاییزی']},
  compare: {title: 'دو انتخاب داری؟ کنار هم ببین', items: [
    {title: 'هتل زندیه شیراز', image: A + 'imgThumb1.jpg', href: '/hotels/zandiyeh-hotel-w999233441'},
    {title: 'هتل عباسی اصفهان', image: A + 'imgThumb.jpg', href: '/hotels/abbasi-hotel-r4769549'}]},
  organization: {title: 'سفر سازمانی، بدون پیچیدگی', items: ['اعتبار کارکنان', 'تأیید مرحله‌ای', 'گزارش مالی']},
  footer: {tagline: 'سفر، قصه‌ی ماست. کارن تراول، همراه هر سفر توست.', copyright: '© کارن تراول. همهٔ حقوق محفوظ است.'},
  // Built-in answers describe only what the site really does; business rules (refund rates, deadlines) are added by the team in /admin/content.
  faq: {title: 'سؤالات متداول', intro: 'پاسخ پرسش‌های رایج درباره‌ی خرید، پرداخت و پیگیری سفر در کارن تراول.', items: [
    {question: 'چطور بلیت، هتل یا تور رزرو کنم؟', answer: 'از صفحه‌ی اصلی نوع سفر را انتخاب کنید، مبدأ، مقصد، تاریخ و تعداد مسافران را وارد کنید و از میان نتیجه‌ها گزینه‌ی دلخواه را بردارید. قیمت و ظرفیت هر گزینه پیش از پرداخت دوباره از تأمین‌کننده استعلام می‌شود.'},
    {question: 'اگر نتیجه‌ای برای سفرم پیدا نشد چه کنم؟', answer: 'در همان صفحه‌ی نتیجه، فرم «درخواست سفر» را پر کنید. کارشناسان کارن تراول با شما تماس می‌گیرند و گزینه‌های موجود را پیشنهاد می‌دهند.'},
    {question: 'قیمت نهایی چه زمانی مشخص می‌شود؟', answer: 'قیمت هر بلیت، اتاق یا تور در لحظه‌ی خرید از تأمین‌کننده گرفته می‌شود و پیش از پرداخت به شما نمایش داده می‌شود. کارن تراول قیمت نمونه یا تخمینی نشان نمی‌دهد.'},
    {question: 'بلیت و واچر خود را کجا ببینم؟', answer: 'پس از ورود به حساب کاربری، در بخش «سفرهای من» همه‌ی خریدها، وضعیت صدور و واچر (همراه با کد QR) در دسترس است.'},
    {question: 'شرایط لغو و استرداد چیست؟', answer: 'شرایط لغو به نوع خدمت و قوانین تأمین‌کننده (ایرلاین، هتل یا برگزارکننده‌ی تور) بستگی دارد پیش از پرداخت می‌توانید آن را از پشتیبانی بپرسید. برای درخواست لغو از «سفرهای من» یا پشتیبانی اقدام کنید.'},
    {question: 'برای سفر خارجی ویزا هم می‌گیرید؟', answer: 'در صفحه‌ی «ویزا و مدارک سفر» کشور مقصد و تاریخ سفر را ثبت کنید تا کارشناس مدارک لازم و روند کار را به شما اعلام کند.'},
    {question: 'سازمان ما چطور می‌تواند برای کارکنانش سفر بخرد؟', answer: 'کارن تراول برای سازمان‌ها اعتبار کارکنان، تأیید مرحله‌ای و گزارش مالی دارد. از صفحه‌ی «سفر سازمانی» درخواست همکاری بدهید.'},
    {question: 'چطور با پشتیبانی تماس بگیرم؟', answer: 'از صفحه‌ی پشتیبانی پیام بفرستید یا با شماره‌ی پشتیبانی که پایین همه‌ی صفحه‌ها آمده تماس بگیرید. پیگیری درخواست‌ها در حساب کاربری شما ثبت می‌شود.'},
  ]},
  special_tours: {title: 'تورهای ویژه', intro: 'تورهایی که کارشناسان کارن تراول برای این فصل انتخاب کرده‌اند.', tour_ids: []},
  festival: {active: false, title: 'جشنواره‌ی سفر کارن تراول', intro: '', starts_on: '', ends_on: '', image: '', tour_ids: [], terms: ''},
  installment: {intro: '', nopay: true, vamipay: true, dibacard: true, organization: true, tour_ids: []},
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
