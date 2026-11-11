'use client';
/* Panels Phase 1 (rest): «امروز», two-person approvals, change-price proposals (ops + customer), failed payments, gateway
   settlement import, bank payout batches, dated tax rates, ops SLA settings and saved passengers of an organization/agency.
   Styling follows the Panels library (Figma 207:2); none of these pages has its own Figma frame yet (see
   docs/product/panels/07-phase1-rest-security.md). Every figure comes from the API; nothing here computes money. */
import Link from 'next/link';
import {useMemo, useState, type FormEvent} from 'react';
import {useAuth} from '../../../lib/api/auth-context';
import {homeFor, type Area} from '../../../lib/panel-access';
import {FundingApprovals} from '../FundingApprovals';
import {AgencyScope} from '../AgencyPanel';
import {OrgScope} from '../OrganizationPanel';
import {PanelShell, useLoad} from '../PanelKit';
import {ConfirmMoney, DataTable, EmptyState, Loaded, Ref, StatusChip, Unavail, jDate, jDateTime, newKey, rial, toman} from '../aftersales/kit';
import {DateField, Feedback, Field, digitsLatin, parseRial, pct, useAction} from '../b2b/B2BKit';
import './phase1.css';

const roleOf = (session: unknown) => (session as {user?: {role?: string}} | null)?.user?.role ?? '';

/* ------------------------------------------------------------------ «امروز» (spec §1.4) */
type TodayItem = {key: string; level: 'bad' | 'warn' | 'info'; count: number; label: string; href: string; oldest_at: string | null; sla_due_at: string | null};
type McRow = {id: string; kind_label: string; summary: string; amount: number | null; created_at: string | null};
const LEVEL_FA = {bad: 'SLA گذشته', warn: 'نیازمند اقدام', info: 'برای اطلاع'};

export function TodayPage() {
  const {session} = useAuth(); const role = roleOf(session);
  const home = homeFor(role);
  const area: Area = ['backoffice_expert'].includes(role) ? 'ops' : role === 'finance_operator' ? 'finance' : ['tenant_admin', 'platform_admin'].includes(role) ? 'admin'
    : home.startsWith('/agency') ? 'agency' : home.startsWith('/organization') || home.startsWith('/employee') ? 'organization' : home.startsWith('/supplier') ? 'supplier' : 'customer';
  return <PanelShell area={area} title="امروز" intro="کارهای منتظر شما، به ترتیب فوریت. فقط صف‌هایی که نقش شما روی آن‌ها کار می‌کند."><div className="as"><TodayBody/></div></PanelShell>;
}
function TodayBody() {
  const {state, reload} = useLoad<{items: TodayItem[]; approvals: McRow[]; generated_at: string}>('/panel/today');
  return <Loaded state={state} reload={reload}>{d => <>
    {d.items.length === 0 ? <EmptyState title="کار منتظری ندارید">صف‌های شما خالی است.</EmptyState>
      : <ul className="p1-today" aria-label="کارهای منتظر">{d.items.slice(0, 8).map(i => <li key={i.key} className={i.level} data-key={i.key}>
        <span className="p1-count">{i.count.toLocaleString('fa-IR')}</span>
        <span className="p1-today-text"><b>{i.label}</b><small>{LEVEL_FA[i.level]}{i.sla_due_at ? ` · موعد: ${jDateTime(i.sla_due_at)}` : ''}{i.oldest_at ? ` · قدیمی‌ترین: ${jDate(i.oldest_at)}` : ''}</small></span>
        <Link className="as-btn ghost" href={i.href}>رسیدگی</Link></li>)}</ul>}
    {d.approvals.length > 0 && <section className="as-card" id="approvals"><h2>منتظر تأیید شما (دو نفره)</h2>
      <DataTable caption="درخواست‌های منتظر تأیید" rows={d.approvals} rowKey={r => r.id} cols={[{label: 'نوع', cell: r => r.kind_label}, {label: 'شرح', cell: r => r.summary || '—'},
        {label: 'مبلغ', cell: r => r.amount === null ? '—' : rial(r.amount)}, {label: 'ثبت', cell: r => jDateTime(r.created_at)}]}/>
      <Link className="as-link" href="/finance/approvals">رفتن به صف تأیید</Link></section>}
    <p className="pn-muted">به‌روزرسانی: {jDateTime(d.generated_at)} <button type="button" className="as-btn ghost" onClick={reload}>تازه‌سازی</button></p>
  </>}</Loaded>;
}

export function ApprovalsPage() {
  return <><FundingApprovals/><p className="pn-muted">تغییر قیمت رزرو، فایل پرداخت گروهی بانکی، شارژ و کاهش کیف پول و سقف اعتبار همه از همین صف تأیید می‌شوند. ثبت‌کننده نمی‌تواند درخواست خودش را تأیید کند.</p></>;
}

/* ------------------------------------------------------------------ change-price proposals */
type Proposal = {id: string; status: string; current_total: number; proposed_total: number; difference: number; reason: string; created_at: string | null;
  customer_decided_at: string | null; customer_note: string | null; settlement: string | null; proposed_by?: string; approved_by?: string; customer?: string;
  reservation: {id: string; booking_reference: string | null; service_type: string; status: string} | null};
