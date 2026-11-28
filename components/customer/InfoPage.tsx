/* Plain information pages (about, terms, privacy, refund policy). Server-rendered text only; facts come from the
   owner-confirmed list in docs/content/OWNER_INPUTS_NEEDED.md — no address, licence number or figure is written here
   until the owner supplies it. */
import Link from 'next/link';
import type {ReactNode} from 'react';
import {supportPhone} from '../../lib/site-contact';
import './info-pages.css';

export type InfoSection = {id?: string; title: string; paragraphs?: string[]; list?: string[]; children?: ReactNode};

export function InfoPage({kicker, title, lead, sections, related, ld}: {kicker?: string; title: string; lead: string; sections: InfoSection[];
  related?: [string, string][]; ld?: object | object[]}) {
  return <article className="container customer-page info-page">
    {kicker && <span className="eyebrow">{kicker}</span>}
    <h1>{title}</h1>
    <p className="info-lead">{lead}</p>
    {sections.map(s => <section key={s.title} id={s.id} className="info-section">
      <h2>{s.title}</h2>
      {s.paragraphs?.map((p, i) => <p key={i}>{p}</p>)}
      {s.list && <ul>{s.list.map((x, i) => <li key={i}>{x}</li>)}</ul>}
      {s.children}
    </section>)}
    <aside className="info-contact panel">
      <b>پرسشی دارید؟</b>
      <p>کارشناسان کارن تراول از طریق شمارهٔ پشتیبانی پاسخ‌گوی پرسش‌های شما دربارهٔ رزرو، پرداخت و استرداد هستند.</p>
      <div className="customer-actions"><a className="button primary" href={supportPhone.href}>تماس با پشتیبانی <span dir="ltr">{supportPhone.display}</span></a>
        <Link className="button secondary" href="/contact">ثبت درخواست و راه‌های تماس</Link></div>
    </aside>
    {related && related.length > 0 && <nav className="info-related" aria-label="صفحه‌های مرتبط"><b>صفحه‌های مرتبط</b>
      <ul>{related.map(([label, href]) => <li key={href}><Link href={href}>{label}</Link></li>)}</ul></nav>}
    {ld && <script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(ld).replace(/</g, '\\u003c')}}/>}
  </article>;
}
