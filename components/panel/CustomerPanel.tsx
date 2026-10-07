'use client';
/* Customer / passenger panel. Every list is the signed-in user's own records from /me/* and /support/*. */
import Link from 'next/link';
import {useState} from 'react';
import {type Load, Async, Badge, Card, Empty, Stats, Table, Unavailable, dateFa, errorOf, fa, money, serviceFa, useLoad} from './PanelKit';

type Reservation = {id: string; booking_reference: string | null; service_type: string; status: string; price_snapshot?: {total_amount?: number; currency?: string} | null; created_at: string; manage_link: string; provider_connected?: boolean};
type Trip = {id: string; title: string; destination: string | null; starts_at: string | null; status: string; timeline_link: string};
type Invoice = {id: string; reservation_id: string; invoice_number: string; subtotal_amount: number; tax_amount: number; total_amount: number; currency: string; status: string; issued_at: string | null};
type Payment = {id: string; reservation_id: string; status: string; amount: number; currency: string; captured_amount: number; refunded_amount: number};
type Installment = {id: string; reservation_id: string; principal_amount: number; total_payable: number; currency: string; status: string; schedule: unknown[]};
type Notification = {id: string; topic: string; title: string; message: string; deep_link: string | null; status: string; created_at: string};
type Case = {id: string; subject: string; status: string; priority: string; case_type: string; sla_due_at: string | null};
type Wallet = {id: string; owner_type: string; currency: string; available: number; reserved: number; consumed: number};
type Credit = {id: string; organization_id: string | null; currency: string; limit_amount: number; available: number; reserved: number; consumed: number};
const isCancelled = (s: string) => /cancel|refund|void/i.test(s);
const reservationCols = [
  {label: 'کد پیگیری', cell: (r: Reservation) => <span className="pn-ltr">{r.booking_reference ?? r.id.slice(0, 8)}</span>},
  {label: 'خدمت', cell: (r: Reservation) => serviceFa(r.service_type)},
  {label: 'وضعیت', cell: (r: Reservation) => <Badge status={r.status}/>},
  {label: 'مبلغ', cell: (r: Reservation) => money(r.price_snapshot?.total_amount, r.price_snapshot?.currency)},
  {label: 'تاریخ ثبت', cell: (r: Reservation) => dateFa(r.created_at)},
  {label: '', cell: (r: Reservation) => <Link className="pn-link" href={r.manage_link}>مدیریت رزرو</Link>},
];

export function CustomerOverview() {
  const profile = useLoad<{name: string; email: string; role: string}>('/me/profile'); const res = useLoad<Reservation[]>('/me/reservations'); const trips = useLoad<Trip[]>('/me/trips');
  const inv = useLoad<Invoice[]>('/me/invoices'); const notes = useLoad<Notification[]>('/me/notifications'); const cases = useLoad<Case[]>('/support/cases');
  const count = <T,>(s: Load<T[]>, f: (x: T) => boolean = () => true) => s.kind === 'ready' ? fa(s.data.filter(f).length) : s.kind === 'error' ? '—' : '…';
  return <>
    <Async state={profile.state}>{p => <p className="pn-muted">{p.name} · <span className="pn-ltr">{p.email}</span></p>}</Async>
    <Stats items={[{label: 'رزروها', value: count(res.state)}, {label: 'رزروهای فعال', value: count(res.state, r => !isCancelled(r.status))}, {label: 'سفرها', value: count(trips.state)}, {label: 'فاکتورها', value: count(inv.state)},
      {label: 'اعلان خوانده‌نشده', value: count(notes.state, n => n.status !== 'read')}, {label: 'پروندهٔ باز پشتیبانی', value: count(cases.state, c => !/resolved|closed/.test(c.status))}]}/>
    <Card title="آخرین رزروها" action={<Link className="pn-link" href="/account/bookings">همهٔ رزروها</Link>}>
      <Async state={res.state}>{rows => <Table rows={rows.slice(0, 5)} cols={reservationCols} rowKey={r => r.id} empty={<>هنوز رزروی در این حساب ثبت نشده است. <Link className="pn-link" href="/hotels">جست‌وجوی هتل</Link> · <Link className="pn-link" href="/tours">تورها</Link></>}/>}</Async></Card>
    <Card title="آخرین اعلان‌ها" action={<Link className="pn-link" href="/account/notifications">همهٔ اعلان‌ها</Link>}>
      <Async state={notes.state}>{rows => rows.length === 0 ? <Empty>اعلانی ندارید.</Empty> : <ul className="pn-list">{rows.slice(0, 4).map(n => <li key={n.id}><span><b>{n.title}</b> — {n.message}</span><span className="pn-muted">{dateFa(n.created_at)}</span></li>)}</ul>}</Async></Card>
  </>;
}

