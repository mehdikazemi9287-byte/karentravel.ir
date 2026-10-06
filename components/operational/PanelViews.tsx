'use client';
/* Role workspaces on top of real records only: finance, support desk, agency, supplier settlements,
   notification deliveries, reference tours. Every list has loading, empty, error and permission states. */
import Link from 'next/link';
import {FormEvent, ReactNode, useCallback, useEffect, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError, newId} from '../../lib/api/karenseir-client';
import {ErrorState} from './ConnectedViews';

type Load<T> = {kind: 'loading'} | {kind: 'ready'; data: T} | {kind: 'error'; status: number};
type Row = Record<string, unknown>;
const fa = (n: number) => n.toLocaleString('fa-IR');
const when = (iso?: string | null) => iso ? new Date(iso).toLocaleString('fa-IR', {dateStyle: 'medium', timeStyle: 'short'}) : '—';
const statusOf = (e: unknown) => e instanceof ApiError ? e.status : 503;
const detailOf = (e: unknown, fallback: string) => {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return 'نقش شما اجازهٔ این اقدام را ندارد.';
  const raw = e.detail && typeof e.detail === 'object' && 'detail' in (e.detail as object) ? (e.detail as {detail?: unknown}).detail : e.detail ?? e.message;
  return typeof raw === 'string' ? raw : Array.isArray(raw) ? raw.map((i: {loc?: unknown[]; msg?: string}) => `${(i.loc ?? []).slice(1).join('.')}: ${i.msg}`).join(' | ') : fallback;
};
const field = 'mt-1 w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2 text-sm';
const money = (v: unknown, c?: unknown) => typeof v === 'number' ? `${fa(v)} ${c === 'IRR' || !c ? 'ریال' : String(c)}` : '—';

function useLoad<T>(path: string | null) {
  const {api, session} = useAuth();
  const [result, setResult] = useState<{key: string; state: Load<T>} | null>(null);
  const [tick, setTick] = useState(0);
  const key = `${path}#${tick}`;
  useEffect(() => {
    if (!session || !path) return;
    let active = true;
    api.get<T>(path).then(data => {if (active) setResult({key, state: {kind: 'ready', data}});}).catch(e => {if (active) setResult({key, state: {kind: 'error', status: statusOf(e)}});});
    return () => {active = false;};
  }, [api, session, path, key]);
  // a reload keeps showing the previous data of the same path instead of flashing the loading state
  const state: Load<T> = result && (result.key === key || result.key.split('#')[0] === path) ? result.state : {kind: 'loading'};
  return {state, reload: useCallback(() => setTick(t => t + 1), []), session, api};
}
const Loading = ({children = 'در حال دریافت اطلاعات معتبر…'}: {children?: ReactNode}) => <div role="status" className="my-4 animate-pulse rounded-2xl bg-white p-6 text-center text-slate-600">{children}</div>;
const Empty = ({children}: {children: ReactNode}) => <div role="status" className="my-4 rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-slate-600">{children}</div>;
const Failed = ({status}: {status: number}) => <div role="alert" className="my-4 rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-800">{status === 403 ? 'نقش شما به این بخش دسترسی ندارد.' : status === 404 ? 'این مورد در دسترس حساب شما نیست.' : 'دریافت اطلاعات انجام نشد. دوباره تلاش کنید.'}</div>;
const Notice = ({n}: {n: {ok: boolean; text: string} | null}) => n ? <p role={n.ok ? 'status' : 'alert'} className={`my-3 rounded-xl p-3 text-sm ${n.ok ? 'bg-emerald-50 text-emerald-800' : 'bg-rose-50 text-rose-800'}`}>{n.text}</p> : null;

function Shell({title, intro, back, children}: {title: string; intro: string; back?: [string, string]; children: ReactNode}) {
  return <section className="container customer-page">{back && <Link href={back[1]}>{back[0]}</Link>}<h1>{title}</h1><p>{intro}</p>{children}</section>;
}
function Table({columns, rows, labels = {}, render = {}}: {columns: string[]; rows: Row[]; labels?: Record<string, string>; render?: Record<string, (r: Row) => ReactNode>}) {
  return <div className="my-3 overflow-x-auto rounded-2xl bg-white"><table className="w-full min-w-[36rem] text-right text-sm"><thead><tr className="border-b border-slate-200 text-slate-500">{columns.map(c => <th key={c} className="p-3 font-bold">{labels[c] ?? c}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={String(r.id ?? i)} className="border-b border-slate-100">{columns.map(c => <td key={c} className="max-w-[16rem] break-words p-3" dir="auto">{render[c] ? render[c](r) : r[c] === null || r[c] === undefined ? '—' : String(r[c])}</td>)}</tr>)}</tbody></table></div>;
}
function Tabs({value, onChange, options}: {value: string; onChange: (v: string) => void; options: Record<string, string>}) {
  return <div className="my-3 flex flex-wrap gap-2" role="tablist">{Object.entries(options).map(([k, v]) => <button key={k} type="button" role="tab" aria-selected={value === k} className={`rounded-full border px-4 py-1.5 text-sm ${value === k ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white text-slate-700'}`} onClick={() => onChange(k)}>{v}</button>)}</div>;
}
function Gate({session, children}: {session: unknown; children: ReactNode}) {return session ? <>{children}</> : <ErrorState status={401} message="برای دسترسی به این بخش وارد شوید."/>;}

