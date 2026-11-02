'use client';
/* Customer app screens. Each one reads the signed-in customer's own data from existing /me/* endpoints;
   a capability the platform does not have yet (loyalty level, referral code) is shown as unavailable, never as a made-up value. */
import Link from 'next/link';
import {useEffect, useState, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {errorOf, useLoad, type Load} from '../panel/PanelKit';

const fa = (n: number) => n.toLocaleString('fa-IR');
const money = (n: number | null | undefined, c?: string | null) => (n === null || n === undefined ? 'نامشخص' : `${fa(n)} ${!c || c === 'IRR' ? 'ریال' : c}`);
const dateFa = (iso?: string | null) => {if (!iso) return '—'; const d = new Date(iso); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fa-IR', {month: 'long', day: 'numeric', year: 'numeric'});};
const SERVICE: Record<string, string> = {flight: 'پرواز', hotel: 'هتل', tour: 'تور', train: 'قطار', bus: 'اتوبوس', visa: 'ویزا', package: 'پرواز + هتل', car_rental: 'خودرو', vacation_rental: 'اقامتگاه', insurance: 'بیمه', cip: 'CIP', transfer: 'ترانسفر'};
const STATUS: Record<string, [string, string]> = {confirmed: ['قطعی', 'ok'], issued: ['صادرشده', 'ok'], fulfilled: ['انجام‌شده', 'ok'], completed: ['انجام‌شده', 'ok'], active: ['فعال', 'ok'], paid: ['پرداخت‌شده', 'ok'],
  reserved: ['رزرو موقت', 'warn'], awaiting_payment: ['منتظر پرداخت', 'warn'], pending_payment: ['منتظر پرداخت', 'warn'], pending: ['در انتظار', 'warn'], planned: ['برنامه‌ریزی‌شده', 'warn'], draft: ['پیش‌نویس', 'warn'],
  cancelled: ['لغوشده', 'bad'], canceled: ['لغوشده', 'bad'], failed: ['ناموفق', 'bad'], expired: ['منقضی', 'bad'], refunded: ['مستردشده', '']};
function Badge({s}: {s?: string | null}) {const h = s ? STATUS[s.toLowerCase()] : undefined; return <span className={`ca-badge ${h?.[1] ?? ''}`}>{h?.[0] ?? s ?? 'نامشخص'}</span>;}

function SignIn({what}: {what: string}) {
  return <section className="ca-card"><h2>ورود به حساب</h2><p className="ca-muted">برای دیدن {what} وارد حساب خود شوید.</p><Link className="ca-btn" href="/login?redirect=/app">ورود / ثبت‌نام با موبایل</Link></section>;
}
function Async<T>({state, children}: {state: Load<T>; children: (d: T) => ReactNode}) {
  if (state.kind === 'loading') return <p className="ca-muted" role="status">در حال دریافت…</p>;
  if (state.kind === 'error') return <p className="ca-error" role="alert">{state.status === 403 ? 'این حساب به این بخش دسترسی ندارد.' : state.status === 401 ? 'نشست شما پایان یافته است؛ دوباره وارد شوید.' : state.message}</p>;
  return <>{children(state.data)}</>;
}
function Unavailable({children}: {children: ReactNode}) {return <div className="ca-unavail" data-state="unavailable">{children}</div>;}

type Trip = {id: string; title: string; destination: string | null; starts_at: string | null; status: string; timeline_link: string};
type Reservation = {id: string; booking_reference: string | null; service_type: string; status: string; price_snapshot?: {total_amount?: number; currency?: string} | null; created_at: string; manage_link: string};
type Wallet = {id: string; currency: string; available: number; reserved: number; consumed: number};
type Credit = {id: string; currency: string; limit_amount: number; available: number; reserved: number; consumed: number};
type Installment = {id: string; reservation_id: string; total_payable: number; currency: string; status: string; schedule: {number?: number; due_date?: string; amount?: number; status?: string}[]};
type Payment = {id: string; reservation_id: string; status: string; amount: number; currency: string; captured_amount: number; refunded_amount: number};
type PublicTour = {id: string; title: string; origin: string; destination: string; tour_type: string; details?: {description?: string}};

const SERVICES: [string, string, string][] = [['/flights', 'پرواز', '✈'], ['/hotels', 'هتل', '⌂'], ['/tours', 'تور', '☼'], ['/trains', 'قطار', '⇄'], ['/villas', 'اقامتگاه', '◇'], ['/visa', 'ویزا', '▤'], ['/car-rental', 'خودرو', '◉'], ['/experiences', 'تجربه‌ها', '✦']];

function PublicTours() {
  const {api} = useAuth();
  const [state, setState] = useState<Load<PublicTour[]>>({kind: 'loading'});
  useEffect(() => {
    let live = true;
    api.publicGet<PublicTour[]>('/public/tour-products').then(d => {if (live) setState({kind: 'ready', data: d});}).catch(e => {if (live) setState({kind: 'error', ...errorOf(e)});});
    return () => {live = false;};
  }, [api]);
  return <section className="ca-card"><div className="ca-row"><h2>تورهای پیش رو</h2><Link href="/tours" className="ca-muted">همه</Link></div>
    <Async state={state}>{tours => tours.length === 0 ? <p className="ca-muted">فعلاً توری با ظرفیت باز منتشر نشده است.</p> :
      <div className="ca-scroll">{tours.slice(0, 8).map(t => <Link key={t.id} href={`/tours/${t.id}`} className="ca-card" style={{background: '#fff'}}>
        <h3>{t.title}</h3><p className="ca-muted">{t.origin} ← {t.destination}</p>
        {t.details?.description && <p className="ca-muted" style={{display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden'}}>{t.details.description}</p>}
        <span className="ca-btn ghost">جزئیات و تاریخ‌ها</span></Link>)}</div>}</Async>
  </section>;
}

function NextTrip() {
  const {state} = useLoad<Trip[]>('/me/trips');
  return <Async state={state}>{trips => {
    const now = Date.now();
    const next = trips.filter(t => t.starts_at && new Date(t.starts_at).getTime() > now && !/cancel/i.test(t.status)).sort((a, b) => +new Date(a.starts_at!) - +new Date(b.starts_at!))[0];
    return next ? <section className="ca-card"><div className="ca-row"><h2>سفر بعدی شما</h2><Badge s={next.status}/></div>
      <p style={{margin: 0, fontWeight: 800}}>{next.title}</p><p className="ca-muted">{next.destination ?? ''} — {dateFa(next.starts_at)}</p>
      <Link className="ca-btn ghost" href={next.timeline_link || `/trips/${next.id}`}>مسیر سفر، واچر و مدارک</Link></section> : null;
  }}</Async>;
}

export function Home() {
  const {session} = useAuth();
  return <>
    <section className="ca-hero">
      <h1>{session?.user ? `سلام ${session.user.name}، کجا برویم؟` : 'سفر بعدی‌ات را همین‌جا بساز'}</h1>
      <p>پرواز، هتل، تور و خدمات سفر با قیمت تأییدشده و پشتیبانی کارن‌سیر.</p>
      <nav className="ca-services" aria-label="خدمات">{SERVICES.map(([href, label, glyph]) => <Link key={href} href={href}><span aria-hidden="true">{glyph}</span><span>{label}</span></Link>)}</nav>
      <Link className="ca-btn" href="/search">جستجوی همه‌ی خدمات</Link>
    </section>
    {session?.user && <NextTrip/>}
    <section className="ca-card"><div className="ca-row"><h2>خرید اقساطی و اعتبار سازمانی</h2></div>
      <p className="ca-muted">اگر سازمان شما اعتبار سفر دارد یا طرح اقساط برایتان فعال است، هنگام پرداخت نمایش داده می‌شود.</p>
      <Link className="ca-btn ghost" href="/app/wallet">مشاهده‌ی اعتبار و اقساط من</Link></section>
    <PublicTours/>
  </>;
}

export function Trips() {
  const {session} = useAuth();
  const trips = useLoad<Trip[]>(session ? '/me/trips' : null);
  const res = useLoad<Reservation[]>(session ? '/me/reservations' : null);
  if (!session) return <SignIn what="سفرهای خود"/>;
  const now = Date.now();
  return <>
    <section className="ca-card"><h2>سفرهای من</h2>
      <Async state={trips.state}>{list => {
        if (list.length === 0) return <><p className="ca-muted">هنوز سفری ثبت نکرده‌اید.</p><Link className="ca-btn" href="/search">شروع جستجو</Link></>;
        const upcoming = list.filter(t => !t.starts_at || new Date(t.starts_at).getTime() >= now), past = list.filter(t => t.starts_at && new Date(t.starts_at).getTime() < now);
        const row = (t: Trip) => <li key={t.id}><div className="ca-row"><strong>{t.title}</strong><Badge s={t.status}/></div>
          <span className="ca-muted">{t.destination ?? ''}{t.starts_at ? ` — ${dateFa(t.starts_at)}` : ''}</span>
          <div className="ca-row"><Link className="ca-btn ghost" href={t.timeline_link || `/trips/${t.id}`}>مسیر سفر و واچر</Link><Link className="ca-muted" href="/account/support">پشتیبانی</Link></div></li>;
        return <>{upcoming.length > 0 && <><h3>پیش رو</h3><ul className="ca-list">{upcoming.map(row)}</ul></>}
          {past.length > 0 && <><h3>گذشته</h3><ul className="ca-list">{past.map(row)}</ul><Link className="ca-btn ghost" href="/search">سفر دوباره</Link></>}</>;
      }}</Async>
    </section>
    <section className="ca-card"><h2>رزروها</h2>
      <Async state={res.state}>{list => list.length === 0 ? <p className="ca-muted">رزروی ندارید.</p> : <ul className="ca-list">{list.slice(0, 20).map(r => <li key={r.id}>
        <div className="ca-row"><strong>{SERVICE[r.service_type] ?? r.service_type}</strong><Badge s={r.status}/></div>
        <span className="ca-muted"><span className="ca-ltr">{r.booking_reference ?? r.id.slice(0, 8)}</span> — {money(r.price_snapshot?.total_amount, r.price_snapshot?.currency)}</span>
        <div className="ca-row"><Link className="ca-btn ghost" href={r.manage_link || `/manage-booking/${r.id}`}>مدیریت رزرو</Link>
          {['reserved', 'awaiting_payment', 'pending_payment'].includes(r.status) && <Link className="ca-btn" href={`/checkout/${r.id}`}>پرداخت</Link>}</div></li>)}</ul>}</Async>
    </section>
  </>;
}

export function WalletScreen() {
  const {session} = useAuth();
  const wallets = useLoad<Wallet[]>(session ? '/me/wallets' : null);
  const credit = useLoad<Credit[]>(session ? '/me/organization-credit' : null);
  const inst = useLoad<Installment[]>(session ? '/me/installments' : null);
  const pays = useLoad<Payment[]>(session ? '/me/payments' : null);
  if (!session) return <SignIn what="کیف پول و اعتبار"/>;
  return <>
    <section className="ca-hero"><p>موجودی کیف پول</p>
      <Async state={wallets.state}>{ws => ws.length === 0 ? <p>هنوز کیف پولی برای شما ساخته نشده است.</p> :
        <>{ws.map(w => <div key={w.id}><div className="ca-balance">{money(w.available, w.currency)}</div><p>رزروشده: {money(w.reserved, w.currency)}</p></div>)}</>}</Async>
    </section>
    <section className="ca-card"><h2>اعتبار سازمانی</h2>
      <Async state={credit.state}>{cs => cs.length === 0 ? <p className="ca-muted">اعتبار سازمانی برای شما تعریف نشده است.</p> :
        <div className="ca-grid2">{cs.map(c => <div className="ca-stat" key={c.id}><small>قابل استفاده از {money(c.limit_amount, c.currency)}</small><strong>{money(c.available, c.currency)}</strong></div>)}</div>}</Async>
    </section>
    <section className="ca-card"><h2>اقساط</h2>
      <Async state={inst.state}>{is => is.length === 0 ? <p className="ca-muted">طرح اقساطی ندارید.</p> : <ul className="ca-list">{is.map(i => {
        const next = (i.schedule ?? []).find(s => s.status !== 'paid');
        return <li key={i.id}><div className="ca-row"><strong>{money(i.total_payable, i.currency)}</strong><Badge s={i.status}/></div>
          {next && <span className="ca-muted">قسط بعدی{next.number ? ` (شماره‌ی ${fa(next.number)} از ${fa(i.schedule.length)})` : ''}: {money(next.amount ?? null, i.currency)}{next.due_date ? ` — ${dateFa(next.due_date)}` : ''}</span>}</li>;
      })}</ul>}</Async>
    </section>
    <section className="ca-card"><h2>تراکنش‌ها</h2>
      <Async state={pays.state}>{ps => ps.length === 0 ? <p className="ca-muted">تراکنشی ثبت نشده است.</p> : <ul className="ca-list">{ps.slice(0, 20).map(p => <li key={p.id}>
        <div className="ca-row"><strong>{money(p.captured_amount || p.amount, p.currency)}</strong><Badge s={p.status}/></div>
        {p.refunded_amount > 0 && <span className="ca-muted">مسترد: {money(p.refunded_amount, p.currency)}</span>}</li>)}</ul>}</Async>
      <Link className="ca-btn ghost" href="/account/payments">فاکتورها و جزئیات</Link>
    </section>
  </>;
}

type Profile = {user_id: number; name: string; email: string; role: string};
type Traveller = {id: string; full_name: string};
export function AccountScreen() {
  const {session, logout} = useAuth();
  const profile = useLoad<Profile>(session ? '/me/profile' : null);
  const travellers = useLoad<Traveller[]>(session ? '/me/travellers' : null);
  if (!session) return <SignIn what="حساب خود"/>;
  return <>
    <section className="ca-card"><Async state={profile.state}>{p => <><h2>{p.name}</h2><p className="ca-muted ca-ltr" style={{textAlign: 'right'}}>{p.email}</p></>}</Async></section>
    <section className="ca-card"><h2>حلقه‌ی همسفران</h2>
      <Unavailable>سطح، امتیاز و کد معرف هنوز در سامانه فعال نشده‌اند؛ پس از راه‌اندازی همین‌جا نمایش داده می‌شوند.</Unavailable></section>
    <section className="ca-card"><div className="ca-row"><h2>مسافران ذخیره‌شده</h2><Link className="ca-muted" href="/account/profile">ویرایش</Link></div>
      <Async state={travellers.state}>{ts => ts.length === 0 ? <p className="ca-muted">مسافری ذخیره نکرده‌اید.</p> : <ul className="ca-list">{ts.map(t => <li key={t.id}>{t.full_name}</li>)}</ul>}</Async></section>
    <section className="ca-card"><h2>بیشتر</h2><ul className="ca-list">
      {[['/account/notifications', 'اعلان‌ها'], ['/account/saved', 'ذخیره‌شده‌ها'], ['/account/refunds', 'لغو و استرداد'], ['/account/visa', 'ویزا'], ['/account/support', 'پشتیبانی'], ['/account', 'نسخه‌ی کامل حساب']].map(([h, l]) =>
        <li key={h}><Link href={h}>{l}</Link></li>)}</ul>
      <button className="ca-btn ghost" onClick={() => {void logout();}}>خروج از حساب</button></section>
  </>;
}
