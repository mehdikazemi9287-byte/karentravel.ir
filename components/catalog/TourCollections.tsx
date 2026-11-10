'use client';
/* Themed tour pages (last-minute, Nowruz, special) and the FAQ page. Tours come only from real, bookable departures;
   when nothing matches, the page says so and offers a trip request instead of showing sample tours. */
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {resolveApiBase} from '../../lib/api/karenseir-client';
import {formatJalali} from '../../lib/domain/jalali';
import {imageSrc, tenantSlug, useSiteContent} from '../../lib/site-content';
import {TripRequestForm} from '../customer/TripRequestForm';

export type CollectionKey = 'last-minute' | 'nowruz' | 'special' | 'festival' | 'installment';
type Dep = {id: string; starts_at: string; ends_at: string; seats_left: boolean};
type Item = {id: string; title: string; origin: string; destination: string; details: {description?: string}; departures: Dep[]; nights?: number; departure_count?: number; transport?: string; rating?: {average: number; count: number}; installment?: boolean};
const faN = (n: number) => n.toLocaleString('fa-IR');
type Festival = {title: string; intro: string; starts_on: string; ends_on: string; image: string; terms: string};
type Data = {key: CollectionKey; items: Item[]; window?: {from: string; to: string}; festival?: Festival | null};

const tehranDay = (iso: string) => new Date(iso).toLocaleDateString('en-CA', {timeZone: 'Asia/Tehran'});
const day = (iso: string) => formatJalali(tehranDay(iso));
const todayTehran = () => new Date().toLocaleDateString('en-CA', {timeZone: 'Asia/Tehran'});

export const COLLECTION_LINKS: {key: CollectionKey; href: string; label: string}[] = [
  {key: 'last-minute', href: '/tours/last-minute', label: 'تورهای لحظه‌آخری'},
  {key: 'nowruz', href: '/tours/nowruz', label: 'تورهای نوروزی'},
  {key: 'special', href: '/tours/special', label: 'تورهای ویژه'},
  {key: 'installment', href: '/tours/installment', label: 'تور اقساطی'},
];

