'use client';
/* Markup-rule import from Excel (upload -> review per-row errors -> confirm -> result). The server validates every row
   with the same rules as the markup form and writes all rows or none; nothing is computed on the client. */
import {useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {Card, Stats, Table, errorOf, fa, useLoad} from './PanelKit';

type Row = Record<string, any>;
type Msg = {ok: boolean; text: string} | null;
const SCOPE_FA: Record<string, string> = {any: 'همه', domestic: 'داخلی', international: 'خارجی'};
const FTYPE_FA: Record<string, string> = {any: 'همه', system: 'سیستمی', charter: 'چارتری'};

export function MarkupImport({done}: {done?: () => void}) {
  const {api} = useLoad<unknown>(null);
  const {api: client, session} = useAuth();
  const [file, setFile] = useState<File | null>(null); const [report, setReport] = useState<Row | null>(null); const [msg, setMsg] = useState<Msg>(null); const [busy, setBusy] = useState(false);
  async function template() {
    setMsg(null);
    try {
      const res = await fetch(`${client.apiBase}/commerce/markup-rules/import/template?fmt=xlsx`, {headers: session ? {Authorization: `Bearer ${session.access_token}`} : {}});
      if (!res.ok) throw new Error(res.status === 403 ? 'این حساب به قالب دسترسی ندارد.' : 'دریافت قالب انجام نشد.');
      const url = URL.createObjectURL(await res.blob()); const a = document.createElement('a'); a.href = url; a.download = 'markup-rules-import.xlsx'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  async function send(confirm: boolean) {
    if (!file) return; setBusy(true); setMsg(null);
    const form = new FormData(); form.append('file', file); form.append('confirm', confirm ? 'true' : 'false');
    try {const r = await api.postForm<Row>('/commerce/markup-rules/import', form); setReport(r); if (r.stage === 'done') {setMsg({ok: true, text: `${fa(r.created)} قاعده ثبت شد.`}); done?.();}}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});} finally {setBusy(false);}
  }
  const rate = (d: Row, k: string) => d.calc === 'fixed' ? `${fa(d[k])} ریال` : `${fa(d[k] / 100)}٪`;
  return <Card title="ورود قاعده‌های مارک‌آپ از اکسل" action={<button className="pn-btn ghost" onClick={() => void template()}>دریافت قالب</button>}>
    <p className="pn-muted">ستون‌ها: گروه (نام)، تأمین‌کننده، داخلی/خارجی، سیستمی/چارتری، ایرلاین، مبدأ، مقصد، درصد یا مبلغ ثابت بزرگسال/کودک/نوزاد، فعال. ارقام فارسی پذیرفته می‌شوند. گروه و تأمین‌کننده باید از قبل تعریف شده باشند. تا وقتی ردیف خطادار باشد چیزی ثبت نمی‌شود.</p>
    <div className="pn-form"><label htmlFor="f-markup-import">فایل xlsx یا csv<input id="f-markup-import" type="file" accept=".xlsx,.csv" onChange={e => {setFile(e.target.files?.[0] ?? null); setReport(null); setMsg(null);}}/></label>
      <button className="pn-btn" disabled={!file || busy} onClick={() => void send(false)}>بررسی فایل</button>
      {report?.stage === 'review' && <button className="pn-btn" disabled={busy || report.errors > 0 || !report.total} onClick={() => void send(true)}>{report.errors > 0 ? 'ابتدا خطاها را در فایل اصلاح کنید' : `ثبت ${fa(report.total)} قاعده`}</button>}</div>
    {msg && <p className={`pn-note ${msg.ok ? '' : 'error'}`} role={msg.ok ? 'status' : 'alert'}>{msg.text}</p>}
    {report?.stage === 'review' && <>
      <Stats items={[{label: 'ردیف‌ها', value: fa(report.total)}, {label: 'سالم', value: fa(report.valid)}, {label: 'خطا', value: fa(report.errors)}, {label: 'هشدار', value: fa(report.warnings)}]}/>
      <Table rows={report.rows} rowKey={(r: Row) => String(r.row)} empty="ردیفی در فایل نیست." cols={[
        {label: 'ردیف', cell: (r: Row) => fa(r.row)}, {label: 'عنوان', cell: (r: Row) => r.data.title || '—'},
        {label: 'شرط', cell: (r: Row) => [r.data.supplier_id, SCOPE_FA[r.data.scope], FTYPE_FA[r.data.flight_type], r.data.airline_code, [r.data.origin, r.data.destination].filter(Boolean).join('→')].filter(Boolean).join('، ')},
        {label: 'بزرگسال/کودک/نوزاد', cell: (r: Row) => r.errors.length ? '—' : `${rate(r.data, 'adult')} / ${rate(r.data, 'child')} / ${rate(r.data, 'infant')}`},
        {label: 'وضعیت', cell: (r: Row) => r.errors.length ? <span className="pn-badge bad">{r.errors.join('، ')}</span> : r.warnings.length ? <span className="pn-badge warn">{r.warnings.join('، ')}</span> : <span className="pn-badge ok">سالم</span>}]}/>
    </>}
  </Card>;
}
