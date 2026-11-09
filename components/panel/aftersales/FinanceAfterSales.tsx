'use client';
/* Finance after-sales (spec §2.10 FIN-02 refund queue, FIN-02a execute with ConfirmMoney + two-person rule, FIN-04
   reconciliation actions; Figma 217:2637, 217:3134, 217:3366, 218:3922). Every payment needs two finance users: the
   first prepares (method, bank reference), the second approves and the money moves once (server-enforced). */
import Link from 'next/link';
import {useRef, useState} from 'react';
import {useLoad} from '../PanelKit';
import {ConfirmMoney, DataTable, DecisionDialog, EmptyState, Loaded, MoneyRows, Ref, Skeleton, StatusChip, Timeline, Unavail, faNum, jDateTime, messageOf, newKey, rial, type Next, type Step} from './kit';

type FinRefund = {id: string; status: string; amount: number; destination: string | null; destination_label: string | null; method: string | null; bank_reference: string | null; paid_at: string | null;
  destination_detail: {holder_name?: string; sheba_masked?: string; bank?: string; verified?: boolean}; penalty_amount: number; paid_total: number; penalty_source: string | null;
  breakdown: {basis: string; reason?: string; vat_rate_bps: number; agency_commission_reversed?: number; platform_markup_reversed?: number; service_fee_reversed?: number; vat_base_reversed?: number; vat_reversed?: number};
  prepared_by: string | null; prepared_by_user_id: number | null; prepared_at: string | null; approved_by: string | null; approved_at: string | null; pending_bank_reference: string | null; note: string | null;
  request_id: string; request_type: string; booking_reference: string | null; reservation_id: string; customer_name: string | null; created_at: string; approved_by_ops: string | null; age_hours: number};
type FinDetail = FinRefund & {journal: {account: string; debit: number; credit: number; memo: string}[]; tax_document: {subject: string; basis: string; status: string; lines: {code: string; base_reversed_irr: number; vat_irr: number}[]; totals: {vat_reversed: number | null; reason?: string}; due_at: string} | null;
  timeline: {steps: Step[]; next: Next}; can_approve: boolean; destinations: {key: string; label: string; available: boolean; detail: string; sheba_masked?: string}[]};
const ACCOUNT_FA: Record<string, string> = {customer_refunds: 'برگشت از فروش / استرداد مشتریان', customer_wallets: 'کیف پول مشتریان (بدهی)', bank: 'بانک'};
const CODE_FA: Record<string, string> = {AGENCY_COMMISSION: 'کمیسیون آژانس', PLATFORM_MARKUP: 'markup پلتفرم', SERVICE_FEE: 'کارمزد خدمات'};