const PC_FA: Record<string, [string, string]> = {pending_approval: ['منتظر تأیید مالی', 'warn'], awaiting_customer: ['منتظر پاسخ مشتری', 'info'], accepted: ['پذیرفته‌شده', 'ok'],
  declined: ['ردشده توسط مشتری', 'bad'], rejected: ['ردشده در تأیید', 'bad'], withdrawn: ['پس‌گرفته‌شده', '']};
function PcChip({s}: {s: string}) {const h = PC_FA[s]; return <span className={`as-chip ${h?.[1] ?? ''}`}>{h?.[0] ?? s}</span>;}

export function OpsPriceChanges() {
  const {session} = useAuth(); const canPropose = ['backoffice_expert', 'platform_admin'].includes(roleOf(session));
  const [filter, setFilter] = useState('');
  const {state, reload} = useLoad<{items: Proposal[]}>(`/ops/price-changes${filter ? `?status=${filter}` : ''}`);
  const act = useAction();
  const [form, setForm] = useState({reservation_id: '', proposed_total: '', reason: ''}); const [key] = useState(() => newKey('pc'));
  async function submit(e: FormEvent) {
    e.preventDefault(); const amount = parseRial(form.proposed_total);
    if (!Number.isFinite(amount) || amount <= 0) {act.setError('مبلغ پیشنهادی را به ریال و به عدد وارد کنید.'); return;}
    const r = await act.run(api => api.post('/ops/price-changes', {reservation_id: form.reservation_id.trim(), proposed_total: amount, reason: form.reason}, key), 'پیشنهاد ثبت شد و برای تأیید مالی رفت؛ تا تأیید مالی و پذیرش مشتری هیچ مبلغی جابه‌جا نمی‌شود.');
    if (r) {setForm({reservation_id: '', proposed_total: '', reason: ''}); reload();}
  }
  async function withdraw(p: Proposal) {const reason = window.prompt('علت پس‌گرفتن پیشنهاد'); if (!reason) return; if (await act.run(api => api.post(`/ops/price-changes/${p.id}/withdraw`, {reason}), 'پیشنهاد پس گرفته شد.')) reload();}
  return <>
    {canPropose && <section className="as-card"><h2>ثبت پیشنهاد تغییر قیمت</h2>
      <p className="pn-muted">کارشناس عملیات پیشنهاد می‌دهد، کارشناس مالی یا مدیر مجموعه تأیید می‌کند و سپس مشتری باید آن را بپذیرد. هیچ مبلغی خودکار کسر یا پرداخت نمی‌شود.</p>
      <form className="p1-form" onSubmit={submit}>
        <Field label="شناسهٔ رزرو"><input value={form.reservation_id} onChange={e => setForm({...form, reservation_id: e.target.value})} dir="ltr" minLength={36} maxLength={36} required/></Field>
        <Field label="مبلغ کل پیشنهادی (ریال)" hint={form.proposed_total && Number.isFinite(parseRial(form.proposed_total)) ? rial(parseRial(form.proposed_total)) : undefined}><input value={form.proposed_total} onChange={e => setForm({...form, proposed_total: e.target.value})} inputMode="numeric" required/></Field>
        <Field label="دلیل (برای مشتری هم نمایش داده می‌شود)"><textarea value={form.reason} onChange={e => setForm({...form, reason: e.target.value})} minLength={10} maxLength={500} rows={2} required/></Field>
        <button className="as-btn" disabled={act.busy}>ثبت و ارسال برای تأیید</button>
      </form></section>}
    <Feedback error={act.error} done={act.done}/>
    <section className="as-card"><div className="as-card-head"><h2>پیشنهادها</h2>
      <label className="p1-inline">وضعیت<select value={filter} onChange={e => setFilter(e.target.value)}><option value="">همه</option>{Object.entries(PC_FA).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select></label></div>
      <Loaded state={state} reload={reload}>{d => d.items.length === 0 ? <EmptyState title="پیشنهادی ثبت نشده است"/> : <DataTable caption="پیشنهادهای تغییر قیمت" rows={d.items} rowKey={p => p.id} cols={[
        {label: 'رزرو', cell: p => <Ref>{p.reservation?.booking_reference ?? p.reservation?.id.slice(0, 8) ?? '—'}</Ref>}, {label: 'مبلغ فعلی', cell: p => rial(p.current_total)},
        {label: 'پیشنهادی', cell: p => rial(p.proposed_total)}, {label: 'تفاوت', cell: p => `${p.difference > 0 ? '+' : '−'}${rial(Math.abs(p.difference))}`},
        {label: 'وضعیت', cell: p => <PcChip s={p.status}/>}, {label: 'پیشنهاددهنده / تأییدکننده', cell: p => `${p.proposed_by ?? '—'} / ${p.approved_by ?? '—'}`},
        {label: 'دلیل', cell: p => p.reason}, {label: '', cell: p => ['pending_approval', 'awaiting_customer'].includes(p.status) && canPropose ? <button type="button" className="as-btn ghost" onClick={() => withdraw(p)}>پس‌گرفتن</button> : null}]}/>}</Loaded>
    </section></>;
}

export function CustomerPriceChanges() {
  const {state, reload} = useLoad<{items: Proposal[]}>('/me/price-changes'); const act = useAction();
  const [open, setOpen] = useState<Proposal | null>(null);
  async function decide(p: Proposal, accept: boolean) {
    const r = await act.run(api => api.post(`/me/price-changes/${p.id}/${accept ? 'accept' : 'decline'}`, {}), accept ? 'تغییر قیمت را پذیرفتید. کارشناس مالی برای دریافت یا بازگشت تفاوت با شما هماهنگ می‌کند؛ هیچ مبلغی خودکار کسر نشد.' : 'پیشنهاد را رد کردید؛ رزرو با مبلغ قبلی می‌ماند و کارشناس با شما تماس می‌گیرد.');
    if (r) {setOpen(null); reload();}
  }
  return <Loaded state={state} reload={reload}>{d => <>
    <Feedback error={act.error} done={act.done}/>
    {d.items.length === 0 ? <EmptyState title="پیشنهاد تغییر قیمتی ندارید">اگر مبلغ رزروی نیاز به تغییر داشته باشد، اینجا از شما تأیید گرفته می‌شود.</EmptyState>
      : d.items.map(p => <section key={p.id} className="as-card"><div className="as-card-head"><h2>رزرو <Ref>{p.reservation?.booking_reference ?? '—'}</Ref></h2><PcChip s={p.status}/></div>
        <dl className="as-money" aria-label="تغییر مبلغ"><div><dt>مبلغ فعلی</dt><dd>{toman(p.current_total)}</dd></div><div><dt>مبلغ پیشنهادی</dt><dd>{toman(p.proposed_total)}</dd></div>
          <div className="total"><dt>{p.difference > 0 ? 'مبلغ اضافه' : 'مبلغ بازگشتی'}</dt><dd>{toman(Math.abs(p.difference))}</dd></div></dl>
        <p>دلیل: {p.reason}</p>
        {p.status === 'awaiting_customer' && <div className="as-row"><button type="button" className="as-btn" onClick={() => setOpen(p)}>بررسی و پذیرش</button>
          <button type="button" className="as-btn ghost" disabled={act.busy} onClick={() => decide(p, false)}>رد پیشنهاد</button></div>}
      </section>)}
    {open && <ConfirmMoney open title="پذیرش تغییر مبلغ رزرو" amount={Math.abs(open.difference)} destination={open.difference > 0 ? 'پرداخت تفاوت پس از هماهنگی کارشناس مالی (کسر خودکار نمی‌شود)' : 'بازگشت تفاوت پس از هماهنگی کارشناس مالی'}
      reason={open.reason} busy={act.busy} error={act.error} confirmLabel="می‌پذیرم" onConfirm={() => decide(open, true)} onClose={() => setOpen(null)}/>}
  </>}</Loaded>;
}

/* ------------------------------------------------------------------ failed payments */
type Failed = {id: string; status: string; amount: number; provider: string; authority: string | null; last_event: string | null; updated_at: string | null; customer: string | null; later_paid: boolean;
  reservation: {id: string; booking_reference: string | null; service_type: string; status: string}};
export function FailedPayments() {
  const [days, setDays] = useState(30); const [abandoned, setAbandoned] = useState(true);
  const {state, reload} = useLoad<{items: Failed[]; summary: {failed: number; abandoned: number; failed_amount: number; recovered: number}}>(`/finance/payments/failed?days=${days}&include_abandoned=${abandoned}`);
  return <section className="as-card"><div className="as-card-head"><h2>پرداخت‌های ناموفق و رهاشده</h2>
    <div className="as-row"><label className="p1-inline">بازه<select value={days} onChange={e => setDays(Number(e.target.value))}>{[7, 30, 90].map(n => <option key={n} value={n}>{n.toLocaleString('fa-IR')} روز</option>)}</select></label>
      <label className="p1-inline"><input type="checkbox" checked={abandoned} onChange={e => setAbandoned(e.target.checked)}/> رهاشده (بیش از یک ساعت بی‌پاسخ)</label></div></div>
    <Loaded state={state} reload={reload}>{d => <>
      <div className="p1-stats"><span><small>ناموفق</small><b>{d.summary.failed.toLocaleString('fa-IR')}</b></span><span><small>رهاشده</small><b>{d.summary.abandoned.toLocaleString('fa-IR')}</b></span>
        <span><small>مبلغ ناموفق</small><b>{rial(d.summary.failed_amount)}</b></span><span><small>بعداً پرداخت‌شده</small><b>{d.summary.recovered.toLocaleString('fa-IR')}</b></span></div>
      {d.items.length === 0 ? <EmptyState title="پرداخت ناموفقی در این بازه نیست"/> : <DataTable caption="پرداخت‌های ناموفق" rows={d.items} rowKey={r => r.id} cols={[
        {label: 'زمان', cell: r => jDateTime(r.updated_at)}, {label: 'رزرو', cell: r => <Ref>{r.reservation.booking_reference ?? r.reservation.id.slice(0, 8)}</Ref>},
        {label: 'مشتری', cell: r => r.customer ?? '—'}, {label: 'مبلغ', cell: r => rial(r.amount)}, {label: 'وضعیت', cell: r => <span className={`as-chip ${r.status === 'failed' ? 'bad' : 'warn'}`}>{r.status === 'failed' ? 'ناموفق' : 'رهاشده'}</span>},
        {label: 'شناسهٔ درگاه', cell: r => r.authority ? <Ref>{r.authority}</Ref> : '—'}, {label: 'آخرین رویداد', cell: r => r.last_event ?? '—'},
        {label: 'بعداً پرداخت شد؟', cell: r => r.later_paid ? <span className="as-chip ok">بله</span> : <span className="as-chip">خیر</span>}]}/>}
      <p className="pn-muted">این فهرست فقط خواندنی است؛ تلاش دوباره را مشتری از مسیر پرداخت خودش انجام می‌دهد و هیچ درگاهی از این صفحه فراخوانی نمی‌شود.</p>
    </>}</Loaded></section>;
}

/* ------------------------------------------------------------------ gateway settlement import */
type ImportLine = {line: number; reference: string; amount: number; settled_on: string | null; match_status: string; note: string | null};
type ImportOut = {id?: string; filename?: string; row_count: number; matched_count: number; unmatched_count?: number; total_amount?: number; created_at?: string; uploaded_by?: string; lines?: ImportLine[]; dry_run?: boolean; duplicate_file?: boolean};
const MATCH_FA: Record<string, [string, string]> = {matched: ['منطبق', 'ok'], amount_mismatch: ['مغایرت مبلغ', 'bad'], not_captured: ['پرداخت در سامانه ثبت نشده', 'warn'], unmatched: ['یافت نشد', 'bad'], duplicate: ['تکراری در فایل', 'warn']};
export function SettlementImport() {
  const act = useAction(); const [file, setFile] = useState<{name: string; text: string} | null>(null); const [preview, setPreview] = useState<ImportOut | null>(null);
  const [onlyBad, setOnlyBad] = useState(true); const [pick, setPick] = useState('');
  const list = useLoad<{items: ImportOut[]}>('/finance/settlement-imports'); const detail = useLoad<ImportOut>(pick ? `/finance/settlement-imports/${pick}` : null);
  const [errors, setErrors] = useState<{line: number; column: string; message: string}[]>([]);
  async function read(f: File | undefined) {setPreview(null); setErrors([]); if (!f) return setFile(null); if (f.size > 2_000_000) {act.setError('حجم فایل بیش از ۲ مگابایت است.'); return;} setFile({name: f.name, text: await f.text()});}
  async function send(dry: boolean) {
    if (!file) return; setErrors([]);
    try {const r = await act.api.post<ImportOut>('/finance/settlement-imports', {filename: file.name, content: file.text, dry_run: dry}); act.setError('');
      if (dry) setPreview(r); else {setPreview(null); setFile(null); setPick(r.id ?? ''); list.reload();}}
    catch (e) {const d = (e as {detail?: {detail?: {errors?: typeof errors; message?: string}}})?.detail?.detail; setErrors(d?.errors ?? []); act.setError(d?.message ?? 'ارسال فایل ممکن نشد.');}
  }
  const shown = (lines?: ImportLine[]) => (lines ?? []).filter(l => !onlyBad || l.match_status !== 'matched');
  const lineTable = (lines?: ImportLine[]) => shown(lines).length === 0 ? <EmptyState title={onlyBad ? 'همهٔ ردیف‌ها منطبق‌اند' : 'ردیفی نیست'}/> : <DataTable caption="ردیف‌های فایل تسویه" rows={shown(lines)} rowKey={l => `${l.line}`} cols={[
    {label: 'ردیف', cell: l => l.line.toLocaleString('fa-IR')}, {label: 'شناسه', cell: l => <Ref>{l.reference}</Ref>}, {label: 'مبلغ', cell: l => rial(l.amount)}, {label: 'تاریخ تسویه', cell: l => l.settled_on ?? '—'},
    {label: 'نتیجه', cell: l => <span className={`as-chip ${MATCH_FA[l.match_status]?.[1] ?? ''}`}>{MATCH_FA[l.match_status]?.[0] ?? l.match_status}</span>}, {label: 'توضیح', cell: l => l.note ?? '—'}]}/>;
  return <>
    <section className="as-card"><h2>بارگذاری فایل تسویهٔ درگاه</h2>
      <p className="pn-muted">فایل CSV با سطر عنوان <Ref>reference,amount,settled_on</Ref> (مبلغ به ریال). ابتدا پیش‌نمایش بگیرید؛ ثبت فایل وضعیت هیچ پرداختی را تغییر نمی‌دهد و به درگاه وصل نمی‌شود. همان فایل دوبار ثبت نمی‌شود.</p>
      <div className="as-row"><input type="file" accept=".csv,text/csv" aria-label="فایل CSV تسویه" onChange={e => read(e.target.files?.[0])}/>
        <button type="button" className="as-btn ghost" disabled={!file || act.busy} onClick={() => send(true)}>پیش‌نمایش و تطبیق</button>
        <button type="button" className="as-btn" disabled={!preview || act.busy} onClick={() => send(false)}>ثبت فایل</button></div>
      <Feedback error={act.error}/>
      {errors.length > 0 && <DataTable caption="خطاهای فایل" rows={errors} rowKey={e => `${e.line}-${e.column}`} cols={[{label: 'ردیف', cell: e => e.line.toLocaleString('fa-IR')}, {label: 'ستون', cell: e => e.column}, {label: 'خطا', cell: e => e.message}]}/>}
      {preview && <><p><b>{preview.row_count.toLocaleString('fa-IR')}</b> ردیف، <b>{preview.matched_count.toLocaleString('fa-IR')}</b> منطبق.</p>
        <label className="p1-inline"><input type="checkbox" checked={onlyBad} onChange={e => setOnlyBad(e.target.checked)}/> فقط ردیف‌های نامنطبق</label>{lineTable(preview.lines)}</>}
    </section>
    <section className="as-card"><h2>فایل‌های ثبت‌شده</h2>
      <Loaded state={list.state} reload={list.reload}>{d => d.items.length === 0 ? <EmptyState title="هنوز فایلی ثبت نشده است"/> : <DataTable caption="فایل‌های تسویه" rows={d.items} rowKey={r => r.id ?? ''} cols={[
        {label: 'فایل', cell: r => r.filename}, {label: 'زمان', cell: r => jDateTime(r.created_at)}, {label: 'ثبت‌کننده', cell: r => r.uploaded_by ?? '—'}, {label: 'ردیف', cell: r => r.row_count.toLocaleString('fa-IR')},
        {label: 'منطبق', cell: r => r.matched_count.toLocaleString('fa-IR')}, {label: 'نامنطبق', cell: r => (r.unmatched_count ?? 0).toLocaleString('fa-IR')}, {label: 'جمع', cell: r => rial(r.total_amount)},
        {label: '', cell: r => <button type="button" className="as-btn ghost" onClick={() => setPick(r.id ?? '')}>ردیف‌ها</button>}]}/>}</Loaded>
      {pick && <Loaded state={detail.state} reload={detail.reload}>{d => <><h3>{d.filename}</h3><label className="p1-inline"><input type="checkbox" checked={onlyBad} onChange={e => setOnlyBad(e.target.checked)}/> فقط ردیف‌های نامنطبق</label>{lineTable(d.lines)}</>}</Loaded>}
    </section></>;
}

/* ------------------------------------------------------------------ bank payout batches */
type Candidate = {refund_id: string; amount: number; holder_name: string | null; sheba_masked: string | null; has_sheba: boolean; created_at: string | null};
type Batch = {id: string; status: string; item_count: number; total_amount: number; created_at: string | null; created_by: string | null; created_by_user_id: number; approved_by: string | null;
  file_name: string | null; file_sha256: string | null; file_ready: boolean; note: string | null; items: {refund_id: string; amount: number; holder_name: string; sheba_masked: string}[]};
const BATCH_FA: Record<string, [string, string]> = {pending_approval: ['منتظر تأیید نفر دوم', 'warn'], approved: ['تأییدشده، فایل آماده', 'ok'], rejected: ['ردشده', 'bad']};
export function BankBatches() {
  const cands = useLoad<{items: Candidate[]}>('/finance/bank-batches/candidates'); const list = useLoad<{items: Batch[]; me: number}>('/finance/bank-batches');
  const act = useAction(); const [sel, setSel] = useState<string[]>([]); const [confirm, setConfirm] = useState(false); const [key, setKey] = useState(() => newKey('bank-batch'));
  const total = useMemo(() => cands.state.kind === 'ready' ? cands.state.data.items.filter(c => sel.includes(c.refund_id)).reduce((s, c) => s + c.amount, 0) : 0, [cands.state, sel]);
  async function create() {
    const r = await act.run(api => api.post('/finance/bank-batches', {refund_ids: sel}, key), 'دسته ساخته شد و برای تأیید نفر دوم مالی رفت. فایل بانکی فقط پس از تأیید ساخته می‌شود.');
    if (r) {setSel([]); setConfirm(false); setKey(newKey('bank-batch')); cands.reload(); list.reload();}
  }
  async function download(b: Batch) {
    const blob = await act.run(api => api.getBlob(`/finance/bank-batches/${b.id}/file`)); if (!blob) return;
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = b.file_name ?? 'payout.csv'; a.click(); URL.revokeObjectURL(url);
  }
  return <>
    <section className="as-card"><h2>استردادهای آمادهٔ واریز بانکی</h2>
      <p className="pn-muted">استردادهایی که عملیات تأیید کرده و مقصد آن‌ها واریز به شباست. فایل گروهی فقط ساخته می‌شود و به هیچ بانکی ارسال نمی‌شود؛ پس از انجام واریز در بانک، کد پیگیری هر مورد را در «صف استرداد مالی» ثبت کنید.</p>
      <Loaded state={cands.state} reload={cands.reload}>{d => d.items.length === 0 ? <EmptyState title="موردی برای واریز بانکی نیست"/> : <>
        <DataTable caption="استردادهای قابل واریز" rows={d.items} rowKey={c => c.refund_id} cols={[
          {label: 'انتخاب', cell: c => <input type="checkbox" aria-label={`انتخاب ${c.holder_name ?? c.refund_id}`} disabled={!c.has_sheba} checked={sel.includes(c.refund_id)} onChange={e => setSel(e.target.checked ? [...sel, c.refund_id] : sel.filter(x => x !== c.refund_id))}/>},
          {label: 'صاحب حساب', cell: c => c.holder_name ?? '—'}, {label: 'شبا', cell: c => c.sheba_masked ? <Ref>{c.sheba_masked}</Ref> : <span className="as-chip bad">ثبت نشده</span>},
          {label: 'مبلغ', cell: c => rial(c.amount)}, {label: 'تأیید عملیات', cell: c => jDate(c.created_at)}]}/>
        <div className="as-row"><b>{sel.length.toLocaleString('fa-IR')} مورد · {rial(total)}</b><button type="button" className="as-btn" disabled={!sel.length || act.busy} onClick={() => setConfirm(true)}>ساخت دستهٔ پرداخت</button></div></>}</Loaded>
      <Feedback error={act.error} done={act.done}/>
    </section>
    <section className="as-card"><h2>دسته‌های پرداخت</h2>
      <Loaded state={list.state} reload={list.reload}>{d => d.items.length === 0 ? <EmptyState title="دسته‌ای ساخته نشده است"/> : <DataTable caption="دسته‌های پرداخت بانکی" rows={d.items} rowKey={b => b.id} cols={[
        {label: 'زمان', cell: b => jDateTime(b.created_at)}, {label: 'تعداد', cell: b => b.item_count.toLocaleString('fa-IR')}, {label: 'جمع', cell: b => rial(b.total_amount)},
        {label: 'وضعیت', cell: b => <span className={`as-chip ${BATCH_FA[b.status]?.[1] ?? ''}`}>{BATCH_FA[b.status]?.[0] ?? b.status}</span>},
        {label: 'سازنده / تأییدکننده', cell: b => `${b.created_by ?? '—'}${b.created_by_user_id === d.me ? ' (شما)' : ''} / ${b.approved_by ?? '—'}`},
        {label: 'فایل', cell: b => b.file_ready ? <button type="button" className="as-btn ghost" onClick={() => download(b)}>دریافت CSV</button> : b.status === 'pending_approval' ? <Link className="as-link" href="/finance/approvals">صف تأیید</Link> : '—'}]}/>}</Loaded>
    </section>
    {confirm && <ConfirmMoney open title="ساخت دستهٔ پرداخت بانکی" amount={total} destination={`${sel.length.toLocaleString('fa-IR')} حساب شبا (فایل؛ بدون ارسال به بانک)`} reason="واریز استردادهای تأییدشده"
      twoPerson="فایل بانکی فقط پس از تأیید یک کارشناس مالی دیگر ساخته می‌شود." busy={act.busy} error={act.error} confirmLabel="ساخت و ارسال برای تأیید" idempotencyKey={key} onConfirm={create} onClose={() => setConfirm(false)}/>}
  </>;
}

/* ------------------------------------------------------------------ dated tax rates (FIN-11) */
type TaxRow = {id: string; code: string; rate_bps: number; effective_from: string; effective_to: string | null; legal_reference: string; status: string; created_by: string | null; retire_reason: string | null};
type TaxOut = {source: 'table' | 'code_default'; current: {id: string; rate_bps: number; legal_reference: string} | null; items: TaxRow[];
  code_default: {code: string; rate_bps: number; effective_from: string; effective_to: string | null; legal_reference: string}[]};
export function TaxRates() {
  const {session} = useAuth(); const admin = ['tenant_admin', 'platform_admin'].includes(roleOf(session));
  const {state, reload} = useLoad<TaxOut>('/finance/tax-rates'); const act = useAction();
  const [f, setF] = useState({code: '', rate: '', from: '', to: '', ref: ''});
  async function add(e: FormEvent) {
    e.preventDefault(); const pctNum = Number(digitsLatin(f.rate)); if (!Number.isFinite(pctNum) || pctNum < 0 || pctNum > 50) {act.setError('نرخ را به درصد (مثلاً ۱۰) وارد کنید.'); return;}
    if (await act.run(api => api.post('/admin/tax-rates', {code: f.code, rate_bps: Math.round(pctNum * 100), effective_from: f.from, effective_to: f.to || null, legal_reference: f.ref}), 'نرخ ثبت شد و در سوابق ممیزی آمد.')) {setF({code: '', rate: '', from: '', to: '', ref: ''}); reload();}
  }
  async function retire(r: TaxRow) {const reason = window.prompt('علت بازنشسته کردن این نرخ'); if (!reason) return; if (await act.run(api => api.post(`/admin/tax-rates/${r.id}/retire`, {reason}), 'نرخ بازنشسته شد.')) reload();}
  return <Loaded state={state} reload={reload}>{d => <>
    <section className="as-card"><h2>نرخ جاری ارزش افزوده</h2>
      {d.current ? <p><b>{pct(d.current.rate_bps)}</b> — <Ref>{d.current.id}</Ref> — {d.current.legal_reference}</p> : <Unavail title="نرخی برای امروز ثبت نیست">تا ثبت نرخ معتبر، محاسبهٔ ارزش افزوده انجام نمی‌شود (هیچ نرخی حدس زده نمی‌شود).</Unavail>}
      <p className="pn-muted">{d.source === 'table' ? 'منبع: جدول تاریخ‌دار همین مجموعه.' : 'منبع: جدول پیش‌فرض بازبینی‌شده در کد (هنوز ردیفی در جدول این مجموعه ثبت نشده است). با ثبت اولین ردیف، فقط جدول ملاک است.'}</p>
      <p className="pn-muted">نرخ‌ها و مرجع قانونی باید پیش از استفاده با حسابدار تأیید شوند.</p></section>
    <section className="as-card"><h2>دوره‌های ثبت‌شده</h2>
      {d.items.length === 0 ? <DataTable caption="جدول پیش‌فرض" rows={d.code_default} rowKey={r => r.code} cols={[{label: 'کد', cell: r => <Ref>{r.code}</Ref>}, {label: 'نرخ', cell: r => pct(r.rate_bps)},
        {label: 'از', cell: r => jDate(r.effective_from)}, {label: 'تا', cell: r => r.effective_to ? jDate(r.effective_to) : 'ادامه دارد'}, {label: 'مرجع', cell: r => r.legal_reference}]}/>
        : <DataTable caption="نرخ‌های ثبت‌شده" rows={d.items} rowKey={r => r.id} cols={[{label: 'کد', cell: r => <Ref>{r.code}</Ref>}, {label: 'نرخ', cell: r => pct(r.rate_bps)},
          {label: 'از', cell: r => jDate(r.effective_from)}, {label: 'تا', cell: r => r.effective_to ? jDate(r.effective_to) : 'ادامه دارد'}, {label: 'مرجع', cell: r => r.legal_reference},
          {label: 'وضعیت', cell: r => <span className={`as-chip ${r.status === 'active' ? 'ok' : ''}`}>{r.status === 'active' ? 'فعال' : `بازنشسته${r.retire_reason ? ` (${r.retire_reason})` : ''}`}</span>},
          {label: '', cell: r => admin && r.status === 'active' ? <button type="button" className="as-btn ghost" onClick={() => retire(r)}>بازنشسته کردن</button> : null}]}/>}
    </section>
    {admin && <section className="as-card"><h2>ثبت نرخ تازه</h2><p className="pn-muted">ردیف‌ها ویرایش نمی‌شوند؛ برای اصلاح، ردیف قبلی را بازنشسته کنید و ردیف تازه ثبت کنید. بازه‌های فعال نباید هم‌پوشانی داشته باشند.</p>
      <form className="p1-form" onSubmit={add}>
        <Field label="کد"><input value={f.code} onChange={e => setF({...f, code: e.target.value})} dir="ltr" pattern="[A-Za-z0-9\-_.]{3,40}" required/></Field>
        <Field label="نرخ (درصد)"><input value={f.rate} onChange={e => setF({...f, rate: e.target.value})} inputMode="decimal" required/></Field>
        <DateField label="از تاریخ" value={f.from} onChange={v => setF({...f, from: v})} required/>
        <DateField label="تا تاریخ (اختیاری)" value={f.to} onChange={v => setF({...f, to: v})}/>
        <Field label="مرجع قانونی"><input value={f.ref} onChange={e => setF({...f, ref: e.target.value})} minLength={5} maxLength={300} required/></Field>
        <button className="as-btn" disabled={act.busy}>ثبت نرخ</button></form></section>}
    <Feedback error={act.error} done={act.done}/>
  </>}</Loaded>;
}

/* ------------------------------------------------------------------ ops SLA settings */
type SlaRow = {request_type: string; request_type_fa: string; status: string; status_fa: string; step: string; owner: string; default_minutes: number; minutes: number; source: string; reason: string | null; updated_by: string | null; updated_at: string | null};
const dur = (m: number) => m % 60 === 0 ? `${(m / 60).toLocaleString('fa-IR')} ساعت` : `${m.toLocaleString('fa-IR')} دقیقه`;
export function SlaSettings() {
  const {state, reload} = useLoad<{items: SlaRow[]; range_minutes: [number, number]}>('/ops/sla-policies'); const act = useAction();
  const [edit, setEdit] = useState<{row: SlaRow; minutes: string; reason: string} | null>(null);
  async function save(e: FormEvent) {
    e.preventDefault(); if (!edit) return; const minutes = Number(digitsLatin(edit.minutes));
    if (await act.run(api => api.put('/admin/sla-policies', {request_type: edit.row.request_type, status: edit.row.status, minutes, reason: edit.reason}), 'SLA ذخیره شد و در سوابق ممیزی آمد.')) {setEdit(null); reload();}
  }
  async function reset(r: SlaRow) {const reason = window.prompt('علت بازگشت به مقدار پیش‌فرض'); if (!reason) return; if (await act.run(api => api.post('/admin/sla-policies/reset', {request_type: r.request_type, status: r.status, reason}), 'به مقدار پیش‌فرض برگشت.')) reload();}
  return <Loaded state={state} reload={reload}>{d => <section className="as-card"><h2>SLA صف لغو، تغییر و استرداد</h2>
    <p className="pn-muted">زمان هدف هر گام برای هر نوع درخواست (بین {dur(d.range_minutes[0])} و {dur(d.range_minutes[1])}). موعد هدف در صف عملیات، صفحهٔ «امروز» و روند مشتری از همین جدول خوانده می‌شود. هر تغییر با دلیل در سوابق ممیزی ثبت می‌شود.</p>
    <DataTable caption="SLA" rows={d.items} rowKey={r => `${r.request_type}-${r.status}`} cols={[{label: 'نوع', cell: r => r.request_type_fa}, {label: 'وضعیت', cell: r => r.status_fa}, {label: 'گام', cell: r => `${r.step} (${r.owner})`},
      {label: 'SLA', cell: r => <b>{dur(r.minutes)}</b>}, {label: 'منبع', cell: r => r.source === 'tenant' ? <span className="as-chip info">اختصاصی{r.updated_by ? ` · ${r.updated_by}` : ''}</span> : <span className="as-chip">پیش‌فرض</span>},
      {label: '', cell: r => <span className="as-row"><button type="button" className="as-btn ghost" onClick={() => setEdit({row: r, minutes: String(r.minutes), reason: ''})}>ویرایش</button>{r.source === 'tenant' && <button type="button" className="as-btn ghost" onClick={() => reset(r)}>پیش‌فرض</button>}</span>}]}/>
    {edit && <form className="p1-form" onSubmit={save} aria-label="ویرایش SLA"><b>{edit.row.request_type_fa} · {edit.row.status_fa}</b>
      <Field label="دقیقه" hint={`پیش‌فرض: ${dur(edit.row.default_minutes)}`}><input value={edit.minutes} onChange={e => setEdit({...edit, minutes: e.target.value})} inputMode="numeric" required/></Field>
      <Field label="دلیل تغییر"><input value={edit.reason} onChange={e => setEdit({...edit, reason: e.target.value})} minLength={5} maxLength={300} required/></Field>
      <button className="as-btn" disabled={act.busy}>ذخیره</button><button type="button" className="as-btn ghost" onClick={() => setEdit(null)}>انصراف</button></form>}
    <Feedback error={act.error} done={act.done}/>
  </section>}</Loaded>;
}

/* ------------------------------------------------------------------ passengers of an organization / agency */
type Passenger = {id: string; full_name: string; national_code_masked: string | null; passport_number_masked: string | null; nationality: string | null; birth_date: string | null; passport_expiry: string | null};
function PassengersBody({scope, id, canEdit = true}: {scope: 'organization' | 'agency'; id: string; canEdit?: boolean}) {
  const [q, setQ] = useState(''); const base = `/scopes/${scope}/${id}/passengers`;
  const {state, reload} = useLoad<{items: Passenger[]}>(`${base}${q ? `?q=${encodeURIComponent(q)}` : ''}`); const act = useAction();
  const [f, setF] = useState({full_name: '', national_code: '', passport_number: '', passport_expiry: '', nationality: '', birth_date: ''});
  async function add(e: FormEvent) {
    e.preventDefault(); const body: Record<string, string> = {full_name: f.full_name};
    for (const k of ['national_code', 'passport_number', 'passport_expiry', 'nationality', 'birth_date'] as const) if (f[k]) body[k] = k === 'national_code' ? digitsLatin(f[k]) : f[k];
    if (await act.run(api => api.post(base, body), 'مسافر ذخیره شد.')) {setF({full_name: '', national_code: '', passport_number: '', passport_expiry: '', nationality: '', birth_date: ''}); reload();}
  }
  async function remove(p: Passenger) {if (!window.confirm(`«${p.full_name}» از فهرست حذف شود؟ رزروهای قبلی تغییر نمی‌کنند.`)) return; if (await act.run(api => api.post(`${base}/${p.id}/remove`, {}), 'از فهرست حذف شد.')) reload();}
  return <>
    <section className="as-card"><div className="as-card-head"><h2>مسافران ذخیره‌شده</h2><label className="p1-inline">جست‌وجو<input value={q} onChange={e => setQ(e.target.value)} maxLength={80}/></label></div>
      <p className="pn-muted">در فهرست فقط چهار رقم آخر کد ملی و گذرنامه نمایش داده می‌شود.</p>
      <Loaded state={state} reload={reload}>{d => d.items.length === 0 ? <EmptyState title="مسافری ذخیره نشده است"/> : <DataTable caption="مسافران" rows={d.items} rowKey={p => p.id} cols={[
        {label: 'نام', cell: p => p.full_name}, {label: 'کد ملی', cell: p => p.national_code_masked ? <Ref>{p.national_code_masked}</Ref> : '—'},
        {label: 'گذرنامه', cell: p => p.passport_number_masked ? <Ref>{p.passport_number_masked}</Ref> : '—'}, {label: 'انقضای گذرنامه', cell: p => p.passport_expiry ? jDate(p.passport_expiry) : '—'},
        {label: 'تابعیت', cell: p => p.nationality ?? '—'}, {label: '', cell: p => canEdit ? <button type="button" className="as-btn ghost" onClick={() => remove(p)}>حذف از فهرست</button> : null}]}/>}</Loaded>
    </section>
    {canEdit && <section className="as-card"><h2>افزودن مسافر</h2><form className="p1-form" onSubmit={add}>
      <Field label="نام و نام خانوادگی"><input value={f.full_name} onChange={e => setF({...f, full_name: e.target.value})} minLength={3} maxLength={160} required autoComplete="off"/></Field>
      <Field label="کد ملی (ایرانی)"><input value={f.national_code} onChange={e => setF({...f, national_code: e.target.value})} inputMode="numeric" maxLength={10} dir="ltr" autoComplete="off"/></Field>
      <Field label="تابعیت (کد دوحرفی)"><input value={f.nationality} onChange={e => setF({...f, nationality: e.target.value.toUpperCase()})} maxLength={2} dir="ltr" placeholder="IR"/></Field>
      <Field label="شمارهٔ گذرنامه"><input value={f.passport_number} onChange={e => setF({...f, passport_number: e.target.value.toUpperCase()})} maxLength={12} dir="ltr" autoComplete="off"/></Field>
      <DateField label="انقضای گذرنامه" value={f.passport_expiry} onChange={v => setF({...f, passport_expiry: v})}/>
      <DateField label="تاریخ تولد" value={f.birth_date} onChange={v => setF({...f, birth_date: v})}/>
      <button className="as-btn" disabled={act.busy}>ذخیره</button></form></section>}
    <Feedback error={act.error} done={act.done}/>
  </>;
}
export function OrgPassengers() {return <OrgScope>{org => <PassengersBody scope="organization" id={org.id}/>}</OrgScope>;}
export function AgencyPassengers() {return <AgencyScope>{a => <PassengersBody scope="agency" id={a.id}/>}</AgencyScope>;}
