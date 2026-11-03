'use client';
/* Traveller documents: customer upload/list/delete; staff review queue with blurred preview and audited reveal. */
import {useEffect, useState, type FormEvent} from 'react';
import {Async, Card, Stats, Table, dateFa, errorOf, fa, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;
const TYPES: [string, string][] = [['passport', 'گذرنامه'], ['national_id', 'کارت ملی'], ['visa', 'ویزا'], ['photo', 'عکس پرسنلی'], ['birth_certificate', 'شناسنامه'], ['other', 'سایر']];
const STATUS: Record<string, [string, string]> = {submitted: ['در انتظار بررسی', 'warn'], approved: ['تأیید شد', 'ok'], rejected: ['رد شد', 'bad'], deleted: ['حذف شد', '']};
const badge = (s: string) => <span className={`pn-badge ${STATUS[s]?.[1] ?? ''}`}>{STATUS[s]?.[0] ?? s}</span>;
const size = (b: number) => b > 1024 * 1024 ? `${fa(Math.round(b / 1024 / 102.4) / 10)} مگابایت` : `${fa(Math.round(b / 1024))} کیلوبایت`;

export function CustomerDocuments() {
  const {state, reload, api} = useLoad<Row>('/me/documents');
  const [msg, setMsg] = useState<Msg>(null); const [busy, setBusy] = useState(false);
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setMsg(null); setBusy(true);
    const form = new FormData(e.currentTarget);
    for (const k of ['number', 'holder_name', 'expires_on', 'reservation_id']) if (!form.get(k)) form.delete(k);
    try {await api.postForm('/me/documents', form); e.currentTarget.reset(); setMsg({ok: true, text: 'مدرک بارگذاری شد و در صف بررسی است.'}); reload();}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});} finally {setBusy(false);}
  }
  async function remove(id: string) {setMsg(null); try {await api.delete(`/me/documents/${id}`, {}); setMsg({ok: true, text: 'فایل مدرک حذف شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Async state={state}>{d => <>
    <Card title="بارگذاری مدرک">
      <p className="pn-muted">فایل JPG، PNG یا PDF تا ۱۵ مگابایت. فقط کارشناس عملیات آن را می‌بیند و {fa(d.retention_days)} روز بعد (یا پس از پایان سفر) خودکار حذف می‌شود.</p>
      <Note msg={msg}/>
      <form className="pn-form" onSubmit={upload}>
        <label>نوع مدرک<select name="doc_type" required defaultValue="passport">{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label>نام دارنده<input name="holder_name" maxLength={160}/></label>
        <label>شماره‌ی مدرک (فقط سه رقم آخر نگه داشته می‌شود)<input name="number" className="pn-ltr" maxLength={30}/></label>
        <label>تاریخ انقضا<input name="expires_on" type="date"/></label>
        <label>فایل<input name="file" type="file" accept=".jpg,.jpeg,.png,.pdf" required/></label>
        <button className="pn-btn" disabled={busy}>{busy ? 'در حال ارسال…' : 'بارگذاری'}</button>
      </form>
    </Card>
    <Card title="مدارک من"><Table rows={d.items} rowKey={(r: Row) => r.id} empty="مدرکی بارگذاری نکرده‌اید." cols={[
      {label: 'نوع', cell: (r: Row) => r.doc_type_fa}, {label: 'شماره', cell: (r: Row) => <span className="pn-ltr">{r.number ?? '—'}</span>},
      {label: 'وضعیت', cell: (r: Row) => <>{badge(r.status)}{r.status === 'rejected' && r.review_note ? <small className="pn-muted"> {r.review_note}</small> : null}</>},
      {label: 'بارگذاری', cell: (r: Row) => dateFa(r.uploaded_at)}, {label: 'حذف خودکار', cell: (r: Row) => r.has_file ? dateFa(r.delete_after) : '—'},
      {label: '', cell: (r: Row) => r.has_file ? <button className="pn-btn ghost" onClick={() => void remove(r.id)}>حذف فایل</button> : null}]}/></Card>
  </>}</Async>;
}

function Preview({doc, close}: {doc: Row; close: () => void}) {
  const {api} = useLoad<Row>(null);
  const [url, setUrl] = useState<string | null>(null); const [orig, setOrig] = useState<string | null>(null);
  const [reason, setReason] = useState(''); const [note, setNote] = useState(''); const [msg, setMsg] = useState<Msg>(null);
  useEffect(() => {
    let u: string | null = null;
    if (doc.content_type?.startsWith('image/')) api.getBlob(`/ops/documents/${doc.id}/preview`).then(b => {u = URL.createObjectURL(b); setUrl(u);}).catch(x => setMsg({ok: false, text: errorOf(x).message}));
    return () => {if (u) URL.revokeObjectURL(u);};
  }, [api, doc.id, doc.content_type]);
  useEffect(() => () => {if (orig) URL.revokeObjectURL(orig);}, [orig]);
  async function reveal(e: FormEvent) {e.preventDefault(); setMsg(null); try {const b = await api.postBlob(`/ops/documents/${doc.id}/reveal`, {reason}); setOrig(URL.createObjectURL(b)); setMsg({ok: true, text: 'اصل مدرک باز شد و در سوابق ممیزی ثبت شد.'});} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  async function decide(decision: 'approve' | 'reject') {setMsg(null); try {await api.post(`/ops/documents/${doc.id}/review`, {decision, note: note || null}); close();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title={`${doc.doc_type_fa} — ${doc.owner ?? ''}`} action={<button className="pn-btn ghost" onClick={close}>بازگشت به صف</button>}>
    <Stats items={[{label: 'شماره', value: doc.number ?? '—'}, {label: 'انقضا', value: doc.expires_on ? dateFa(doc.expires_on) : '—'}, {label: 'رزرو', value: doc.booking_reference ?? '—'}, {label: 'حجم', value: size(doc.byte_size)}]}/>
    <div className="doc-view">
      {orig ? (doc.content_type === 'application/pdf' ? <iframe title="اصل مدرک" src={orig} className="doc-frame"/> : <img src={orig} alt="اصل مدرک" className="doc-img"/>)
        : url ? <img src={url} alt="پیش‌نمایش پوشانده‌ی مدرک" className="doc-img"/> : <p className="pn-muted">{doc.content_type === 'application/pdf' ? 'برای PDF پیش‌نمایش پوشانده وجود ندارد.' : 'در حال دریافت پیش‌نمایش…'}</p>}
    </div>
    <Note msg={msg}/>
    {!orig && <form className="pn-form" onSubmit={reveal}><label>دلیل دیدن اصل مدرک (در سوابق ثبت می‌شود)<input value={reason} onChange={e => setReason(e.target.value)} minLength={5} required/></label><button className="pn-btn ghost">نمایش اصل</button></form>}
    {doc.status !== 'deleted' && <div className="pn-form"><label>یادداشت بررسی (برای رد لازم است)<input value={note} onChange={e => setNote(e.target.value)} maxLength={500}/></label>
      <div className="sec-actions"><button className="pn-btn" onClick={() => void decide('approve')}>تأیید مدرک</button><button className="pn-btn ghost" onClick={() => void decide('reject')}>رد مدرک</button></div></div>}
  </Card>;
}

export function DocumentQueue() {
  const [status, setStatus] = useState('submitted'); const [open, setOpen] = useState<Row | null>(null);
  const {state, reload} = useLoad<Row>(`/ops/documents?status=${status}`);
  if (open) return <Preview doc={open} close={() => {setOpen(null); reload();}}/>;
  return <Async state={state}>{d => <>
    <Stats items={[{label: 'در انتظار بررسی', value: fa(d.counts.submitted)}, {label: 'تأییدشده', value: fa(d.counts.approved)}, {label: 'ردشده', value: fa(d.counts.rejected)}, {label: 'حذف‌شده', value: fa(d.counts.deleted), hint: `نگهداری ${fa(d.retention_days)} روز`}]}/>
    {d.purged_now > 0 && <p className="pn-note">{fa(d.purged_now)} فایل که مهلت نگهداری‌اش تمام شده بود حذف شد.</p>}
    <Card title="صف مدارک" action={<select aria-label="وضعیت" value={status} onChange={e => setStatus(e.target.value)}>{[['submitted', 'در انتظار بررسی'], ['approved', 'تأییدشده'], ['rejected', 'ردشده'], ['deleted', 'حذف‌شده'], ['all', 'همه']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}>
      <Table rows={d.items} rowKey={(r: Row) => r.id} empty="مدرکی در این وضعیت نیست." cols={[
        {label: 'مسافر/مشتری', cell: (r: Row) => r.holder_name ?? r.owner}, {label: 'نوع', cell: (r: Row) => r.doc_type_fa}, {label: 'شماره', cell: (r: Row) => <span className="pn-ltr">{r.number ?? '—'}</span>},
        {label: 'رزرو', cell: (r: Row) => <span className="pn-ltr">{r.booking_reference ?? '—'}</span>}, {label: 'وضعیت', cell: (r: Row) => badge(r.status)},
        {label: 'بارگذاری', cell: (r: Row) => dateFa(r.uploaded_at)}, {label: '', cell: (r: Row) => r.has_file ? <button className="pn-btn ghost" onClick={() => setOpen(r)}>بررسی</button> : null}]}/>
    </Card>
  </>}</Async>;
}
