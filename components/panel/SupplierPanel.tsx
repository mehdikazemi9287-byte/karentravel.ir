'use client';
/* Supplier panel. Scope is the suppliers the signed-in user is a member of; prices and capacities shown are the supplier's own entries. */
import Link from 'next/link';
import {Async, Badge, Card, Stats, Table, Unavailable, dateFa, fa, money, serviceFa, useLoad} from './PanelKit';

type Dashboard = {suppliers: number; offers: number; available_units: number; settlements: {count: number; amount: number | null; currency: string | null; totals?: {currency: string; amount: number}[]}; supplier_records: {id: string; name: string; type: string; status: string}[];
  offer_records: {id: string; supplier_id: string; title: string; service_type: string; amount: number; currency: string; available_units: number; status: string}[]};
const EDITORS: [string, string][] = [['/supplier/offers/new', 'ثبت عرضهٔ اقامت'], ['/supplier/accommodation', 'تقویم و نرخ اقامتگاه'], ['/supplier/hotels', 'هتل‌های من در فهرست مرجع'], ['/supplier/train/new', 'ظرفیت قراردادی قطار'], ['/supplier/car-rental/new', 'ظرفیت قراردادی خودرو'],
  ['/supplier/guides/new', 'خدمت راهنما'], ['/supplier/transport/new', 'حمل‌ونقل قراردادی'], ['/supplier/handicrafts/new', 'صنایع‌دستی']];

