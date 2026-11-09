'use client';
/* Shared pieces for the after-sales panels (Figma library "Panels / Library" 207:2): status chip, timeline with the next step
   and its ETA, skeleton/empty/error states, money rows and the ConfirmMoney dialog. Amounts are integer rial from the API;
   the customer sees toman, ops and finance see rial (spec §1.6). Nothing here computes a price or a penalty. */
import Link from 'next/link';
import {useEffect, useRef, type ReactNode} from 'react';
import {errorOf, type Load} from '../PanelKit';
import './aftersales.css';

export const faNum = (n: number) => n.toLocaleString('fa-IR');
export const rial = (n: number | null | undefined) => (n === null || n === undefined ? 'نامشخص' : `${faNum(n)} ریال`);
export const toman = (n: number | null | undefined) => (n === null || n === undefined ? 'نامشخص' : `${(n / 10).toLocaleString('fa-IR', {maximumFractionDigits: 1})} تومان`);
export const jDate = (iso?: string | null) => {if (!iso) return '—'; const d = new Date(iso); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fa-IR', {year: 'numeric', month: 'long', day: 'numeric'});};
export const jDateTime = (iso?: string | null) => {if (!iso) return '—'; const d = new Date(iso); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('fa-IR', {year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'});};
export const newKey = (prefix: string) => `${prefix}-${typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;

/** Reference codes (booking, PNR, IBAN, bank tracking) are isolated so RTL text never reorders them. */
export function Ref({children}: {children: ReactNode}) {return <bdi className="as-ltr">{children}</bdi>;}

const REQ: Record<string, [string, string]> = {submitted: ['ثبت‌شده', 'warn'], under_review: ['در حال بررسی', 'warn'], waiting_supplier: ['در انتظار تأمین‌کننده', 'warn'],
  needs_customer: ['منتظر پاسخ شما', 'bad'], approved: ['تأییدشده', 'ok'], refund_queued: ['در صف پرداخت', 'info'], refund_paid: ['پرداخت‌شده', 'ok'],
  closed: ['بسته‌شده', ''], rejected: ['ردشده', 'bad'], withdrawn: ['پس‌گرفته‌شده', ''],
  pending_finance: ['منتظر آماده‌سازی مالی', 'warn'], awaiting_approval: ['منتظر تأیید نفر دوم', 'info'], succeeded: ['پرداخت‌شده', 'ok'], returned: ['برگشت به عملیات', 'bad'],
  requested: ['درخواست‌شده', 'warn'], pending_review: ['در انتظار بررسی', 'warn'],
  confirmed: ['تأییدشده', 'ok'], issued: ['صادرشده', 'ok'], completed: ['انجام‌شده', 'ok'], reserved: ['رزرو موقت', 'warn'], awaiting_payment: ['در انتظار پرداخت', 'warn'],
  cancel_requested: ['درخواست لغو', 'warn'], change_requested: ['درخواست تغییر', 'warn'], refund_requested: ['درخواست استرداد', 'warn'], cancelled: ['لغوشده', 'bad'],
  refunded: ['مستردشده', ''], changed: ['تغییریافته', 'ok'], failed: ['ناموفق', 'bad'], expired: ['منقضی', ''],
  UNMATCHED: ['تطبیق‌نشده', 'warn'], MATCHED: ['تطبیق‌شده', 'ok'], DISPUTED: ['مغایرت', 'bad'], RESOLVED: ['حل‌شده', 'ok']};
/** Text + colour, never colour alone (spec §1.5). */
export function StatusChip({status, label}: {status?: string | null; label?: string}) {
  const hit = status ? REQ[status] : undefined;
  return <span className={`as-chip ${hit?.[1] ?? ''}`} data-status={status ?? ''}>{label ?? hit?.[0] ?? 'نامشخص'}</span>;
}

export type Step = {id?: string; title: string; actor?: string | null; at?: string | null; note?: string | null; type?: string; to_status?: string | null};
export type Next = {title: string; owner: string; eta: string | null; overdue: boolean; paused?: boolean} | null;
/** Vertical timeline, newest last; the next step is dashed with owner and ETA, red "تأخیر" when the ETA has passed. */
export function Timeline({steps, next, followUpHref}: {steps: Step[]; next?: Next; followUpHref?: string}) {
  return <ol className="as-tl" aria-label="روند">
    {steps.map((s, i) => <li key={s.id ?? `${s.title}-${i}`} className={s.type === 'reject' || s.to_status === 'rejected' ? 'bad' : ''}>
      <b>{s.title}</b><small>{[s.actor, jDateTime(s.at)].filter(Boolean).join(' · ')}</small>{s.note && <q>{s.note}</q>}</li>)}
    {next && <li className={`next ${next.overdue ? 'late' : ''}`} aria-label="گام بعدی"><div className="as-next-box">
      <b>گام بعدی: {next.title}</b>
      <small>مسئول: {next.owner}{next.paused ? ' · زمان‌سنج تا پاسخ شما متوقف است' : next.eta ? ` · موعد هدف: ${jDateTime(next.eta)}` : ''}</small>
      {next.overdue && <span className="as-row"><span className="as-chip bad">تأخیر</span>{followUpHref && <Link className="as-link" href={followUpHref}>پیگیری با پشتیبانی</Link>}</span>}
    </div></li>}
  </ol>;
}

export function Skeleton({rows = 4, kind = 'card'}: {rows?: number; kind?: 'card' | 'table' | 'timeline'}) {
  return <div className="as-card as-sk" role="status" aria-live="polite" aria-label="در حال دریافت">{kind === 'card' && <span className="tall"/>}{Array.from({length: rows}, (_, i) => <span key={i}/>)}<span className="sr-only" style={{position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)'}}>در حال دریافت…</span></div>;
}
export function EmptyState({title, children, action}: {title: string; children?: ReactNode; action?: ReactNode}) {
  return <div className="as-empty" data-state="empty"><b>{title}</b>{children && <span>{children}</span>}{action}</div>;
}
export function ErrorState({status, message, onRetry}: {status: number; message: string; onRetry?: () => void}) {
  const text = status === 401 ? 'نشست شما پایان یافته است؛ دوباره وارد شوید.' : status === 403 ? 'این حساب به این بخش دسترسی ندارد.' : status === 404 ? 'این مورد پیدا نشد یا به حساب شما تعلق ندارد.' : message || 'دریافت اطلاعات ممکن نشد.';
  return <div className="as-note bad" role="alert" data-state="error"><p>{text}</p><div className="as-actions" style={{marginTop: 8}}>
    {status === 401 ? <Link className="as-btn" href="/login">ورود دوباره</Link> : onRetry && <button type="button" className="as-btn ghost" onClick={onRetry}>تلاش دوباره</button>}
    <Link className="as-btn ghost" href="/account/support">تماس با پشتیبانی</Link></div></div>;
}
export function Loaded<T>({state, reload, skeleton, children}: {state: Load<T>; reload?: () => void; skeleton?: ReactNode; children: (data: T) => ReactNode}) {
  if (state.kind === 'loading') return <>{skeleton ?? <Skeleton/>}</>;
  if (state.kind === 'error') return <ErrorState status={state.status} message={state.message} onRetry={reload}/>;
  return <>{children(state.data)}</>;
}
export function Unavail({title, children}: {title: string; children: ReactNode}) {return <div className="as-unavail" data-state="unavailable"><b>{title}</b><span>{children}</span></div>;}

export type MoneyLine = {label: string; value: string; tone?: 'neg' | 'total' | 'good'};
export function MoneyRows({lines, label}: {lines: MoneyLine[]; label: string}) {
  return <dl className="as-money" aria-label={label}>{lines.map(l => <div key={l.label} className={l.tone ?? ''}><dt>{l.label}</dt><dd>{l.value}</dd></div>)}</dl>;
}

export type Col<R> = {label: string; cell: (row: R) => ReactNode};
export function DataTable<R>({rows, cols, rowKey, caption}: {rows: R[]; cols: Col<R>[]; rowKey: (r: R) => string; caption: string}) {
  return <div className="as-scroll"><table className="as-table"><caption style={{position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)'}}>{caption}</caption>
    <thead><tr>{cols.map(c => <th key={c.label} scope="col">{c.label}</th>)}</tr></thead>
    <tbody>{rows.map(r => <tr key={rowKey(r)}>{cols.map(c => <td key={c.label} data-label={c.label}>{c.cell(r)}</td>)}</tr>)}</tbody></table></div>;
}

/* ---- Persian amount in words (ConfirmMoney shows the amount in digits and words) */
const ONES = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه', 'ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده'];
const TENS = ['', '', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود'];
const HUNDREDS = ['', 'صد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد'];
const SCALES = ['', 'هزار', 'میلیون', 'میلیارد', 'هزار میلیارد'];
function below1000(n: number): string {
  const parts: string[] = []; const h = Math.floor(n / 100), r = n % 100;
  if (h) parts.push(HUNDREDS[h]);
  if (r < 20) {if (r) parts.push(ONES[r]);} else {parts.push(TENS[Math.floor(r / 10)]); if (r % 10) parts.push(ONES[r % 10]);}
  return parts.join(' و ');
}
export function amountWords(n: number): string {
  if (!Number.isFinite(n) || n < 0 || !Number.isInteger(n)) return '';
  if (n === 0) return 'صفر';
  const groups: string[] = []; let i = 0; let x = n;
  while (x > 0 && i < SCALES.length) {const g = x % 1000; if (g) groups.unshift(`${below1000(g)}${SCALES[i] ? ' ' + SCALES[i] : ''}`); x = Math.floor(x / 1000); i += 1;}
  return groups.join(' و ');
}

/** ConfirmMoney (Figma 211:341): amount in digits and words, destination, reason, and the second-person notice. */
export function ConfirmMoney({open, title, amount, destination, reason, twoPerson, busy, error, confirmLabel, idempotencyKey, onConfirm, onClose, children}: {
  open: boolean; title: string; amount: number; destination: ReactNode; reason?: ReactNode; twoPerson?: ReactNode; busy?: boolean; error?: string;
  confirmLabel: string; idempotencyKey?: string; onConfirm: () => void; onClose: () => void; children?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null); const checkRef = useRef<HTMLInputElement>(null);
  useEffect(() => {const d = ref.current; if (!d) return; if (open && !d.open) d.showModal?.(); if (!open && d.open) d.close();}, [open]);
  return <dialog ref={ref} className="as-dialog" aria-labelledby="as-cm-title" onClose={onClose} onCancel={e => {e.preventDefault(); onClose();}}>
    <form method="dialog" onSubmit={e => {e.preventDefault(); if (checkRef.current?.checked) onConfirm();}}>
      <h2 id="as-cm-title">{title}</h2>
      <div className="as-amount"><span className="as-muted">مبلغ</span><strong>{rial(amount)}</strong><span className="as-muted">به حروف: {amountWords(amount)} ریال</span></div>
      <div><span className="as-muted">مقصد وجه</span><div>{destination}</div></div>
      {reason && <div><span className="as-muted">دلیل</span><div>{reason}</div></div>}
      {children}
      {twoPerson && <div className="as-mc" role="note">{twoPerson}</div>}
      <label className="as-check"><input ref={checkRef} type="checkbox" required/> مبلغ، مقصد و نام صاحب حساب را بررسی کردم.</label>
      {idempotencyKey && <small className="as-muted">کلید یکتای درخواست: <Ref>{idempotencyKey.slice(0, 14)}…</Ref></small>}
      {error && <p className="as-note bad" role="alert">{error}</p>}
      <div className="as-actions"><button type="submit" className="as-btn" disabled={busy}>{busy ? 'در حال ثبت…' : confirmLabel}</button><button type="button" className="as-btn ghost" onClick={onClose}>انصراف</button></div>
    </form></dialog>;
}

/** A small modal for an ops decision (approve / reject / ask the customer), with a required reason where the rule demands one. */
export function DecisionDialog({open, title, children, busy, error, confirmLabel, danger, onSubmit, onClose}: {
  open: boolean; title: string; children: ReactNode; busy?: boolean; error?: string; confirmLabel: string; danger?: boolean; onSubmit: () => void; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {const d = ref.current; if (!d) return; if (open && !d.open) d.showModal?.(); if (!open && d.open) d.close();}, [open]);
  return <dialog ref={ref} className="as-dialog" aria-labelledby="as-dd-title" onClose={onClose} onCancel={e => {e.preventDefault(); onClose();}}>
    <form method="dialog" onSubmit={e => {e.preventDefault(); onSubmit();}}><h2 id="as-dd-title">{title}</h2>{children}
      {error && <p className="as-note bad" role="alert">{error}</p>}
      <div className="as-actions"><button type="submit" className={`as-btn ${danger ? 'danger' : ''}`} disabled={busy}>{busy ? 'در حال ثبت…' : confirmLabel}</button><button type="button" className="as-btn ghost" onClick={onClose}>انصراف</button></div>
    </form></dialog>;
}

export function messageOf(e: unknown): string {return errorOf(e).message;}
