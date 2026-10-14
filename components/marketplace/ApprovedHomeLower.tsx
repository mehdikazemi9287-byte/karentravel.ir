'use client';
/* Lower half of the approved homepage and the shared footer, laid out after the approved reference render.
   Presentation only: no price, rating or availability is shown here; those come from real offers elsewhere. */
import Link from 'next/link';
import type {ReactNode} from 'react';
import {supportPhone} from '../../lib/site-contact';
import ApprovedMobileAI from './ApprovedMobileAI';

const A = '/images/approved-figma/';
const TRIPS = [
  {href: '/destinations/masuleh', img: A + 'trip-imgImage2.png', title: ['مسیر سبز', 'شمال'], nights: '۳ روز و ۲ شب'},
  {href: '/destinations/qeshm', img: A + 'trip-imgImage1.png', title: ['آرامش در', 'جزیره قشم'], nights: '۴ روز و ۳ شب'},
  {href: '/destinations/shiraz', img: A + 'trip-imgImage.png', title: ['سه روز در', 'شیراز'], nights: '۳ روز و ۲ شب'},
];
const PROMPTS = ['با ۲۰ میلیون کجا برم؟', 'سفر خانوادگی ۴ روزه', 'بهترین مقصد پاییزی'];
const SERVICES = [
 {href:'/services',label:'خدمات سفر',icon:'alignedNavServices.svg'},
 {href:'/tours',label:'تور',icon:'alignedNavTour.svg'},
 {href:'/trains',label:'قطار',icon:'alignedNavTrain.svg'},
 {href:'/hotels',label:'اقامت',icon:'alignedNavHotel.svg'},
 {href:'/flights',label:'پرواز',icon:'alignedNavFlight.svg'},
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
      <div className="kh-ai kh-ai-desktop">
        <h2 id="kh-ai-title">همراه هوشمند کارن‌سیر</h2>
        <Link href="/assistant" className="kh-ai-cta"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z"/></svg>شروع گفتگو</Link>
        <div className="kh-ai-chips">{PROMPTS.map(p => <Link key={p} href={`/assistant?q=${encodeURIComponent(p)}`}>{p}</Link>)}</div>
      </div>
      <div className="kh-ai-responsive"><ApprovedMobileAI/></div>
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
    <section className="kh-sec kh-org-wrap" aria-labelledby="kh-org-title">
      <div className="kh-org">
        <div className="kh-org-text">
          <h2 id="kh-org-title">سفر سازمانی، بدون پیچیدگی</h2>
          <ul>{[['اعتبار کارکنان', 'imgIconStaff.svg'], ['تأیید مرحله‌ای', 'imgIconCheck1.svg'], ['گزارش مالی', 'imgIconChart.svg']].map(([label, icon]) => <li key={label}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <span className="kh-org-icon"><img src={A + icon} alt=""/></span>{label}</li>)}</ul>
          <Link href="/organization" className="kh-org-cta">راهکارهای سازمانی<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></Link>
        </div>
        <div className="kh-org-art" aria-hidden="true">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="kh-org-laptop" src={A+'alignedLaptop.svg'} alt=""/><img className="kh-org-tablet" src={A+'alignedTablet.svg'} alt=""/><span className="kh-org-plant"/>
        </div>
      </div>
    </section>
    <nav className="kh-strip" aria-label="خدمات کارن‌سیر">{SERVICES.map(s => <Link key={s.href} href={s.href}><img src={A+s.icon} alt=""/><span>{s.label}</span></Link>)}</nav>
  </div>;
}

