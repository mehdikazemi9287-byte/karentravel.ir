'use client';
/* Supplier performance: cancellation rate, purchases, and purchase reconciliation against the supplier's statement. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Table, errorOf, fa, money, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;

function Reconcile({supplier, close}: {supplier: Row; close: () => void}) {
  const runs = useLoad<Row>(`/commerce/suppliers/${supplier.id}/reconciliations`);
  const today = new Date().toISOString().slice(0, 10);
  const [range, setRange] = useState({from: today.slice(0, 8) + '01', to: today});
  const [file, setFile] = useState<File | null>(null); const [result, setResult] = useState<Row | null>(null); const [msg, setMsg] = useState<Msg>(null);
  async function send(confirm: boolean) {
    if (!file) return; setMsg(null);
    const f = new FormData(); f.append('file', file); f.append('date_from', range.from); f.append('date_to', range.to); f.append('confirm', confirm ? 'true' : 'false');
    try {const r = await runs.api.postForm<Row>(`/commerce/suppliers/${supplier.id}/reconcile`, f); setResult(r); if (confirm) {setMsg({ok: true, text: 'نتیجه‌ی تطبیق ذخیره شد.'}); runs.reload();}}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  const submit = (e: FormEvent) => {e.preventDefault(); void send(false);};
  const tbl = (rows: Row[], empty: string, diff = false) => <Table rows={rows} rowKey={(r: Row) => `${r.ref}-${r.date ?? ''}`} empty={empty} cols={[
    {label: 'مرجع', cell: (r: Row) => <span className="pn-ltr">{r.ref}</span>}, {label: 'تاریخ', cell: (r: Row) => <span className="pn-ltr">{r.date ?? '—'}</span>},
    {label: 'صورت‌حساب تأمین‌کننده', cell: (r: Row) => r.their_amount !== undefined ? money(r.their_amount, 'IRR') : r.amount !== undefined ? money(r.amount, 'IRR') : '—'},
    {label: 'دفتر ما', cell: (r: Row) => r.our_amount !== undefined ? money(r.our_amount, 'IRR') : '—'}, ...(diff ? [{label: 'اختلاف', cell: (r: Row) => money(r.difference, 'IRR')}] : [])]}/>;
  return <Card title={`تطبیق خرید — ${supplier.name}`} action={<button className="pn-btn ghost" onClick={close}>بازگشت</button>}>
    <p className="pn-muted">صورت‌حساب تأمین‌کننده را به‌صورت اکسل یا CSV بارگذاری کنید؛ سطر اول باید ستون «شماره/مرجع» و «مبلغ» (و اختیاری «تاریخ») داشته باشد. مرجع با شماره‌ی رزرو، شناسه‌ی رزرو یا شماره‌ی پیگیری ما تطبیق داده می‌شود.</p>
    <Note msg={msg}/>
    <form className="pn-form" onSubmit={submit}>
      <label>از تاریخ<input type="date" dir="ltr" value={range.from} onChange={e => setRange({...range, from: e.target.value})} required/></label>
      <label>تا تاریخ<input type="date" dir="ltr" value={range.to} onChange={e => setRange({...range, to: e.target.value})} required/></label>
      <label>فایل صورت‌حساب<input type="file" accept=".xlsx,.csv" onChange={e => setFile(e.target.files?.[0] ?? null)} required/></label>
      <button className="pn-btn">پیش‌نمایش تطبیق</button>
    </form>
    {result && <>
      <div className="pn-stats">{[['تطبیق کامل', result.matched.length], ['اختلاف مبلغ', result.amount_differs.length], ['فقط در صورت‌حساب آن‌ها', result.only_theirs.length], ['فقط در دفتر ما', result.only_ours.length]].map(([l, v]) =>
        <div className="pn-stat" key={l as string}><small>{l}</small><strong>{fa(v as number)}</strong></div>)}
        <div className="pn-stat"><small>اختلاف جمع</small><strong>{money(result.totals.difference, 'IRR')}</strong><span>آن‌ها {money(result.totals.theirs, 'IRR')} / ما {money(result.totals.ours, 'IRR')}</span></div></div>
      {result.errors?.length > 0 && <p className="pn-note error">{result.errors.slice(0, 5).join('؛ ')}</p>}
      <h3>اختلاف مبلغ</h3>{tbl(result.amount_differs, 'اختلاف مبلغی نیست.', true)}
      <h3>فقط در صورت‌حساب تأمین‌کننده</h3>{tbl(result.only_theirs, 'موردی نیست.')}
      <h3>فقط در دفتر ما</h3>{tbl(result.only_ours, 'موردی نیست.')}
      {!result.run_id && <div><button className="pn-btn" onClick={() => void send(true)}>ذخیره‌ی نتیجه به‌عنوان سابقه</button></div>}
    </>}
    <h3>سوابق تطبیق</h3>
    <Async state={runs.state}>{d => <Table rows={d.items} rowKey={(r: Row) => r.id} empty="تطبیقی ذخیره نشده است." cols={[
      {label: 'بازه', cell: (r: Row) => <span className="pn-ltr">{r.from} → {r.to}</span>}, {label: 'فایل', cell: (r: Row) => r.file}, {label: 'کامل', cell: (r: Row) => fa(r.matched)},
      {label: 'اختلاف', cell: (r: Row) => fa(r.differs)}, {label: 'فقط آن‌ها', cell: (r: Row) => fa(r.only_theirs)}, {label: 'فقط ما', cell: (r: Row) => fa(r.only_ours)}, {label: 'اختلاف جمع', cell: (r: Row) => money(r.difference, 'IRR')}]}/>}</Async>
  </Card>;
}

export function SupplierInsights() {
  const [days, setDays] = useState(90); const [open, setOpen] = useState<Row | null>(null);
  const {state} = useLoad<Row>(`/commerce/suppliers/insights?days=${days}`);
  if (open) return <Reconcile supplier={open} close={() => setOpen(null)}/>;
  return <Async state={state}>{d => <Card title="عملکرد تأمین‌کنندگان" action={<select aria-label="بازه" value={days} onChange={e => setDays(Number(e.target.value))}>{[30, 90, 180, 365].map(n => <option key={n} value={n}>{fa(n)} روز اخیر</option>)}</select>}>
    <p className="pn-muted">نرخ کنسلی = رزروهای کنسل، ناموفق، مسترد یا منقضی ÷ همه‌ی رزروهای تأمین‌کننده در بازه. رزروی که تأمین‌کننده‌اش معلوم نیست شمرده نمی‌شود.</p>
    <Table rows={d.items} rowKey={(r: Row) => r.id} empty="تأمین‌کننده‌ای ثبت نشده است." cols={[
      {label: 'تأمین‌کننده', cell: (r: Row) => r.name}, {label: 'رزرو', cell: (r: Row) => fa(r.reservations)}, {label: 'کنسلی', cell: (r: Row) => fa(r.cancelled)},
      {label: 'نرخ کنسلی', cell: (r: Row) => r.cancellation_rate === null ? '—' : <span className={`pn-badge ${r.cancellation_rate >= 20 ? 'bad' : r.cancellation_rate >= 10 ? 'warn' : 'ok'}`}>{fa(r.cancellation_rate)}٪</span>},
      {label: 'خرید در بازه', cell: (r: Row) => money(r.purchases, 'IRR')},
      {label: 'آخرین تطبیق', cell: (r: Row) => r.last_recon ? (r.last_recon.differs || r.last_recon.only_theirs || r.last_recon.only_ours ? <span className="pn-badge warn">{fa(r.last_recon.differs + r.last_recon.only_theirs + r.last_recon.only_ours)} مغایرت</span> : <span className="pn-badge ok">بدون مغایرت</span>) : '—'},
      {label: '', cell: (r: Row) => <button className="pn-btn ghost" onClick={() => setOpen(r)}>تطبیق خرید</button>}]}/>
  </Card>}</Async>;
}
