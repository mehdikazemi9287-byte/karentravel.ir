'use client';
/* Lower half of the approved homepage and the shared footer, laid out after the approved reference render.
   Presentation only: no price, rating or availability is shown here; those come from real offers elsewhere. */
import Link from 'next/link';
import type {ReactNode} from 'react';
import {supportPhone} from '../../lib/site-contact';
import {imageSrc, useSiteContent} from '../../lib/site-content';

const A = '/images/approved-figma/';
const svg = (children: ReactNode, size = 44) => <svg width={size} height={size} viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;
const SERVICES: {href: string; label: string; icon: ReactNode}[] = [
  {href: '/services', label: 'خدمات سفر', icon: svg(<><rect x="9" y="15" width="24" height="24" rx="3"/><path d="M16 15v-4a3 3 0 0 1 3-3h4a3 3 0 0 1 3 3v4M9 24h24M33 20h4a3 3 0 0 1 3 3v13a3 3 0 0 1-3 3h-4"/></>)},
  {href: '/tours', label: 'تور', icon: svg(<><rect x="7" y="14" width="34" height="24" rx="4"/><circle cx="24" cy="26" r="7"/><path d="M17 14l2-4h10l2 4M35 20h1"/></>)},
  {href: '/trains', label: 'قطار', icon: svg(<><rect x="11" y="7" width="26" height="28" rx="6"/><path d="M11 22h26M17 13h14M16 41l3-6M32 41l-3-6M13 41h22"/><circle cx="18" cy="28" r="1.4"/><circle cx="30" cy="28" r="1.4"/></>)},
  {href: '/hotels', label: 'اقامت', icon: svg(<><path d="M10 41V12l14-5 14 5v29M6 41h36"/><path d="M17 17h3M28 17h3M17 24h3M28 24h3M17 31h3M28 31h3M22 41v-5h4v5"/></>)},
  {href: '/flights', label: 'پرواز', icon: svg(<><path d="M5 30l36-13a3.4 3.4 0 0 0-2.3-6.4L28 14.5 14 9l-4 1.6 9.5 7.7-8 3-4.5-2-2.5 1 4.5 6.5z"/><path d="M12 39h26"/></>)},
];

const ECOSYSTEM: {href: string; icon: string; title: string; text: string}[] = [
  {href: '/flights', icon: '✈', title: 'پرواز، قطار و حمل‌ونقل', text: 'بلیط هواپیما و قطار برای مسیرهای داخلی و خارجی'},
  {href: '/hotels', icon: '⌂', title: 'هتل و اقامتگاه', text: 'هتل، ویلا و بوم‌گردی متناسب با بودجه'},
  {href: '/tours', icon: '⌘', title: 'تور و تجربه', text: 'تورهای آژانس‌های همکار و سفرهای گروهی'},
  {href: '/car-rental', icon: '⌁', title: 'خودرو و ترانسفر', text: 'اجاره‌ی خودرو و ترانسفر فرودگاهی و بین‌شهری'},
  {href: '/restaurants', icon: '♨', title: 'رستوران و تفریح', text: 'رستوران، استخر و تفریح‌های شهری'},
  {href: '/destinations', icon: '◎', title: 'راهنمای مقصد', text: 'شهرها، جاذبه‌ها و بهترین زمان سفر'},
  {href: '/souvenirs', icon: '✿', title: 'سوغات شهرها', text: 'سوغات هر شهر، تا درِ خانه'},
  {href: '/visa', icon: '▣', title: 'ویزا و خدمات سفر', text: 'ویزا، بیمه‌ی مسافرتی و تشریفات فرودگاهی'},
];

