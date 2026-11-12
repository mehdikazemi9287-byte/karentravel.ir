'use client';
/* Ops after-sales (spec §2.9 OPS-02 queue with SLA, OPS-03 handling with approve/reject dialogs; Figma 216:1587 / 216:2070).
   The server applies the state machine (a wrong transition is 409) and computes the refund from the verified policy;
   ops only choose policy vs. manual penalty (with a reason). No margin or commission is shown here (spec §3.3). */
import Link from 'next/link';
import {useState} from 'react';
import {serviceFa, useLoad} from '../PanelKit';
import {DataTable, DecisionDialog, EmptyState, Loaded, MoneyRows, Ref, Skeleton, StatusChip, Timeline, Unavail, faNum, jDate, jDateTime, messageOf, newKey, rial, type Next, type Step} from './kit';

type QueueItem = {id: string; request_type: string; request_type_fa: string; status: string; created_at: string; reservation: {id: string; booking_reference: string | null; service_type: string; status: string};
  customer_name: string | null; assigned_to: string | null; assigned_to_user_id: number | null; amount: number | null; severity: string; next: Next};
type Queue = {items: QueueItem[]; has_more: boolean; counts: Record<string, number>; generated_at: string};
type Detail = QueueItem & {reason: string | null; quote: {total_amount: number; penalty_amount: number; refundable_amount: number; policy_source: string} | null;
  current_quote: {total_amount: number; penalty_amount: number; refundable_amount: number; policy_source: string} | null; refund_destination_label: string | null; destination_detail: {holder_name?: string; sheba_masked?: string};
  penalty_amount: number | null; penalty_source: string | null; approved_amount: number | null; decision_reason: string | null; decided_by: string | null; supplier: {reference?: string; requested_at?: string; response?: {refundable_amount?: number | null; penalty_amount?: number | null; reference?: string | null; note?: string | null}};
  refund: {id: string; status: string; amount: number} | null; payment: {captured_amount: number; refunded_amount: number; refundable_remaining: number; provider_reference: string | null} | null;
  money: {customer_total: number; supplier_amount: number | null; service_fee: number | null; taxes: Record<string, number>} | null; can_override: boolean; allowed_actions: string[];
  agency_credit: {available: boolean; label: string; agency_name: string | null; net_irr: number; remaining_irr: number; required: boolean} | null;
  timeline: {steps: Step[]; next: Next}; policy_at_booking: {source?: string; cancellation?: {refundable?: boolean; penalty_amount?: number}}};

const slaChip = (n: Next) => {
  if (!n) return <span className="as-muted">—</span>;
  if (n.paused) return <StatusChip status="needs_customer" label="متوقف (منتظر مشتری)"/>;
  if (!n.eta) return '—';
  const h = Math.round((new Date(n.eta).getTime() - Date.now()) / 3_600_000);
  return <StatusChip status={h < 0 ? 'failed' : h < 4 ? 'pending_review' : 'approved'} label={h < 0 ? `${faNum(-h)} ساعت گذشته` : `${faNum(h)} ساعت مانده`}/>;
};

