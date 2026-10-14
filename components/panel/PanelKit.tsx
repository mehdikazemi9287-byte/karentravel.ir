'use client';
/* Shared kit for the role panels: one shell, one way to load data, one set of states.
   A value that the backend does not return is shown as unavailable; nothing here invents a figure. */
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {useCallback, useEffect, useState, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';
import {AccountMenu} from '../marketplace/ApprovedFigmaHome';
import './panel.css';

export type Area = 'customer' | 'organization' | 'agency' | 'supplier' | 'admin';
const NAV: Record<Area, {title: string; links: [string, string][]}> = {
  customer: {title: 'حساب من', links: [['نمای کلی', '/account'], ['پروفایل و مسافران', '/account/profile'], ['رزروها و سفرها', '/account/bookings'], ['تغییرات سفر', '/account/changes'], ['ویزا', '/account/visa'], ['پرداخت و فاکتور', '/account/payments'], ['لغو و استرداد', '/account/refunds'], ['کیف پول و اعتبار', '/account/wallet'], ['مزایای سازمانی', '/account/benefits'], ['ذخیره‌شده‌ها و پیشنهادها', '/account/saved'], ['اعلان‌ها', '/account/notifications'], ['پشتیبانی', '/account/support']]},
  organization: {title: 'پنل سازمان', links: [['نمای کلی', '/organization'], ['میز کار کارمند', '/employee'], ['کارکنان و دسترسی‌ها', '/organization/members'], ['درخواست و تأیید سفر', '/organization/requests'], ['سیاست سفر', '/organization/policy'], ['واحدها و مراکز هزینه', '/organization/structure'], ['اعتبار و اقساط', '/organization/credit'], ['رزروهای سازمان', '/organization/bookings'], ['صورتحساب و تسویه', '/organization/billing'], ['گزارش', '/organization/reports'], ['سوابق و گردش تأیید', '/organization/audit'], ['تعهد مالی سفر', '/organization/financial-context']]},
  agency: {title: 'پنل همکار', links: [['نمای کلی', '/agency'], ['فروش و پیشنهاد قیمت', '/agency/sales'], ['رزروها', '/agency/bookings'], ['مشتریان', '/agency/customers'], ['کمیسیون', '/agency/commissions'], ['اعتبار و حساب', '/agency/credit'], ['تسویه و اسناد', '/agency/documents'], ['گزارش', '/agency/reports'], ['میز کار کامل', '/agency/workspace'], ['پشتیبانی', '/agency/support']]},
  supplier: {title: 'پنل تأمین‌کننده', links: [['نمای کلی', '/supplier'], ['خدمات، نرخ و ظرفیت', '/supplier/services'], ['هتل‌های من', '/supplier/hotels'], ['اقامتگاه و تقویم', '/supplier/accommodation'], ['سفارش‌ها و تأیید', '/supplier/fulfillment'], ['کنترل بلیت', '/supplier/admission'], ['درخواست‌های سازمانی', '/supplier/rfqs'], ['تسویه و قرارداد', '/supplier/settlements'], ['گزارش', '/supplier/reports'], ['پشتیبانی', '/supplier/support'], ['روابط مالی قرارداد', '/supplier/financial-context']]},
  admin: {title: 'مدیریت مجموعه', links: [['کاربران و نقش‌ها', '/admin'], ['سازمان‌ها', '/admin/organizations'], ['تأمین‌کنندگان و آژانس‌ها', '/admin/partners'], ['سوابق ممیزی', '/admin/audit'], ['هتل‌ها', '/admin/catalog'], ['داده‌های مرجع', '/admin/catalog/reference'], ['تورها', '/admin/tours'], ['عملیات و پشتیبانی', '/backoffice'], ['مالی', '/finance'], ['روابط مالی اکوسیستم', '/admin/ecosystem']]},
};
const ORG_ROLES = ['manager', 'welfare_manager', 'organization_admin', 'tenant_admin', 'platform_admin', 'employee'];
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
  const {api, session} = useAuth(); const [state, setState] = useState<Load<T>>({kind: 'loading'}); const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!session || !path) return; let active = true; setState({kind: 'loading'});
    api.get<T>(path).then(data => {if (active) setState({kind: 'ready', data});}).catch(e => {if (active) setState({kind: 'error', ...errorOf(e)});});
    return () => {active = false;};
  }, [api, session, path, tick]);
  return {state, reload: useCallback(() => setTick(t => t + 1), []), api, session};
}

export function PanelShell({area, title, intro, children}: {area: Area; title: string; intro?: string; children: ReactNode}) {
  const {session} = useAuth(); const path = usePathname(); const nav = NAV[area];
  const role = (session as {user?: {role?: string}} | null)?.user?.role ?? '';
  const nativeTitle = nav.links.find(([, href]) => href === path)?.[0] ?? title;
  return <div className="pn-page" data-figma-page="129:11966">
    <header className="pn-page-header"><Link className="pn-page-brand" href="/">کارن‌سیر</Link>
      {session?.user ? <AccountMenu variant="panel"/> : <Link className="pn-page-login" href="/login">ورود / ثبت‌نام</Link>}
    </header><div className="pn" data-area={area}>
    <nav className="pn-nav" aria-label={nav.title}><span className="pn-nav-title">{nav.title}</span>
      {nav.links.map(([label, href]) => <Link key={href} href={href} aria-current={path === href ? 'page' : undefined}>{label}</Link>)}
      <span className="pn-nav-foot">{area !== 'customer' && <Link href="/account">حساب من</Link>}{area === 'customer' && ORG_ROLES.includes(role) && role !== 'customer' && <Link href="/organization">پنل سازمان</Link>}</span>
    </nav>
    <main className="pn-main"><header className="pn-head"><h1>{nativeTitle}</h1>{intro && <p>{intro}</p>}</header>
      {session ? children : <div className="pn-card"><p>برای دیدن این بخش وارد حساب خود شوید.</p><div><Link className="pn-btn" href="/login">ورود / ثبت‌نام</Link></div></div>}
      <Card title="وضعیت و دسترسی"><p className="pn-access-note">اطلاعات تأییدنشده و خدمات متصل‌نشده با وضعیت مشخص نمایش داده می‌شوند.</p><p className="pn-access-note">عملیات فقط با نقش و مجوز همان حساب انجام می‌شود.</p></Card>
    </main></div><p className="pn-page-foot">اطلاعات واقعی از حساب و سازمان شما دریافت می‌شود.</p></div>;
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