const COPY: Record<Exclude<CollectionKey, 'special' | 'festival' | 'installment'>, {eyebrow: string; title: string; intro: string; empty: string}> = {
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
  const fest = data?.festival;
  const copy = collection === 'special'
    ? {eyebrow: 'انتخاب کارشناسان', title: site.special_tours.title, intro: site.special_tours.intro, empty: 'تورهای ویژه‌ی این فصل به‌زودی معرفی می‌شوند.'}
    : collection === 'installment'
      ? {eyebrow: 'سفر حالا، پرداخت در چند قسط', title: 'خرید تور اقساطی', intro: site.installment.intro || 'تورهای منتخب را با یکی از سرویس‌های اقساطی همکار یا اقساط سازمانی بخرید. تعداد اقساط، پیش‌پرداخت و کارمزد را هر سرویس هنگام اعتبارسنجی اعلام می‌کند.',
        empty: 'فهرست تورهای اقساطی به‌زودی منتشر می‌شود. درخواست خرید اقساطی ثبت کنید تا کارشناس فروش با شما تماس بگیرد.'}
    : collection === 'festival'
      ? {eyebrow: fest ? `تا ${formatJalali(fest.ends_on)}` : 'جشنواره', title: fest?.title || 'جشنواره‌ی سفر', intro: fest?.intro || '',
        empty: fest ? 'تورهای این جشنواره به‌زودی اضافه می‌شوند.' : 'در حال حاضر جشنواره‌ای برگزار نمی‌شود. تورهای ویژه و لحظه‌آخری را ببینید یا درخواست سفر بدهید.'}
      : COPY[collection];
  const left = fest ? Math.max(0, Math.round((new Date(fest.ends_on + 'T00:00:00+03:30').getTime() - new Date(todayTehran() + 'T00:00:00+03:30').getTime()) / 864e5)) : 0;
  return <section className="tour-marketplace customer-page">
    <span className="eyebrow">{copy.eyebrow}</span>
    <h1>{copy.title}</h1>
    {copy.intro && <p>{copy.intro}</p>}
    {fest && <div className="festival-ribbon"><b>{left === 0 ? 'آخرین روز جشنواره' : `${faN(left)} روز تا پایان جشنواره`}</b><span>از {formatJalali(fest.starts_on)} تا {formatJalali(fest.ends_on)}</span></div>}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    {fest?.image && <img className="festival-cover" src={imageSrc(fest.image)} alt={fest.title}/>}
    {data?.window && collection === 'nowruz' && <p className="tour-window">حرکت از {day(data.window.from)} تا {day(new Date(new Date(data.window.to).getTime() - 864e5).toISOString())}</p>}
    <nav className="tour-collection-nav" aria-label="صفحه‌های تور">
      <Link href="/tours">همه‌ی تورها</Link>
      <FestivalLink current={collection === 'festival'}/>
      {COLLECTION_LINKS.map(l => <Link key={l.key} href={l.href} aria-current={l.key === collection ? 'page' : undefined}>{l.label}</Link>)}
    </nav>
    <DestinationStamps/>
    {collection === 'installment' && <InstallmentOptions/>}
    {error ? <section role="alert"><p>فهرست تورها اکنون دریافت نشد؛ دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.</p><button className="button secondary" onClick={() => setTick(t => t + 1)}>تلاش دوباره</button></section>
      : !data ? <p role="status">در حال دریافت تورها…</p>
      : data.items.length ? <div className="pass-grid">{data.items.map(t => <TourPass key={t.id} t={t} badge={collection === 'special' ? 'انتخاب کارشناس' : collection === 'festival' ? 'جشنواره' : collection === 'installment' ? 'اقساطی' : collection === 'last-minute' ? 'لحظه‌آخری' : 'نوروز'}/>)}</div>
      : <div className="tour-collection-empty"><p role="status">{copy.empty}</p>
          <TripRequestForm compact title="درخواست تور" intro="مقصد و زمان سفرتان را بنویسید؛ کارشناس تور گزینه‌های موجود را به شما پیشنهاد می‌دهد."/></div>}
    {collection === 'installment' && data && data.items.length > 0 && <div className="installment-request"><TripRequestForm compact title="درخواست خرید اقساطی" intro="مقصد، تاریخ و روش اقساط دلخواه را بنویسید؛ کارشناس فروش شرایط واقعی را اعلام و رزرو را انجام می‌دهد."/></div>}
    {fest?.terms && <details className="panel festival-terms"><summary>شرایط جشنواره</summary><p>{fest.terms}</p></details>}
  </section>;
}

/** Boarding-pass tour card: route across the top, nights on the torn-off stub, real departures as stamps. */
function TourPass({t, badge}: {t: Item; badge: string}) {
  const limited = t.departures.some(d => d.seats_left);
  const more = (t.departure_count ?? t.departures.length) - 1;
  return <Link className="tour-pass" href={'/tours/' + t.id}>
    <div className="tour-pass-main">
      <div className="tour-pass-route" aria-label={`از ${t.origin} به ${t.destination}`}>
        <span>{t.origin}</span><i aria-hidden="true"/><span>{t.destination}</span>
      </div>
      <h2>{t.title}</h2>
      {t.rating && <p className="tour-pass-rating" aria-label={`امتیاز ${faN(t.rating.average)} از ۵ در ${faN(t.rating.count)} نظر`}><span aria-hidden="true">★</span> {faN(t.rating.average)} <small>({faN(t.rating.count)} نظر مسافران)</small></p>}
      {t.details.description && <p className="tour-pass-desc">{t.details.description}</p>}
      <ul className="tour-pass-dates">{t.departures.slice(0, 3).map(d => <li key={d.id}>{day(d.starts_at)}</li>)}</ul>
      <span className="tour-pass-cta">برنامه، استعلام قیمت و رزرو</span>
    </div>
    <div className="tour-pass-stub">
      <small>{badge}</small>
      {t.nights ? <b>{faN(t.nights)}<em>شب</em></b> : <b>—</b>}
      {more > 0 && <small>{faN(more + 1)} تاریخ حرکت</small>}
      {t.transport && <small>{t.transport}</small>}
      {t.installment && <span className="tour-pass-inst">قابل خرید اقساطی</span>}
      {limited && <span className="tour-pass-stamp">ظرفیت محدود</span>}
    </div>
  </Link>;
}