/* ---------------------------------------------------------------- FIN-02 queue */
export function FinanceRefundQueue() {
  const [status, setStatus] = useState('open'); const q = useLoad<{items: FinRefund[]; summary: Record<string, {count: number; amount: number}>; me: number}>(`/finance/refunds?status=${status}`);
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton kind="table" rows={6}/>}>{d => <>
    <section className="as-today" aria-label="خلاصهٔ صف">{([['pending_finance', 'منتظر آماده‌سازی (نفر اول)'], ['awaiting_approval', 'منتظر تأیید (نفر دوم)'], ['succeeded', 'پرداخت‌شده'], ['returned', 'برگشت به عملیات']] as const).map(([k, l]) =>
      <a key={k} href={`#${k}`} className={k === 'awaiting_approval' && (d.summary[k]?.count ?? 0) > 0 ? 'warn' : ''} onClick={e => {e.preventDefault(); setStatus(k);}}><span className="as-muted">{l}</span><strong>{faNum(d.summary[k]?.count ?? 0)}</strong><span>{rial(d.summary[k]?.amount ?? 0)}</span></a>)}</section>
    <section className="as-card"><div className="as-tabs" role="tablist" aria-label="وضعیت">{([['open', 'باز'], ['pending_finance', 'نفر اول'], ['awaiting_approval', 'نفر دوم'], ['succeeded', 'پرداخت‌شده'], ['all', 'همه']] as const).map(([k, l]) =>
      <button key={k} type="button" role="tab" aria-selected={status === k} onClick={() => setStatus(k)}>{l}</button>)}</div>
      {d.items.length === 0 ? <EmptyState title="استردادی در این صف نیست"/> : <DataTable caption="صف استرداد" rows={d.items} rowKey={r => r.id} cols={[
        {label: 'رزرو', cell: r => <Ref>{r.booking_reference ?? r.reservation_id.slice(0, 8)}</Ref>}, {label: 'مشتری', cell: r => r.customer_name ?? '—'}, {label: 'مبلغ', cell: r => <b className="as-num">{rial(r.amount)}</b>},
        {label: 'مقصد', cell: r => <span>{r.destination_label ?? '—'}{r.destination_detail?.sheba_masked ? <> · <Ref>{r.destination_detail.sheba_masked}</Ref></> : null}</span>},
        {label: 'تأیید عملیات', cell: r => r.approved_by_ops ?? '—'}, {label: 'سن', cell: r => `${faNum(r.age_hours)} ساعت`},
        {label: 'وضعیت', cell: r => <span><StatusChip status={r.status}/>{r.status === 'awaiting_approval' && r.prepared_by_user_id === d.me ? <small className="as-muted"> (آماده‌سازی شما)</small> : null}</span>},
        {label: '', cell: r => <Link className="as-link" href={`/finance/refunds/${r.id}`}>{r.status === 'pending_finance' ? 'آماده‌سازی پرداخت' : r.status === 'awaiting_approval' ? 'بررسی و تأیید' : 'جزئیات'}</Link>}]}/>}
    </section></>}</Loaded></div>;
}

