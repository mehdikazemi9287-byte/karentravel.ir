'use client';
/* Stitch round 6 — desktop/16 «پورتال تأمین‌کنندگان تجربیات بومی و کارگاه‌ها». All figures come from /supplier/experience-portal. */
import {useState} from 'react';
import {Async, Card, Empty, Stats, Unavailable, dateFa, errorOf, fa, money, useLoad} from '../panel/PanelKit';
import {newId} from '../../lib/api/karenseir-client';
import '../tours/tours-round6.css';

type Ticket = {id: string; label: string; price: number; currency: string};
type Product = {id: string; title: string; service_type: string; status: string; duration_minutes?: number | null; description?: string; ticket_types: Ticket[]; upcoming_sessions: number};
type SessionRow = {id: string; experience_product_id: string; product_title: string; starts_at: string; ends_at: string; capacity_total: number; capacity_available?: number; seats_sold: number; status: string};
type Arrival = {reservation_id: string; booking_reference?: string | null; status: string; session_id: string; starts_at: string; product_title: string; guests: number; amount: number; currency: string};
type Portal = {places: {id: string; name: string; city: string}[]; products: Product[]; sessions: SessionRow[]; arrivals: Arrival[]; kpis: {sessions: number; seats_total: number; seats_sold: number; bookings: number; gross_amount: number; currency: string; window_days: number}; payout: {provider: string; status: string}};
const time = (iso: string) => new Date(iso).toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tehran'});
const dayKey = (iso: string) => new Date(iso).toLocaleDateString('en-CA', {timeZone: 'Asia/Tehran'});

