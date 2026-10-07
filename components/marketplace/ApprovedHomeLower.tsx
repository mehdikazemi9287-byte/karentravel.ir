'use client';
/* Lower half of the approved homepage and the shared footer, laid out after the approved reference render.
   Presentation only: no price, rating or availability is shown here; those come from real offers elsewhere. */
import Link from 'next/link';
import type {ReactNode} from 'react';
import {supportPhone} from '../../lib/site-contact';

const A = '/images/approved-figma/';
const TRIPS = [
  {href: '/destinations/masuleh', img: A + 'imgImage2.jpg', title: ['مسیر سبز', 'شمال'], nights: '۳ روز و ۲ شب'},
  {href: '/destinations/qeshm', img: A + 'imgImage1.jpg', title: ['آرامش در', 'جزیره قشم'], nights: '۴ روز و ۳ شب'},
  {href: '/destinations/shiraz', img: A + 'imgImage.jpg', title: ['سه روز در', 'شیراز'], nights: '۳ روز و ۲ شب'},
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
        <Link href="/compare" className="kh-cmp-cta">مقایسه کن</Link>
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
          <img src={A + 'imgLaptopScreen.svg'} alt=""/>
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
      <div className="kh-foot-col"><h3>خدمات</h3><Link href="/flights">پرواز</Link><Link href="/hotels">هتل و اقامت</Link><Link href="/trains">قطار</Link><Link href="/tours">تور</Link><Link href="/visa">راهنمای ویزا</Link></div>
    </div>
    <p className="kh-foot-copy">© کارن‌سیر. همهٔ حقوق محفوظ است.</p>
  </div>;
}