export function CustomerBookings() {
  const res = useLoad<Reservation[]>('/me/reservations'); const trips = useLoad<Trip[]>('/me/trips'); const [service, setService] = useState('');
  return <>
    <Card title="رزروها"><Async state={res.state}>{rows => {const kinds = rows.map(r => r.service_type).filter((k, i, all) => all.indexOf(k) === i); const shown = rows.filter(r => !service || r.service_type === service);
      return <>{kinds.length > 1 && <div className="pn-chips" role="group" aria-label="نوع خدمت"><button type="button" aria-pressed={service === ''} onClick={() => setService('')}>همه ({fa(rows.length)})</button>{kinds.map(k => <button type="button" key={k} aria-pressed={service === k} onClick={() => setService(k)}>{serviceFa(k)}</button>)}</div>}
        <Table rows={shown} cols={reservationCols} rowKey={r => r.id} empty={<>رزروی ثبت نشده است. از <Link className="pn-link" href="/flights">پرواز</Link>، <Link className="pn-link" href="/hotels">هتل</Link> یا <Link className="pn-link" href="/tours">تور</Link> شروع کنید.</>}/></>;}}</Async></Card>
    <Card title="سفرها"><Async state={trips.state}>{rows => <Table rows={rows} rowKey={t => t.id} empty="سفری ساخته نشده است." cols={[{label: 'عنوان', cell: t => t.title}, {label: 'مقصد', cell: t => t.destination ?? '—'}, {label: 'شروع', cell: t => dateFa(t.starts_at)}, {label: 'وضعیت', cell: t => <Badge status={t.status}/>}, {label: '', cell: t => <Link className="pn-link" href={t.timeline_link}>برنامه و تغییرات</Link>}]}/>}</Async></Card>
  </>;
}

export function CustomerVisa() {
  const res = useLoad<Reservation[]>('/me/reservations'); const products = useLoad<{id: string; title?: string; name?: string; country?: string}[]>('/visa-products');
  const guides = useLoad<{countries: {id: string; name: string}[]; articles: {id: string; title: string}[]}>('/catalog/visa');
  return <>
    <Card title="درخواست‌های ویزای من"><Async state={res.state}>{rows => <Table rows={rows.filter(r => /visa/i.test(r.service_type))} cols={reservationCols} rowKey={r => r.id} empty="درخواست ویزایی در این حساب ثبت نشده است."/>}</Async></Card>
    <Card title="خدمات ویزای قابل‌درخواست"><Async state={products.state}>{rows => rows.length === 0 ? <Unavailable>هنوز هیچ خدمت ویزایی با قیمت و شرایط واقعی توسط تأمین‌کننده ثبت نشده است؛ به همین دلیل ثبت درخواست آنلاین ویزا فعال نیست.</Unavailable>
      : <ul className="pn-list">{rows.map(p => <li key={p.id}><span>{p.title ?? p.name ?? p.id}</span><Link className="pn-link" href="/visa">مشاهده و درخواست</Link></li>)}</ul>}</Async></Card>
    <Card title="راهنمای ویزای کشورها" action={<Link className="pn-link" href="/visa">همهٔ راهنماها</Link>}><Async state={guides.state}>{g => g.countries.length + g.articles.length === 0 ? <Empty>راهنمایی ثبت نشده است.</Empty>
      : <div className="pn-chips">{g.countries.map(c => <Link key={c.id} className="pn-badge" href={`/visa/cl-visa-country-${c.id}`}>{c.name}</Link>)}</div>}</Async><p className="pn-muted">این متن‌ها راهنمای عمومی‌اند؛ شرایط و مدارک را سفارت مقصد تعیین می‌کند.</p></Card>
  </>;
}