/* ---------------------------------------------------------------- OPS-02 queue */
export function OpsServiceQueue({queue}: {queue: string}) {
  const [filter, setFilter] = useState<'open' | 'me' | 'unassigned' | 'closed'>('open'); const [type, setType] = useState('');
  const path = `/ops/queues/service_requests?status=${filter === 'closed' ? 'closed' : 'open'}${filter === 'me' || filter === 'unassigned' ? `&assignee=${filter}` : ''}${type ? `&request_type=${type}` : ''}`;
  const q = useLoad<Queue>(queue === 'service_requests' ? path : null); const [busy, setBusy] = useState(''); const [error, setError] = useState('');
  if (queue !== 'service_requests') return <div className="as"><Unavail title="این صف هنوز ساخته نشده است">در فاز ۱ فقط صف «درخواست‌های لغو، تغییر و استرداد» فعال است؛ صف‌های صدور ناموفق، تأیید تأمین‌کننده و تغییرات برنامه در فاز ۴ می‌آیند.</Unavail>
    <Link className="as-btn" href="/backoffice/queues/service_requests">رفتن به صف درخواست‌ها</Link></div>;
  async function take(id: string) {setBusy(id); setError(''); try {await q.api.post(`/ops/queues/service_requests/items/${id}/assign`, {}); q.reload();} catch (e) {setError(messageOf(e));} finally {setBusy('');}}
  return <div className="as"><section className="as-card">
    <div className="as-row" style={{justifyContent: 'space-between'}}>
      <div className="as-tabs" role="tablist" aria-label="فیلتر صف">{([['open', 'همهٔ باز'], ['me', 'کارهای من'], ['unassigned', 'بدون مسئول'], ['closed', 'بسته‌شده']] as const).map(([k, l]) =>
        <button key={k} type="button" role="tab" aria-selected={filter === k} onClick={() => setFilter(k)}>{l}</button>)}</div>
      <label className="as-field" style={{flex: '0 1 220px'}}>نوع درخواست<select value={type} onChange={e => setType(e.target.value)}><option value="">همه</option><option value="cancel">لغو</option><option value="refund">استرداد</option><option value="change">تغییر</option></select></label>
    </div>
    {error && <p className="as-note bad" role="alert">{error}</p>}
    <Loaded state={q.state} reload={q.reload} skeleton={<Skeleton kind="table" rows={6}/>}>{d => <>
      <p className="as-muted">بازشده: {faNum((d.counts.submitted ?? 0) + (d.counts.under_review ?? 0) + (d.counts.waiting_supplier ?? 0) + (d.counts.needs_customer ?? 0))} · در صف مالی: {faNum(d.counts.refund_queued ?? 0)} · به‌روزرسانی {jDateTime(d.generated_at)}</p>
      {d.items.length === 0 ? <EmptyState title="درخواستی در این صف نیست"/> : <DataTable caption="صف درخواست‌های لغو، تغییر و استرداد" rows={d.items} rowKey={r => r.id} cols={[
        {label: 'SLA', cell: r => slaChip(r.next)}, {label: 'نوع', cell: r => <span>{r.request_type_fa} <small className="as-muted">({r.severity === 'HIGH' ? 'اولویت بالا' : 'متوسط'})</small></span>},
        {label: 'رزرو', cell: r => <Ref>{r.reservation.booking_reference ?? r.reservation.id.slice(0, 8)}</Ref>}, {label: 'مشتری', cell: r => r.customer_name ?? '—'},
        {label: 'مبلغ', cell: r => <span className="as-num">{rial(r.amount)}</span>}, {label: 'وضعیت', cell: r => <StatusChip status={r.status}/>}, {label: 'مسئول', cell: r => r.assigned_to ?? <button type="button" className="as-btn ghost" disabled={busy === r.id} onClick={() => void take(r.id)}>برداشتن</button>},
        {label: '', cell: r => <Link className="as-link" href={`/backoffice/requests/${r.id}`}>رسیدگی</Link>}]}/>}</>}</Loaded>
  </section></div>;
}

