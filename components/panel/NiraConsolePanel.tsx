'use client';
/* Staff-only Niira (NRS) test console: provider/airline status → ONE AvailabilityFare call for ONE configured airline.
   Every figure comes from /flights/suppliers/nira/*; nothing is invented here. The host is never sent from this page —
   the API takes it from server configuration. No reservation or ticket issue is possible from here. */
import {useState, type FormEvent} from 'react';
import {ApiError} from '../../lib/api/karenseir-client';
import {isoDate, latinDigits} from '../../lib/mahan-console';
import {Async, Card, Stats, Table, fa, money, useLoad} from './PanelKit';
import {Note} from './CommercePanel';

type AirlineRow = {code: string; name_fa: string; enabled: boolean; reason: string; missing_settings: string[]; host: string | null; route_table: string[] | null};
type Status = {provider: string; mode: string; enabled: boolean; reason: string; airlines: AirlineRow[]; test_inventory: boolean; ticket_issuance: string};
type Cls = {rbd: string; state: string; seats: number; more_than_nine: boolean; price: number | null; currency: string | null};
type Flight = {flight_no: string; origin: string; destination: string; departure: string; arrival: string | null; aircraft: string; classes: Cls[]};
type ConsoleResult = {airline: string; name_fa: string; mode: string; host: string; status: 'ok' | 'error'; ms: number; test_inventory: boolean;
  flights?: Flight[]; rejected?: {flight_no: string; reason: string}[]; error?: {code: string; category: string; message: string; nrs_text: string}; raw?: unknown};
type Msg = {ok: boolean; text: string} | null;

const MODE_FA: Record<string, string> = {off: 'خاموش', sandbox: 'آزمایشی (A1)', live: 'عملیاتی'};
const REASON_FA: Record<string, string> = {
  ok: 'فعال', off: 'خاموش (NIRA_MODE=off)', invalid_mode: 'مقدار NIRA_MODE نامعتبر است؛ اتصال بسته است.', no_airline: 'هیچ ایرلاین قابل‌استفاده‌ای پیکربندی نشده است.',
  sandbox_only_a1: 'در حالت آزمایشی فقط A1', test_airline_in_live: 'A1 در حالت عملیاتی مجاز نیست', unknown_airline: 'کد ناشناخته', missing_credentials: 'تنظیمات ناقص',
  invalid_host: 'آدرس نامعتبر', host_not_allowed: 'آدرس برای این حالت مجاز نیست', invalid_cgi: 'نام cgi نامعتبر',
};
const STATE_FA: Record<string, string> = {open: 'باز', closed: 'پر/بسته', cancelled: 'کنسل'};
const REJECT_FA: Record<string, string> = {date_mismatch: 'تاریخ پرواز با تاریخ درخواستی یکی نیست', route_mismatch: 'مسیر متفاوت', no_departure_time: 'بدون ساعت حرکت', no_flight_no: 'بدون شمارهٔ پرواز'};
const today = () => {const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;};