export function CustomerPayments() {
  const pay = useLoad<Payment[]>('/me/payments'); const inv = useLoad<Invoice[]>('/me/invoices'); const inst = useLoad<Installment[]>('/me/installments');
  return <>
    <Card title="پرداخت‌ها"><Async state={pay.state}>{rows => <Table rows={rows} rowKey={p => p.id} empty="پرداختی ثبت نشده است." cols={[{label: 'وضعیت', cell: p => <Badge status={p.status}/>}, {label: 'مبلغ', cell: p => money(p.amount, p.currency)}, {label: 'پرداخت‌شده', cell: p => money(p.captured_amount, p.currency)}, {label: 'مستردشده', cell: p => money(p.refunded_amount, p.currency)}, {label: '', cell: p => <Link className="pn-link" href={`/payments/${p.id}`}>جزئیات پرداخت</Link>}]}/>}</Async></Card>
    <Card title="فاکتورها"><Async state={inv.state}>{rows => <Table rows={rows} rowKey={i => i.id} empty="فاکتوری صادر نشده است." cols={[{label: 'شماره', cell: i => <span className="pn-ltr">{i.invoice_number}</span>}, {label: 'جمع', cell: i => money(i.subtotal_amount, i.currency)}, {label: 'مالیات', cell: i => money(i.tax_amount, i.currency)}, {label: 'قابل پرداخت', cell: i => money(i.total_amount, i.currency)}, {label: 'وضعیت', cell: i => <Badge status={i.status}/>}, {label: 'تاریخ صدور', cell: i => dateFa(i.issued_at)}, {label: '', cell: i => <Link className="pn-link" href={`/manage-booking/${i.reservation_id}`}>رزرو مربوط</Link>}]}/>}</Async></Card>
    <Card title="اقساط"><Async state={inst.state}>{rows => <Table rows={rows} rowKey={i => i.id} empty="طرح قسطی برای این حساب فعال نشده است." cols={[{label: 'اصل مبلغ', cell: i => money(i.principal_amount, i.currency)}, {label: 'جمع قابل پرداخت', cell: i => money(i.total_payable, i.currency)}, {label: 'تعداد قسط', cell: i => fa(i.schedule.length)}, {label: 'وضعیت', cell: i => <Badge status={i.status}/>}]}/>}</Async></Card>
  </>;
}

export function CustomerRefunds() {
  const res = useLoad<Reservation[]>('/me/reservations'); const pay = useLoad<Payment[]>('/me/payments');
  return <>
    <Card title="رزروهای قابل لغو"><p className="pn-muted">جریمه و مبلغ قابل استرداد هر رزرو از قوانین همان رزرو محاسبه می‌شود و پیش از تأیید نهایی در صفحهٔ مدیریت رزرو نمایش داده می‌شود.</p>
      <Async state={res.state}>{rows => <Table rows={rows.filter(r => !isCancelled(r.status))} rowKey={r => r.id} empty="رزرو فعالی برای لغو وجود ندارد." cols={[...reservationCols.slice(0, 4), {label: '', cell: r => <Link className="pn-link" href={r.manage_link}>مشاهدهٔ شرایط لغو</Link>}]}/>}</Async></Card>
    <Card title="رزروهای لغوشده"><Async state={res.state}>{rows => <Table rows={rows.filter(r => isCancelled(r.status))} rowKey={r => r.id} empty="رزرو لغوشده‌ای ندارید." cols={reservationCols}/>}</Async></Card>
    <Card title="استردادها"><Async state={pay.state}>{rows => <Table rows={rows.filter(p => p.refunded_amount > 0)} rowKey={p => p.id} empty="استردادی ثبت نشده است." cols={[{label: 'مبلغ مسترد', cell: p => money(p.refunded_amount, p.currency)}, {label: 'از پرداخت', cell: p => money(p.captured_amount, p.currency)}, {label: 'وضعیت پرداخت', cell: p => <Badge status={p.status}/>}, {label: '', cell: p => <Link className="pn-link" href={`/payments/${p.id}`}>جزئیات</Link>}]}/>}</Async></Card>
  </>;
}

