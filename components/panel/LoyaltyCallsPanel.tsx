'use client';
/* Loyalty call schedule: today's calls from real completed trips and dormant members; claim, record outcome, follow-up. */
import {useState} from 'react';
import {Async, Card, Stats, Table, dateFa, errorOf, fa, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;

function ResultForm({task, outcomes, done}: {task: Row; outcomes: Record<string, string>; done: (m: Msg) => void}) {
  const {api} = useLoad<Row>(null);
  const [v, setV] = useState({outcome: 'reached', note: '', next_call_on: ''});
  async function save() {
    try {const r = await api.post<Row>(`/loyalty/calls/${task.id}/result`, {outcome: v.outcome, note: v.note || null, next_call_on: v.next_call_on || null});
      done({ok: true, text: r.follow_up_created ? 'نتیجه ثبت شد و تماس بعدی در برنامه قرار گرفت.' : 'نتیجه‌ی تماس ثبت شد.'});}
    catch (x) {done({ok: false, text: errorOf(x).message});}
  }
  return <div className="lc-form">
    <select aria-label="نتیجه‌ی تماس" value={v.outcome} onChange={e => setV({...v, outcome: e.target.value})}>{Object.entries(outcomes).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
    <input aria-label="یادداشت" placeholder="یادداشت" value={v.note} onChange={e => setV({...v, note: e.target.value})} maxLength={1000}/>
    <label>تماس بعدی<input type="date" dir="ltr" value={v.next_call_on} onChange={e => setV({...v, next_call_on: e.target.value})}/></label>
    <button className="pn-btn" type="button" onClick={() => void save()}>ثبت نتیجه</button>
  </div>;
}

export function LoyaltyCalls() {
  const [status, setStatus] = useState('open'); const [mine, setMine] = useState(false);
  const {state, reload, api} = useLoad<Row>(`/loyalty/calls?status=${status}${mine ? '&mine=true' : ''}`);
  const [msg, setMsg] = useState<Msg>(null); const [open, setOpen] = useState<string | null>(null);
  async function act(fn: () => Promise<unknown>, ok: string) {setMsg(null); try {await fn(); setMsg({ok: true, text: ok}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  const generate = () => act(async () => {const r = await api.post<Row>('/loyalty/calls/generate', {}); setMsg({ok: true, text: `${fa(r.created.post_trip)} پیگیری بعد از سفر و ${fa(r.created.dormant)} مشتری کم‌فعال به برنامه اضافه شد.`});}, '');
  return <Async state={state}>{d => <>
    <Stats items={[{label: 'تماس باز', value: fa(d.counts.open)}, {label: 'انجام‌شده', value: fa(d.counts.done)}, {label: 'کنار گذاشته', value: fa(d.counts.skipped)}]}/>
    <Note msg={msg}/>
    <Card title="برنامه‌ی تماس" action={<span className="sec-actions">
      <select aria-label="وضعیت" value={status} onChange={e => setStatus(e.target.value)}>{[['open', 'باز'], ['done', 'انجام‌شده'], ['skipped', 'کنار گذاشته'], ['all', 'همه']].map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      <label className="lc-mine"><input type="checkbox" checked={mine} onChange={e => setMine(e.target.checked)}/> فقط تماس‌های من</label>
      <button className="pn-btn" onClick={() => void generate()}>ساخت برنامه‌ی امروز</button></span>}>
      <p className="pn-muted">از سفرهای تمام‌شده‌ی اخیر و اعضایی که بیش از ۱۸۰ روز خرید نکرده‌اند ساخته می‌شود؛ هیچ پیامی خودکار برای مشتری فرستاده نمی‌شود.</p>
      <Table rows={d.items} rowKey={(r: Row) => r.id} empty="تماسی در این وضعیت نیست." cols={[
        {label: 'مشتری', cell: (r: Row) => r.customer}, {label: 'موبایل', cell: (r: Row) => r.mobile ? <a className="pn-ltr" href={`tel:${r.mobile}`}>{r.mobile}</a> : '—'},
        {label: 'دلیل', cell: (r: Row) => <>{r.reason_fa}{r.booking_reference ? <small className="pn-muted pn-ltr"> {r.booking_reference}</small> : null}</>},
        {label: 'موعد', cell: (r: Row) => r.overdue ? <span className="pn-badge bad">{dateFa(r.due_on)}</span> : dateFa(r.due_on)},
        {label: 'کارشناس', cell: (r: Row) => r.assigned_to ?? '—'},
        {label: 'نتیجه', cell: (r: Row) => r.outcome_fa ? <>{r.outcome_fa}{r.note ? <small className="pn-muted"> — {r.note}</small> : null}</> : r.note ? <small className="pn-muted">{r.note}</small> : '—'},
        {label: '', cell: (r: Row) => r.status !== 'open' ? null : open === r.id ? <ResultForm task={r} outcomes={d.outcomes} done={m => {setMsg(m); setOpen(null); reload();}}/> : <span className="sec-actions">
          {!r.assigned_to && <button className="pn-btn ghost" onClick={() => void act(() => api.post(`/loyalty/calls/${r.id}/claim`, {}), 'تماس به شما سپرده شد.')}>برداشتن</button>}
          {(r.mine || !r.assigned_to) && <button className="pn-btn ghost" onClick={() => setOpen(r.id)}>ثبت نتیجه</button>}
          <button className="pn-btn ghost" onClick={() => void act(() => api.post(`/loyalty/calls/${r.id}/skip`, {}), 'تماس کنار گذاشته شد.')}>کنار گذاشتن</button></span>}]}/>
    </Card>
  </>}</Async>;
}