/** Destinations of published tours as passport stamps linking to the filtered tour list. */
export function DestinationStamps() {
  const [list, setList] = useState<string[]>([]);
  useEffect(() => {
    let live = true;
    const base = resolveApiBase(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000');
    fetch(`${base}/public/tour-products`).then(r => (r.ok ? r.json() : [])).then((rows: {destination?: string}[]) => {
      if (!live || !Array.isArray(rows)) return;
      const count = new Map<string, number>();
      rows.forEach(r => {const d = (r.destination || '').trim(); if (d) count.set(d, (count.get(d) ?? 0) + 1);});
      setList(Array.from(count.entries()).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([d]) => d));
    }).catch(() => undefined);
    return () => {live = false;};
  }, []);
  if (!list.length) return null;
  return <div className="dest-stamps" aria-label="مقصدهای تورها"><span>مقصدت کجاست؟</span>
    {list.map((d, i) => <Link key={d} className={i % 2 ? 'alt' : ''} href={'/tours?destination=' + encodeURIComponent(d)}>{d}</Link>)}</div>;
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

/** Installment routes switched on in the CMS. Terms (count, down-payment, fee) come from each provider at credit check. */
function InstallmentOptions() {
  const {installment: i} = useSiteContent();
  const opts = [
    i.nopay && {t: 'نوپی (بانک ملی)', d: 'خرید اقساطی با اعتبار نوپی بانک ملی.'},
    i.vamipay && {t: 'وامی‌پی', d: 'پرداخت اقساطی با وامی‌پی پس از اعتبارسنجی.'},
    i.dibacard && {t: 'دیباکارت', d: 'خرید اقساطی با اعتبار دیباکارت پس از اعتبارسنجی.'},
    i.organization && {t: 'اقساط سازمانی', d: 'برای کارکنان سازمان‌های طرف قرارداد کارن تراول؛ با تأیید سازمان و کسر از حقوق.', org: true},
  ].filter(Boolean) as {t: string; d: string; org?: boolean}[];
  if (!opts.length) return null;
  return <div className="installment-options">{opts.map(o => <div key={o.t} className={o.org ? 'org' : ''}><span>اقساطی</span><b>{o.t}</b><p>{o.d}</p>
    {o.org && <Link href="/solutions">همکاری سازمانی ←</Link>}</div>)}</div>;
}

function FestivalLink({current = false}: {current?: boolean}) {
  const {festival: f} = useSiteContent();
  const today = todayTehran();
  if (!current && !(f.active && f.starts_on && f.starts_on <= today && today <= f.ends_on)) return null;
  return <Link className="festival-link" href="/festival" aria-current={current ? 'page' : undefined}>{f.title || 'جشنواره'}</Link>;
}

export function TourCollectionNav() {
  return <><DestinationStamps/><nav className="tour-collection-nav" aria-label="صفحه‌های ویژه‌ی تور">
    <FestivalLink/>
    {COLLECTION_LINKS.map(l => <Link key={l.key} href={l.href}>{l.label}</Link>)}
    <Link href="/visa">ویزا</Link>
    <Link href="/faq">سؤالات متداول</Link>
    <Link href="/blog">راهنمای سفر</Link>
  </nav></>;
}
