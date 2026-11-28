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
  // Built-in answers describe only what the site really does (reviewed 2026-11-28: request-to-book flights, SMS one-time code
  // sign-in, installment partners, Tazheban licences). A FAQ published in /admin/content replaces this list.
  faq: {title: 'پرسش‌های متداول', intro: 'پاسخ پرسش‌های رایج دربارهٔ رزرو بلیت هواپیما، هتل و تور، ورود به حساب، پرداخت اقساطی و استرداد در کارن تراول.', items: [
    {question: 'بلیت هواپیما را چطور از کارن تراول بگیرم؟', answer: 'در صفحهٔ «بلیت هواپیما» مبدأ، مقصد، تاریخ و تعداد مسافران را وارد کنید. کنار هر پرواز دکمهٔ «درخواست رزرو» هست؛ آن را بزنید و فرم کوتاه را پر کنید. کارشناس کارن تراول با شما تماس می‌گیرد، ظرفیت و مبلغ نهایی را تأیید می‌کند و پس از پرداخت، بلیت صادر می‌شود.'},
    {question: 'چرا خرید پرواز آنلاین نیست و «درخواست رزرو» است؟', answer: 'پروازهای داخلی هواپیمایی‌هایی مانند وارش و یزد از طریق سامانهٔ نیرا نمایش داده می‌شوند و در حال حاضر صدور بلیت پس از تأیید کارشناس انجام می‌شود. به همین دلیل ثبت درخواست به‌تنهایی رزرو قطعی نیست؛ رزرو پس از تماس کارشناس، پرداخت و صدور بلیت قطعی می‌شود.'},
    {question: 'قیمتی که کنار پرواز می‌بینم قیمت نهایی است؟', answer: 'قیمت کنار پرواز تقریبی است. مبلغ نهایی را کارشناس هنگام تماس و پیش از پرداخت اعلام می‌کند. سقف قیمت بلیت در کارن تراول نرخ مصوب سازمان هواپیمایی کشوری است و بلیتی بالاتر از این نرخ فروخته نمی‌شود.'},
    {question: 'بعد از ثبت درخواست چه اتفاقی می‌افتد؟', answer: 'درخواست شما برای کارشناسان کارن تراول ثبت می‌شود و کارشناس با شمارهٔ همراهی که وارد کرده‌اید تماس می‌گیرد. اگر گزینهٔ انتخابی ظرفیت نداشت، پرواز یا گزینهٔ جایگزین پیشنهاد می‌شود. برای پیگیری می‌توانید با شمارهٔ پشتیبانی هم تماس بگیرید.'},
    {question: 'چطور وارد حساب کاربری شوم؟', answer: 'روی «ورود» بزنید و شمارهٔ همراه خود را وارد کنید. یک کد یک‌بارمصرف پیامک می‌شود که با وارد کردن آن وارد حساب می‌شوید؛ رمز عبور لازم نیست. این کد را به هیچ‌کس، حتی پشتیبانی، ندهید.'},
    {question: 'رزرو هتل و تور هم دارید؟', answer: 'بله. در صفحه‌های «هتل» و «تور» گزینه‌های موجود را ببینید. هر جا رزرو آنلاین فعال نبود یا گزینهٔ دلخواه را پیدا نکردید، فرم درخواست سفر را پر کنید تا کارشناس گزینه‌ها و شرایط را اعلام کند.'},
    {question: 'تور اقساطی چطور کار می‌کند؟', answer: 'تورهای قابل خرید اقساطی را می‌توانید با سرویس‌های اقساطی همکار مانند نوپی (بانک ملی)، وامی‌پی و دیباکارت بخرید. اعتبارسنجی، پیش‌پرداخت و تعداد اقساط را همان سرویس تعیین می‌کند. کارکنان سازمان‌های طرف قرارداد ممکن است اقساط سازمانی هم داشته باشند. جزئیات در صفحهٔ «تور اقساطی» آمده است.'},
    {question: 'شرایط استرداد بلیت هواپیما چیست؟', answer: 'جریمهٔ استرداد بلیت پرواز سیستمی داخلی طبق دستورالعمل سازمان هواپیمایی کشوری و کلاس نرخی ایرلاین محاسبه می‌شود و هرچه به زمان پرواز نزدیک‌تر شوید بیشتر است. پرواز چارتری طبق شرایط عرضه‌کنندهٔ همان پرواز است. جزئیات در صفحهٔ «قوانین استرداد و کنسلی» آمده است؛ برای درخواست استرداد با پشتیبانی تماس بگیرید.'},
    {question: 'سازمان ما چطور می‌تواند برای کارکنانش سفر رزرو کند؟', answer: 'کارن تراول خدمات سفر سازمانی و رفاهی کارکنان را برای سازمان‌های طرف قرارداد ارائه می‌دهد. قرارداد با «تاژبان گشت پارس»، دارندهٔ مجوزهای کارن تراول، امضا می‌شود. برای شروع از صفحهٔ «راهکارهای سازمانی» درخواست همکاری بدهید یا با پشتیبانی تماس بگیرید.'},
    {question: 'کارن تراول مجوز دارد؟', answer: 'کارن تراول زیر مجوزهای «تاژبان گشت پارس» فعالیت می‌کند: مجوز بند الف، مجوز بند ب، مجوز فروش آنلاین و مجوز وزارت میراث فرهنگی، گردشگری و صنایع دستی. تاژبان گشت پارس بیش از ۱۵ سال سابقه در خدمات مسافرتی دارد.'},
    {question: 'چطور با پشتیبانی تماس بگیرم؟', answer: 'شمارهٔ پشتیبانی در بالای سایت و پایین همهٔ صفحه‌ها آمده است. می‌توانید فرم درخواست سفر را در صفحهٔ «تماس با ما» هم پر کنید تا کارشناس با شما تماس بگیرد.'},
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
