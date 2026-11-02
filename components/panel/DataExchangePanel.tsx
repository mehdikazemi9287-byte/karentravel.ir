'use client';
/* Excel lead import for the sales desk (upload -> review errors/warnings -> confirm -> result)
   and the journal export with the tenant's account codes (for Faranegar). */
import {useState, type FormEvent} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {Async, Card, Stats, Table, errorOf, fa, useLoad} from './PanelKit';
import {FormFields, Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;

function useDownload() {
  const {api, session} = useAuth();
  return async (path: string, filename: string) => {
    const res = await fetch(`${api.apiBase}${path}`, {headers: session ? {Authorization: `Bearer ${session.access_token}`} : {}});
    if (!res.ok) throw new Error(res.status === 403 ? 'این حساب به خروجی دسترسی ندارد.' : 'دریافت فایل انجام نشد.');
    const url = URL.createObjectURL(await res.blob()); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
}

export function LeadImport({done}: {done?: () => void}) {
  const {api} = useLoad<unknown>(null);
  const download = useDownload();
  const [file, setFile] = useState<File | null>(null); const [report, setReport] = useState<Row | null>(null); const [msg, setMsg] = useState<Msg>(null); const [busy, setBusy] = useState(false);
  async function send(confirm: boolean) {
    if (!file) return; setBusy(true); setMsg(null);
    const form = new FormData(); form.append('file', file); form.append('confirm', confirm ? 'true' : 'false');
    try {const r = await api.postForm<Row>('/sales-desk/import', form); setReport(r); if (r.stage === 'done') {setMsg({ok: true, text: `${fa(r.created)} پرونده ساخته شد.`}); done?.();}}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});} finally {setBusy(false);}
  }
  const step = !file ? 1 : !report ? 2 : report.stage === 'review' ? 3 : 4;
  return <Card title="ورود اکسل مشتریان" action={<button className="pn-btn ghost" onClick={() => download('/sales-desk/import/template?fmt=xlsx', 'sales-desk-import.xlsx').catch(e => setMsg({ok: false, text: e.message}))}>دریافت قالب</button>}>
    <ol className="pn-chips" style={{listStyle: 'none', padding: 0}}>{['انتخاب فایل', 'بررسی', 'تأیید', 'نتیجه'].map((s, i) => <li key={s} className={step === i + 1 ? 'active' : ''} style={{padding: '4px 12px', borderRadius: 99, background: step === i + 1 ? 'var(--pn-plum,#3a1b3d)' : '#f3ebe2', color: step === i + 1 ? '#fff' : undefined}}>{fa(i + 1)}. {s}</li>)}</ol>
    <div className="pn-form"><label htmlFor="f-import">فایل xlsx یا csv (ستون‌های نام، موبایل، سفر لازم‌اند)<input id="f-import" type="file" accept=".xlsx,.csv" onChange={e => {setFile(e.target.files?.[0] ?? null); setReport(null); setMsg(null);}}/></label>
      <button className="pn-btn" disabled={!file || busy} onClick={() => send(false)}>بررسی فایل</button>
      {report?.stage === 'review' && <button className="pn-btn" disabled={busy || !report.importable} onClick={() => send(true)}>ثبت {fa(report.importable)} ردیف سالم</button>}</div>
    <Note msg={msg}/>
    {report && <>
      <Stats items={[{label: 'ردیف‌ها', value: fa(report.total)}, {label: 'قابل ثبت', value: fa(report.stage === 'done' ? report.created : report.importable)}, {label: 'خطا', value: fa(report.errors)}, {label: 'هشدار', value: fa(report.warnings)}]}/>
      <Table rows={report.rows.filter((r: Row) => r.errors.length || r.warnings.length || report.stage === 'review')} rowKey={(r: Row) => String(r.row)} empty="همه‌ی ردیف‌ها سالم‌اند." cols={[
        {label: 'ردیف', cell: (r: Row) => fa(r.row)}, {label: 'نام', cell: (r: Row) => r.data.customer_name || '—'}, {label: 'موبایل', cell: (r: Row) => <span className="pn-ltr">{r.data.mobile || '—'}</span>},
        {label: 'سفر', cell: (r: Row) => r.data.trip || '—'},
        {label: 'وضعیت', cell: (r: Row) => r.errors.length ? <span className="pn-badge bad">{r.errors.join('، ')}</span> : r.warnings.length ? <span className={`pn-badge ${r.will_import ? 'warn' : ''}`}>{r.warnings.join('، ')}</span> : <span className="pn-badge ok">سالم</span>}]}/>
    </>}
  </Card>;
}