export function HostExperiencePortal() {
  const {state, reload, api} = useLoad<Portal>('/supplier/experience-portal?days=30');
  const [form, setForm] = useState({product: '', start: '', minutes: 120, capacity: 10});
  const [busy, setBusy] = useState(false), [note, setNote] = useState('');
  const [days] = useState(() => {const n = Date.now(); return {today: dayKey(new Date(n).toISOString()), tomorrow: dayKey(new Date(n + 864e5).toISOString())};});
  async function addSession(e: React.FormEvent) {
    e.preventDefault(); if (!form.product || !form.start || busy) return;
    const start = new Date(form.start); if (Number.isNaN(start.getTime()) || start.getTime() <= Date.now()) {setNote('زمان شروع باید در آینده باشد.'); return;}
    setBusy(true); setNote('');
    try {
      await api.post(`/supplier/experience-products/${form.product}/sessions`, {starts_at: start.toISOString(), ends_at: new Date(start.getTime() + form.minutes * 60000).toISOString(), capacity_total: form.capacity}, newId());
      setNote('سانس تازه ثبت شد.'); setForm(f => ({...f, start: ''})); reload();
    } catch (err) {setNote(errorOf(err).message || 'ثبت سانس انجام نشد.');} finally {setBusy(false);}
  }
  return <Async state={state}>{d => {
    const {today, tomorrow} = days;
    const todays = d.arrivals.filter(a => dayKey(a.starts_at) === today), nexts = d.arrivals.filter(a => dayKey(a.starts_at) === tomorrow);
    const fill = d.kpis.seats_total ? Math.round((d.kpis.seats_sold / d.kpis.seats_total) * 100) : 0;
    return <div className="host-portal">
      <Stats items={[
        {label: `فروش ناخالص ${fa(d.kpis.window_days)} روز آینده`, value: money(d.kpis.gross_amount, d.kpis.currency), hint: 'از رزروهای ثبت‌شده'},
        {label: 'رزروهای فعال', value: fa(d.kpis.bookings)},
        {label: 'سانس‌های پیش رو', value: fa(d.kpis.sessions)},
        {label: 'ظرفیت فروخته‌شده', value: `${fa(fill)}٪`, hint: `${fa(d.kpis.seats_sold)} از ${fa(d.kpis.seats_total)} صندلی`},
      ]}/>
      <div className="hp-grid">
        <Card title="کاتالوگ کارگاه‌ها و مسترکلاس‌ها">{d.products.length === 0 ? <Empty>هنوز تجربه یا کارگاهی ثبت نکرده‌اید. از «خدمات، نرخ و ظرفیت» مکان و محصول را بسازید.</Empty> :
          <div className="hp-products">{d.products.map(p => <article key={p.id} className="hp-product">
            <header><b>{p.title}</b><span className={`hp-status ${p.status}`}>{p.status === 'published' ? 'فعال' : p.status === 'draft' ? 'پیش‌نویس' : p.status}</span></header>
            {p.description && <p>{p.description}</p>}
            <small>{p.duration_minutes ? `${fa(p.duration_minutes)} دقیقه · ` : ''}{p.ticket_types.length ? p.ticket_types.map(t => `${t.label}: ${money(t.price, t.currency)}`).join(' · ') : 'نرخ بلیت ثبت نشده'}</small>
            <small>{fa(p.upcoming_sessions)} سانس در پیش</small>
          </article>)}</div>}
        </Card>
        <Card title="ورود کاروان‌های امروز و فردا">
          {[['امروز', todays], ['فردا', nexts]].map(([label, list]) => <div key={label as string} className="hp-arrivals"><h3>{label as string}</h3>
            {(list as Arrival[]).length === 0 ? <p className="pn-muted">ورودی ثبت نشده است.</p> : <ul>{(list as Arrival[]).map(a => <li key={a.reservation_id}><b>{time(a.starts_at)}</b><span>{a.product_title}</span><span>{fa(a.guests)} نفر</span><small>{a.booking_reference || '—'}</small></li>)}</ul>}
          </div>)}
        </Card>
      </div>
      <Card title="سانس‌ها و ظرفیت">
        {d.sessions.length === 0 ? <Empty>سانسی در {fa(d.kpis.window_days)} روز آینده ندارید.</Empty> :
          <table className="hp-sessions"><thead><tr><th>تجربه</th><th>تاریخ</th><th>ساعت</th><th>ظرفیت</th><th>فروش</th></tr></thead><tbody>{d.sessions.map(s => <tr key={s.id}><td>{s.product_title}</td><td>{dateFa(s.starts_at)}</td><td>{time(s.starts_at)}</td><td>{fa(s.capacity_total)}</td><td><div className="hp-bar" role="img" aria-label={`${fa(s.seats_sold)} از ${fa(s.capacity_total)}`}><i style={{width: `${Math.min(100, (s.seats_sold / Math.max(1, s.capacity_total)) * 100)}%`}}/></div><small>{fa(s.seats_sold)} / {fa(s.capacity_total)}</small></td></tr>)}</tbody></table>}
        {d.products.length > 0 && <form className="hp-form" onSubmit={addSession}>
          <h3>افزودن سانس تازه</h3>
          <label>تجربه<select required value={form.product} onChange={e => setForm({...form, product: e.target.value})}><option value="">انتخاب</option>{d.products.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}</select></label>
          <label>شروع<input required type="datetime-local" value={form.start} onChange={e => setForm({...form, start: e.target.value})}/></label>
          <label>مدت (دقیقه)<input type="number" min={15} max={1440} value={form.minutes} onChange={e => setForm({...form, minutes: Math.max(15, Number(e.target.value) || 15)})}/></label>
          <label>ظرفیت<input type="number" min={1} max={500} value={form.capacity} onChange={e => setForm({...form, capacity: Math.max(1, Number(e.target.value) || 1)})}/></label>
          <button className="pn-btn" disabled={busy}>{busy ? 'در حال ثبت…' : 'ثبت سانس'}</button>
          {note && <p role="status">{note}</p>}
        </form>}
      </Card>
      <Card title="تسویهٔ مالی میزبان">
        {d.payout.status === 'configured' ? <p>تسویه از طریق درگاه ونداپی انجام می‌شود؛ وجه پس از تأیید ورود مسافر و طبق قرارداد به حساب شما واریز می‌شود.</p> :
          <Unavailable title="تسویهٔ آنی هنوز فعال نیست">کیف پول و تسویهٔ آنی میزبان پس از فعال شدن درگاه ونداپی برای کارن تراول روشن می‌شود. تا آن زمان تسویه طبق قرارداد و از بخش «تسویه‌ها» پیگیری می‌شود.</Unavailable>}
      </Card>
    </div>;
  }}</Async>;
}