/* ---------------------------------------------------------------- FIN-02a execute */
export function FinanceRefundExecute({id}: {id: string}) {
  const d = useLoad<FinDetail>(`/finance/refunds/${id}`);
  const [method, setMethod] = useState<string>(''); const [ref, setRef] = useState(''); const [paidAt, setPaidAt] = useState(''); const [note, setNote] = useState('');
  const [confirm, setConfirm] = useState<'' | 'prepare' | 'approve'>(''); const [dialog, setDialog] = useState<'' | 'decline' | 'return'>(''); const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [ok, setOk] = useState('');
  const prepKey = useRef(newKey('refund-prepare')); const approveKey = useRef(newKey('refund-approve'));
  async function prepare(method: string) {
    setBusy(true); setError('');
    try {await d.api.post(`/finance/refunds/${id}/execute`, {method, bank_reference: method === 'bank_transfer' ? ref.trim() : null, paid_at: method === 'bank_transfer' && paidAt ? new Date(paidAt).toISOString() : null, note: note.trim() || null}, prepKey.current);
      prepKey.current = newKey('refund-prepare'); setConfirm(''); setOk('آماده شد و برای تأیید نفر دوم مالی ارسال شد.'); d.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}
  }
  async function approve() {
    setBusy(true); setError('');
    try {await d.api.post(`/finance/refunds/${id}/approve`, {}, approveKey.current); setConfirm(''); setOk('پرداخت ثبت شد؛ مشتری اعلان و کد پیگیری را می‌بیند.'); d.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}
  }
  async function side(kind: 'decline' | 'return') {
    setBusy(true); setError('');
    try {await d.api.post(`/finance/refunds/${id}/${kind}`, {reason: reason.trim()}); setDialog(''); setReason(''); setOk(kind === 'decline' ? 'به مرحلهٔ آماده‌سازی برگشت.' : 'به عملیات برگشت داده شد.'); d.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}
  }
  return <div className="as"><Loaded state={d.state} reload={d.reload} skeleton={<><Skeleton rows={3}/><Skeleton rows={4}/></>}>{r => {
    const m = method || r.destination || 'wallet'; const dest = <><b>{m === 'wallet' ? 'کیف پول کارن تراول' : m === 'bank_transfer' ? 'واریز بانکی (پایا/ساتنا) به شبا' : 'درگاه'}</b>
      {m === 'bank_transfer' && r.destination_detail?.sheba_masked && <div><Ref>{r.destination_detail.sheba_masked}</Ref> · صاحب حساب: {r.destination_detail.holder_name}{r.destination_detail.verified ? '' : ' (احراز نشده؛ با نام مشتری تطبیق دهید)'}</div>}</>;
    return <>
      <section className="as-card"><div className="as-card-head"><div><h2>استرداد رزرو <Ref>{r.booking_reference ?? r.reservation_id.slice(0, 8)}</Ref></h2><p className="as-muted">مشتری: {r.customer_name ?? '—'} · تأیید عملیات: {r.approved_by_ops ?? '—'} · ثبت {jDateTime(r.created_at)}</p></div><StatusChip status={r.status}/></div>
        <MoneyRows label="مبلغ استرداد" lines={[{label: 'مبلغ پرداخت‌شدهٔ باقی‌مانده', value: rial(r.paid_total)}, {label: `جریمه (${r.penalty_source === 'manual' ? 'دستی با دلیل' : 'طبق قوانین'})`, value: `− ${rial(r.penalty_amount)}`, tone: 'neg'}, {label: 'مبلغ استرداد', value: rial(r.amount), tone: 'good'}]}/></section>
      {ok && <p className="as-note ok" role="status">{ok}</p>}{error && !confirm && !dialog && <p className="as-note bad" role="alert">{error}</p>}
      <div className="as-grid2">
        <div style={{display: 'grid', gap: 16}}>
          {r.status === 'pending_finance' && <section className="as-card" aria-labelledby="fx-prep"><h2 id="fx-prep">آماده‌سازی پرداخت (نفر اول)</h2>
            <fieldset className="as-choice" style={{border: 0, padding: 0, margin: 0}}><legend className="as-muted">روش پرداخت</legend>
              {r.destinations.map(o => <label key={o.key} aria-disabled={!o.available && o.key !== 'wallet'}><input type="radio" name="m" disabled={o.key === 'gateway' || (o.key === 'bank_transfer' && !o.available)} checked={m === o.key} onChange={() => setMethod(o.key)}/>
                <b>{o.label}{o.key === r.destination ? ' (انتخاب مشتری)' : ''}</b><small>{o.key === 'wallet' ? 'فوری؛ موجودی کیف پول مشتری افزایش می‌یابد.' : o.detail}</small></label>)}</fieldset>
            {m === 'bank_transfer' && <div className="as-grid3"><label className="as-field">کد پیگیری پایا/ساتنا<input dir="ltr" value={ref} onChange={e => setRef(e.target.value)} required minLength={4}/></label>
              <label className="as-field">زمان واریز<input type="datetime-local" value={paidAt} onChange={e => setPaidAt(e.target.value)}/><small>اختیاری؛ پیش‌فرض زمان تأیید</small></label></div>}
            <label className="as-field">یادداشت<textarea rows={2} value={note} onChange={e => setNote(e.target.value)}/></label>
            <div className="as-actions"><button type="button" className="as-btn" disabled={m === 'bank_transfer' && ref.trim().length < 4} onClick={() => {setError(''); setConfirm('prepare');}}>ثبت و ارسال برای تأیید نفر دوم</button>
              <button type="button" className="as-btn ghost" onClick={() => setDialog('return')}>برگشت به عملیات</button></div></section>}
          {r.status === 'awaiting_approval' && <section className="as-card" aria-labelledby="fx-appr"><h2 id="fx-appr">تأیید پرداخت (نفر دوم)</h2>
            <dl className="as-dl"><dt>آماده‌کننده</dt><dd>{r.prepared_by} · {jDateTime(r.prepared_at)}</dd><dt>روش</dt><dd>{r.destination_label}</dd>{r.pending_bank_reference && <><dt>کد پیگیری</dt><dd><Ref>{r.pending_bank_reference}</Ref></dd></>}{r.note && <><dt>یادداشت</dt><dd>{r.note}</dd></>}</dl>
            {r.can_approve ? <div className="as-actions"><button type="button" className="as-btn" onClick={() => {setError(''); setConfirm('approve');}}>تأیید و پرداخت</button><button type="button" className="as-btn ghost" onClick={() => setDialog('decline')}>برگشت به نفر اول</button><button type="button" className="as-btn ghost" onClick={() => setDialog('return')}>برگشت به عملیات</button></div>
              : <p className="as-note warn" role="note">شما این پرداخت را آماده کرده‌اید؛ تأیید آن با کاربر دیگری از واحد مالی است.</p>}</section>}
          {r.status === 'succeeded' && <section className="as-card"><h2>پرداخت انجام شد</h2><dl className="as-dl"><dt>روش</dt><dd>{r.destination_label}</dd>{r.bank_reference && <><dt>کد پیگیری</dt><dd><Ref>{r.bank_reference}</Ref></dd></>}<dt>آماده‌کننده</dt><dd>{r.prepared_by}</dd><dt>تأییدکننده</dt><dd>{r.approved_by} · {jDateTime(r.approved_at)}</dd></dl></section>}
          {r.status === 'returned' && <p className="as-note warn">این استرداد به عملیات برگشت داده شده است.</p>}
          <section className="as-card" aria-labelledby="fx-tl"><h2 id="fx-tl">روند درخواست</h2><Timeline steps={r.timeline.steps} next={r.timeline.next}/></section>
        </div>
        <div style={{display: 'grid', gap: 16}}>
          <section className="as-card" aria-labelledby="fx-vat"><h2 id="fx-vat">ارزش افزوده (نمای مالی)</h2>
            {r.breakdown.basis === 'price_breakdown' ? <MoneyRows label="برگشت ارزش افزوده" lines={[{label: 'کمیسیون برگشتی', value: rial(r.breakdown.agency_commission_reversed ?? 0)}, {label: 'markup برگشتی', value: rial(r.breakdown.platform_markup_reversed ?? 0)},
              {label: 'کارمزد خدمات برگشتی', value: rial(r.breakdown.service_fee_reversed ?? 0)}, {label: `ارزش افزودهٔ برگشتی (${faNum(r.breakdown.vat_rate_bps / 100)}٪)`, value: rial(r.breakdown.vat_reversed ?? 0), tone: 'total'}]}/>
              : <Unavail title="مبنای ارزش افزوده ثبت نشده">تفکیک قیمت (کمیسیون، کارمزد) برای این رزرو ثبت نشده است؛ سند برگشت از فروش بدون مبلغ مالیات ساخته می‌شود و حسابدار باید تکمیل کند.</Unavail>}
            <p className="as-muted">نرخ ۱۰٪ پیش‌فرض ۱۴۰۵ است تا جدول نرخ‌های تاریخ‌دار (FIN-11) ساخته شود.</p></section>
          {r.tax_document && <section className="as-card" aria-labelledby="fx-doc"><h2 id="fx-doc">سند برگشت از فروش (مودیان)</h2><p><StatusChip status="pending_review" label="در صف داخلی — ارسال نشده"/> مهلت: {jDateTime(r.tax_document.due_at)}</p>
            {r.tax_document.lines.length > 0 ? <MoneyRows label="ردیف‌های سند" lines={r.tax_document.lines.map(l => ({label: `${CODE_FA[l.code] ?? l.code} (مبنا ${rial(l.base_reversed_irr)})`, value: rial(l.vat_irr)}))}/> : <p className="as-muted">ردیف مالیاتی ندارد.</p>}
            <p className="as-muted">اتصال به سامانهٔ مودیان برقرار نیست؛ این سند فقط ثبت داخلی است.</p></section>}
          {r.journal.length > 0 && <section className="as-card" aria-labelledby="fx-j"><h2 id="fx-j">سند حسابداری استرداد</h2>
            <DataTable caption="سطرهای سند" rows={r.journal} rowKey={j => j.account + j.debit} cols={[{label: 'حساب', cell: j => ACCOUNT_FA[j.account] ?? j.account}, {label: 'بدهکار', cell: j => <span className="as-num">{j.debit ? rial(j.debit) : '—'}</span>}, {label: 'بستانکار', cell: j => <span className="as-num">{j.credit ? rial(j.credit) : '—'}</span>}]}/></section>}
        </div>
      </div>
      <ConfirmMoney open={confirm !== ''} title={confirm === 'approve' ? 'تأیید پرداخت استرداد (نفر دوم)' : 'ثبت پرداخت استرداد (نفر اول)'} amount={r.amount} destination={confirm === 'approve' ? <b>{r.destination_label}{r.pending_bank_reference ? <> · کد پیگیری <Ref>{r.pending_bank_reference}</Ref></> : null}</b> : dest}
        reason={<>استرداد رزرو <Ref>{r.booking_reference ?? ''}</Ref> · جریمه {rial(r.penalty_amount)}</>} busy={busy} error={error} idempotencyKey={confirm === 'approve' ? approveKey.current : prepKey.current}
        twoPerson={confirm === 'approve' ? 'با تأیید شما پول جابه‌جا می‌شود و سند ثبت می‌شود. این اقدام فقط یک بار اجرا می‌شود.' : 'هر پرداخت استرداد دو نفر لازم دارد: پس از ثبت شما، کاربر دیگری از مالی باید تأیید کند؛ سازنده نمی‌تواند تأییدکننده باشد.'}
        confirmLabel={confirm === 'approve' ? 'تأیید و پرداخت' : 'ثبت و ارسال برای تأیید نفر دوم'} onConfirm={() => void (confirm === 'approve' ? approve() : prepare(m))} onClose={() => setConfirm('')}/>
      <DecisionDialog open={dialog !== ''} title={dialog === 'decline' ? 'برگشت به نفر اول' : 'برگشت به عملیات'} confirmLabel="ثبت برگشت" danger busy={busy} error={error} onClose={() => setDialog('')} onSubmit={() => void side(dialog as 'decline' | 'return')}>
        <label className="as-field">دلیل (اجباری)<textarea rows={3} value={reason} onChange={e => setReason(e.target.value)} required minLength={5}/></label></DecisionDialog>
    </>;
  }}</Loaded><p><Link className="as-link" href="/finance/refunds">بازگشت به صف استرداد</Link></p></div>;
}

