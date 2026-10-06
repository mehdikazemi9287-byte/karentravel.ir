'use client';
/* Partner administration, supplier hotels, finance accounting/commission ledger, customer quotes, agency quotes,
   provider mapping editor. Built from the same primitives and tokens as the other operational screens. */
import {FormEvent, useState} from 'react';
import {ErrorState} from './ConnectedViews';
import {Empty, Failed, FIN_LABELS, Gate, Loading, Notice, Shell, Table, Tabs, detailOf, fa, field, money, useLoad, when} from './PanelViews';

type Row = Record<string, unknown>;
type Note = {ok: boolean; text: string} | null;
const QUOTE_FA: Record<string, string> = {sent: 'ارسال‌شده', accepted: 'پذیرفته‌شده', declined: 'ردشده', expired: 'منقضی', cancelled: 'لغوشده', booked: 'رزروشده'};
const COMMISSION_FA: Record<string, string> = {accrued: 'ثبت‌شده', approved: 'تأییدشده', settled: 'تسویه‌شده', reversed: 'برگشت‌خورده'};
const values = (form: HTMLFormElement) => Object.fromEntries(new FormData(form)) as Record<string, string>;

function useAction(reload: () => void) {
  const [notice, setNotice] = useState<Note>(null); const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<unknown>, done: string, form?: HTMLFormElement) {
    if (busy) return; setBusy(true); setNotice(null);
    try {await fn(); form?.reset(); reload(); setNotice({ok: true, text: done});} catch (e) {setNotice({ok: false, text: detailOf(e, 'انجام نشد.')});} finally {setBusy(false);}
  }
  return {notice, busy, run};
}

/* ------------------------------------------------------------------ Partners administration */
type Member = {user_id: number; name: string | null};
type Partners = {suppliers: {id: string; name: string; type: string; status: string; lifecycle_status: string; members: Member[]; hotels: {hotel_id: string; name: string | null}[]}[];
  agencies: {id: string; name: string; status: string; commission_bps: number; markup_bps: number; sales_channel_id: string | null; credit_account_id: string | null; members: Member[]}[];
  sales_channels: {id: string; name: string; type: string; agency_id: string | null}[]; credit_accounts: {id: string; currency: string; limit_amount: number}[]; agency_users: Member[]; supplier_users: Member[]};