export function SupplierOverview() {
  const d = useLoad<Dashboard>('/supplier/dashboard'); const ready = useLoad<unknown[]>('/supplier/reservations/ready');
  return <Async state={d.state}>{x => <>
    <Stats items={[{label: 'تأمین‌کننده‌های من', value: fa(x.suppliers)}, {label: 'عرضه‌های ثبت‌شده', value: fa(x.offers)}, {label: 'ظرفیت اعلام‌شده', value: fa(x.available_units)}, {label: 'سفارش آمادهٔ تأیید', value: ready.state.kind === 'ready' ? fa(ready.state.data.length) : '…'}, {label: 'تسویه‌ها', value: fa(x.settlements.count), hint: x.settlements.totals?.length ? x.settlements.totals.map(t => money(t.amount, t.currency)).join(' · ') : x.settlements.count ? 'جزئیات ارز تسویه‌ها در دسترس نیست' : 'تسویه‌ای ثبت نشده است'}]}/>
    <Card title="وضعیت تأمین‌کننده"><Table rows={x.supplier_records} rowKey={s => s.id} empty="حساب شما به تأمین‌کننده‌ای متصل نیست؛ عضویت را مدیر مجموعه ثبت می‌کند." cols={[{label: 'نام', cell: s => s.name}, {label: 'نوع', cell: s => serviceFa(s.type)}, {label: 'وضعیت', cell: s => <Badge status={s.status}/>}]}/></Card>
    <Card title="کارهای امروز"><ul className="pn-list"><li><span>سفارش‌های پرداخت‌شده را تأیید یا رد کنید و مدارک را صادر کنید.</span><Link className="pn-link" href="/supplier/fulfillment">سفارش‌ها و تأیید</Link></li><li><span>نرخ و ظرفیت عرضه‌ها را به‌روز نگه دارید.</span><Link className="pn-link" href="/supplier/services">خدمات و موجودی</Link></li></ul></Card></>}</Async>;
}
export function SupplierServices() {
  const d = useLoad<Dashboard>('/supplier/dashboard');
  return <>
    <Card title="عرضه‌ها، نرخ و ظرفیت"><p className="pn-muted">نرخ و ظرفیت همان مقدارهایی است که خودتان ثبت کرده‌اید؛ سامانه نرخی پیشنهاد یا تخمین نمی‌زند.</p>
      <Async state={d.state}>{x => <Table rows={x.offer_records} rowKey={o => o.id} empty="عرضه‌ای ثبت نکرده‌اید." cols={[{label: 'عنوان', cell: o => o.title}, {label: 'خدمت', cell: o => serviceFa(o.service_type)}, {label: 'نرخ ثبت‌شده', cell: o => money(o.amount, o.currency)}, {label: 'ظرفیت', cell: o => fa(o.available_units)}, {label: 'وضعیت', cell: o => <Badge status={o.status}/>}]}/>}</Async></Card>
    <Card title="ثبت و ویرایش خدمات"><ul className="pn-list">{EDITORS.map(([href, label]) => <li key={href}><span>{label}</span><Link className="pn-link" href={href}>باز کردن</Link></li>)}</ul></Card>
    <Unavailable title="نرخ هتل‌های فهرست مرجع">هتل‌های فهرست مرجع تا اتصال نرخ واقعی (قرارداد و سرویس تأمین‌کننده) قیمت و موجودی ندارند و قابل رزرو آنلاین نیستند.</Unavailable>
  </>;
}
export function SupplierRfqs() {
  const r = useLoad<{id: string; title?: string; status?: string; destination?: string; headcount?: number; starts_at?: string}[]>('/enterprise/supplier/rfqs');
  return <Card title="درخواست‌های پیشنهاد قیمت سازمان‌ها"><Async state={r.state}>{rows => <Table rows={rows} rowKey={x => x.id} empty="سازمانی از شما درخواست پیشنهاد قیمت نکرده است." cols={[{label: 'عنوان', cell: x => x.title ?? '—'}, {label: 'مقصد', cell: x => x.destination ?? '—'}, {label: 'نفرات', cell: x => x.headcount ? fa(x.headcount) : '—'}, {label: 'تاریخ', cell: x => dateFa(x.starts_at)}, {label: 'وضعیت', cell: x => <Badge status={x.status}/>}]}/>}</Async></Card>;
}
export function SupplierReports() {
  const d = useLoad<Dashboard>('/supplier/dashboard'); const s = useLoad<{items: {id: string; amount: number; currency: string; status: string; created_at: string}[]; totals?: {status: string; currency: string; amount: number}[]}>('/supplier/settlements'); const c = useLoad<{contracts: {id: string; provider_key: string; mode: string; configured: boolean}[]}>('/supplier/contracts');
  return <>
    <Async state={d.state}>{x => {const by: Record<string, number> = {}; x.offer_records.forEach(o => {by[o.service_type] = (by[o.service_type] ?? 0) + 1;});
      return <Card title="عرضه‌ها بر اساس خدمت"><Table rows={Object.entries(by)} rowKey={([k]) => k} empty="عرضه‌ای ثبت نشده است." cols={[{label: 'خدمت', cell: ([k]) => serviceFa(k)}, {label: 'تعداد عرضه', cell: ([, v]) => fa(v)}]}/></Card>;}}</Async>
    <Async state={s.state}>{x => <Card title="تسویه‌ها بر اساس وضعیت">{x.totals ? <Table rows={x.totals} rowKey={row => row.status+'|'+row.currency} empty="تسویه‌ای ثبت نشده است." cols={[{label: 'وضعیت', cell: row => <Badge status={row.status}/>}, {label: 'جمع', cell: row => money(row.amount, row.currency)}]}/> : <Unavailable title="جمع تسویه‌ها">جمع همهٔ سوابق به تفکیک وضعیت و ارز در دسترس نیست.</Unavailable>}</Card>}</Async>
    <Async state={c.state}>{x => <Card title="اتصال‌های قراردادی"><Table rows={x.contracts} rowKey={k => k.id} empty="قرارداد اتصالی ثبت نشده است." cols={[{label: 'سرویس', cell: k => <span className="pn-ltr">{k.provider_key}</span>}, {label: 'حالت', cell: k => k.mode}, {label: 'پیکربندی', cell: k => <Badge status={k.configured ? 'active' : 'pending'}/>}]}/></Card>}</Async>
  </>;
}