/* ------------------------------------------------------------------ Finance */
const DATASETS: Record<string, string> = {payments: 'پرداخت‌ها', refunds: 'استردادها', settlements: 'تسویه‌ها', invoices: 'فاکتورها', ledger: 'دفتر مالی', 'credit-accounts': 'حساب‌های اعتباری'};
const FIN_LABELS: Record<string, string> = {id: 'شناسه', reservation_id: 'رزرو', user_id: 'کاربر', amount: 'مبلغ', currency: 'ارز', status: 'وضعیت', provider_key: 'درگاه', provider_reference: 'مرجع درگاه', captured_amount: 'وصول‌شده', refunded_amount: 'مستردشده',
  created_at: 'ثبت', payment_intent_id: 'پرداخت', supplier_id: 'تأمین‌کننده', external_reference: 'مرجع بیرونی', invoice_number: 'شمارهٔ فاکتور', subtotal_amount: 'جمع جزء', tax_amount: 'مالیات', total_amount: 'جمع کل', issued_at: 'صدور',
  wallet_id: 'کیف پول', credit_account_id: 'حساب اعتباری', entry_type: 'نوع ثبت', reversal_of_id: 'برگشتِ', organization_id: 'سازمان', limit_amount: 'سقف'};
type Overview = Record<'payments' | 'refunds' | 'settlements' | 'invoices', {status: string; count: number; amount: number; currency: string | null}[]> & {credit_accounts: number; note: string};

export function FinanceRecords() {
  const [dataset, setDataset] = useState('payments');
  const overview = useLoad<Overview>('/finance/overview');
  const records = useLoad<{total: number; columns: string[]; items: Row[]}>(`/finance/records/${dataset}`);
  const [notice, setNotice] = useState<{ok: boolean; text: string} | null>(null);
  async function exportCsv() {
    setNotice(null);
    try {
      const text = await overview.api.getText(`/finance/export/${dataset}`); const url = URL.createObjectURL(new Blob([text], {type: 'text/csv;charset=utf-8'}));
      const a = document.createElement('a'); a.href = url; a.download = `${dataset}.csv`; a.click(); URL.revokeObjectURL(url); setNotice({ok: true, text: 'خروجی CSV ساخته شد و در سابقهٔ ممیزی ثبت گردید.'});
    } catch (e) {setNotice({ok: false, text: detailOf(e, 'ساخت خروجی انجام نشد.')});}
  }
  return <Gate session={overview.session}>{overview.state.kind === 'error' ? <ErrorState status={overview.state.status} message="دسترسی به رکوردهای مالی ممکن نیست."/> :
    <Shell title="رکوردهای مالی" intro="فقط ردیف‌های ثبت‌شده به تفکیک وضعیت. مانده، مطالبات یا بدهیِ محاسبه‌شده در این صفحه نمایش داده نمی‌شود." back={['بازگشت به پنل مالی', '/finance']}>
      {overview.state.kind === 'loading' ? <Loading/> : <div className="my-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{(['payments', 'refunds', 'settlements', 'invoices'] as const).map(k => <div key={k} className="rounded-xl bg-white p-3 text-sm"><h2 className="font-bold">{DATASETS[k]}</h2>
        {overview.state.kind === 'ready' && overview.state.data[k].length ? <ul className="mt-1">{overview.state.data[k].map(s => <li key={s.status + s.currency} className="flex justify-between gap-2"><span dir="ltr">{s.status} · {fa(s.count)}</span><span>{money(s.amount, s.currency)}</span></li>)}</ul> : <p className="mt-1 text-slate-500">ردیفی ثبت نشده است.</p>}</div>)}</div>}
      <Tabs value={dataset} onChange={setDataset} options={DATASETS}/>
      <div className="flex flex-wrap items-center gap-3 text-sm"><span aria-live="polite">{records.state.kind === 'ready' ? `${fa(records.state.data.total)} ردیف` : ''}</span><button type="button" className="button secondary" onClick={() => void exportCsv()}>خروجی CSV</button></div>
      <Notice n={notice}/>
      {records.state.kind === 'loading' ? <Loading/> : records.state.kind === 'error' ? <Failed status={records.state.status}/> : records.state.data.items.length === 0 ? <Empty>برای «{DATASETS[dataset]}» ردیفی ثبت نشده است.</Empty>
        : <Table columns={records.state.data.columns} rows={records.state.data.items} labels={FIN_LABELS} render={{created_at: r => when(r.created_at as string), issued_at: r => when(r.issued_at as string), amount: r => money(r.amount, r.currency), total_amount: r => money(r.total_amount, r.currency), subtotal_amount: r => money(r.subtotal_amount, r.currency), tax_amount: r => money(r.tax_amount, r.currency), captured_amount: r => money(r.captured_amount, r.currency), refunded_amount: r => money(r.refunded_amount, r.currency), limit_amount: r => money(r.limit_amount, r.currency), id: r => <span dir="ltr">{String(r.id).slice(0, 8)}</span>}}/>}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Support desk */