export function CustomerWallet() {
  const wallets = useLoad<Wallet[]>('/me/wallets'); const credit = useLoad<Credit[]>('/me/organization-credit'); const [note, setNote] = useState<{ok: boolean; text: string} | null>(null); const [busy, setBusy] = useState(false);
  async function create() {
    setBusy(true); setNote(null);
    try {await wallets.api.post('/me/wallets', {currency: 'IRR'}, `wallet-${crypto.randomUUID()}`); wallets.reload(); setNote({ok: true, text: 'کیف پول ریالی ایجاد شد.'});} catch (e) {setNote({ok: false, text: errorOf(e).message});} finally {setBusy(false);}
  }
  const balance = (w: {available: number; reserved: number; consumed: number; currency: string}) => <dl className="pn-dl"><dt>قابل استفاده</dt><dd>{money(w.available, w.currency)}</dd><dt>رزروشده</dt><dd>{money(w.reserved, w.currency)}</dd><dt>مصرف‌شده</dt><dd>{money(w.consumed, w.currency)}</dd></dl>;
  return <>
    {note && <div className={`pn-note ${note.ok ? 'ok' : 'error'}`} role={note.ok ? 'status' : 'alert'}>{note.text}</div>}
    <Card title="کیف پول"><Async state={wallets.state}>{rows => rows.length === 0 ? <Empty>برای این حساب کیف پولی ساخته نشده است. موجودی کیف پول فقط از تراکنش‌های واقعی (شارژ، استرداد) تشکیل می‌شود.<div><button type="button" className="pn-btn" disabled={busy} onClick={() => void create()}>{busy ? 'در حال ایجاد…' : 'ایجاد کیف پول ریالی'}</button></div></Empty>
      : <>{rows.map(w => <div key={w.id}>{balance(w)}</div>)}<Unavailable title="شارژ آنلاین">شارژ کیف پول به درگاه پرداخت فعال نیاز دارد که هنوز متصل نشده است.</Unavailable></>}</Async></Card>
    <Card title="اعتبار سازمانی"><Async state={credit.state}>{rows => rows.length === 0 ? <Empty>اعتبار سازمانی برای این حساب تعریف نشده است.</Empty> : <>{rows.map(c => <div key={c.id}><dl className="pn-dl"><dt>سقف اعتبار</dt><dd>{money(c.limit_amount, c.currency)}</dd></dl>{balance(c)}</div>)}</>}</Async></Card>
  </>;
}

export function CustomerNotifications() {
  const notes = useLoad<Notification[]>('/me/notifications'); const prefs = useLoad<{topic: string; channel: string; enabled: boolean}[]>('/me/notification-preferences'); const [error, setError] = useState('');
  async function read(id: string) {setError(''); try {await notes.api.post(`/me/notifications/${id}/read`, {}); notes.reload();} catch (e) {setError(errorOf(e).message);}}
  return <>
    {error && <div className="pn-note error" role="alert">{error}</div>}
    <Card title="اعلان‌ها"><Async state={notes.state}>{rows => rows.length === 0 ? <Empty>اعلانی ندارید.</Empty> : <ul className="pn-list">{rows.map(n => <li key={n.id}><span><Badge status={n.status === 'read' ? 'read' : 'unread'}/> <b>{n.title}</b> — {n.message} <span className="pn-muted">· {dateFa(n.created_at)}</span></span>
      <span>{n.deep_link && <Link className="pn-link" href={n.deep_link}>مشاهده</Link>} {n.status !== 'read' && <button type="button" className="pn-btn ghost" onClick={() => void read(n.id)}>خواندم</button>}</span></li>)}</ul>}</Async></Card>
    <Card title="کانال‌های دریافت"><Async state={prefs.state}>{rows => rows.length === 0 ? <Empty>تنظیم جداگانه‌ای ثبت نشده است؛ اعلان‌ها داخل همین حساب نمایش داده می‌شوند.</Empty> : <ul className="pn-list">{rows.map(p => <li key={p.topic + p.channel}><span>{p.topic} · <span className="pn-ltr">{p.channel}</span></span><Badge status={p.enabled ? 'active' : 'cancelled'}/></li>)}</ul>}</Async>
      <Unavailable title="پیامک و اعلان همراه">ارسال پیامک و Push به سرویس‌دهندهٔ پیام متصل نیست؛ فقط اعلان داخل حساب فعال است.</Unavailable></Card>
  </>;
}

export function CustomerSupport() {
  const cases = useLoad<Case[]>('/support/cases');
  return <Card title="پرونده‌های پشتیبانی" action={<Link className="pn-btn" href="/support">ثبت درخواست جدید</Link>}>
    <Async state={cases.state}>{rows => <Table rows={rows} rowKey={c => c.id} empty="پرونده‌ای ثبت نکرده‌اید." cols={[{label: 'موضوع', cell: c => c.subject}, {label: 'وضعیت', cell: c => <Badge status={c.status}/>}, {label: 'اولویت', cell: c => c.priority}, {label: 'مهلت پاسخ', cell: c => dateFa(c.sla_due_at)}, {label: '', cell: c => <Link className="pn-link" href={`/support?case=${c.id}`}>گفت‌وگو</Link>}]}/>}</Async></Card>;
}