export function PartnersAdmin() {
  const p = useLoad<Partners>('/admin/partners'); const [tab, setTab] = useState('agencies'); const a = useAction(p.reload); const api = p.api;
  const submit = (e: FormEvent<HTMLFormElement>, fn: (v: Record<string, string>) => Promise<unknown>, done: string) => {e.preventDefault(); const f = e.currentTarget; void a.run(() => fn(values(f)), done, f);};
  return <Gate session={p.session}>{p.state.kind === 'error' ? <ErrorState status={p.state.status} message="مدیریت همکاران فقط برای مدیر مجموعه است."/> :
    <Shell title="مدیریت تأمین‌کنندگان و آژانس‌ها" intro="تعریف همکار، عضویت کاربران، کانال فروش آژانس و واگذاری هتل به تأمین‌کننده. هر تغییر در سابقهٔ ممیزی ثبت می‌شود." back={['مدیریت کاربران', '/admin']}>
      <Tabs value={tab} onChange={setTab} options={{agencies: 'آژانس‌ها', suppliers: 'تأمین‌کنندگان'}}/>
      <Notice n={a.notice}/>
      {p.state.kind === 'loading' ? <Loading/> : tab === 'agencies' ? (d => <>
        <form className="my-3 grid gap-2 rounded-2xl bg-white p-4 sm:grid-cols-[2fr_1fr_auto]" aria-label="آژانس جدید" onSubmit={e => submit(e, v => api.post('/admin/partners/agencies', {display_name: v.display_name, commission_bps: Math.round(Number(v.commission || 0) * 100)}), 'آژانس ایجاد شد.')}>
          <label className="text-sm">نام آژانس<input name="display_name" required minLength={2} maxLength={180} className={field}/></label><label className="text-sm">کمیسیون (٪)<input name="commission" type="number" min={0} max={50} step="0.01" defaultValue={0} className={field}/></label><button className="button primary self-end" disabled={a.busy}>ایجاد آژانس</button></form>
        {d.agencies.length === 0 ? <Empty>آژانسی تعریف نشده است.</Empty> : <div className="grid gap-3">{d.agencies.map(ag => <article key={ag.id} className="grid gap-2 rounded-2xl bg-white p-4 text-sm" data-agency={ag.name}>
          <h2 className="font-bold">{ag.name} <span className="text-xs font-normal text-slate-500">کمیسیون {fa(ag.commission_bps / 100)}٪</span></h2>
          {ag.sales_channel_id ? <p className="text-emerald-700">کانال فروش: {d.sales_channels.find(c => c.id === ag.sales_channel_id)?.name ?? '—'}</p>
            : <form className="flex flex-wrap items-end gap-2" aria-label={`کانال فروش ${ag.name}`} onSubmit={e => submit(e, v => api.post(`/admin/partners/agencies/${ag.id}/sales-channel`, {name: v.name}), 'کانال فروش آژانس ساخته و متصل شد.')}>
              <label className="grow">نام کانال فروش<input name="name" required minLength={3} maxLength={160} className={field}/></label><button className="button secondary" disabled={a.busy}>ساخت کانال فروش</button></form>}
          <div><span className="text-slate-500">اعضا: </span>{ag.members.length ? ag.members.map(mb => <span key={mb.user_id} className="mr-1 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5">{mb.name}
            <button type="button" aria-label={`حذف ${mb.name}`} className="text-rose-700" onClick={() => void a.run(() => api.delete(`/admin/partners/agencies/${ag.id}/members/${mb.user_id}`, {}), 'عضویت حذف شد.')}>×</button></span>) : 'بدون عضو'}</div>
          <form className="flex flex-wrap items-end gap-2" aria-label={`عضو جدید ${ag.name}`} onSubmit={e => submit(e, v => api.post(`/agency/${ag.id}/members`, {user_id: Number(v.user_id)}), 'عضو اضافه شد.')}>
            <label className="grow">افزودن کاربر آژانس<select name="user_id" required className={field} defaultValue=""><option value="" disabled>انتخاب کاربر</option>{d.agency_users.filter(u => !ag.members.some(mb => mb.user_id === u.user_id)).map(u => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}</select></label><button className="button secondary" disabled={a.busy}>افزودن عضو</button></form>
          <form className="flex flex-wrap items-end gap-2" aria-label={`اعتبار ${ag.name}`} onSubmit={e => submit(e, v => api.put(`/admin/partners/agencies/${ag.id}/credit-account`, {credit_account_id: v.credit_account_id || null}), 'حساب اعتباری آژانس به‌روز شد.')}>
            <label className="grow">حساب اعتباری<select name="credit_account_id" className={field} defaultValue={ag.credit_account_id ?? ''}><option value="">بدون حساب اعتباری</option>{d.credit_accounts.map(c => <option key={c.id} value={c.id}>{money(c.limit_amount, c.currency)} — {c.id.slice(0, 8)}</option>)}</select></label><button className="button secondary" disabled={a.busy}>ثبت</button></form>
        </article>)}</div>}</>)(p.state.data) : (d => <>
        <form className="my-3 grid gap-2 rounded-2xl bg-white p-4 sm:grid-cols-[2fr_1fr_auto]" aria-label="تأمین‌کنندهٔ جدید" onSubmit={e => submit(e, v => api.post('/admin/partners/suppliers', {display_name: v.display_name, supplier_type: v.supplier_type}), 'تأمین‌کننده ایجاد شد.')}>
          <label className="text-sm">نام تأمین‌کننده<input name="display_name" required minLength={2} maxLength={180} className={field}/></label>
          <label className="text-sm">نوع<select name="supplier_type" className={field} defaultValue="hotel">{Object.entries({hotel: 'هتل', tour: 'تور', transport: 'حمل‌ونقل', experience: 'تجربه', flight: 'پرواز', other: 'سایر'}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label><button className="button primary self-end" disabled={a.busy}>ایجاد تأمین‌کننده</button></form>
        {d.suppliers.length === 0 ? <Empty>تأمین‌کننده‌ای تعریف نشده است.</Empty> : <div className="grid gap-3">{d.suppliers.map(s => <article key={s.id} className="grid gap-2 rounded-2xl bg-white p-4 text-sm" data-supplier={s.name}>
          <h2 className="font-bold">{s.name} <span className="text-xs font-normal text-slate-500" dir="ltr">{s.type} · {s.status} · {s.lifecycle_status}</span></h2>
          <div><span className="text-slate-500">اعضا: </span>{s.members.length ? s.members.map(mb => <span key={mb.user_id} className="mr-1 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5">{mb.name}
            <button type="button" aria-label={`حذف ${mb.name}`} className="text-rose-700" onClick={() => void a.run(() => api.delete(`/admin/partners/suppliers/${s.id}/members/${mb.user_id}`, {}), 'عضویت حذف شد.')}>×</button></span>) : 'بدون عضو'}</div>
          <form className="flex flex-wrap items-end gap-2" aria-label={`عضو جدید ${s.name}`} onSubmit={e => submit(e, v => api.post(`/admin/partners/suppliers/${s.id}/members`, {user_id: Number(v.user_id)}), 'عضو اضافه شد.')}>
            <label className="grow">افزودن کاربر تأمین‌کننده<select name="user_id" required className={field} defaultValue=""><option value="" disabled>انتخاب کاربر</option>{d.supplier_users.filter(u => !s.members.some(mb => mb.user_id === u.user_id)).map(u => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}</select></label><button className="button secondary" disabled={a.busy}>افزودن عضو</button></form>
          <div><span className="text-slate-500">هتل‌های واگذارشده: </span>{s.hotels.length ? s.hotels.map(h => <span key={h.hotel_id} className="mr-1 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5">{h.name ?? h.hotel_id}
            <button type="button" aria-label={`حذف ${h.name ?? h.hotel_id}`} className="text-rose-700" onClick={() => void a.run(() => api.delete(`/admin/partners/suppliers/${s.id}/hotels/${encodeURIComponent(h.hotel_id)}`, {}), 'واگذاری هتل حذف شد.')}>×</button></span>) : 'هیچ'}</div>
          <form className="flex flex-wrap items-end gap-2" aria-label={`واگذاری هتل ${s.name}`} onSubmit={e => submit(e, v => api.post(`/admin/partners/suppliers/${s.id}/hotels`, {hotel_id: v.hotel_id.trim()}), 'هتل به تأمین‌کننده واگذار شد.')}>
            <label className="grow">شناسهٔ هتل در فهرست مرجع<input name="hotel_id" required maxLength={40} dir="ltr" className={field}/></label><button className="button secondary" disabled={a.busy}>واگذاری هتل</button></form>
        </article>)}</div>}</>)(p.state.data)}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Supplier: my hotels and provider ids */
type MyHotel = {hotel_id: string; name: string; status: string; content_complete: boolean; mappings: {id: number; provider: string; provider_hotel_id: string; status: string}[]};
export function SupplierHotels() {
  const h = useLoad<{items: MyHotel[]}>('/supplier/hotels'); const a = useAction(h.reload);
  return <Gate session={h.session}>{h.state.kind === 'error' ? <ErrorState status={h.state.status} message="دسترسی به هتل‌های تأمین‌کننده ممکن نیست."/> :
    <Shell title="هتل‌های من و شناسهٔ سامانهٔ رزرو" intro="هتل‌هایی که مدیر مجموعه به تأمین‌کنندهٔ شما واگذار کرده است. شناسهٔ هتل در سامانهٔ خودتان را ثبت کنید؛ تا تأیید کارن‌سیر و اتصال منبع نرخ، نرخی نمایش داده نمی‌شود." back={['بازگشت به پنل تأمین‌کننده', '/supplier']}>
      <Notice n={a.notice}/>
      {h.state.kind === 'loading' ? <Loading/> : h.state.data.items.length === 0 ? <Empty>هتلی به تأمین‌کنندهٔ شما واگذار نشده است.</Empty> : <div className="grid gap-3">{h.state.data.items.map(x => <article key={x.hotel_id} className="grid gap-2 rounded-2xl bg-white p-4 text-sm" data-hotel={x.hotel_id}>
        <h2 className="font-bold">{x.name}</h2><p className="text-xs text-slate-500">{x.status === 'published' ? 'منتشرشده' : 'منتشرنشده'} · محتوای {x.content_complete ? 'کامل' : 'ناقص'} · نرخ: متصل نیست</p>
        {x.mappings.length ? <ul className="grid gap-1">{x.mappings.map(mp => <li key={mp.id} className="flex flex-wrap gap-2"><span dir="ltr">{mp.provider} · {mp.provider_hotel_id}</span><span className={`rounded px-2 text-xs ${mp.status === 'verified' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{mp.status === 'verified' ? 'تأییدشده' : 'در انتظار تأیید کارن‌سیر'}</span></li>)}</ul> : <p className="text-slate-500">شناسه‌ای ثبت نشده است.</p>}
        <form className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]" aria-label={`شناسهٔ جدید ${x.hotel_id}`} onSubmit={e => {e.preventDefault(); const f = e.currentTarget; const v = values(f); void a.run(() => h.api.post(`/supplier/hotels/${encodeURIComponent(x.hotel_id)}/provider-mappings`, {provider: v.provider.trim(), provider_hotel_id: v.provider_hotel_id.trim()}), 'شناسه ثبت شد و منتظر تأیید است.', f);}}>
          <label>سامانه<input name="provider" required pattern="[a-z0-9_-]{2,40}" dir="ltr" placeholder="grs" className={field}/></label><label>شناسهٔ هتل در آن سامانه<input name="provider_hotel_id" required maxLength={120} dir="ltr" className={field}/></label><button className="button secondary self-end" disabled={a.busy}>ثبت شناسه</button></form>
      </article>)}</div>}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Finance: accounting views and commission ledger */
type Section = {formula: string; items: Row[]};
type Accounting = {receivables: Section; supplier_payables: Section; commissions: Section; organization_credit: Section; tax_summary: Section; approved_chart_of_accounts: boolean};
type Commissions = {items: Row[]; not_posted: Row[]};
const accLabels = () => ({...FIN_LABELS, invoice_number: 'فاکتور', invoiced: 'صادرشده', tax: 'مالیات', captured: 'وصول‌شده', refunded: 'مستردشده', outstanding: 'مانده', supplier_name: 'تأمین‌کننده', count: 'تعداد', agency_name: 'آژانس', base_amount: 'مبلغ پایه',
  commission_bps: 'نرخ', booking_reference: 'کد رزرو', external_reference: 'مرجع پرداخت', action: '', used: 'مصرف‌شده', available: 'در دسترس', reserved: 'رزروشده', invoices: 'تعداد فاکتور', tax_amount: 'جمع مالیات', taxable_subtotal: 'جمع مشمول', credit_account_id: 'حساب'});
const cur = (k: string) => (r: Row) => money(r[k], r.currency);

export function FinanceAccounting() {
  const acc = useLoad<Accounting>('/finance/accounting'); const com = useLoad<Commissions>('/finance/commissions'); const [tab, setTab] = useState('commissions');
  const a = useAction(() => {acc.reload(); com.reload();}); const api = acc.api;
  const act = (r: Row) => r.status === 'accrued' ? <span className="flex flex-wrap gap-1"><button type="button" className="button secondary" onClick={() => void a.run(() => api.post(`/finance/commissions/${r.id}/approve`, {}), 'کمیسیون تأیید شد.')}>تأیید</button>
      <button type="button" className="button secondary" onClick={() => {const reason = window.prompt('دلیل برگشت'); if (reason) void a.run(() => api.post(`/finance/commissions/${r.id}/reverse`, {reason}), 'ثبت کمیسیون برگشت خورد.');}}>برگشت</button></span>
    : r.status === 'approved' ? <form className="flex flex-wrap gap-1" aria-label="تسویهٔ کمیسیون" onSubmit={e => {e.preventDefault(); const f = e.currentTarget; void a.run(() => api.post(`/finance/commissions/${r.id}/settle`, {external_reference: values(f).ref}), 'کمیسیون تسویه شد.', f);}}>
      <input name="ref" required minLength={3} maxLength={160} placeholder="مرجع پرداخت" dir="ltr" className="w-32 rounded-lg border border-slate-300 p-1 text-sm"/><button className="button secondary">تسویه</button></form> : null;
  const section = (s: Section, columns: string[], render: Record<string, (r: Row) => React.ReactNode>, empty: string) => <><p className="rounded-xl bg-white p-3 text-xs text-slate-600" dir="ltr">{s.formula}</p>{s.items.length === 0 ? <Empty>{empty}</Empty> : <Table columns={columns} rows={s.items} labels={accLabels()} render={render}/>}</>;
  return <Gate session={acc.session}>{acc.state.kind === 'error' ? <ErrorState status={acc.state.status} message="دسترسی به حسابداری ممکن نیست."/> :
    <Shell title="حسابداری و دفتر کمیسیون" intro="همهٔ ارقام جمع ردیف‌های ثبت‌شده با فرمول نوشته‌شده‌اند. این نما جایگزین دفاتر قانونی نیست و سرفصل حساب تأییدشده ندارد." back={['رکوردهای مالی', '/finance/records']}>
      <Tabs value={tab} onChange={setTab} options={{commissions: 'دفتر کمیسیون', receivables: 'مطالبات', supplier_payables: 'بدهی به تأمین‌کننده', organization_credit: 'اعتبار سازمانی', tax_summary: 'خلاصهٔ مالیات'}}/>
      <Notice n={a.notice}/>
      {acc.state.kind === 'loading' || com.state.kind === 'loading' ? <Loading/> : com.state.kind === 'error' ? <Failed status={com.state.status}/> : tab === 'commissions' ? <>
        <h2 className="mt-3 font-bold">رزروهای تأییدشدهٔ آژانس بدون ثبت کمیسیون</h2>
        {com.state.data.not_posted.length === 0 ? <Empty>رزرو ثبت‌نشده‌ای وجود ندارد.</Empty> : <Table columns={['agency_name', 'booking_reference', 'base_amount', 'commission_bps', 'amount', 'action']} rows={com.state.data.not_posted} labels={accLabels()}
          render={{base_amount: cur('base_amount'), amount: cur('amount'), commission_bps: r => `${fa((r.commission_bps as number) / 100)}٪`, action: r => <button type="button" className="button secondary" onClick={() => void a.run(() => api.post('/finance/commissions/accrue', {reservation_id: r.reservation_id}), 'کمیسیون در دفتر ثبت شد.')}>ثبت در دفتر</button>}}/>}
        <h2 className="mt-3 font-bold">دفتر کمیسیون</h2>
        {com.state.data.items.length === 0 ? <Empty>ثبتی در دفتر کمیسیون نیست.</Empty> : <Table columns={['agency_name', 'base_amount', 'commission_bps', 'amount', 'status', 'external_reference', 'created_at', 'action']} rows={com.state.data.items} labels={accLabels()}
          render={{base_amount: cur('base_amount'), amount: cur('amount'), commission_bps: r => `${fa((r.commission_bps as number) / 100)}٪`, status: r => COMMISSION_FA[r.status as string] ?? String(r.status), created_at: r => when(r.created_at as string), action: act}}/>}</>
        : tab === 'receivables' ? section(acc.state.data.receivables, ['invoice_number', 'invoiced', 'tax', 'captured', 'refunded', 'outstanding'], {invoiced: cur('invoiced'), tax: cur('tax'), captured: cur('captured'), refunded: cur('refunded'), outstanding: cur('outstanding')}, 'فاکتور صادرشدهٔ دارای مانده وجود ندارد.')
        : tab === 'supplier_payables' ? section(acc.state.data.supplier_payables, ['supplier_name', 'count', 'amount'], {amount: cur('amount')}, 'تسویهٔ در انتظار پرداختی وجود ندارد.')
        : tab === 'organization_credit' ? section(acc.state.data.organization_credit, Object.keys(acc.state.data.organization_credit.items[0] ?? {credit_account_id: 1}).filter(k => k !== 'organization_id'), {credit_account_id: r => <span dir="ltr">{String(r.credit_account_id).slice(0, 8)}</span>, limit_amount: cur('limit_amount')}, 'حساب اعتباری ثبت نشده است.')
        : section(acc.state.data.tax_summary, ['currency', 'invoices', 'taxable_subtotal', 'tax_amount'], {taxable_subtotal: cur('taxable_subtotal'), tax_amount: cur('tax_amount')}, 'فاکتور صادرشده‌ای وجود ندارد.')}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Customer: quotes from agencies */
type MyQuote = {id: string; agency_name: string | null; offer_title: string; amount: number; currency: string; valid_until: string; status: string; note: string | null; booking: {offer_id: string} | null};
export function MyQuotes() {
  const q = useLoad<{items: MyQuote[]}>('/me/agency-quotes'); const a = useAction(q.reload);
  return <Gate session={q.session}>{q.state.kind === 'error' ? <ErrorState status={q.state.status} message="دریافت پیشنهادهای قیمت ممکن نیست."/> :
    <Shell title="پیشنهادهای قیمت آژانس" intro="هر پیشنهاد به یک پیشنهاد واقعی تأمین‌کننده با همان قیمت اشاره می‌کند و تا زمان اعتبارش قابل پذیرش است. پذیرفتن پیشنهاد، رزرو یا پرداخت نیست." back={['حساب من', '/account']}>
      <Notice n={a.notice}/>
      {q.state.kind === 'loading' ? <Loading/> : q.state.data.items.length === 0 ? <Empty>پیشنهاد قیمتی برای شما ثبت نشده است.</Empty> : <div className="grid gap-3">{q.state.data.items.map(x => <article key={x.id} className="grid gap-1 rounded-2xl bg-white p-4 text-sm" data-quote={x.id}>
        <h2 className="font-bold">{x.offer_title}</h2><p>{money(x.amount, x.currency)} · {x.agency_name ?? 'آژانس'} · اعتبار تا {when(x.valid_until)}</p>{x.note && <p className="text-slate-600">{x.note}</p>}
        <p><span className="rounded bg-slate-200 px-2 py-0.5 text-xs">{QUOTE_FA[x.status] ?? x.status}</span></p>
        {x.status === 'sent' && <div className="mt-1 flex flex-wrap gap-2"><button type="button" className="button primary" disabled={a.busy} onClick={() => void a.run(() => q.api.post(`/me/agency-quotes/${x.id}/decision`, {decision: 'accept'}), 'پیشنهاد پذیرفته شد. اکنون می‌توانید همین خدمت را از مسیر رزرو ثبت کنید.')}>می‌پذیرم</button>
          <button type="button" className="button secondary" disabled={a.busy} onClick={() => void a.run(() => q.api.post(`/me/agency-quotes/${x.id}/decision`, {decision: 'decline'}), 'پیشنهاد رد شد.')}>نمی‌پذیرم</button></div>}
        {x.status === 'accepted' && <p className="text-emerald-700">پذیرفته‌اید. رزرو این خدمت روی کانال همین آژانس ثبت می‌شود.</p>}
      </article>)}</div>}
    </Shell>}</Gate>;
}

/* ------------------------------------------------------------------ Agency: quotes tab */
type Quote = {id: string; offer_title: string; customer_name: string | null; customer_user_id: number; amount: number; currency: string; valid_until: string; status: string; reservation_id: string | null};
export function AgencyQuotes({agencyId}: {agencyId: string}) {
  const q = useLoad<{sales_channel_linked: boolean; items: Quote[]}>(`/agency/${agencyId}/quotes`);
  const offers = useLoad<{items: {id: string; title: string; amount: number; currency: string; valid_until: string}[]}>(`/agency/${agencyId}/offers`);
  const customers = useLoad<{items: {customer_id: number; name: string | null}[]}>(`/agency/${agencyId}/customers`); const a = useAction(q.reload);
  if (q.state.kind === 'loading') return <Loading/>; if (q.state.kind === 'error') return <Failed status={q.state.status}/>;
  const known = customers.state.kind === 'ready' ? customers.state.data.items : [];
  return <div data-quotes>
    <Notice n={a.notice}/>
    {!q.state.data.sales_channel_linked ? <Empty>تا کانال فروش آژانس ثبت نشود، پیشنهاد قیمت قابل صدور نیست.</Empty> : <form className="my-3 grid gap-2 rounded-2xl bg-white p-4 sm:grid-cols-2" aria-label="پیشنهاد قیمت جدید" onSubmit={e => {e.preventDefault(); const f = e.currentTarget; const v = values(f);
      void a.run(() => q.api.post(`/agency/${agencyId}/quotes`, {offer_id: v.offer_id, customer_user_id: Number(v.customer_known || v.customer_user_id), note: v.note || null}), 'پیشنهاد قیمت با همان قیمت تأمین‌کننده برای مشتری ثبت شد.', f);}}>
      <label className="text-sm sm:col-span-2">پیشنهاد فعال تأمین‌کننده<select name="offer_id" required className={field} defaultValue=""><option value="" disabled>{offers.state.kind === 'ready' && offers.state.data.items.length === 0 ? 'پیشنهاد فعالی وجود ندارد' : 'انتخاب پیشنهاد'}</option>
        {offers.state.kind === 'ready' && offers.state.data.items.map(o => <option key={o.id} value={o.id}>{o.title} — {money(o.amount, o.currency)}</option>)}</select></label>
      <label className="text-sm">مشتری قبلی<select name="customer_known" className={field} defaultValue=""><option value="">—</option>{known.map(c => <option key={c.customer_id} value={c.customer_id}>{c.name ?? c.customer_id}</option>)}</select></label>
      <label className="text-sm">یا شناسهٔ کاربری مشتری<input name="customer_user_id" type="number" min={1} className={field} dir="ltr"/></label>
      <label className="text-sm sm:col-span-2">یادداشت برای مشتری<input name="note" maxLength={1000} className={field}/></label><button className="button primary sm:col-span-2" disabled={a.busy}>ثبت پیشنهاد قیمت</button></form>}
    {q.state.data.items.length === 0 ? <Empty>پیشنهاد قیمتی ثبت نشده است.</Empty> : <Table columns={['offer_title', 'customer_name', 'amount', 'valid_until', 'status', 'action']} rows={q.state.data.items as unknown as Row[]}
      labels={{offer_title: 'خدمت', customer_name: 'مشتری', amount: 'قیمت تأمین‌کننده', valid_until: 'اعتبار تا', status: 'وضعیت', action: ''}}
      render={{amount: cur('amount'), valid_until: r => when(r.valid_until as string), status: r => QUOTE_FA[r.status as string] ?? String(r.status),
        action: r => <span className="flex flex-wrap items-center gap-1">{r.status === 'accepted' && <form className="flex flex-wrap gap-1" aria-label="وصل به رزرو" onSubmit={e => {e.preventDefault(); const f = e.currentTarget; void a.run(() => q.api.post(`/agency/${agencyId}/quotes/${r.id}/link-booking`, {reservation_id: values(f).reservation_id.trim()}), 'پیشنهاد به رزرو مشتری وصل شد.', f);}}>
          <input name="reservation_id" required minLength={36} maxLength={36} placeholder="شناسهٔ رزرو مشتری" dir="ltr" className="w-40 rounded-lg border border-slate-300 p-1 text-sm"/><button className="button secondary" disabled={a.busy}>وصل به رزرو</button></form>}
          {['sent', 'accepted'].includes(r.status as string) && <button type="button" className="button secondary" disabled={a.busy} onClick={() => void a.run(() => q.api.post(`/agency/${agencyId}/quotes/${r.id}/cancel`, {}), 'پیشنهاد لغو شد.')}>لغو</button>}</span>}}/>}
  </div>;
}

/* ------------------------------------------------------------------ Catalog admin: provider / room / rate-plan mapping editor */
type Mapping = {id: number; provider: string; provider_hotel_id: string; status: string; rooms: {id: number; room_type_id: number; provider_room_id: string}[]; rate_plans: {id: number; provider_rate_plan_id: string; board: string | null; refundable: boolean | null}[]};
type HotelMaps = {id: string; provider_mappings: Mapping[]; room_types: {id: number; name_fa: string}[]};
const BOARD: Record<string, string> = {RO: 'بدون وعده', BB: 'صبحانه', HB: 'نیم‌پانسیون', FB: 'تمام‌پانسیون', AI: 'همه‌چیز رایگان', UAI: 'اولترا آل‌اینکلوسیو'};
export function ProviderMappings({hotelId}: {hotelId: string}) {
  const h = useLoad<HotelMaps>(`/admin/catalog/hotels/${encodeURIComponent(hotelId)}`); const a = useAction(h.reload); const api = h.api;
  const submit = (e: FormEvent<HTMLFormElement>, fn: (v: Record<string, string>) => Promise<unknown>, done: string) => {e.preventDefault(); const f = e.currentTarget; void a.run(() => fn(values(f)), done, f);};
  if (h.state.kind === 'loading') return <Loading/>; if (h.state.kind === 'error') return <Failed status={h.state.status}/>;
  const d = h.state.data;
  return <div className="grid gap-3 text-sm" data-mappings>
    <Notice n={a.notice}/>
    {d.provider_mappings.length === 0 && <Empty>نگاشتی ثبت نشده است؛ بدون نگاشت تأییدشده نرخی نمایش داده نمی‌شود.</Empty>}
    {d.provider_mappings.map(mp => <div key={mp.id} className="grid gap-2 rounded-xl border border-slate-200 p-3" data-mapping={mp.provider_hotel_id}>
      <p className="flex flex-wrap items-center gap-2"><strong dir="ltr">{mp.provider} · {mp.provider_hotel_id}</strong><span className={`rounded px-2 text-xs ${mp.status === 'verified' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{mp.status === 'verified' ? 'تأییدشده' : 'تأییدنشده'}</span>
        {mp.status !== 'verified' && <button type="button" className="button secondary" disabled={a.busy} onClick={() => void a.run(() => api.post(`/admin/catalog/provider-mappings/${mp.id}/verify`, {}), 'نگاشت تأیید شد.')}>تأیید با سند تأمین‌کننده</button>}</p>
      <p className="text-slate-600">اتاق‌ها: {mp.rooms.length ? mp.rooms.map(r => `${d.room_types.find(t => t.id === r.room_type_id)?.name_fa ?? r.room_type_id} ↔ ${r.provider_room_id}`).join(' · ') : '—'}</p>
      <p className="text-slate-600">طرح‌های نرخ: {mp.rate_plans.length ? mp.rate_plans.map(r => `${r.provider_rate_plan_id} (${r.board ? BOARD[r.board] : 'وعده نامشخص'}، ${r.refundable === null ? 'استرداد نامشخص' : r.refundable ? 'قابل استرداد' : 'غیرقابل استرداد'})`).join(' · ') : '—'}</p>
      <form className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]" aria-label={`اتاق ${mp.provider_hotel_id}`} onSubmit={e => submit(e, v => api.post(`/admin/catalog/provider-mappings/${mp.id}/rooms`, {room_type_id: Number(v.room_type_id), provider_room_id: v.provider_room_id.trim()}), 'نگاشت اتاق ثبت شد.')}>
        <label>نوع اتاق کارن‌سیر<select name="room_type_id" required className={field} defaultValue=""><option value="" disabled>{d.room_types.length ? 'انتخاب' : 'ابتدا نوع اتاق را ذخیره کنید'}</option>{d.room_types.map(t => <option key={t.id} value={t.id}>{t.name_fa}</option>)}</select></label>
        <label>شناسهٔ اتاق نزد تأمین‌کننده<input name="provider_room_id" required maxLength={120} dir="ltr" className={field}/></label><button className="button secondary self-end" disabled={a.busy}>افزودن اتاق</button></form>
      <form className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_auto]" aria-label={`طرح نرخ ${mp.provider_hotel_id}`} onSubmit={e => submit(e, v => api.post(`/admin/catalog/provider-mappings/${mp.id}/rate-plans`, {provider_rate_plan_id: v.plan.trim(), board: v.board || null, refundable: v.refundable === '' ? null : v.refundable === 'yes'}), 'طرح نرخ ثبت شد (بدون مبلغ).')}>
        <label>شناسهٔ طرح نرخ<input name="plan" required maxLength={120} dir="ltr" className={field}/></label><label>وعده<select name="board" className={field} defaultValue=""><option value="">نامشخص</option>{Object.entries(BOARD).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>استرداد<select name="refundable" className={field} defaultValue=""><option value="">نامشخص</option><option value="yes">قابل استرداد</option><option value="no">غیرقابل استرداد</option></select></label><button className="button secondary self-end" disabled={a.busy}>افزودن طرح نرخ</button></form>
    </div>)}
    <form className="grid gap-2 rounded-xl border border-dashed border-slate-300 p-3 sm:grid-cols-[1fr_2fr_auto]" aria-label="نگاشت تأمین‌کنندهٔ جدید" onSubmit={e => submit(e, v => api.post(`/admin/catalog/hotels/${encodeURIComponent(hotelId)}/provider-mappings`, {provider: v.provider.trim(), provider_hotel_id: v.provider_hotel_id.trim()}), 'نگاشت ثبت شد (تأییدنشده).')}>
      <label>سامانهٔ تأمین‌کننده<input name="provider" required pattern="[a-z0-9_-]{2,40}" dir="ltr" placeholder="grs" className={field}/></label><label>شناسهٔ هتل در آن سامانه<input name="provider_hotel_id" required maxLength={120} dir="ltr" className={field}/></label><button className="button secondary self-end" disabled={a.busy}>افزودن نگاشت</button></form>
  </div>;
}

/* ------------------------------------------------------------------ Reference tour: hotels of the tour */
export function TourHotels({hotels, onChange}: {hotels: {hotel_id: string; nights: number | null}[]; onChange: (h: {hotel_id: string; nights: number | null}[]) => void}) {
  const [q, setQ] = useState(''); const [applied, setApplied] = useState('');
  const found = useLoad<{items: {id: string; name: string; city: string | null; country_code: string}[]}>(applied ? `/admin/catalog/hotels?limit=8&status=published&q=${encodeURIComponent(applied)}` : null);
  return <div className="grid gap-2 rounded-2xl bg-white p-4 text-sm" data-tour-hotels><h2 className="font-bold">هتل‌های تور <span className="font-normal text-slate-500">(از فهرست مرجع؛ بدون نرخ)</span></h2>
    {hotels.length === 0 ? <p className="text-slate-500">هتلی به این تور وصل نشده است.</p> : hotels.map((h, i) => <div key={h.hotel_id} className="flex flex-wrap items-end gap-2" data-linked-hotel={h.hotel_id}><span className="grow break-all" dir="ltr">{h.hotel_id}</span>
      <label>شب<input type="number" min={1} max={60} className="w-20 rounded-lg border border-slate-300 p-1" value={h.nights ?? ''} onChange={e => onChange(hotels.map((x, j) => j === i ? {...x, nights: e.target.value === '' ? null : Number(e.target.value)} : x))}/></label>
      <button type="button" className="text-rose-700" onClick={() => onChange(hotels.filter((_, j) => j !== i))}>حذف</button></div>)}
    <div className="flex flex-wrap items-end gap-2"><label className="grow">جست‌وجوی هتل<input className={field} value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => {if (e.key === 'Enter') {e.preventDefault(); setApplied(q);}}}/></label><button type="button" className="button secondary" onClick={() => setApplied(q)}>جست‌وجو</button></div>
    {applied && (found.state.kind === 'loading' ? <Loading/> : found.state.kind === 'error' ? <Failed status={found.state.status}/> : found.state.data.items.length === 0 ? <p className="text-slate-500">هتلی پیدا نشد.</p>
      : <ul className="grid gap-1">{found.state.data.items.map(h => <li key={h.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 p-2"><span>{h.name} <span className="text-xs text-slate-500">{h.city ?? ''} {h.country_code}</span></span>
        <button type="button" className="button secondary" disabled={hotels.some(x => x.hotel_id === h.id)} onClick={() => onChange([...hotels, {hotel_id: h.id, nights: null}])}>افزودن به تور</button></li>)}</ul>)}
  </div>;
}
