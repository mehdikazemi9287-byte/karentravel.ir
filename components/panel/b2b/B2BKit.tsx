'use client';
/* Panels Phase 2 shared pieces (Figma "Panels / P2 B2B+Charter", 222:2): the agency-buyer and agency-seller views of
   MoneyBreakdown, status chips for KYC / licences / blocks, a small action hook and a Jalali read-out for date inputs.
   Every amount is integer rial returned by the API; nothing here computes a price, a commission or a tax. */
import {useCallback, useState, type ReactNode} from 'react';
import {useAuth} from '../../../lib/api/auth-context';
import {MoneyRows, StatusChip, rial, type MoneyLine} from '../aftersales/kit';
import {errorOf} from '../PanelKit';
import './b2b.css';

export const pct = (bps: number | null | undefined) => (bps === null || bps === undefined ? '—' : `${(bps / 100).toLocaleString('fa-IR', {maximumFractionDigits: 2})}٪`);
export const jalali = (iso?: string | null, withTime = false) => {
  if (!iso) return '—'; const d = new Date(iso); if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('fa-IR', withTime ? {year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tehran'} : {year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Asia/Tehran'});
};

const KYC: Record<string, [string, string]> = {draft: ['پیش‌نویس', 'warn'], submitted: ['منتظر احراز', 'info'], active: ['فعال', 'ok'], rejected: ['ردشده', 'bad'], suspended: ['معلق', 'bad']};
const LIC: Record<string, [string, string]> = {pending: ['منتظر احراز', 'warn'], verified: ['تأییدشده', 'ok'], rejected: ['ردشده', 'bad'], expired: ['منقضی', '']};
const BLOCK: Record<string, [string, string]> = {draft: ['پیش‌نویس', 'warn'], submitted: ['در بازبینی عملیات', 'info'], published: ['منتشرشده', 'ok'], rejected: ['ردشده', 'bad']};
const CHECK: Record<string, [string, string]> = {confirmed: ['منطبق', 'ok'], mismatch: ['نامنطبق', 'bad'], not_found: ['یافت نشد', 'bad']};
function Chip({map, status}: {map: Record<string, [string, string]>; status?: string | null}) {
  const hit = status ? map[status] : undefined;
  return <span className={`as-chip ${hit?.[1] ?? ''}`} data-status={status ?? ''}>{hit?.[0] ?? (status || 'نامشخص')}</span>;
}
export const KycChip = ({status}: {status?: string | null}) => <Chip map={KYC} status={status}/>;
export const LicenceChip = ({status}: {status?: string | null}) => <Chip map={LIC} status={status}/>;
export const BlockChip = ({status}: {status?: string | null}) => <Chip map={BLOCK} status={status}/>;
export const CheckChip = ({result}: {result?: string | null}) => result ? <Chip map={CHECK} status={result}/> : <span className="as-chip warn">در انتظار بررسی</span>;
export {StatusChip};

export type BuyerBreakdown = {net_irr: number; units?: number; commission_bps: number; commission_irr: number; vat_rate_bps: number; vat_rate_id?: string; vat_irr: number;
  markup_irr: number; customer_price_irr: number; agency_pays_irr?: number; price_cap_unit_irr?: number | null; price_cap_total_irr?: number | null; price_cap_status?: string;
  price_cap_reference?: string | null; max_markup_irr?: number; vat_legal_reference?: string};
export type SellerBreakdown = {view: 'agency_seller'; sold_seats: number; agency_rate_unit_irr: number; gross_at_agency_rate_irr: number; platform_fee_bps: number | null;
  platform_fee_irr: number | null; vat_rate_bps?: number; vat_on_fee_irr: number | null; net_payable_irr: number | null; fee_status: string};

/** MoneyBreakdown, agency views (spec §3.3). The buyer sees net, commission, VAT on commission, own markup and own customer price;
 *  the seller (charterer) sees its own rate, the platform fee, VAT on that fee and the net payable — never the final customer price. */
