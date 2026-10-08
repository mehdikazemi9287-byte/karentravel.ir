'use client';
/* Partner / agency panel. The agency comes from the signed-in user's memberships (/agency/workspace); every figure below is
   returned by the API for that agency: bookings attributed through its sales channel, its commission ledger, its credit account. */
import Link from 'next/link';
import {useEffect, useState, type ReactNode} from 'react';
import {AgencyQuotes} from '../operational/PartnerViews';
import {Async, Badge, Card, Empty, Failed, Loading, Stats, Table, Unavailable, dateFa, fa, money, serviceFa, useLoad} from './PanelKit';

type Agency = {id: string; name: string; status: string; markup_bps: number; commission_bps: number; sales_channel_linked: boolean};
type Booking = {id: string; booking_reference: string; service_type: string; status: string; customer_id: number; total_amount: number | null; currency: string; created_at: string; confirmed_at: string | null};
type Money = {currency: string; amount: number};
const KEY = 'karenseir-panel-agency'; const pct = (bps: number) => `${(bps / 100).toLocaleString('fa-IR')}٪`;
export function AgencyScope({children}: {children: (agency: Agency) => ReactNode}) {
  const ws = useLoad<{agencies: Agency[]; can_administer: boolean}>('/agency/workspace'); const [picked, setPicked] = useState('');
  useEffect(() => {try {setPicked(sessionStorage.getItem(KEY) ?? '');} catch {/* storage unavailable */}}, []);
  if (ws.state.kind === 'loading') return <Loading/>; if (ws.state.kind === 'error') return <Failed status={ws.state.status} message={ws.state.message}/>;
  const list = ws.state.data.agencies; const agency = list.find(a => a.id === picked) ?? list[0];
  if (!agency) return <Empty>حساب شما عضو هیچ آژانسی نیست. عضویت را مدیر مجموعه از بخش «تأمین‌کنندگان و آژانس‌ها» ثبت می‌کند.</Empty>;
  return <>{list.length > 1 && <div className="pn-form"><label>آژانس<select value={agency.id} onChange={e => {setPicked(e.target.value); try {sessionStorage.setItem(KEY, e.target.value);} catch {/* ignore */}}}>{list.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label></div>}
    {!agency.sales_channel_linked && <Unavailable title="کانال فروش متصل نیست">تا وقتی کانال فروش این آژانس توسط مدیر مجموعه متصل نشود، رزروی به نام آژانس ثبت نمی‌شود و فهرست رزروها خالی می‌ماند.</Unavailable>}{children(agency)}</>;
}
const bookingCols = [{label: 'کد پیگیری', cell: (b: Booking) => <span className="pn-ltr">{b.booking_reference}</span>}, {label: 'خدمت', cell: (b: Booking) => serviceFa(b.service_type)}, {label: 'وضعیت', cell: (b: Booking) => <Badge status={b.status}/>},
  {label: 'مبلغ', cell: (b: Booking) => money(b.total_amount, b.currency)}, {label: 'ثبت', cell: (b: Booking) => dateFa(b.created_at)}, {label: 'تأیید', cell: (b: Booking) => dateFa(b.confirmed_at)}];

export function AgencyOverview() {return <AgencyScope>{a => <OverviewBody a={a}/>}</AgencyScope>;}
function OverviewBody({a}: {a: Agency}) {
  const report = useLoad<{bookings: number; by_status: Record<string, number>; confirmed_sales: Money[]}>(`/agency/${a.id}/report`); const credit = useLoad<{linked: boolean; currency: string; balances?: {available: number; limit_amount: number}}>(`/agency/${a.id}/credit`); const bookings = useLoad<{items: Booking[]}>(`/agency/${a.id}/bookings`);
  return <>
    <p className="pn-muted">{a.name} · <Badge status={a.status}/> · نرخ کمیسیون {pct(a.commission_bps)}{a.markup_bps ? ` · حاشیهٔ فروش ${pct(a.markup_bps)}` : ''}</p>
    <Stats items={[{label: 'رزروها', value: report.state.kind === 'ready' ? fa(report.state.data.bookings) : '…'}, {label: 'تأییدشده', value: report.state.kind === 'ready' ? fa(report.state.data.by_status.confirmed ?? 0) : '…'},
      ...(report.state.kind === 'ready' ? report.state.data.confirmed_sales.map(s => ({label: 'فروش تأییدشده', value: money(s.amount, s.currency)})) : []),
      {label: 'اعتبار قابل استفاده', value: credit.state.kind === 'ready' ? (credit.state.data.linked && credit.state.data.balances ? money(credit.state.data.balances.available, credit.state.data.currency) : 'تعریف نشده') : '…'}]}/>
    <Card title="آخرین رزروها" action={<Link className="pn-link" href="/agency/bookings">همهٔ رزروها</Link>}><Async state={bookings.state}>{b => <Table rows={b.items.slice(0, 6)} cols={bookingCols} rowKey={x => x.id} empty="رزروی به نام این آژانس ثبت نشده است."/>}</Async></Card>
  </>;
}
export function AgencySales() {return <AgencyScope>{a => <><p className="pn-muted">پیشنهاد قیمت روی عرضهٔ فعال تأمین‌کننده و با قیمت همان عرضه ساخته می‌شود؛ مشتری در حساب خود آن را می‌پذیرد یا رد می‌کند.</p><AgencyQuotes agencyId={a.id}/></>}</AgencyScope>;}
export function AgencyBookings() {return <AgencyScope>{a => <BookingsBody a={a}/>}</AgencyScope>;}
function BookingsBody({a}: {a: Agency}) {
  const bookings = useLoad<{items: Booking[]}>(`/agency/${a.id}/bookings`); const [status, setStatus] = useState('');
  return <Card title="رزروهای آژانس"><Async state={bookings.state}>{b => {const kinds = b.items.map(x => x.status).filter((k, i, all) => all.indexOf(k) === i);
    return <>{kinds.length > 1 && <div className="pn-chips" role="group" aria-label="وضعیت"><button type="button" aria-pressed={status === ''} onClick={() => setStatus('')}>همه ({fa(b.items.length)})</button>{kinds.map(k => <button type="button" key={k} aria-pressed={status === k} onClick={() => setStatus(k)}><Badge status={k}/></button>)}</div>}
      <Table rows={b.items.filter(x => !status || x.status === status)} cols={bookingCols} rowKey={x => x.id} empty="رزروی ثبت نشده است."/></>;}}</Async>
    <p className="pn-muted">وضعیت عملیاتی هر رزرو همان وضعیت ثبت‌شدهٔ رزرو است. واچر و مدارک سفر در حساب مشتری صادر می‌شود و آژانس به آن دسترسی ندارد.</p></Card>;
}
export function AgencyCustomers() {return <AgencyScope>{a => <CustomersBody a={a}/>}</AgencyScope>;}
function CustomersBody({a}: {a: Agency}) {
  const c = useLoad<{items: {customer_id: number; name: string; bookings: number}[]}>(`/agency/${a.id}/customers`);
  return <Card title="مشتریان آژانس"><Async state={c.state}>{d => <Table rows={d.items} rowKey={x => String(x.customer_id)} empty="هنوز مشتری‌ای از طریق این آژانس رزرو نکرده است." cols={[{label: 'نام', cell: x => x.name}, {label: 'تعداد رزرو', cell: x => fa(x.bookings)}]}/>}</Async>
    <p className="pn-muted">فقط نام و تعداد رزرو نمایش داده می‌شود؛ اطلاعات تماس و مدارک مسافر در اختیار آژانس قرار نمی‌گیرد.</p></Card>;
}
type Ledger = {id: string; reservation_id: string; base_amount: number; commission_bps: number; amount: number; currency: string; status: string; created_at: string; settled_at: string | null};
export function AgencyCommissions() {return <AgencyScope>{a => <CommissionsBody a={a}/>}</AgencyScope>;}
function CommissionsBody({a}: {a: Agency}) {
  const st = useLoad<{commission_bps: number; items: {reservation_id: string; booking_reference: string; confirmed_at: string; base_amount: number; currency: string; commission_bps: number; commission_amount: number}[]; totals: {currency: string; commission_amount: number}[]; note: string}>(`/agency/${a.id}/commissions`);
  const ledger = useLoad<{items: Ledger[]; totals: {status: string; currency: string; amount: number}[]}>(`/agency/${a.id}/commission-ledger`);
  return <>
    <Card title="دفتر کمیسیون"><Async state={ledger.state}>{l => <><Stats items={l.totals.map(t => ({label: `کمیسیون ${t.status === 'settled' ? 'تسویه‌شده' : t.status === 'approved' ? 'تأییدشده' : t.status === 'accrued' ? 'ثبت‌شده' : t.status}`, value: money(t.amount, t.currency)}))}/>
      <Table rows={l.items} rowKey={x => x.id} empty="هنوز کمیسیونی در دفتر ثبت نشده است." cols={[{label: 'مبنای محاسبه', cell: x => money(x.base_amount, x.currency)}, {label: 'نرخ', cell: x => pct(x.commission_bps)}, {label: 'کمیسیون', cell: x => money(x.amount, x.currency)}, {label: 'وضعیت', cell: x => <Badge status={x.status}/>}, {label: 'ثبت', cell: x => dateFa(x.created_at)}, {label: 'تسویه', cell: x => dateFa(x.settled_at)}]}/></>}</Async></Card>
    <Card title="صورت کمیسیون رزروهای تأییدشده"><Async state={st.state}>{s => <><p className="pn-muted">{s.note}</p><Table rows={s.items} rowKey={x => x.reservation_id} empty="رزرو تأییدشده‌ای برای محاسبهٔ کمیسیون وجود ندارد."
      cols={[{label: 'کد پیگیری', cell: x => <span className="pn-ltr">{x.booking_reference}</span>}, {label: 'تأیید', cell: x => dateFa(x.confirmed_at)}, {label: 'مبنای محاسبه', cell: x => money(x.base_amount, x.currency)}, {label: 'نرخ', cell: x => pct(x.commission_bps)}, {label: 'کمیسیون', cell: x => money(x.commission_amount, x.currency)}]}/></>}</Async></Card>
  </>;
}
export function AgencyCredit() {return <AgencyScope>{a => <CreditBody a={a}/>}</AgencyScope>;}
function CreditBody({a}: {a: Agency}) {
  const c = useLoad<{linked: boolean; currency: string; balances?: {limit_amount: number; available: number; reserved: number; consumed: number}; items: {id?: string; entry_type?: string; amount?: number; created_at?: string}[]}>(`/agency/${a.id}/credit`);
  return <Card title="اعتبار آژانس"><Async state={c.state}>{d => !d.linked || !d.balances ? <Empty>برای این آژانس حساب اعتباری تعریف نشده است. حساب اعتباری پس از قرارداد توسط مدیر مجموعه متصل می‌شود.</Empty>
    : <><dl className="pn-dl"><dt>سقف اعتبار</dt><dd>{money(d.balances.limit_amount, d.currency)}</dd><dt>قابل استفاده</dt><dd>{money(d.balances.available, d.currency)}</dd><dt>رزروشده</dt><dd>{money(d.balances.reserved, d.currency)}</dd><dt>مصرف‌شده</dt><dd>{money(d.balances.consumed, d.currency)}</dd></dl>
      <Table rows={d.items} rowKey={x => String(x.id)} empty="گردشی روی این حساب ثبت نشده است." cols={[{label: 'نوع', cell: x => x.entry_type ?? '—'}, {label: 'مبلغ', cell: x => money(x.amount, d.currency)}, {label: 'تاریخ', cell: x => dateFa(x.created_at)}]}/></>}</Async></Card>;
}
export function AgencyDocuments() {return <AgencyScope>{a => <DocumentsBody a={a}/>}</AgencyScope>;}
function DocumentsBody({a}: {a: Agency}) {
  const s = useLoad<{items: {id: string; reservation_id: string; amount: number; currency: string; status: string; external_reference: string | null; created_at: string}[]}>(`/agency/${a.id}/settlements`);
  return <>
    <Card title="تسویه‌ها"><Async state={s.state}>{d => <Table rows={d.items} rowKey={x => x.id} empty="تسویه‌ای ثبت نشده است." cols={[{label: 'مبلغ', cell: x => money(x.amount, x.currency)}, {label: 'وضعیت', cell: x => <Badge status={x.status}/>}, {label: 'شمارهٔ مرجع', cell: x => x.external_reference ? <span className="pn-ltr">{x.external_reference}</span> : 'ثبت نشده'}, {label: 'تاریخ', cell: x => dateFa(x.created_at)}]}/>}</Async></Card>
    <Unavailable title="واچر و فاکتور مشتری">واچر و فاکتور هر رزرو به نام مسافر صادر می‌شود و فقط در حساب خود او قابل دریافت است؛ نسخهٔ آژانسی این مدارک در سامانه تعریف نشده است.</Unavailable>
  </>;
}
export function AgencyReports() {return <AgencyScope>{a => <ReportsBody a={a}/>}</AgencyScope>;}
function ReportsBody({a}: {a: Agency}) {
  const r = useLoad<{bookings: number; by_status: Record<string, number>; by_service_type: Record<string, number>; confirmed_sales: Money[]}>(`/agency/${a.id}/report`);
  return <Async state={r.state}>{d => <>
    <Stats items={[{label: 'کل رزروها', value: fa(d.bookings)}, ...d.confirmed_sales.map(s => ({label: 'فروش تأییدشده', value: money(s.amount, s.currency)}))]}/>
    <Card title="بر اساس وضعیت"><Table rows={Object.entries(d.by_status)} rowKey={([k]) => k} empty="داده‌ای نیست." cols={[{label: 'وضعیت', cell: ([k]) => <Badge status={k}/>}, {label: 'تعداد', cell: ([, v]) => fa(v)}]}/></Card>
    <Card title="بر اساس خدمت"><Table rows={Object.entries(d.by_service_type)} rowKey={([k]) => k} empty="داده‌ای نیست." cols={[{label: 'خدمت', cell: ([k]) => serviceFa(k)}, {label: 'تعداد', cell: ([, v]) => fa(v)}]}/></Card></>}</Async>;
}