/* ---------------------------------------------------------------- OPS-03 handling */
const ACTION_FA: Record<string, string> = {start_review: 'شروع بررسی', request_supplier: 'ارسال به تأمین‌کننده', record_supplier_response: 'ثبت پاسخ تأمین‌کننده', need_customer: 'پرسش از مشتری', approve: 'تأیید و ارسال به مالی', reject: 'رد درخواست', close: 'بستن درخواست'};
export function OpsRequestHandling({id}: {id: string}) {
  const d = useLoad<Detail>(`/ops/service-requests/${id}`);
  const [dialog, setDialog] = useState<string>(''); const [reason, setReason] = useState(''); const [mode, setMode] = useState<'policy' | 'manual'>('policy'); const [penalty, setPenalty] = useState('');
  const [supRef, setSupRef] = useState(''); const [supAmount, setSupAmount] = useState(''); const [supPenalty, setSupPenalty] = useState(''); const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [ok, setOk] = useState('');
  const toInt = (s: string) => {const n = Number(s.replace(/[۰-۹]/g, c => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[,٬\s]/g, '')); return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null;};
  async function run(action: string, body: Record<string, unknown> = {}) {
    setBusy(true); setError(''); setOk('');
    try {await d.api.post(`/backoffice/booking-requests/${id}/actions`, {action, ...body}, newKey('sr-action')); setDialog(''); setReason(''); setNote(''); setOk(`«${ACTION_FA[action] ?? 'یادداشت'}» ثبت شد.`); d.reload();}
    catch (e) {setError(messageOf(e));} finally {setBusy(false);}
  }
  async function take() {setBusy(true); setError(''); try {await d.api.post(`/ops/queues/service_requests/items/${id}/assign`, {}); d.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}}
  return <div className="as"><Loaded state={d.state} reload={d.reload} skeleton={<><Skeleton rows={3}/><Skeleton kind="timeline"/></>}>{r => {
    const quote = r.current_quote ?? r.quote; const remaining = r.agency_credit?.required ? r.agency_credit.remaining_irr : r.payment?.refundable_remaining ?? 0;
    const manualPenalty = toInt(penalty); const manualRefund = manualPenalty !== null ? remaining - manualPenalty : null;
    const needsOverride = mode === 'manual' && manualRefund !== null && (quote ? manualRefund > Math.min(quote.refundable_amount, remaining) : manualRefund > 0);
    return <>
      <section className="as-card"><div className="as-card-head"><div><h2>{r.request_type_fa} · رزرو <Ref>{r.reservation.booking_reference ?? r.reservation.id.slice(0, 8)}</Ref></h2>
        <p className="as-muted">{serviceFa(r.reservation.service_type)} · مشتری: {r.customer_name ?? '—'} · ثبت {jDateTime(r.created_at)}</p></div>
        <div className="as-row"><StatusChip status={r.status}/>{slaChip(r.next)}</div></div>
        <dl className="as-dl"><dt>مسئول</dt><dd>{r.assigned_to ?? <button type="button" className="as-btn ghost" disabled={busy} onClick={() => void take()}>برداشتن (تخصیص به من)</button>}</dd>
          <dt>وضعیت رزرو</dt><dd><StatusChip status={r.reservation.status}/></dd><dt>دلیل مشتری</dt><dd>{r.reason ?? '—'}</dd>
          <dt>مقصد وجه</dt><dd>{r.refund_destination_label ?? '—'}{r.destination_detail?.sheba_masked ? <> · <Ref>{r.destination_detail.sheba_masked}</Ref> ({r.destination_detail.holder_name})</> : null}</dd>
          {r.decision_reason && <><dt>تصمیم</dt><dd>{r.decision_reason}{r.decided_by ? ` — ${r.decided_by}` : ''}</dd></>}</dl></section>
      {ok && <p className="as-note ok" role="status">{ok}</p>}{error && <p className="as-note bad" role="alert">{error}</p>}
      <div className="as-grid2">
        <div style={{display: 'grid', gap: 16}}>
          <section className="as-card" aria-labelledby="op-tl"><h2 id="op-tl">روند درخواست</h2><Timeline steps={r.timeline.steps} next={r.timeline.next}/></section>
          <section className="as-card" aria-labelledby="op-sup"><h2 id="op-sup">وضعیت تأمین‌کننده</h2>
            {r.supplier.response ? <dl className="as-dl"><dt>مبلغ قابل استرداد تأمین‌کننده</dt><dd>{rial(r.supplier.response.refundable_amount ?? null)}</dd><dt>جریمهٔ تأمین‌کننده</dt><dd>{rial(r.supplier.response.penalty_amount ?? null)}</dd><dt>مرجع</dt><dd><Ref>{r.supplier.response.reference ?? '—'}</Ref></dd></dl>
              : r.supplier.requested_at ? <p>ارسال‌شده در {jDateTime(r.supplier.requested_at)} {r.supplier.reference ? <>· مرجع <Ref>{r.supplier.reference}</Ref></> : null}؛ منتظر پاسخ.</p> : <p className="as-muted">هنوز برای تأمین‌کننده ارسال نشده است.</p>}</section>
          <section className="as-card" aria-labelledby="op-note"><h2 id="op-note">یادداشت داخلی</h2><label className="as-field">یادداشت (فقط کارکنان می‌بینند)<textarea rows={2} value={note} onChange={e => setNote(e.target.value)}/></label>
            <div className="as-actions"><button type="button" className="as-btn ghost" disabled={busy || note.trim().length < 2} onClick={() => void run('note', {reason: note.trim()})}>ثبت یادداشت</button></div></section>
        </div>
        <div style={{display: 'grid', gap: 16}}>
          <section className="as-card" aria-labelledby="op-act"><h2 id="op-act">اقدام‌ها</h2>
            {r.allowed_actions.filter(a => a !== 'note').length === 0 ? <p className="as-muted">اقدامی در این وضعیت ممکن نیست.</p> : <div style={{display: 'grid', gap: 8}}>
              {r.allowed_actions.filter(a => a !== 'note').map(a => <button key={a} type="button" className={`as-btn ${a === 'approve' ? '' : a === 'reject' ? 'danger' : 'ghost'}`} disabled={busy}
                onClick={() => (['start_review', 'close'].includes(a) ? void run(a) : setDialog(a))}>{ACTION_FA[a]}</button>)}</div>}
            <p className="as-muted">هر اقدام با نام شما در سوابق ثبت و به مشتری اطلاع داده می‌شود.</p></section>
          <section className="as-card" aria-labelledby="op-money"><h2 id="op-money">تفکیک مبلغ (نمای عملیات)</h2>
            {r.money ? <MoneyRows label="تفکیک مبلغ" lines={[{label: 'جمع پرداختی مشتری', value: rial(r.money.customer_total), tone: 'total'}, ...(r.money.supplier_amount !== null ? [{label: 'مبلغ تأمین‌کننده', value: rial(r.money.supplier_amount)}] : []),
              ...(r.money.service_fee ? [{label: 'کارمزد خدمات', value: rial(r.money.service_fee)}] : [])]}/> : <Unavail title="تفکیک قیمت ثبت نشده">برای این رزرو PriceBreakdown ثبت نشده است.</Unavail>}
            {quote ? <MoneyRows label="quote استرداد" lines={[{label: 'جریمه طبق قوانین زمان خرید', value: rial(quote.penalty_amount), tone: 'neg'}, {label: 'قابل استرداد (محاسبهٔ سرور)', value: rial(Math.min(quote.refundable_amount, remaining)), tone: 'good'}]}/>
              : <Unavail title="قوانین لغو تأییدشده ندارد">جریمه را پس از پاسخ تأمین‌کننده، دستی و با دلیل وارد کنید.</Unavail>}
            {r.payment && <p className="as-muted">پرداخت ثبت‌شده: {rial(r.payment.captured_amount)} · مسترد قبلی: {rial(r.payment.refunded_amount)}</p>}
            {r.refund && <p>استرداد صف مالی: {rial(r.refund.amount)} <StatusChip status={r.refund.status}/></p>}</section>
        </div>
      </div>
      <DecisionDialog open={dialog === 'approve'} title="تأیید درخواست و ارسال به مالی" confirmLabel="تأیید و ارسال به صف مالی" busy={busy} error={error} onClose={() => setDialog('')}
        onSubmit={() => void run('approve', r.request_type === 'change' ? {reason: reason.trim() || null} : {penalty_mode: mode, penalty_amount: mode === 'manual' ? manualPenalty : null, reason: reason.trim() || null, ...(r.agency_credit ? {refund_destination: 'agency_credit'} : {})})}>
        {r.request_type === 'change' ? <p>تغییر رزرو تأیید می‌شود و رزرو به وضعیت «تغییریافته» می‌رود.</p> : <>
          {r.agency_credit && <fieldset className="as-choice" style={{border: 0, padding: 0, margin: 0}}><legend className="as-muted">مقصد استرداد</legend>
            <label><input type="radio" name="dest" checked readOnly/><b>بازگشت به اعتبار آژانس</b><small>{r.agency_credit.agency_name ?? 'آژانس'} · قابل برگشت {rial(r.agency_credit.remaining_irr)} · پس از تأیید کارشناس مالی</small></label>
            <label aria-disabled><input type="radio" name="dest" disabled/><b>کیف پول یا کارت مسافر</b><small>برای رزرو پرداخت‌شده از حساب آژانس مجاز نیست</small></label></fieldset>}
          <fieldset className="as-choice" style={{border: 0, padding: 0, margin: 0}}><legend className="as-muted">جریمه</legend>
            <label aria-disabled={!quote}><input type="radio" name="pm" disabled={!quote} checked={mode === 'policy'} onChange={() => setMode('policy')}/><b>طبق قوانین لغو تأییدشده</b><small>{quote ? `استرداد ${rial(Math.min(quote.refundable_amount, remaining))}` : 'برای این رزرو ثبت نشده است'}</small></label>
            <label><input type="radio" name="pm" checked={mode === 'manual'} onChange={() => setMode('manual')}/><b>دستی (با دلیل)</b><small>مثلاً جریمهٔ اعلامی تأمین‌کننده</small></label></fieldset>
          {mode === 'manual' && <label className="as-field">مبلغ جریمه (ریال)<input inputMode="numeric" value={penalty} onChange={e => setPenalty(e.target.value)} aria-describedby="pm-help"/>
            <small id="pm-help">{manualRefund !== null ? `مبلغ استرداد: ${rial(Math.max(manualRefund, 0))}` : 'عدد صحیح ریال'}</small>
            {needsOverride && <span className="as-err">{r.can_override ? 'بیشتر از محاسبهٔ قوانین است؛ با مجوز سرپرستی شما ثبت می‌شود.' : 'بیشتر از محاسبهٔ قوانین است و تأیید سرپرست (refund:override) لازم دارد.'}</span>}</label>}
        </>}
        <label className="as-field">دلیل {mode === 'manual' ? '(اجباری)' : '(اختیاری)'}<textarea rows={3} value={reason} onChange={e => setReason(e.target.value)} required={mode === 'manual'} minLength={mode === 'manual' ? 5 : undefined}/></label>
      </DecisionDialog>
      <DecisionDialog open={dialog === 'reject'} title="رد درخواست" confirmLabel="رد درخواست" danger busy={busy} error={error} onClose={() => setDialog('')} onSubmit={() => void run('reject', {reason: reason.trim()})}>
        <p>رزرو به وضعیت پیش از درخواست برمی‌گردد و دلیل برای مشتری نمایش داده می‌شود.</p>
        <label className="as-field">دلیل رد (اجباری، برای مشتری)<textarea rows={3} value={reason} onChange={e => setReason(e.target.value)} required minLength={5}/></label></DecisionDialog>
      <DecisionDialog open={dialog === 'need_customer'} title="پرسش از مشتری" confirmLabel="ارسال پرسش" busy={busy} error={error} onClose={() => setDialog('')} onSubmit={() => void run('need_customer', {reason: reason.trim()})}>
        <p className="as-muted">تا پاسخ مشتری، زمان‌سنج SLA متوقف می‌شود.</p><label className="as-field">پرسش<textarea rows={3} value={reason} onChange={e => setReason(e.target.value)} required minLength={5}/></label></DecisionDialog>
      <DecisionDialog open={dialog === 'request_supplier'} title="ارسال به تأمین‌کننده" confirmLabel="ثبت ارسال" busy={busy} error={error} onClose={() => setDialog('')} onSubmit={() => void run('request_supplier', {supplier_reference: supRef.trim() || null, reason: reason.trim() || null})}>
        <label className="as-field">مرجع / شمارهٔ درخواست نزد تأمین‌کننده<input value={supRef} onChange={e => setSupRef(e.target.value)} dir="ltr"/></label>
        <label className="as-field">توضیح<textarea rows={2} value={reason} onChange={e => setReason(e.target.value)}/></label></DecisionDialog>
      <DecisionDialog open={dialog === 'record_supplier_response'} title="ثبت پاسخ تأمین‌کننده" confirmLabel="ثبت پاسخ" busy={busy} error={error} onClose={() => setDialog('')}
        onSubmit={() => void run('record_supplier_response', {supplier_refundable_amount: toInt(supAmount), supplier_penalty_amount: toInt(supPenalty), supplier_reference: supRef.trim() || null, reason: reason.trim() || null})}>
        <label className="as-field">مبلغ قابل استرداد تأمین‌کننده (ریال)<input inputMode="numeric" value={supAmount} onChange={e => setSupAmount(e.target.value)}/></label>
        <label className="as-field">جریمهٔ تأمین‌کننده (ریال)<input inputMode="numeric" value={supPenalty} onChange={e => setSupPenalty(e.target.value)}/></label>
        <label className="as-field">مرجع<input value={supRef} onChange={e => setSupRef(e.target.value)} dir="ltr"/></label>
        <label className="as-field">توضیح<textarea rows={2} value={reason} onChange={e => setReason(e.target.value)}/></label></DecisionDialog>
    </>;
  }}</Loaded><p className="as-muted"><Link className="as-link" href="/backoffice/queues/service_requests">بازگشت به صف</Link></p></div>;
}