export function MoneyBreakdown(props: {view: 'agency_buyer'; data: BuyerBreakdown} | {view: 'agency_seller'; data: SellerBreakdown}) {
  if (props.view === 'agency_buyer') {
    const d = props.data;
    const lines: MoneyLine[] = [
      {label: 'قیمت خالص آژانس (net)', value: rial(d.net_irr)},
      {label: 'markup شما', value: `+ ${rial(d.markup_irr)}`},
      {label: 'قیمت به مشتری شما', value: rial(d.customer_price_irr), tone: d.price_cap_status === 'exceeded' ? 'neg' : 'total'},
    ];
    if (d.price_cap_total_irr !== null && d.price_cap_total_irr !== undefined) lines.push({label: 'سقف سازمان هواپیمایی (این مسیر و تاریخ)', value: rial(d.price_cap_total_irr)});
    lines.push({label: `کمیسیون شما در این فروش (${pct(d.commission_bps)})`, value: rial(d.commission_irr), tone: 'good'},
      {label: `ارزش افزودهٔ کمیسیون (${pct(d.vat_rate_bps)})`, value: rial(d.vat_irr)},
      {label: 'کسر از حساب آژانس', value: rial(d.agency_pays_irr ?? d.net_irr), tone: 'total'});
    return <div className="b2b-money" data-view="agency_buyer"><MoneyRows label="تفکیک مبلغ (نمای آژانس خریدار)" lines={lines}/>
      {d.price_cap_status === 'not_configured' && <p className="as-muted">برای این مسیر و تاریخ سقف قیمتی ثبت نشده است؛ کنترل سقف انجام نشد.</p>}
      {d.price_cap_status === 'exceeded' && <p className="as-note bad" role="alert">فروش مسدود می‌شود: قیمت مشتری از سقف سازمان هواپیمایی بیشتر است{d.max_markup_irr !== undefined ? `؛ حداکثر markup مجاز ${rial(d.max_markup_irr)}` : ''}.</p>}
      <p className="as-muted">ارزش افزوده فقط روی کمیسیون حساب می‌شود، نه روی نرخ بلیت.</p></div>;
  }
  const d = props.data;
  const lines: MoneyLine[] = [{label: 'صندلی فروخته‌شده', value: d.sold_seats.toLocaleString('fa-IR')}, {label: 'نرخ آژانس (بزرگسال، هر صندلی)', value: rial(d.agency_rate_unit_irr)},
    {label: 'جمع به نرخ آژانس', value: rial(d.gross_at_agency_rate_irr)}];
  if (d.fee_status === 'contract') lines.push({label: `کارمزد پلتفرم (${pct(d.platform_fee_bps)})`, value: `− ${rial(d.platform_fee_irr)}`, tone: 'neg'},
    {label: `ارزش افزودهٔ کارمزد (${pct(d.vat_rate_bps)})`, value: `− ${rial(d.vat_on_fee_irr)}`, tone: 'neg'}, {label: 'خالص قابل پرداخت به شما', value: rial(d.net_payable_irr), tone: 'total'});
  return <div className="b2b-money" data-view="agency_seller"><MoneyRows label="تفکیک مبلغ (نمای آژانس فروشنده)" lines={lines}/>
    {d.fee_status !== 'contract' && <p className="as-muted">کارمزد پلتفرم این بلوک هنوز طبق قرارداد ثبت نشده است؛ خالص قابل پرداخت در تسویه مشخص می‌شود.</p>}
    <p className="as-muted">قیمت فروش به مسافر در این نما نمایش داده نمی‌شود.</p></div>;
}

/** One async action with busy/error state; returns the result or undefined on failure. */
export function useAction() {
  const {api} = useAuth(); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [done, setDone] = useState('');
  const run = useCallback(async <T,>(fn: (a: typeof api) => Promise<T>, ok?: string): Promise<T | undefined> => {
    setBusy(true); setError(''); setDone('');
    try {const r = await fn(api); if (ok) setDone(ok); return r;} catch (e) {setError(apiMessage(e)); return undefined;} finally {setBusy(false);}
  }, [api]);
  return {api, busy, error, done, run, setError};
}

/** Readable Persian message of an API error: plain string detail, {code, message} detail, or pydantic field errors. */
export function apiMessage(e: unknown): string {
  const d = (e as {detail?: unknown})?.detail;
  if (d && typeof d === 'object' && !Array.isArray(d) && 'message' in d) return String((d as {message: unknown}).message);
  if (Array.isArray(d)) return d.map(x => (x && typeof x === 'object' && 'msg' in x ? String((x as {msg: unknown}).msg).replace(/^Value error, /, '') : '')).filter(Boolean).join('، ') || 'ورودی نامعتبر است.';
  return errorOf(e).message;
}
export function apiCode(e: unknown): string | undefined {const d = (e as {detail?: unknown})?.detail; return d && typeof d === 'object' && 'code' in d ? String((d as {code: unknown}).code) : undefined;}

export function Feedback({error, done}: {error?: string; done?: string}) {
  return <>{error && <p className="as-note bad" role="alert">{error}</p>}{done && <p className="as-note ok" role="status">{done}</p>}</>;
}

/** A datetime-local value is Tehran wall-clock time (Iran has no DST since 1401): convert it to an absolute ISO instant. */
export const tehranIso = (local: string) => {const d = new Date(`${local.length === 16 ? `${local}:00` : local}+03:30`); return Number.isNaN(d.getTime()) ? '' : d.toISOString();};
/** Native date/time input with the Persian (Jalali) reading under it. Stored and sent as ISO. */
export function DateField({label, value, onChange, type = 'date', required, name}: {label: string; value: string; onChange: (v: string) => void; type?: 'date' | 'datetime-local'; required?: boolean; name?: string}) {
  return <label className="as-field">{label}<input type={type} name={name} value={value} required={required} onChange={e => onChange(e.target.value)} dir="ltr"/>
    <small className="as-muted">{value ? `شمسی: ${jalali(type === 'date' ? `${value}T12:00:00Z` : tehranIso(value), type !== 'date')}` : 'تاریخ را انتخاب کنید'}</small></label>;
}

export function Field({label, children, hint}: {label: string; children: ReactNode; hint?: ReactNode}) {
  return <label className="as-field">{label}{children}{hint && <small className="as-muted">{hint}</small>}</label>;
}

export function digitsLatin(v: string) {return v.replace(/[۰-۹]/g, c => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g, c => String('٠١٢٣٤٥٦٧٨٩'.indexOf(c)));}
/** Amount inputs accept Persian or Latin digits and thousands separators; returns an integer or NaN. */
export function parseRial(v: string): number {const s = digitsLatin(v).replace(/[,\s٬،]/g, ''); return /^\d+$/.test(s) ? Number(s) : NaN;}

export function BarMeter({value, label}: {value: number; label: string}) {
  const v = Math.max(0, Math.min(10000, value));
  return <div className="b2b-meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v / 100)} aria-label={label}>
    <div className="b2b-meter-bar"><span style={{width: `${v / 100}%`}} className={v >= 8000 ? 'warn' : ''}/></div><small>{label}</small></div>;
}