type CaseRow = {id: string; subject: string; status: string; priority: string; severity: string; sla_due_at: string | null};
type Workspace = {case: {id: string; subject: string; status: string; priority: string; severity: string; case_type: string}; sla: {due_at: string | null; breached: boolean};
  messages: {id: string; author_kind: string; is_human: boolean; visible_to_customer: boolean; body: string; created_at: string}[]; customer: {name: string; reservations: number; open_cases: number} | null;
  booking: {service_type: string; status: string; booking_reference: string | null} | null; trip_events: {id: string; category_fa: string | null; title: string; severity: string; visibility: string; created_at: string}[]; history: {at: string; action: string}[]};
const AUTHOR: Record<string, string> = {customer: 'مشتری', human_support: 'پشتیبان انسانی', internal_note: 'یادداشت داخلی', ai_assistant: 'دستیار هوشمند'};
const HISTORY: Record<string, string> = {internal_note_added: 'یادداشت داخلی', escalated: 'ارجاع فوری', assigned: 'تخصیص', resolved: 'حل‌شده', human_reply: 'پاسخ پشتیبان'};

export function SupportDesk() {
  const cases = useLoad<CaseRow[]>('/support/cases');
  const [selected, setSelected] = useState('');
  const ws = useLoad<Workspace>(selected ? `/support/cases/${selected}/workspace` : null);
  const [notice, setNotice] = useState<{ok: boolean; text: string} | null>(null);
  const [busy, setBusy] = useState(false);
  async function send(e: FormEvent<HTMLFormElement>, path: string, body: (v: Record<string, string>) => unknown, done: string, idem = false) {
    e.preventDefault(); if (busy) return; const form = e.currentTarget; const v = Object.fromEntries(new FormData(form)) as Record<string, string>;
    setBusy(true); setNotice(null);
    try {await cases.api.post(`/support/cases/${selected}/${path}`, body(v), idem ? newId() : undefined); form.reset(); ws.reload(); cases.reload(); setNotice({ok: true, text: done});}
    catch (err) {setNotice({ok: false, text: detailOf(err, 'ثبت انجام نشد.')});} finally {setBusy(false);}
  }
  const role = cases.session?.user?.role ?? '';
  if (cases.session && !['backoffice_expert', 'platform_admin'].includes(role)) return <ErrorState status={403} message="میز پشتیبانی فقط برای کارشناسان پشتیبانی است."/>;
  return <Gate session={cases.session}>{cases.state.kind === 'error' ? <ErrorState status={cases.state.status} message="دسترسی به میز پشتیبانی ممکن نیست."/> :
    <Shell title="میز پشتیبانی" intro="پرونده، زمینهٔ رزرو و مشتری، رویدادهای ثبت‌شدهٔ سفر و یادداشت‌های داخلی در یک نما. یادداشت داخلی هرگز به مشتری نمایش داده نمی‌شود." back={['بازگشت به پنل عملیات', '/backoffice']}>
      {cases.state.kind === 'loading' ? <Loading/> : cases.state.data.length === 0 ? <Empty>پرونده‌ای ثبت نشده است.</Empty> :
        <label className="my-3 block text-sm">پرونده<select className={field} value={selected} onChange={e => {setSelected(e.target.value); setNotice(null);}} aria-label="انتخاب پرونده"><option value="">انتخاب پرونده</option>
          {cases.state.data.map(c => <option key={c.id} value={c.id}>{c.subject} — {c.status} — {c.priority}</option>)}</select></label>}
      <Notice n={notice}/>
      {selected && (ws.state.kind === 'loading' ? <Loading/> : ws.state.kind === 'error' ? <Failed status={ws.state.status}/> : (w => <div className="grid gap-4 lg:grid-cols-[2fr_1fr]" data-case={w.case.id}>
        <div className="grid gap-3">
          <div className="rounded-2xl bg-white p-4"><h2 className="font-bold">{w.case.subject}</h2>
            <p className="mt-1 flex flex-wrap gap-2 text-xs"><span className="rounded bg-slate-200 px-2 py-0.5">وضعیت: {w.case.status}</span><span className="rounded bg-slate-200 px-2 py-0.5">اولویت: {w.case.priority}</span><span className="rounded bg-slate-200 px-2 py-0.5">شدت: {w.case.severity}</span>
              <span className={`rounded px-2 py-0.5 ${w.sla.breached ? 'bg-rose-600 text-white' : 'bg-slate-200'}`}>SLA: {w.sla.due_at ? when(w.sla.due_at) : 'تعریف نشده'}{w.sla.breached ? ' — گذشته' : ''}</span></p></div>
          <div className="grid gap-2" aria-label="پیام‌های پرونده">{w.messages.map(msg => <article key={msg.id} data-author={msg.author_kind} className={`rounded-xl border p-3 text-sm ${msg.author_kind === 'internal_note' ? 'border-amber-300 bg-amber-50' : msg.author_kind === 'customer' ? 'border-slate-200 bg-white' : 'border-sky-200 bg-sky-50'}`}>
            <p className="flex flex-wrap gap-2 text-xs text-slate-500"><strong className="text-slate-800">{AUTHOR[msg.author_kind] ?? msg.author_kind}</strong><span>{msg.is_human ? 'نوشتهٔ انسان' : 'تولید خودکار'}</span>{!msg.visible_to_customer && <span className="rounded bg-amber-600 px-2 text-white">فقط داخلی</span>}<time>{when(msg.created_at)}</time></p>
            <p className="mt-1 whitespace-pre-wrap break-words">{msg.body}</p></article>)}</div>
          <form className="grid gap-2 rounded-2xl bg-white p-4" aria-label="پاسخ به مشتری" onSubmit={e => void send(e, 'human-replies', v => ({body: v.body}), 'پاسخ برای مشتری ثبت شد.', true)}><label className="text-sm">پاسخ پشتیبان به مشتری<textarea name="body" required minLength={3} maxLength={4000} rows={3} className={field}/></label><button className="button primary" disabled={busy}>ارسال پاسخ</button></form>
          <form className="grid gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4" aria-label="یادداشت داخلی" onSubmit={e => void send(e, 'internal-notes', v => ({body: v.body}), 'یادداشت داخلی ثبت شد (مشتری آن را نمی‌بیند).')}><label className="text-sm">یادداشت داخلی<textarea name="body" required minLength={2} maxLength={4000} rows={2} className={field}/></label><button className="button secondary" disabled={busy}>ثبت یادداشت داخلی</button></form>
          <form className="grid gap-2 rounded-2xl bg-white p-4 sm:grid-cols-[1fr_auto_auto]" aria-label="ارجاع فوری" onSubmit={e => void send(e, 'escalate', v => ({reason: v.reason, severity: v.severity}), 'پرونده ارجاع فوری شد و در مرکز عملیات سفر ثبت گردید.')}>
            <label className="text-sm">دلیل ارجاع<input name="reason" required minLength={3} maxLength={500} className={field}/></label><label className="text-sm">شدت<select name="severity" className={field} defaultValue="HIGH"><option value="HIGH">بالا</option><option value="CRITICAL">بحرانی</option></select></label><button className="button secondary self-end" disabled={busy}>ارجاع</button></form>
        </div>
        <aside className="grid content-start gap-3 text-sm">
          <div className="rounded-2xl bg-white p-4"><h3 className="font-bold">مشتری</h3>{w.customer ? <p className="mt-1">{w.customer.name}<br/>{fa(w.customer.reservations)} رزرو · {fa(w.customer.open_cases)} پروندهٔ باز</p> : <p className="mt-1 text-slate-500">—</p>}</div>
          <div className="rounded-2xl bg-white p-4"><h3 className="font-bold">رزرو مرتبط</h3>{w.booking ? <p className="mt-1" dir="auto">{w.booking.service_type} · {w.booking.status}{w.booking.booking_reference ? ` · ${w.booking.booking_reference}` : ''}</p> : <p className="mt-1 text-slate-500">رزروی به این پرونده وصل نیست.</p>}</div>
          <div className="rounded-2xl bg-white p-4"><h3 className="font-bold">رویدادهای ثبت‌شدهٔ سفر</h3>{w.trip_events.length ? <ul className="mt-1 grid gap-1">{w.trip_events.slice(0, 8).map(ev => <li key={ev.id}>{ev.category_fa ?? ev.title} <span className="text-xs text-slate-500">· {ev.visibility === 'internal' ? 'داخلی' : 'قابل‌مشاهدهٔ مشتری'} · {when(ev.created_at)}</span></li>)}</ul> : <p className="mt-1 text-slate-500">رویدادی برای سفر این پرونده ثبت نشده است.</p>}</div>
          <div className="rounded-2xl bg-white p-4"><h3 className="font-bold">تاریخچه</h3>{w.history.length ? <ul className="mt-1 grid gap-1">{w.history.slice(-8).reverse().map((h, i) => <li key={i}>{HISTORY[h.action] ?? h.action} <span className="text-xs text-slate-500">· {when(h.at)}</span></li>)}</ul> : <p className="mt-1 text-slate-500">—</p>}</div>
        </aside></div>)(ws.state.data))}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Agency */
type AgencyRow = {id: string; name: string; status: string; markup_bps: number; commission_bps: number; sales_channel_linked: boolean};
const AGENCY_TABS: Record<string, string> = {bookings: 'رزروها', customers: 'مشتریان', commissions: 'کمیسیون', settlements: 'تسویه', report: 'گزارش'};

export function AgencyWorkspace() {
  const list = useLoad<{agencies: AgencyRow[]}>('/agency/workspace');
  const [agency, setAgency] = useState(''); const [tab, setTab] = useState('bookings');
  const data = useLoad<Record<string, unknown>>(agency ? `/agency/${agency}/${tab}` : null);
  const current = list.state.kind === 'ready' ? list.state.data.agencies.find(a => a.id === agency) : undefined;
  const items = (data.state.kind === 'ready' ? (data.state.data.items as Row[] | undefined) : undefined) ?? [];
  return <Gate session={list.session}>{list.state.kind === 'error' ? <ErrorState status={list.state.status} message="دسترسی به پنل آژانس ممکن نیست."/> :
    <Shell title="پنل آژانس" intro="رزروها فقط از طریق کانال فروشِ متصل به آژانس به آن نسبت داده می‌شوند. کمیسیون طبق نرخ ثبت‌شده محاسبه می‌شود و پرداخت‌شدنش فقط در بخش تسویه مشخص است.">
      {list.state.kind === 'loading' ? <Loading/> : list.state.data.agencies.length === 0 ? <Empty>آژانسی به حساب شما متصل نشده است. مدیر مجموعه باید عضویت شما را ثبت کند.</Empty> : <>
        <label className="my-3 block text-sm">آژانس<select className={field} value={agency} aria-label="انتخاب آژانس" onChange={e => setAgency(e.target.value)}><option value="">انتخاب آژانس</option>{list.state.data.agencies.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        {current && <><p className="flex flex-wrap gap-2 text-xs"><span className="rounded bg-slate-200 px-2 py-0.5">کمیسیون: {fa(current.commission_bps / 100)}٪</span><span className="rounded bg-slate-200 px-2 py-0.5">افزودهٔ قیمت: {fa(current.markup_bps / 100)}٪</span>
          <span className={`rounded px-2 py-0.5 ${current.sales_channel_linked ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{current.sales_channel_linked ? 'کانال فروش متصل است' : 'کانال فروش متصل نشده؛ رزروی نسبت داده نمی‌شود'}</span></p>
          <Tabs value={tab} onChange={setTab} options={AGENCY_TABS}/>
          {data.state.kind === 'loading' ? <Loading/> : data.state.kind === 'error' ? <Failed status={data.state.status}/> : tab === 'report' ? (r => <div className="grid gap-2 sm:grid-cols-3" data-report>
            <div className="rounded-xl bg-white p-3"><h3 className="text-sm text-slate-500">تعداد رزرو</h3><p className="text-xl font-bold">{fa(r.bookings as number)}</p></div>
            <div className="rounded-xl bg-white p-3 text-sm"><h3 className="text-slate-500">به تفکیک وضعیت</h3>{Object.entries(r.by_status as Record<string, number>).map(([k, v]) => <p key={k} dir="ltr">{k}: {fa(v)}</p>)}{!Object.keys(r.by_status as object).length && <p>—</p>}</div>
            <div className="rounded-xl bg-white p-3 text-sm"><h3 className="text-slate-500">فروش تأییدشده</h3>{(r.confirmed_sales as {currency: string; amount: number}[]).map(s => <p key={s.currency}>{money(s.amount, s.currency)}</p>)}{!(r.confirmed_sales as unknown[]).length && <p>—</p>}</div></div>)(data.state.data)
            : <>{tab === 'commissions' && <p className="rounded-xl bg-white p-3 text-sm">{String(data.state.data.note)} {(data.state.data.totals as {currency: string; commission_amount: number}[]).map(t => <strong key={t.currency} className="mr-2">جمع: {money(t.commission_amount, t.currency)}</strong>)}</p>}
              {items.length === 0 ? <Empty>{tab === 'bookings' ? 'رزروی به این آژانس نسبت داده نشده است.' : tab === 'customers' ? 'مشتری‌ای ثبت نشده است.' : tab === 'commissions' ? 'رزرو تأییدشدهٔ دارای مبلغ وجود ندارد.' : 'تسویه‌ای ثبت نشده است.'}</Empty>
                : <Table columns={Object.keys(items[0])} rows={items} labels={{...FIN_LABELS, booking_reference: 'کد رزرو', service_type: 'خدمت', customer_id: 'مشتری', confirmed_at: 'تأیید', name: 'نام', bookings: 'تعداد رزرو', base_amount: 'مبلغ پایه', commission_bps: 'نرخ', commission_amount: 'کمیسیون'}}
                  render={{created_at: r => when(r.created_at as string), confirmed_at: r => when(r.confirmed_at as string), total_amount: r => money(r.total_amount, r.currency), amount: r => money(r.amount, r.currency), base_amount: r => money(r.base_amount, r.currency), commission_amount: r => money(r.commission_amount, r.currency),
                    commission_bps: r => `${fa((r.commission_bps as number) / 100)}٪`, id: r => <span dir="ltr">{String(r.id).slice(0, 8)}</span>, reservation_id: r => <span dir="ltr">{String(r.reservation_id).slice(0, 8)}</span>}}/>}</>}</>}
      </>}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Supplier settlements & contracts */
export function SupplierSettlements() {
  const s = useLoad<{items: Row[]}>('/supplier/settlements');
  const c = useLoad<{suppliers: Row[]; contracts: Row[]}>('/supplier/contracts');
  return <Gate session={s.session}>{s.state.kind === 'error' ? <ErrorState status={s.state.status} message="دسترسی به تسویه‌های تأمین‌کننده ممکن نیست."/> :
    <Shell title="تسویه و قراردادهای من" intro="فقط تأمین‌کننده‌هایی که عضویت شما برایشان ثبت شده است. مبلغ‌ها همان ردیف‌های ثبت‌شدهٔ تسویه‌اند." back={['بازگشت به پنل تأمین‌کننده', '/supplier']}>
      <h2 className="mt-4 font-bold">تأمین‌کننده و قرارداد</h2>
      {c.state.kind === 'loading' ? <Loading/> : c.state.kind === 'error' ? <Failed status={c.state.status}/> : c.state.data.suppliers.length === 0 ? <Empty>عضویتی در هیچ تأمین‌کننده‌ای برای این حساب ثبت نشده است.</Empty> : <>
        <Table columns={['name', 'type', 'status', 'lifecycle_status']} rows={c.state.data.suppliers} labels={{name: 'نام', type: 'نوع', status: 'وضعیت', lifecycle_status: 'مرحلهٔ همکاری'}}/>
        {c.state.data.contracts.length === 0 ? <Empty>قرارداد یا اتصال فنی برای این تأمین‌کننده ثبت نشده است.</Empty> : <Table columns={['provider_key', 'mode', 'configured']} rows={c.state.data.contracts} labels={{provider_key: 'اتصال', mode: 'حالت', configured: 'پیکربندی'}} render={{configured: r => r.configured ? 'انجام شده' : 'انجام نشده'}}/>}</>}
      <h2 className="mt-4 font-bold">تسویه‌ها</h2>
      {s.state.kind === 'loading' ? <Loading/> : s.state.data.items.length === 0 ? <Empty>تسویه‌ای ثبت نشده است.</Empty> : <Table columns={['id', 'reservation_id', 'amount', 'status', 'external_reference', 'created_at']} rows={s.state.data.items} labels={FIN_LABELS}
        render={{amount: r => money(r.amount, r.currency), created_at: r => when(r.created_at as string), id: r => <span dir="ltr">{String(r.id).slice(0, 8)}</span>}}/>}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Notification deliveries */
const CHANNEL: Record<string, string> = {in_app: 'وب و اپ', web: 'وب', app: 'اپ', push: 'پوش', sms: 'پیامک'};
export function NotificationDeliveries() {
  const [status, setStatus] = useState(''); const [channel, setChannel] = useState('');
  const q = new URLSearchParams(); if (status) q.set('status', status); if (channel) q.set('channel', channel);
  const d = useLoad<{items: Row[]}>(`/operations/notification-deliveries?${q}`);
  const [notice, setNotice] = useState<{ok: boolean; text: string} | null>(null);
  async function requeue(id: string) {setNotice(null); try {await d.api.post(`/operations/notification-deliveries/${id}/requeue`, {}); d.reload(); setNotice({ok: true, text: 'تحویل دوباره در صف ارسال قرار گرفت.'});} catch (e) {setNotice({ok: false, text: detailOf(e, 'انجام نشد.')});}}
  return <Gate session={d.session}>{d.state.kind === 'error' && d.state.status !== 503 ? <ErrorState status={d.state.status} message="دسترسی به وضعیت اعلان‌ها ممکن نیست."/> :
    <Shell title="وضعیت تحویل اعلان‌ها" intro="برای هر رویداد: گیرنده، کانال، قالب، وضعیت تحویل، شمارهٔ تلاش، پیوند و خوانده‌شدن. پیامک و پوش تا اتصال سرویس واقعی ارسال نمی‌شوند." back={['بازگشت به مرکز عملیات سفر', '/backoffice/trip-events']}>
      <div className="my-3 flex flex-wrap gap-3 text-sm"><label>کانال<select className={field} value={channel} onChange={e => setChannel(e.target.value)} aria-label="کانال"><option value="">همه</option>{Object.entries(CHANNEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>وضعیت<select className={field} value={status} onChange={e => setStatus(e.target.value)} aria-label="وضعیت تحویل"><option value="">همه</option>{['pending', 'not_sent', 'retry', 'delivered', 'dead_letter', 'pending_external'].map(s => <option key={s} value={s}>{s}</option>)}</select></label></div>
      <Notice n={notice}/>
      {d.state.kind === 'loading' ? <Loading/> : d.state.kind === 'error' ? <Failed status={d.state.status}/> : d.state.data.items.length === 0 ? <Empty>تحویلی با این شرایط ثبت نشده است.</Empty>
        : <Table columns={['channel', 'template', 'delivery_status', 'attempt', 'recipient_user_id', 'read', 'deep_link', 'action']} rows={d.state.data.items} labels={{channel: 'کانال', template: 'قالب', delivery_status: 'وضعیت تحویل', attempt: 'تلاش', recipient_user_id: 'گیرنده', read: 'خوانده‌شده', deep_link: 'پیوند', action: ''}}
          render={{channel: r => CHANNEL[r.channel as string] ?? String(r.channel), read: r => r.read ? 'بله' : 'خیر', deep_link: r => <span dir="ltr">{String(r.deep_link ?? '—')}</span>,
            action: r => ['dead_letter', 'failed'].includes(r.delivery_status as string) ? <button type="button" className="button secondary" onClick={() => void requeue(r.id as string)}>ارسال دوباره</button> : null}}/>}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Reference tours */
type TourRow = {id: string; title: string; status: string; departures_recorded: number; latest_departure: string | null; duration_nights: number | null; duration_days: number | null};
type Tour = TourRow & {description: string | null; destination_place_id: string | null; origin_place_id: string | null; transport_mode: string | null; board: string | null; guide_included: boolean | null; transfer_included: boolean | null;
  documents_required: string | null; cancellation_policy_text: string | null; itinerary: {day_no: number; title: string; description: string | null; place_id: string | null}[]; hotels: {hotel_id: string; nights: number | null}[];
  departures: {starts_jalali: string | null; ends_jalali: string | null; starts_on: string | null}[]; options: {transport: Record<string, string>; board: Record<string, string>}; sellable: boolean};
const tri = (v: boolean | null) => v === null ? '' : v ? 'yes' : 'no';
const untri = (v: string) => v === '' ? null : v === 'yes';

export function TourReference() {
  const [q, setQ] = useState(''); const [applied, setApplied] = useState('');
  const list = useLoad<{total: number; items: TourRow[]}>(`/admin/catalog/tours?limit=100${applied ? `&q=${encodeURIComponent(applied)}` : ''}`);
  const [id, setId] = useState('');
  const detail = useLoad<Tour>(id ? `/admin/catalog/tours/${id}` : null);
  const [draft, setTour] = useState<Tour | null>(null);
  const [notice, setNotice] = useState<{ok: boolean; text: string} | null>(null); const [busy, setBusy] = useState(false);
  const tour = draft && draft.id === id ? draft : detail.state.kind === 'ready' && detail.state.data.id === id ? detail.state.data : null;
  const set = <K extends keyof Tour>(k: K, v: Tour[K]) => {if (tour) setTour({...tour, [k]: v});};
  async function save(e: FormEvent) {
    e.preventDefault(); if (!tour || busy) return; setBusy(true); setNotice(null);
    try {
      const saved = await list.api.put<Tour>(`/admin/catalog/tours/${tour.id}`, {title_fa: tour.title, description: tour.description || null, origin_place_id: tour.origin_place_id || null, destination_place_id: tour.destination_place_id || null,
        duration_nights: tour.duration_nights, duration_days: tour.duration_days, transport_mode: tour.transport_mode || null, board: tour.board || null, guide_included: tour.guide_included, transfer_included: tour.transfer_included,
        documents_required: tour.documents_required || null, cancellation_policy_text: tour.cancellation_policy_text || null, status: tour.status,
        itinerary: tour.itinerary.map(d => ({day_no: d.day_no, title: d.title, description: d.description || null, place_id: d.place_id || null})), hotels: tour.hotels});
      setTour(saved); list.reload(); setNotice({ok: true, text: 'محتوای مرجع تور ذخیره شد.'});
    } catch (err) {setNotice({ok: false, text: detailOf(err, 'ذخیره انجام نشد.')});} finally {setBusy(false);}
  }
  const n = (v: string) => v === '' ? null : Number(v);
  return <Gate session={list.session}>{list.state.kind === 'error' ? <ErrorState status={list.state.status} message="دسترسی به تورهای مرجع ممکن نیست."/> :
    <Shell title="تورهای مرجع" intro="توضیح تور و تاریخ‌های ثبت‌شده در منبع. این رکوردها محصول قابل‌فروش نیستند: قیمت، ظرفیت، تأمین‌کننده و تاریخ حرکت آینده در این فرم وجود ندارد." back={['مدیریت هتل‌ها', '/admin/catalog']}>
      {!id && <><form className="my-3 flex flex-wrap items-end gap-2" onSubmit={e => {e.preventDefault(); setApplied(q);}}><label className="grow text-sm">جست‌وجو<input className={field} value={q} onChange={e => setQ(e.target.value)}/></label><button className="button primary">اعمال</button></form>
        {list.state.kind === 'loading' ? <Loading/> : list.state.data.items.length === 0 ? <Empty>تور مرجعی با این شرایط ثبت نشده است.</Empty> : <><p className="text-sm text-slate-500">{fa(list.state.data.total)} تور</p>
          <ul className="my-3 grid gap-2">{list.state.data.items.map(t => <li key={t.id}><button type="button" className="grid w-full gap-1 rounded-xl border border-slate-200 bg-white p-3 text-right text-sm sm:grid-cols-[2fr_1fr_1fr]" onClick={() => {setId(t.id); setNotice(null);}}>
            <strong>{t.title}</strong><span className="text-slate-500">{t.duration_nights !== null ? `${fa(t.duration_nights)} شب` : 'مدت نامشخص'} · {fa(t.departures_recorded)} تاریخ ثبت‌شده</span><span className="text-slate-500">{t.status === 'published' ? 'منتشرشده' : t.status === 'hidden' ? 'پنهان' : 'پیش‌نویس'} · غیرقابل‌فروش</span></button></li>)}</ul></>}</>}
      {id && (detail.state.kind === 'loading' || !tour ? <Loading/> : detail.state.kind === 'error' ? <Failed status={detail.state.status}/> : <form className="my-3 grid gap-3" onSubmit={save} aria-label="ویرایش تور مرجع">
        <div className="flex flex-wrap justify-between gap-2"><button type="button" className="button secondary" onClick={() => {setId(''); setTour(null); setNotice(null);}}>بازگشت به فهرست</button><button className="button primary" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیره'}</button></div>
        <Notice n={notice}/>
        <div className="grid gap-3 rounded-2xl bg-white p-4 sm:grid-cols-2">
          <label className="text-sm sm:col-span-2">عنوان<input className={field} value={tour.title} onChange={e => set('title', e.target.value)} required minLength={3} maxLength={200}/></label>
          <label className="text-sm">شناسهٔ مقصد در فهرست مرجع<input className={field} dir="ltr" value={tour.destination_place_id ?? ''} onChange={e => set('destination_place_id', e.target.value)} placeholder="مثلاً am-yerevan"/></label>
          <label className="text-sm">شناسهٔ مبدأ<input className={field} dir="ltr" value={tour.origin_place_id ?? ''} onChange={e => set('origin_place_id', e.target.value)}/></label>
          <label className="text-sm">تعداد شب<input className={field} type="number" min={0} max={60} value={tour.duration_nights ?? ''} onChange={e => set('duration_nights', n(e.target.value))}/></label>
          <label className="text-sm">تعداد روز<input className={field} type="number" min={1} max={61} value={tour.duration_days ?? ''} onChange={e => set('duration_days', n(e.target.value))}/></label>
          <label className="text-sm">حمل‌ونقل<select className={field} value={tour.transport_mode ?? ''} onChange={e => set('transport_mode', e.target.value || null)}><option value="">نامشخص</option>{Object.entries(tour.options.transport).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="text-sm">وعده<select className={field} value={tour.board ?? ''} onChange={e => set('board', e.target.value || null)}><option value="">نامشخص</option>{Object.entries(tour.options.board).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="text-sm">راهنما<select className={field} value={tri(tour.guide_included)} onChange={e => set('guide_included', untri(e.target.value))}><option value="">نامشخص</option><option value="yes">دارد</option><option value="no">ندارد</option></select></label>
          <label className="text-sm">ترانسفر<select className={field} value={tri(tour.transfer_included)} onChange={e => set('transfer_included', untri(e.target.value))}><option value="">نامشخص</option><option value="yes">دارد</option><option value="no">ندارد</option></select></label>
          <label className="text-sm">وضعیت<select className={field} value={tour.status} onChange={e => set('status', e.target.value)}><option value="draft">پیش‌نویس</option><option value="published">منتشرشده (مرجع)</option><option value="hidden">پنهان</option></select></label>
          <label className="text-sm sm:col-span-2">معرفی<textarea className={field} rows={3} value={tour.description ?? ''} onChange={e => set('description', e.target.value)}/></label>
          <label className="text-sm">مدارک لازم<textarea className={field} rows={2} value={tour.documents_required ?? ''} onChange={e => set('documents_required', e.target.value)}/></label>
          <label className="text-sm">قوانین لغو<textarea className={field} rows={2} value={tour.cancellation_policy_text ?? ''} onChange={e => set('cancellation_policy_text', e.target.value)}/></label></div>
        <div className="grid gap-2 rounded-2xl bg-white p-4"><h2 className="font-bold">برنامهٔ سفر</h2>
          {tour.itinerary.map((d, i) => <div key={i} className="grid gap-2 rounded-xl border border-dashed border-slate-300 p-3 sm:grid-cols-[5rem_1fr_auto]" data-day>
            <label className="text-sm">روز<input className={field} type="number" min={1} max={60} value={d.day_no} onChange={e => set('itinerary', tour.itinerary.map((x, j) => j === i ? {...x, day_no: Number(e.target.value)} : x))}/></label>
            <label className="text-sm">عنوان روز<input className={field} value={d.title} required minLength={2} onChange={e => set('itinerary', tour.itinerary.map((x, j) => j === i ? {...x, title: e.target.value} : x))}/></label>
            <button type="button" className="self-end text-sm text-rose-700" onClick={() => set('itinerary', tour.itinerary.filter((_, j) => j !== i))}>حذف روز</button></div>)}
          <button type="button" className="button secondary" onClick={() => set('itinerary', [...tour.itinerary, {day_no: Math.max(0, ...tour.itinerary.map(d => d.day_no)) + 1, title: '', description: null, place_id: null}])}>افزودن روز</button></div>
        <div className="rounded-2xl bg-white p-4 text-sm"><h2 className="font-bold">تاریخ‌های ثبت‌شده در منبع <span className="font-normal text-slate-500">(فقط سابقه؛ قابل‌فروش نیست)</span></h2>
          {tour.departures.length ? <ul className="mt-2 flex flex-wrap gap-2">{tour.departures.map((d, i) => <li key={i} className="rounded bg-slate-100 px-2 py-1" dir="ltr">{d.starts_jalali ?? '—'}{d.starts_on ? '' : ' (نامعتبر)'}</li>)}</ul> : <p className="mt-1 text-slate-500">تاریخی در منبع ثبت نشده است.</p>}</div>
        <div className="flex justify-end"><button className="button primary" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیره'}</button></div>
      </form>)}
    </Shell>}</Gate>;
}
