'use client';
/* Seat quotas for partner agencies on the tenant's own charter flights. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Table, dateFa, errorOf, fa, useLoad} from './PanelKit';
import {FormFields, Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;

export function CharterQuotas() {
  const today = new Date().toISOString().slice(0, 10);
  const flights = useLoad<{items: Row[]}>(`/inventory/flights?date_from=${today}&limit=300`);
  const quotas = useLoad<{items: Row[]; auto_released_seats: number}>('/charter-quotas?status=held');
  const agencies = useLoad<{items: Row[]}>('/charter-quotas/agencies');
  const [v, setV] = useState<Row>({instance_id: '', agency_id: '', seats: null, note: ''}); const [msg, setMsg] = useState<Msg>(null);
  const reload = () => {flights.reload(); quotas.reload();};
  const flightOpts: [string, string][] = flights.state.kind === 'ready' ? [['', '—'], ...flights.state.data.items.filter(f => f.status === 'open').map(f => [f.id, `${f.flight} ${f.route} — ${dateFa(f.flight_date)} (آزاد ${fa(f.remaining)})`] as [string, string])] : [['', '—']];
  const agencyOpts: [string, string][] = agencies.state.kind === 'ready' ? [['', '—'], ...agencies.state.data.items.map(a => [a.id, a.name] as [string, string])] : [['', '—']];
  async function hold(e: FormEvent) {e.preventDefault(); setMsg(null); try {await quotas.api.post('/charter-quotas', {...v, note: v.note || null}); setMsg({ok: true, text: 'سهمیه ثبت شد و این صندلی‌ها از فروش عمومی کنار رفتند.'}); setV({...v, seats: null, note: ''}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  async function release(id: string, seats: number | null, reason: string) {setMsg(null); try {const r = await quotas.api.post<Row>(`/charter-quotas/${id}/release`, {seats, reason}); setMsg({ok: true, text: `${fa(r.released_now)} صندلی به فروش عمومی برگشت.`}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <>
    <Card title="سهمیه‌ی جدید"><form className="pn-form" onSubmit={hold}>
      <FormFields value={v} set={setV} fields={[{key: 'instance_id', label: 'پرواز', type: 'select', options: flightOpts, required: true}, {key: 'agency_id', label: 'آژانس همکار', type: 'select', options: agencyOpts, required: true},
        {key: 'seats', label: 'تعداد صندلی', type: 'number', required: true}, {key: 'note', label: 'توضیح'}]}/>
      <button className="pn-btn">ثبت سهمیه</button></form>
      <p className="pn-muted">صندلی‌های سهمیه از فروش عمومی کنار می‌روند و فروخته‌شده حساب نمی‌شوند. در مهلت پایان سهمیه‌ی هر سری پرواز، مانده‌ی سهمیه خودکار به فروش برمی‌گردد.</p>
      <Note msg={msg}/></Card>
    <Card title="سهمیه‌های فعال"><Async state={quotas.state}>{d => <>
      {d.auto_released_seats > 0 && <p className="pn-note">{fa(d.auto_released_seats)} صندلی با پایان مهلت سهمیه به فروش برگشت.</p>}
      <Table rows={d.items} rowKey={r => r.id} empty="سهمیه‌ی فعالی نیست." cols={[
        {label: 'آژانس', cell: r => r.agency ?? '—'}, {label: 'پرواز', cell: r => {const f = flights.state.kind === 'ready' ? flights.state.data.items.find(x => x.id === r.instance_id) : null; return f ? `${f.flight} ${f.route} ${dateFa(f.flight_date)}` : '—';}},
        {label: 'صندلی', cell: r => `${fa(r.seats)} از ${fa(r.seats_initial)}`}, {label: 'آزادسازی خودکار', cell: r => new Date(r.release_at).toLocaleString('fa-IR', {dateStyle: 'medium', timeStyle: 'short'})},
        {label: '', cell: r => <span style={{display: 'flex', gap: 6}}><button className="pn-btn ghost" onClick={() => release(r.id, 1, 'agency_booking')}>آزاد کردن ۱ صندلی برای رزرو همکار</button><button className="pn-btn ghost" onClick={() => release(r.id, null, 'manual')}>آزاد کردن همه</button></span>}]}/>
    </>}</Async></Card>
    <Card title="پروازهای پیش رو"><Async state={flights.state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="پروازی تعریف نشده است." cols={[
      {label: 'پرواز', cell: r => r.flight}, {label: 'مسیر', cell: r => r.route_name}, {label: 'تاریخ', cell: r => dateFa(r.flight_date)}, {label: 'ظرفیت', cell: r => fa(r.capacity)},
      {label: 'فروخته', cell: r => fa(r.sold)}, {label: 'سهمیه', cell: r => fa(r.held_quota ?? 0)}, {label: 'آزاد', cell: r => fa(r.remaining)}]}/>}</Async></Card>
  </>;
}