/* ---------------------------------------------------------------- FIN-04 reconciliation */
type Recon = {id: string; source_type: string; source_id: string; external_reference: string; external_amount: number; currency: string; status: string; discrepancy_reason: string | null; resolution_note: string | null;
  audit_trail: {event: string; at: string; reason?: string; note?: string; resolution_type?: string}[]; link: {target_type: string; target_id: string; reason: string} | null};
const RES_TYPES: [string, string][] = [['refund_customer', 'برگشت به مشتری'], ['book_reservation', 'ثبت رزرو'], ['gateway_fee', 'کارمزد درگاه'], ['bank_error', 'اشتباه بانک'], ['duplicate', 'تراکنش تکراری'], ['other', 'سایر']];
const EVENT_FA: Record<string, string> = {matched: 'تطبیق', disputed: 'ثبت مغایرت', linked: 'تطبیق دستی', unlinked: 'برداشتن تطبیق', resolved: 'حل'};
export function FinanceReconciliation() {
  const [status, setStatus] = useState(''); const q = useLoad<{items: Recon[]; counts: Record<string, number>}>(`/finance/reconciliation/records${status ? `?status=${status}` : ''}`);
  const [open, setOpen] = useState<{kind: 'link' | 'unlink' | 'resolve'; row: Recon} | null>(null);
  const [targetType, setTargetType] = useState('payment'); const [targetId, setTargetId] = useState(''); const [resType, setResType] = useState('gateway_fee'); const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [ok, setOk] = useState('');
  async function submit() {
    if (!open) return; setBusy(true); setError('');
    const path = `/finance/reconciliation/${open.row.id}/${open.kind === 'resolve' ? 'resolution' : open.kind}`;
    const body = open.kind === 'link' ? {target_type: targetType, target_id: targetId.trim(), reason: reason.trim()} : open.kind === 'resolve' ? {resolution_type: resType, reason: reason.trim()} : {reason: reason.trim()};
    try {await q.api.post(path, body); setOpen(null); setReason(''); setTargetId(''); setOk('ثبت شد و در سوابق آمد.'); q.reload();} catch (e) {setError(messageOf(e));} finally {setBusy(false);}
  }
  return <div className="as"><Loaded state={q.state} reload={q.reload} skeleton={<Skeleton kind="table" rows={6}/>}>{d => <>
    <section className="as-card"><div className="as-tabs" role="tablist" aria-label="وضعیت تطبیق">{([['', 'همه'], ['DISPUTED', 'مغایرت'], ['UNMATCHED', 'تطبیق‌نشده'], ['MATCHED', 'تطبیق‌شده'], ['RESOLVED', 'حل‌شده']] as const).map(([k, l]) =>
      <button key={k || 'all'} type="button" role="tab" aria-selected={status === k} onClick={() => setStatus(k)}>{l}{k ? ` (${faNum(d.counts[k] ?? 0)})` : ''}</button>)}</div>
      {ok && <p className="as-note ok" role="status">{ok}</p>}
      {d.items.length === 0 ? <EmptyState title="رکورد تطبیقی در این وضعیت نیست">رکوردها از «تطبیق» پرداخت با گزارش درگاه ساخته می‌شوند؛ ورود فایل تسویهٔ روزانهٔ درگاه هنوز ساخته نشده است.</EmptyState> :
        <DataTable caption="رکوردهای تطبیق درگاه" rows={d.items} rowKey={r => r.id} cols={[
          {label: 'مرجع درگاه', cell: r => <Ref>{r.external_reference}</Ref>}, {label: 'مبلغ درگاه', cell: r => <span className="as-num">{rial(r.external_amount)}</span>}, {label: 'منبع', cell: r => <span>{r.source_type === 'payment' ? 'پرداخت' : r.source_type === 'refund' ? 'استرداد' : 'تسویه'} <Ref>{r.source_id.slice(0, 8)}</Ref></span>},
          {label: 'وضعیت', cell: r => <StatusChip status={r.status}/>}, {label: 'شرح', cell: r => r.resolution_note ?? r.discrepancy_reason ?? (r.link ? `وصل به ${r.link.target_type === 'payment' ? 'پرداخت' : 'رزرو'} ${r.link.target_id.slice(0, 8)}` : '—')},
          {label: 'سوابق', cell: r => <small className="as-muted">{r.audit_trail.map(e => `${EVENT_FA[e.event] ?? e.event} ${jDateTime(e.at)}`).join(' ← ')}</small>},
          {label: '', cell: r => <div className="as-actions">{(r.status === 'DISPUTED' || r.status === 'UNMATCHED') && !r.link && <button type="button" className="as-btn ghost" onClick={() => {setError(''); setOpen({kind: 'link', row: r});}}>تطبیق دستی</button>}
            {r.link && r.status !== 'RESOLVED' && <button type="button" className="as-btn ghost" onClick={() => {setError(''); setOpen({kind: 'unlink', row: r});}}>برداشتن تطبیق</button>}
            {r.status === 'DISPUTED' && <button type="button" className="as-btn" onClick={() => {setError(''); setOpen({kind: 'resolve', row: r});}}>حل</button>}</div>}]}/>}
    </section></>}</Loaded>
    <DecisionDialog open={open !== null} title={open?.kind === 'link' ? 'تطبیق دستی با پرداخت یا رزرو' : open?.kind === 'unlink' ? 'برداشتن تطبیق' : 'حل مغایرت'} confirmLabel="ثبت" busy={busy} error={error} onClose={() => setOpen(null)} onSubmit={() => void submit()}>
      {open && <p>مرجع درگاه <Ref>{open.row.external_reference}</Ref> · {rial(open.row.external_amount)}</p>}
      {open?.kind === 'link' && <><label className="as-field">نوع<select value={targetType} onChange={e => setTargetType(e.target.value)}><option value="payment">پرداخت</option><option value="reservation">رزرو</option></select></label>
        <label className="as-field">شناسهٔ پرداخت یا رزرو<input dir="ltr" value={targetId} onChange={e => setTargetId(e.target.value)} required minLength={36} maxLength={36}/><small>اگر مبلغ برابر باشد وضعیت «تطبیق‌شده» می‌شود، وگرنه مغایرت می‌ماند.</small></label></>}
      {open?.kind === 'resolve' && <label className="as-field">نوع حل<select value={resType} onChange={e => setResType(e.target.value)}>{RES_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>}
      <label className="as-field">دلیل (اجباری)<textarea rows={3} value={reason} onChange={e => setReason(e.target.value)} required minLength={5}/></label>
    </DecisionDialog></div>;
}