export function NiraConsole() {
  const status = useLoad<Status>('/flights/suppliers/nira/status');
  const api = status.api;
  const [form, setForm] = useState({airline: '', origin: 'THR', destination: 'MHD', depart_on: '', adults: '1'});
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState<Msg>(null); const [result, setResult] = useState<ConsoleResult | null>(null);
  const set = (k: keyof typeof form) => (v: string) => setForm(f => ({...f, [k]: v}));

  async function run(e: FormEvent, enabled: AirlineRow[]) {
    e.preventDefault(); setMsg(null); setResult(null);
    const airline = form.airline || enabled[0]?.code || '';
    const o = form.origin.trim().toUpperCase(), d = form.destination.trim().toUpperCase(), dep = isoDate(form.depart_on);
    const adults = Number(latinDigits(form.adults).trim());
    const errors: string[] = [];
    if (!airline) errors.push('ایرلاین فعالی برای آزمون نیست.');
    if (!/^[A-Z]{3}$/.test(o) || !/^[A-Z]{3}$/.test(d) || o === d) errors.push('مبدأ و مقصد کد سه‌حرفی لاتین و متفاوت باشند (مثل THR و MHD).');
    if (!dep) errors.push('تاریخ میلادی معتبر وارد کنید (مثل 2026-12-01).'); else if (dep < today()) errors.push('تاریخ گذشته است.');
    if (!Number.isInteger(adults) || adults < 1 || adults > 9) errors.push('تعداد بزرگسال ۱ تا ۹ است.');
    if (errors.length) {setMsg({ok: false, text: errors.join(' ')}); return;}
    setBusy(true);
    try {
      const r = await api.post<ConsoleResult>('/flights/suppliers/nira/console/availability', {airline, origin: o, destination: d, depart_on: dep, adults});
      setResult(r);
      setMsg(r.status === 'ok' ? {ok: true, text: `پاسخ در ${fa(r.ms)} میلی‌ثانیه رسید.`} : {ok: false, text: `${r.error?.message ?? 'خطا'} (${r.error?.code ?? '—'})`});
    } catch (x) {
      const detail = x instanceof ApiError ? x.detail as {message?: string; code?: string} | string : null;
      setMsg({ok: false, text: typeof detail === 'string' ? detail : detail?.message ?? 'ارتباط با سرور برقرار نشد.'});
    } finally {setBusy(false);}
  }

  return <Async state={status.state}>{st => {
    const enabled = st.airlines.filter(a => a.enabled);
    return <>
      <Card title="وضعیت اتصال نیرا">
        <Stats items={[{label: 'حالت', value: MODE_FA[st.mode] ?? st.mode}, {label: 'وضعیت', value: st.enabled ? 'فعال' : 'بسته', hint: REASON_FA[st.reason] ?? st.reason},
          {label: 'ایرلاین فعال', value: fa(enabled.length)}, {label: 'صدور بلیت', value: 'غیرفعال', hint: 'تا تأیید مالک'}]}/>
        <Table rows={st.airlines} rowKey={r => r.code} empty="هیچ ایرلاینی در NIRA_AIRLINES نیست." cols={[
          {label: 'کد', cell: r => <span dir="ltr">{r.code}</span>}, {label: 'ایرلاین', cell: r => r.name_fa},
          {label: 'وضعیت', cell: r => r.enabled ? 'فعال' : REASON_FA[r.reason] ?? r.reason},
          {label: 'تنظیمات جاافتاده (فقط نام)', cell: r => r.missing_settings.length ? <span dir="ltr">{r.missing_settings.join('، ')}</span> : '—'},
          {label: 'آدرس', cell: r => <span dir="ltr">{r.host ?? '—'}</span>},
          {label: 'مسیرها', cell: r => r.route_table ? <span dir="ltr">{r.route_table.join(' ')}</span> : 'همهٔ مسیرها'}]}/>
      </Card>

      <Card title="جست‌وجوی تکی (یک درخواست به یک ایرلاین)"><form className="pn-form" onSubmit={e => run(e, enabled)} noValidate>
        <label htmlFor="nr-air">ایرلاین<select id="nr-air" value={form.airline || enabled[0]?.code || ''} onChange={e => set('airline')(e.target.value)}>
          {enabled.map(a => <option key={a.code} value={a.code}>{a.name_fa} ({a.code})</option>)}</select></label>
        <label htmlFor="nr-o">مبدأ (کد شهر)<input id="nr-o" dir="ltr" maxLength={3} value={form.origin} onChange={e => set('origin')(e.target.value.toUpperCase())}/></label>
        <label htmlFor="nr-d">مقصد (کد شهر)<input id="nr-d" dir="ltr" maxLength={3} value={form.destination} onChange={e => set('destination')(e.target.value.toUpperCase())}/></label>
        <label htmlFor="nr-dep">تاریخ (میلادی)<input id="nr-dep" dir="ltr" inputMode="numeric" placeholder="2026-12-01" value={form.depart_on} onChange={e => set('depart_on')(e.target.value)}/></label>
        <label htmlFor="nr-ad">بزرگسال<input id="nr-ad" inputMode="numeric" value={form.adults} onChange={e => set('adults')(e.target.value)}/></label>
        <button className="pn-btn" disabled={busy || enabled.length === 0}>{busy ? 'در حال پرسش از ایرلاین…' : 'جست‌وجو'}</button>
      </form>
        <p className="pn-muted">هر کلیک دقیقاً یک درخواست به ایرلاین می‌فرستد؛ پشت‌سرهم تکرار نکنید. خطای «Sales Channel not Allowed» یعنی یوزر وب‌سرویس (WS) ایرلاین لازم است؛ «Access Denied» ممکن است یعنی IP سرور در فهرست مجاز ایرلاین نیست.</p>
        <Note msg={msg}/>
        {result?.status === 'ok' && <>
          <Table rows={result.flights ?? []} rowKey={r => r.flight_no + r.departure} empty="ایرلاین برای این مسیر و تاریخ پروازی برنگرداند." cols={[
            {label: 'پرواز', cell: r => <span dir="ltr">{result.airline}{r.flight_no} {r.origin}→{r.destination}</span>},
            {label: 'حرکت', cell: r => <span dir="ltr">{r.departure.replace('T', ' ').slice(0, 16)}</span>},
            {label: 'رسیدن', cell: r => <span dir="ltr">{r.arrival ? r.arrival.replace('T', ' ').slice(0, 16) : '—'}</span>},
            {label: 'کلاس‌ها', cell: r => r.classes.map(c => <div key={c.rbd}><span dir="ltr">{c.rbd}</span> {STATE_FA[c.state] ?? c.state} {c.state === 'open' ? (c.more_than_nine ? '۹+' : fa(c.seats)) : ''} {c.price !== null ? money(c.price, c.currency ?? 'IRR') : ''}</div>)}]}/>
          {(result.rejected ?? []).length > 0 && <p className="pn-muted">کنار گذاشته شد: {(result.rejected ?? []).map(x => `${x.flight_no || '—'} (${REJECT_FA[x.reason] ?? x.reason})`).join('، ')}</p>}
        </>}
        {result?.status === 'error' && result.error?.nrs_text && <p className="pn-muted">متن خطای ایرلاین: <span dir="ltr">{result.error.nrs_text}</span></p>}
        {result?.raw !== undefined && result?.raw !== null && <details><summary>پاسخ خام (بدون نام کاربری و رمز)</summary>
          <pre dir="ltr" style={{maxHeight: 360, overflow: 'auto', fontSize: 12, whiteSpace: 'pre-wrap'}}>{JSON.stringify(result.raw, null, 2)}</pre></details>}
      </Card>
    </>;
  }}</Async>;
}
