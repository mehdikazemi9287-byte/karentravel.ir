'use client';
/* Themed tour pages (last-minute, Nowruz, special) and the FAQ page. Tours come only from real, bookable departures;
   when nothing matches, the page says so and offers a trip request instead of showing sample tours. */
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {resolveApiBase} from '../../lib/api/karenseir-client';
import {formatJalali} from '../../lib/domain/jalali';
import {tenantSlug, useSiteContent} from '../../lib/site-content';
import {TripRequestForm} from '../customer/TripRequestForm';

export type CollectionKey = 'last-minute' | 'nowruz' | 'special';
type Dep = {id: string; starts_at: string; ends_at: string; seats_left: boolean};
type Item = {id: string; title: string; origin: string; destination: string; details: {description?: string}; departures: Dep[]};
type Data = {key: CollectionKey; items: Item[]; window?: {from: string; to: string}};

const tehranDay = (iso: string) => new Date(iso).toLocaleDateString('en-CA', {timeZone: 'Asia/Tehran'});
const day = (iso: string) => formatJalali(tehranDay(iso));

export const COLLECTION_LINKS: {key: CollectionKey; href: string; label: string}[] = [
  {key: 'last-minute', href: '/tours/last-minute', label: 'تورهای لحظه‌آخری'},
  {key: 'nowruz', href: '/tours/nowruz', label: 'تورهای نوروزی'},
  {key: 'special', href: '/tours/special', label: 'تورهای ویژه'},
];

const COPY: Record<Exclude<CollectionKey, 'special'>, {eyebrow: string; title: string; intro: string; empty: string}> = {
  'last-minute': {eyebrow: 'حرکت در دو هفته‌ی آینده', title: 'تورهای لحظه‌آخری', intro: 'تورهایی که در ۱۴ روز آینده حرکت می‌کنند و هنوز ظرفیت و مهلت رزرو دارند.',
    empty: 'فعلاً توری با حرکت در دو هفته‌ی آینده و ظرفیت خالی ثبت نشده است.'},
  nowruz: {eyebrow: 'تعطیلات نوروز', title: 'تورهای نوروزی', intro: 'تورهایی که حرکتشان در روزهای پایانی اسفند و تعطیلات نوروز است.',
    empty: 'تورهای نوروزی هنوز توسط برگزارکنندگان ثبت نشده است. درخواست سفر خود را ثبت کنید تا به‌محض ثبت تورها با شما تماس بگیریم.'},
};

export function TourCollection({collection}: {collection: CollectionKey}) {
  const site = useSiteContent();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    const base = resolveApiBase(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000');
    fetch(`${base}/public/tenants/${encodeURIComponent(tenantSlug())}/tour-collections/${collection}`)
      .then(r => {if (!r.ok) throw new Error(String(r.status)); return r.json();})
      .then((d: Data) => {if (live) {setData(d); setError(false);}})
      .catch(() => {if (live) setError(true);});
    return () => {live = false;};
  }, [collection, tick]);
  const copy = collection === 'special'
    ? {eyebrow: 'انتخاب کارشناسان', title: site.special_tours.title, intro: site.special_tours.intro, empty: 'تورهای ویژه‌ی این فصل به‌زودی معرفی می‌شوند.'}
    : COPY[collection];
  return <section className="tour-marketplace customer-page">
    <span className="eyebrow">{copy.eyebrow}</span>
    <h1>{copy.title}</h1>
    {copy.intro && <p>{copy.intro}</p>}
    {data?.window && collection === 'nowruz' && <p className="tour-window">حرکت از {day(data.window.from)} تا {day(new Date(new Date(data.window.to).getTime() - 864e5).toISOString())}</p>}
    <nav className="tour-collection-nav" aria-label="صفحه‌های تور">
      <Link href="/tours">همه‌ی تورها</Link>
      {COLLECTION_LINKS.map(l => <Link key={l.key} href={l.href} aria-current={l.key === collection ? 'page' : undefined}>{l.label}</Link>)}
    </nav>
    {error ? <section role="alert"><p>فهرست تورها اکنون دریافت نشد؛ دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.</p><button className="button secondary" onClick={() => setTick(t => t + 1)}>تلاش دوباره</button></section>
      : !data ? <p role="status">در حال دریافت تورها…</p>
      : data.items.length ? <div className="stay-property-grid">{data.items.map(t => <Link className="panel tour-collection-card" key={t.id} href={'/tours/' + t.id}>
          <h2>{t.title}</h2>
          <p>{t.origin} ← {t.destination}</p>
          {t.details.description && <p className="tour-collection-desc">{t.details.description}</p>}
          <ul className="tour-collection-dates">{t.departures.map(d => <li key={d.id}>حرکت {day(d.starts_at)}{d.seats_left && <span className="tour-seats"> · ظرفیت محدود</span>}</li>)}</ul>
          <strong>برنامه و رزرو ←</strong>
        </Link>)}</div>
      : <div className="tour-collection-empty"><p role="status">{copy.empty}</p>
          <TripRequestForm compact title="درخواست تور" intro="مقصد و زمان سفرتان را بنویسید؛ کارشناس تور گزینه‌های موجود را به شما پیشنهاد می‌دهد."/></div>}
  </section>;
}

export function FaqView() {
  const {faq} = useSiteContent();
  const ld = {'@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: faq.items.map(q => ({'@type': 'Question', name: q.question, acceptedAnswer: {'@type': 'Answer', text: q.answer}}))};
  return <section className="container customer-page faq-page">
    <h1>{faq.title}</h1>
    {faq.intro && <p>{faq.intro}</p>}
    <div className="faq-list">{faq.items.map((q, i) => <details key={i} className="panel faq-item" open={i === 0}>
      <summary>{q.question}</summary>
      <p>{q.answer}</p>
    </details>)}</div>
    <p className="faq-more">پاسخ پرسشتان را پیدا نکردید؟ <Link href="/support">با پشتیبانی در تماس باشید</Link>.</p>
    <script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(ld).replace(/</g, '\\u003c')}}/>
  </section>;
}

export function TourCollectionNav() {
  return <nav className="tour-collection-nav" aria-label="صفحه‌های ویژه‌ی تور">
    {COLLECTION_LINKS.map(l => <Link key={l.key} href={l.href}>{l.label}</Link>)}
    <Link href="/visa">ویزا</Link>
    <Link href="/faq">سؤالات متداول</Link>
  </nav>;
}
