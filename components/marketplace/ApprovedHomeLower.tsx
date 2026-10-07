'use client';
/* Lower half of the approved homepage and the shared footer, laid out after the approved reference render.
   Presentation only: no price, rating or availability is shown here; those come from real offers elsewhere. */
import Link from 'next/link';
import type {ReactNode} from 'react';
import {supportPhone} from '../../lib/site-contact';

const A = '/images/approved-figma/';
const TRIPS = [
  {href: '/destinations/masuleh', img: A + 'refTripNorth.jpg', title: ['مسیر سبز', 'شمال'], nights: '۳ روز و ۲ شب'},
  {href: '/destinations/qeshm', img: A + 'refTripQeshm.jpg', title: ['آرامش در', 'جزیره قشم'], nights: '۴ روز و ۳ شب'},
  {href: '/destinations/shiraz', img: A + 'refTripShiraz.jpg', title: ['سه روز در', 'شیراز'], nights: '۳ روز و ۲ شب'},
];
const PROMPTS = ['با ۲۰ میلیون کجا برم؟', 'سفر خانوادگی ۴ روزه', 'بهترین مقصد پاییزی'];
const svg = (children: ReactNode, size = 44) => <svg width={size} height={size} viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;
const SERVICES: {href: string; label: string; icon: ReactNode}[] = [
  {href: '/services', label: 'خدمات سفر', icon: svg(<><rect x="9" y="15" width="24" height="24" rx="3"/><path d="M16 15v-4a3 3 0 0 1 3-3h4a3 3 0 0 1 3 3v4M9 24h24M33 20h4a3 3 0 0 1 3 3v13a3 3 0 0 1-3 3h-4"/></>)},
  {href: '/tours', label: 'تور', icon: svg(<><rect x="7" y="14" width="34" height="24" rx="4"/><circle cx="24" cy="26" r="7"/><path d="M17 14l2-4h10l2 4M35 20h1"/></>)},
  {href: '/trains', label: 'قطار', icon: svg(<><rect x="11" y="7" width="26" height="28" rx="6"/><path d="M11 22h26M17 13h14M16 41l3-6M32 41l-3-6M13 41h22"/><circle cx="18" cy="28" r="1.4"/><circle cx="30" cy="28" r="1.4"/></>)},
  {href: '/hotels', label: 'اقامت', icon: svg(<><path d="M10 41V12l14-5 14 5v29M6 41h36"/><path d="M17 17h3M28 17h3M17 24h3M28 24h3M17 31h3M28 31h3M22 41v-5h4v5"/></>)},
  {href: '/flights', label: 'پرواز', icon: svg(<><path d="M5 30l36-13a3.4 3.4 0 0 0-2.3-6.4L28 14.5 14 9l-4 1.6 9.5 7.7-8 3-4.5-2-2.5 1 4.5 6.5z"/><path d="M12 39h26"/></>)},
];
const Moon = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>;
const Arrow = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>;

export function ApprovedHomeLower() {
  return <div className="kh">
    <section className="kh-sec" aria-labelledby="kh-trips-title">
      <h2 id="kh-trips-title" className="kh-h2">سفرهای انتخاب‌شده برای تو</h2>
      <div className="kh-trips">{TRIPS.map(t => <Link key={t.href} href={t.href} className="kh-trip">
        <div className="kh-trip-body"><h3>{t.title[0]}<br/>{t.title[1]}</h3><p className="kh-trip-meta"><Moon/>{t.nights}</p><p className="kh-trip-price">استعلام قیمت</p><span className="kh-trip-go"><Arrow/></span></div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={t.img} alt="" loading="lazy"/>
      </Link>)}</div>
    </section>
    <section className="kh-sec" aria-labelledby="kh-ai-title">
      <div className="kh-ai">
        <svg className="kh-ai-path" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden="true"><path d="M20 90C180 10 320 110 480 50s300-60 440 10 180 30 240-20" fill="none" stroke="#fff" strokeWidth="2" strokeDasharray="7 9"/></svg>
        <h2 id="kh-ai-title">همراه هوشمند کارن‌سیر</h2>
        <Link href="/assistant" className="kh-ai-cta"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z"/></svg>شروع گفتگو</Link>
        <div className="kh-ai-chips">{PROMPTS.map(p => <Link key={p} href={`/assistant?q=${encodeURIComponent(p)}`}>{p}</Link>)}</div>
      </div>
    </section>
    <section className="kh-sec" aria-labelledby="kh-cmp-title">
      <div className="kh-cmp">
        <h2 id="kh-cmp-title">دو انتخاب داری؟ کنار هم ببین</h2>
        {[{name: 'هتل زندیه شیراز', img: A + 'imgThumb1.jpg'}, {name: 'هتل عباسی اصفهان', img: A + 'imgThumb.jpg'}].map(h => <div key={h.name} className="kh-cmp-hotel">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={h.img} alt="" loading="lazy"/><div><b>{h.name}</b><span>قیمت پس از استعلام</span></div></div>)}
        <Link href="/compare" className="kh-cmp-cta"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 4v16M6 20h12M5 8h14M5 8l-3 7a3 3 0 0 0 6 0zM19 8l-3 7a3 3 0 0 0 6 0z"/></svg>مقایسه کن</Link>
      </div>
    </section>
    <section className="kh-sec" aria-labelledby="kh-org-title">
      <div className="kh-org">
        <div className="kh-org-text">
          <h2 id="kh-org-title">سفر سازمانی، بدون پیچیدگی</h2>
          <ul>{[['اعتبار کارکنان', 'imgIconStaff.svg'], ['تأیید مرحله‌ای', 'imgIconCheck1.svg'], ['گزارش مالی', 'imgIconChart.svg']].map(([label, icon]) => <li key={label}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={A + icon} alt=""/>{label}</li>)}</ul>
          <Link href="/organization" className="kh-org-cta">راهکارهای سازمانی<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></Link>
        </div>
        <div className="kh-org-art" aria-hidden="true">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={A + 'refOrgDevices.jpg'} alt=""/>
        </div>
      </div>
    </section>
    <nav className="kh-strip" aria-label="خدمات کارن‌سیر">{SERVICES.map(s => <Link key={s.href} href={s.href}>{s.icon}<span>{s.label}</span></Link>)}</nav>
  </div>;
}