export function ApprovedFooterLight() {
  return <footer className="kh kh-foot" data-figma-node="75:595">
    <div className="kh-foot-top">
      <div className="kh-foot-brand"><Link href="/" className="kh-foot-logo" aria-label="کارن‌سیر، صفحه اصلی"><img src={A + 'alignedFooterLogo.svg'} alt=""/>کارن‌سیر</Link>
        <p>سفر، قصه‌ی ماست. کارن‌سیر، همراه هر سفر توست.</p><p>پشتیبانی: <a href={supportPhone.href} dir="ltr">{supportPhone.display}</a></p></div>
      <div className="kh-foot-app"><h3>دانلود اپلیکیشن کارن‌سیر</h3><div className="kh-badges" aria-label="به‌زودی"><span dir="ltr">Google Play</span><span>بازار</span></div><small>به‌زودی</small></div>
    </div>
    <div className="kh-foot-links">
      <div className="kh-foot-col"><h3>کارن‌سیر</h3><Link href="/contact">درباره ما</Link><Link href="/contact">تماس با ما</Link></div>
      <div className="kh-foot-col"><h3>پشتیبانی</h3><Link href="/support">مرکز راهنمایی</Link><Link href="/support">پرسش‌های متداول</Link><Link href="/terms">شرایط استرداد</Link><Link href="/support">گزارش تخلف</Link></div>
      <div className="kh-foot-col"><h3>قوانین</h3><Link href="/terms">قوانین و مقررات</Link><Link href="/privacy">حریم خصوصی</Link></div>
    </div>
    <div className="kh-foot-bottom"><div className="kh-foot-social" aria-hidden="true">{['Instagram','Telegram','LinkedIn'].map(n=><span key={n}><img src={A + 'imgIcon'+n+'.svg'} alt=""/></span>)}</div><p className="kh-foot-copy">© کارن‌سیر. همهٔ حقوق محفوظ است.</p></div>
  </footer>;
}

/* ---- hero and destination mosaic, after the approved reference render */
export function ApprovedHomeHero({search}: {search: ReactNode}) {
  return <div className="kh kh-hero">

    <div className="kh-hero-photo">
      <picture>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={A + 'hero-imgCmsHeroImage.png'} alt="بادگیرهای یزد"/></picture>
      {[['شیراز', '/destinations/shiraz', 'imgThumb2.jpg'], ['کیش', '/destinations/kish', 'imgThumb3.jpg']].map(([name, href, img], i) => <Link key={href} href={href} className={`kh-mini kh-mini-${i + 1}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={A + img} alt=""/><span><b>{name}</b><Arrow/></span></Link>)}
    </div>
    <div className="kh-hero-text">
      <h1>سفر را<br/>زندگی کن</h1>
      <p>از اولین جست‌وجو تا آخرین خاطره،<br/>همه‌چیز در کارن‌سیر کنار هم است.</p>
      <ul>{[['پشتیبانی','راه‌های ارتباط','imgIconSupport.svg'],['رزرو','پیگیری در حساب','imgIconCheck.svg']].map(([label,sub,icon])=><li key={label}><img src={A+icon} alt=""/><img src={A+'imgEllipse.svg'} alt=""/><span className="kh-trust-copy"><b>{label}</b><small>{sub}</small></span></li>)}</ul>
    </div>
    {search}
  </div>;
}

const TILES = [
  {href: '/destinations/qeshm', img: A + 'bento-imgTileQeshm.png', name: 'قشم', cls: 'kh-tile-qeshm'},
  {href: '/destinations/shiraz', img: A + 'bento-imgTileShiraz.png', name: 'شیراز', cls: 'kh-tile-shiraz'},
  {href: '/destinations/masuleh', img: A + 'bento-imgTileMasuleh.png', name: 'ماسوله', cls: 'kh-tile-masuleh'},
  {href: '/destinations/isfahan', img: A + 'bento-imgTileIsfahan.png', name: 'اصفهان', cls: 'kh-tile-isfahan'},
];
export function ApprovedHomeBento() {
  return <div className="kh"><section className="kh-sec kh-bento" aria-labelledby="kh-bento-title">

    <h2 id="kh-bento-title">کجای ایران<br/>صدایت می‌زند؟</h2>
    {TILES.map(t => <Link key={t.href} href={t.href} className={`kh-tile ${t.cls}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={t.img} alt="" loading="lazy"/><b>{t.name}</b></Link>)}
  </section></div>;
}
