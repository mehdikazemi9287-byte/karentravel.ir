'use client';
/* Shared kit for the role panels: one shell, one way to load data, one set of states.
   A value that the backend does not return is shown as unavailable; nothing here invents a figure. */
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {Fragment, useCallback, useEffect, useState, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';
import {AccountMenu} from '../marketplace/ApprovedFigmaHome';
import {AREA_FA, areaFor, canOpen, homeFor, itemFor, mobileTabsFor, navFor, ROLE_FA, staffAreasFor, type Area} from '../../lib/panel-access';
import './panel.css';

export type {Area} from '../../lib/panel-access';
export const fa = (n: number) => n.toLocaleString('fa-IR');
export const money = (amount: number | null | undefined, currency?: string | null) => amount === null || amount === undefined ? 'نامشخص' : `${fa(amount)} ${currency === 'IRR' || !currency ? 'ریال' : currency}`;
export const dateFa = (iso?: string | null) => {if (!iso) return '—'; const d = new Date(iso); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fa-IR', {year: 'numeric', month: 'long', day: 'numeric'});};
const STATUS: Record<string, [string, string]> = {confirmed: ['تأییدشده', 'ok'], issued: ['صادرشده', 'ok'], paid: ['پرداخت‌شده', 'ok'], captured: ['پرداخت‌شده', 'ok'], approved: ['تأییدشده', 'ok'], active: ['فعال', 'ok'], resolved: ['حل‌شده', 'ok'], read: ['خوانده‌شده', ''], completed: ['انجام‌شده', 'ok'], fulfilled: ['انجام‌شده', 'ok'], booked: ['رزروشده', 'ok'],
  pending: ['در انتظار', 'warn'], reserved: ['رزرو موقت', 'warn'], in_review: ['در حال بررسی', 'warn'], closed: ['بسته‌شده', ''], pending_payment: ['در انتظار پرداخت', 'warn'], pending_approval: ['در انتظار تأیید', 'warn'], approval_required: ['نیازمند تأیید', 'warn'], draft: ['پیش‌نویس', 'warn'], open: ['باز', 'warn'], in_progress: ['در حال رسیدگی', 'warn'], unread: ['خوانده‌نشده', 'warn'], new: ['جدید', 'warn'], held: ['نگه‌داشته', 'warn'], requested: ['درخواست‌شده', 'warn'], sent: ['ارسال‌شده', 'warn'], submitted: ['ثبت‌شده', 'warn'], rfq_open: ['در انتظار پیشنهاد', 'warn'], quoted: ['پیشنهاد رسیده', 'warn'],
  cancelled: ['لغوشده', 'bad'], canceled: ['لغوشده', 'bad'], rejected: ['ردشده', 'bad'], failed: ['ناموفق', 'bad'], expired: ['منقضی', 'bad'], refunded: ['مستردشده', ''], withdrawn: ['پس‌گرفته‌شده', ''], escalated: ['ارجاع‌شده', 'warn']};
export const SERVICE_FA: Record<string, string> = {hotel: 'هتل', flight: 'پرواز', tour: 'تور', train: 'قطار', bus: 'اتوبوس', visa: 'ویزا', package: 'پرواز + هتل', vacation_rental: 'اقامتگاه', car_rental: 'اجارهٔ خودرو', cruise: 'سفر دریایی', restaurant: 'رستوران', attraction: 'جاذبه', insurance: 'بیمه', cip: 'تشریفات فرودگاهی', transfer: 'ترانسفر', event_venue: 'سالن و رویداد', pool_sport: 'استخر و ورزش', handicraft: 'صنایع‌دستی', guide: 'راهنمای سفر', tourist_transport: 'حمل‌ونقل گردشگری'};
export const serviceFa = (s?: string | null) => (s ? SERVICE_FA[s.toLowerCase()] ?? s : '—');
export function Badge({status}: {status?: string | null}) {
  if (!status) return <span className="pn-badge">نامشخص</span>;
  const hit = STATUS[status.toLowerCase()]; return <span className={`pn-badge ${hit?.[1] ?? ''}`}>{hit?.[0] ?? status}</span>;
}

export type Load<T> = {kind: 'loading'} | {kind: 'ready'; data: T} | {kind: 'error'; status: number; message: string};
export function errorOf(e: unknown): {status: number; message: string} {
  if (e instanceof ApiError) {const d = e.detail as {detail?: unknown} | undefined; const inner = d && typeof d === 'object' && 'detail' in d ? d.detail : d; return {status: e.status, message: typeof inner === 'string' ? inner : e.message};}
  return {status: 0, message: 'ارتباط با سرور برقرار نشد.'};
}
export function useLoad<T>(path: string | null) {
  const {api, session} = useAuth(); const [tick, setTick] = useState(0);
  // Each result remembers the request inputs it answers; a result for older inputs reads as 'loading' while a request is due.
  const [loaded, setLoaded] = useState<{deps: unknown[]; state: Load<T>} | null>(null);
  const deps = [api, session, path, tick]; const current = !!loaded && loaded.deps.every((d, i) => d === deps[i]);
  // A reload of the same request keeps showing the previous data until the fresh answer arrives (no skeleton flash, forms keep their messages).
  const refreshing = !!loaded && !current && loaded.state.kind === 'ready' && loaded.deps[0] === api && loaded.deps[1] === session && loaded.deps[2] === path;
  const state: Load<T> = current || refreshing ? loaded.state : session && path ? {kind: 'loading'} : loaded?.state ?? {kind: 'loading'};
  useEffect(() => {
    if (!session || !path) return; let active = true; const key = [api, session, path, tick];
    api.get<T>(path).then(data => {if (active) setLoaded({deps: key, state: {kind: 'ready', data}});}).catch(e => {if (active) setLoaded({deps: key, state: {kind: 'error', ...errorOf(e)}});});
    return () => {active = false;};
  }, [api, session, path, tick]);
  return {state, reload: useCallback(() => setTick(t => t + 1), []), api, session};
}

/** Shown instead of a page this role cannot use: says so in plain Persian and points to the user's own panel. */
export function NoAccess({role, path, area}: {role: string; path: string; area: Area}) {
  const moved = itemFor(area, path)?.moved?.[role]; const home = homeFor(role);
  return <div className="pn-card" role="alert" data-state="no-access"><h2>دسترسی ندارید</h2>
    <p>این بخش برای نقش «{ROLE_FA[role] ?? (role || 'نامشخص')}» در دسترس نیست. اگر فکر می‌کنید باید به آن دسترسی داشته باشید، با مدیر مجموعه تماس بگیرید.</p>
    <div style={{display: 'flex', gap: 8, flexWrap: 'wrap'}}>{moved && <Link className="pn-btn" href={moved}>رفتن به همین بخش در پنل شما</Link>}<Link className={moved ? 'pn-btn ghost' : 'pn-btn'} href={home}>بازگشت به پنل من</Link></div></div>;
}

export function PanelShell({area: declared, title, intro, children}: {area: Area; title: string; intro?: string; children: ReactNode}) {
  const {session} = useAuth(); const path = usePathname() ?? '';
  const role = (session as {user?: {role?: string}} | null)?.user?.role ?? '';
  // Staff pages declared as 'admin' sit in the operations, finance or administration area by their path (spec §1.1).
  const area = areaFor(declared, path);
  // Navigation and the guard come from one registry (lib/panel-access.ts); the API stays the authority for every call.
  const links = navFor(area, role); const allowed = canOpen(area, path, role);
  const navTitle = AREA_FA[area];
  const nativeTitle = links.find(i => i.href === path)?.label ?? title;
  const staff = area === 'ops' || area === 'finance' || area === 'admin';
  const areas = staff && session ? staffAreasFor(role) : [];
  const tabs = session ? mobileTabsFor(area, role) : [];
  const current = (href: string) => path === href || (href !== '/agency' && href !== '/admin' && href !== '/finance' && path.startsWith(href + '/'));
  return <div className="pn-page" data-figma-page="129:11966" data-area={area}><a className="skip-link" href="#main-content">پرش به محتوای اصلی</a>
    <header className="pn-page-header"><Link className="pn-page-brand" href="/">کارن تراول</Link>
      {session?.user ? <AccountMenu variant="panel"/> : <Link className="pn-page-login" href="/login">ورود / ثبت‌نام</Link>}
    </header><div className="pn" data-area={area}>
    <nav className="pn-nav" id="pn-nav" aria-label={navTitle}><span className="pn-nav-title">{navTitle}</span>
      {areas.length > 1 && <span className="pn-areas" role="group" aria-label="بخش کاری">{areas.map(a => <Link key={a.area} href={a.href} aria-current={a.area === area ? 'true' : undefined}>{a.label}</Link>)}</span>}
      {session && links.map(({label, href, group}, i) => <Fragment key={href}>{group && group !== links[i - 1]?.group && <span className="pn-nav-group" role="presentation">{group}</span>}
        <Link href={href} aria-current={current(href) ? 'page' : undefined}>{label}</Link></Fragment>)}
      <span className="pn-nav-foot">{area !== 'customer' && <Link href="/account">حساب من</Link>}{area === 'customer' && role && role !== 'customer' && <Link href={homeFor(role)}>پنل کاری من</Link>}</span>
    </nav>
    <main className="pn-main" id="main-content" tabIndex={-1}><header className="pn-head"><h1>{allowed ? nativeTitle : 'دسترسی ندارید'}</h1>{intro && allowed && <p>{intro}</p>}</header>
      {!session ? <div className="pn-card"><p>برای دیدن این بخش وارد حساب خود شوید.</p><div><Link className="pn-btn" href="/login">ورود / ثبت‌نام</Link></div></div>
        : allowed ? children : <NoAccess role={role} path={path} area={area}/>}
      <Card title="وضعیت و دسترسی"><p className="pn-access-note">اطلاعات تأییدنشده و خدمات متصل‌نشده با وضعیت مشخص نمایش داده می‌شوند.</p><p className="pn-access-note">عملیات فقط با نقش و مجوز همان حساب انجام می‌شود.</p></Card>
    </main></div>
    {tabs.length > 1 && <nav className="pn-bottom" aria-label={`میان‌بر پنل ${navTitle}`}>{tabs.map(t => <Link key={t.href} href={t.href} aria-current={current(t.href) ? 'page' : undefined}><span aria-hidden="true">{t.glyph}</span>{t.label}</Link>)}
      <a href="#pn-nav"><span aria-hidden="true">☰</span>بیشتر</a></nav>}
    <p className="pn-page-foot">اطلاعات واقعی از حساب و سازمان شما دریافت می‌شود.</p></div>;
}
export function Card({title, action, children}: {title?: string; action?: ReactNode; children: ReactNode}) {return <section className="pn-card">{(title || action) && <div className="pn-card-head">{title && <h2>{title}</h2>}{action}</div>}{children}</section>;}
export function Stats({items, className = ''}: {items: {label: string; value: string; hint?: string}[]; className?: string}) {return <div className={`pn-stats ${className}`}>{items.map(i => <div className="pn-stat" key={i.label}><small>{i.label}</small><strong>{i.value}</strong>{i.hint && <span>{i.hint}</span>}</div>)}</div>;}
export function Empty({children}: {children: ReactNode}) {return <div className="pn-empty">{children}</div>;}
/** A capability the platform does not have (yet) or a value it does not hold. Says so instead of showing a made-up number. */
export function Unavailable({title = 'در دسترس نیست', children}: {title?: string; children: ReactNode}) {return <div className="pn-unavail" data-state="unavailable"><b>{title}</b><span>{children}</span></div>;}
export function Loading() {return <p className="pn-muted" role="status">در حال دریافت…</p>;}
export function Failed({status, message}: {status: number; message: string}) {return <div className="pn-note error" role="alert">{status === 403 ? 'این حساب به این بخش دسترسی ندارد.' : status === 401 ? 'نشست شما پایان یافته است؛ دوباره وارد شوید.' : message}</div>;}
export function Async<T>({state, children}: {state: Load<T>; children: (data: T) => ReactNode}) {return state.kind === 'loading' ? <Loading/> : state.kind === 'error' ? <Failed status={state.status} message={state.message}/> : <>{children(state.data)}</>;}
export type Col<R> = {label: string; cell: (row: R) => ReactNode};
export function Table<R>({rows, cols, empty, rowKey}: {rows: R[]; cols: Col<R>[]; empty: ReactNode; rowKey: (row: R) => string}) {
  if (rows.length === 0) return <Empty>{empty}</Empty>;
  return <div className="pn-scroll"><table className="pn-table"><thead><tr>{cols.map(c => <th key={c.label} scope="col">{c.label}</th>)}</tr></thead>
    <tbody>{rows.map(r => <tr key={rowKey(r)}>{cols.map(c => <td key={c.label} data-label={c.label}>{c.cell(r)}</td>)}</tr>)}</tbody></table></div>;
}