export function ApprovedFooterLight() {
  return <div className="kh kh-foot" role="contentinfo">
    <div className="kh-foot-grid">
      <div className="kh-foot-brand">
        <Link href="/" className="kh-foot-logo" aria-label="کارن‌سیر، صفحه اصلی">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={A + 'imgComponentLogoMark.svg'} alt=""/>کارن‌سیر</Link>
        <p>سفر، قصه‌ی ماست. کارن‌سیر، همراه هر سفر توست.</p>
        <p>پشتیبانی: <a href={supportPhone.href} dir="ltr">{supportPhone.display}</a></p>
      </div>
      <div className="kh-foot-col"><h3>پشتیبانی</h3><Link href="/support">مرکز راهنمایی</Link><Link href="/support">پرسش‌های متداول</Link><Link href="/terms">شرایط استرداد</Link><Link href="/support">گزارش تخلف</Link></div>
      <div className="kh-foot-col"><h3>کارن‌سیر</h3><Link href="/contact">درباره ما</Link><Link href="/contact">تماس با ما</Link><Link href="/terms">قوانین و مقررات</Link><Link href="/privacy">حریم خصوصی</Link></div>
      <div className="kh-foot-col kh-foot-app"><h3>دانلود اپلیکیشن کارن‌سیر</h3><div className="kh-badges" aria-label="به‌زودی"><span>بازار</span><span dir="ltr">Google Play</span></div><small>به‌زودی</small></div>
    </div>
    <p className="kh-foot-copy">© کارن‌سیر. همهٔ حقوق محفوظ است.</p>
  </div>;
}

/* ---- hero and destination mosaic, after the approved reference render */
const Ornament = ({className}: {className: string}) => <svg className={className} viewBox="0 0 100 100" fill="none" stroke="#e2a93b" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
  {Array.from({length: 16}, (_, i) => {const a = (i * Math.PI) / 8, c = Math.cos(a), s = Math.sin(a); return <g key={i}><path d={`M${(50 + c * 14).toFixed(1)} ${(50 + s * 14).toFixed(1)}L${(50 + c * 36).toFixed(1)} ${(50 + s * 36).toFixed(1)}`}/><circle cx={(50 + c * 43).toFixed(1)} cy={(50 + s * 43).toFixed(1)} r="2.6"/></g>;})}
  <circle cx="50" cy="50" r="8"/></svg>;

export function ApprovedHomeHero({search}: {search: ReactNode}) {
  return <div className="kh kh-hero">
    <Ornament className="kh-orn kh-orn-1"/><Ornament className="kh-orn kh-orn-2"/>
    <div className="kh-hero-photo">
      <picture><source media="(min-width:1200px)" srcSet={A + 'refHero.jpg'}/>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={A + 'refHeroTop.jpg'} alt="مسافری که از زیر طاقی آجری به بام‌های شهر نگاه می‌کند"/></picture>
      {[['شیراز', '/destinations/shiraz', 'imgThumb2.jpg'], ['کیش', '/destinations/kish', 'imgThumb3.jpg']].map(([name, href, img], i) => <Link key={href} href={href} className={`kh-mini kh-mini-${i + 1}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={A + img} alt=""/><span><b>{name}</b><Arrow/></span></Link>)}
    </div>
    <div className="kh-hero-text">
      <h1>سفر را<br/>زندگی کن</h1>
      <p>از اولین جست‌وجو تا آخرین خاطره،<br/>همه‌چیز در کارن‌سیر کنار هم است.</p>
      <ul>
        <li><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 14v-2a8 8 0 0 1 16 0v2M4 14a2 2 0 0 1 2-2h1v6H6a2 2 0 0 1-2-2zM20 14a2 2 0 0 0-2-2h-1v6h1a2 2 0 0 0 2-2zM17 18v1a3 3 0 0 1-3 3h-2"/></svg><span>پشتیبانی<small>همراه شما</small></span></li>
        <li><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16 9.5"/></svg><span>رزرو<small>قابل پیگیری</small></span></li>
      </ul>
    </div>
    {search}
  </div>;
}

const TILES = [
  {href: '/destinations/qeshm', img: A + 'imgImage1.jpg', name: 'قشم', cls: 'kh-tile-qeshm'},
  {href: '/destinations/shiraz', img: A + 'imgThumb2.jpg', name: 'شیراز', cls: 'kh-tile-shiraz'},
  {href: '/destinations/masuleh', img: A + 'imgTileMasuleh.jpg', name: 'ماسوله', cls: 'kh-tile-masuleh'},
  {href: '/destinations/isfahan', img: A + 'imgTileIsfahan.jpg', name: 'اصفهان', cls: 'kh-tile-isfahan'},
];
export function ApprovedHomeBento() {
  return <div className="kh"><section className="kh-sec kh-bento" aria-labelledby="kh-bento-title">
    <Ornament className="kh-orn kh-orn-3"/>
    <h2 id="kh-bento-title">کجای ایران<br/>صدایت می‌زند؟</h2>
    {TILES.map(t => <Link key={t.href} href={t.href} className={`kh-tile ${t.cls}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={t.img} alt="" loading="lazy"/><b>{t.name}</b></Link>)}
  </section></div>;
}