function Codes() {
  const {state, reload, api} = useLoad<Row>('/commerce/accounting-codes');
  const [draft, setDraft] = useState<string | null>(null); const [msg, setMsg] = useState<Msg>(null);
  return <Async state={state}>{d => {
    const text: string = draft ?? d.items.map((c: Row) => [c.counterparty_type, c.account_type, c.code, c.title].join(' | ')).join('\n');
    async function save(e: FormEvent) {
      e.preventDefault(); setMsg(null);
      const items = text.split('\n').map((l: string) => l.trim()).filter(Boolean).map((l: string) => {const [counterparty_type, account_type, code, title] = l.split('|').map((x: string) => x.trim()); return {counterparty_type, account_type, code, title};});
      try {await api.put('/commerce/accounting-codes', {items}); setDraft(null); setMsg({ok: true, text: 'کدینگ ذخیره شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}
    }
    return <Card title="کدینگ حساب‌ها"><form className="pn-form" onSubmit={save}>
      <FormFields value={{codes: text}} set={v => setDraft(String(v.codes ?? ''))} fields={[{key: 'codes', label: 'هر خط: نوع طرف حساب | نوع حساب | کد | عنوان', type: 'textarea', wide: true,
        hint: `طرف حساب: ${d.counterparty_types.join('، ')} — نوع حساب: ${d.account_types.join('، ')}`}]}/>
      <button className="pn-btn">ذخیره (مدیر مالی)</button></form><Note msg={msg}/></Card>;
  }}</Async>;
}

export function JournalExport() {
  const [f, setF] = useState<Row>({date_from: '', date_to: ''});
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]).toString();
  const {state} = useLoad<Row>(`/commerce/treasury/export/check${qs ? `?${qs}` : ''}`);
  const download = useDownload(); const [msg, setMsg] = useState<Msg>(null);
  return <>
    <Card title="خروجی سند برای فرانگر">
      <div className="pn-form"><FormFields value={f} set={setF} fields={[{key: 'date_from', label: 'از تاریخ', type: 'date'}, {key: 'date_to', label: 'تا تاریخ', type: 'date'}]}/></div>
      <Async state={state}>{c => <>
        <Stats items={[{label: 'ردیف سند', value: fa(c.rows)}, {label: 'جمع بدهکار', value: fa(c.debit)}, {label: 'جمع بستانکار', value: fa(c.credit)}]}/>
        {c.unmapped.length > 0 && <p className="pn-note error">برای این ترکیب‌ها کد حساب تعریف نشده و ستون کد خالی می‌ماند: {c.unmapped.map((u: Row) => `${u.pair} (${fa(u.count)})`).join('، ')}</p>}
      </>}</Async>
      <div style={{display: 'flex', gap: 8}}>
        <button className="pn-btn" onClick={() => download(`/commerce/treasury/export?fmt=xlsx${qs ? `&${qs}` : ''}`, 'karenseir-journal.xlsx').catch(e => setMsg({ok: false, text: e.message}))}>دریافت اکسل</button>
        <button className="pn-btn ghost" onClick={() => download(`/commerce/treasury/export?fmt=csv${qs ? `&${qs}` : ''}`, 'karenseir-journal.csv').catch(e => setMsg({ok: false, text: e.message}))}>دریافت CSV</button></div>
      <p className="pn-muted">ستون‌ها یک سند عمومی است (تاریخ، شماره سند، کد و عنوان حساب، طرف حساب، شرح، بدهکار، بستانکار). اگر قالب ورود فرانگر شما ستون‌بندی دیگری دارد، نمونه‌اش را بدهید تا دقیقاً منطبق شود.</p>
      <Note msg={msg}/>
    </Card>
    <Codes/>
  </>;
}