export function ApprovedHomeLower() {
  const c = useSiteContent();
  return <div className="kh">
    <section className="kh-sec" aria-labelledby="kh-eco-title">
      <h2 id="kh-eco-title" className="kh-h2">همه‌ی سفر، در یک جا</h2>
      <p className="kh-eco-sub">از بلیط و اقامت تا تور، تفریح و سوغات</p>
      <div className="kh-eco">{ECOSYSTEM.map(e => <Link key={e.href} href={e.href} className="kh-eco-card"><span className="kh-eco-icon" aria-hidden="true">{e.icon}</span><b>{e.title}</b><span>{e.text}</span></Link>)}</div>
    </section>
    <section className="kh-sec" aria-labelledby="kh-org-title">
      <div className="kh-org">
        <div className="kh-org-text">
          <h2 id="kh-org-title">{c.organization.title}</h2>
          <ul>{c.organization.items.map((label, i) => [label, ['imgIconStaff.svg', 'imgIconCheck1.svg', 'imgIconChart.svg', 'imgIconCheck1.svg'][i]]).map(([label, icon]) => <li key={label}>
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
    <nav className="kh-strip" aria-label="خدمات کارن تراول">{SERVICES.map(s => <Link key={s.href} href={s.href}>{s.icon}<span>{s.label}</span></Link>)}</nav>
  </div>;
}

export function ApprovedFooterLight() {
  const c = useSiteContent();
  return <div className="kh kh-foot" role="contentinfo">
    <div className="kh-foot-grid">
      <div className="kh-foot-brand">
        <Link href="/" className="kh-foot-logo" aria-label="کارن تراول، صفحه اصلی">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={A + 'imgComponentLogoMark.svg'} alt=""/>کارن تراول</Link>
        <p>{c.footer.tagline}</p>
        <p>پشتیبانی: <a href={supportPhone.href} dir="ltr">{supportPhone.display}</a></p>
      </div>
      <div className="kh-foot-col"><h3>پشتیبانی</h3><Link href="/support">مرکز راهنمایی</Link><Link href="/faq">پرسش‌های متداول</Link><Link href="/terms">شرایط استرداد</Link><Link href="/support">گزارش تخلف</Link></div>
      <div className="kh-foot-col"><h3>کارن تراول</h3><Link href="/contact">درباره ما</Link><Link href="/contact">تماس با ما</Link><Link href="/terms">قوانین و مقررات</Link><Link href="/privacy">حریم خصوصی</Link></div>
    </div>
    <p className="kh-foot-copy">{c.footer.copyright}</p>
  </div>;
}

/* ---- hero and destination mosaic, after the approved reference render */
const Ornament = ({className}: {className: string}) => <svg className={className} viewBox="0 0 100 100" fill="none" stroke="#e2a93b" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
  {Array.from({length: 16}, (_, i) => {const a = (i * Math.PI) / 8, c = Math.cos(a), s = Math.sin(a); return <g key={i}><path d={`M${(50 + c * 14).toFixed(1)} ${(50 + s * 14).toFixed(1)}L${(50 + c * 36).toFixed(1)} ${(50 + s * 36).toFixed(1)}`}/><circle cx={(50 + c * 43).toFixed(1)} cy={(50 + s * 43).toFixed(1)} r="2.6"/></g>;})}
  <circle cx="50" cy="50" r="8"/></svg>;

export function ApprovedHomeHero({search}: {search: ReactNode}) {
  const c = useSiteContent(); const h = c.hero; const custom = !h.image.endsWith('refHeroTop.jpg');
  return <div className="kh kh-hero">
    {c.announcement.active && c.announcement.text && <p className="kh-announce" role="status">{c.announcement.href ? <Link href={c.announcement.href}>{c.announcement.text}</Link> : c.announcement.text}</p>}
    <Ornament className="kh-orn kh-orn-1"/><Ornament className="kh-orn kh-orn-2"/>
    <div className="kh-hero-photo">
      <picture>{!custom && <source media="(min-width:1200px)" srcSet={A + 'refHero.jpg'}/>}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={imageSrc(h.image)} alt={h.image_alt}/></picture>
    </div>
    <div className="kh-hero-text">
      <h1>{h.title}{h.title2 ? <><br/>{h.title2}</> : null}</h1>
      <p>{h.subtitle}{h.subtitle2 ? <><br/>{h.subtitle2}</> : null}</p>
    </div>
    {search}
  </div>;
}

export function ApprovedHomeBento() {
  const c = useSiteContent(); const cls = ['kh-tile-qeshm', 'kh-tile-shiraz', 'kh-tile-masuleh', 'kh-tile-isfahan'];
  return <div className="kh"><section className="kh-sec kh-bento" aria-labelledby="kh-bento-title">
    <Ornament className="kh-orn kh-orn-3"/>
    <h2 id="kh-bento-title">{c.bento.title}{c.bento.title2 ? <><br/>{c.bento.title2}</> : null}</h2>
    {c.bento.tiles.map((t, i) => <Link key={t.href + i} href={t.href} className={`kh-tile ${cls[i] ?? ''}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imageSrc(t.image)} alt="" loading="lazy"/><b>{t.title}</b></Link>)}
  </section></div>;
}
