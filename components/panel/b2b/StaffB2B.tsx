'use client';
import Link from 'next/link';
/* Staff screens for Phase 2 (Figma P2: OPS-09 agency onboarding & licence verification, charter block review, FIN credit operations).
   Registry checks are manual (no registry API is connected): staff record result, method and inquiry reference. Money movements
   are always two-person: a request here, approval by a different finance user. */
import {useState} from 'react';
import {Card, Stats, Table, useLoad} from '../PanelKit';
import {EmptyState, Loaded, Ref, Skeleton, Unavail, newKey, rial} from '../aftersales/kit';
import {BlockChip, CheckChip, DateField, Feedback, Field, KycChip, LicenceChip, StatusChip, jalali, parseRial, pct, useAction} from './B2BKit';
import {route, type Block} from './Charter';
import type {Licence} from './AgencyB2B';

type Account = {exists: boolean; balance_irr: number; credit_limit_irr: number; held_irr: number; available_irr: number; usage_bps: number};
type StaffAgency = {id: string; name: string; profile: {kyc_status: string; legal_name?: string | null; national_id?: string | null; economic_code?: string | null; postal_code?: string | null; ceo_name?: string | null; iban?: string | null; complete: boolean; kyc_note?: string | null};
  licences: Licence[]; pending_checks: number; account: Account};

/* ---------------------------------------------------------------- OPS-09 */
export function StaffAgencies() {
  const r = useLoad<{items: StaffAgency[]; summary: {in_queue: number; expiring_30d: number; suspended: number}; can_verify: boolean}>('/staff/agencies');
  const [tab, setTab] = useState('queue'); const [pick, setPick] = useState('');
  return <Loaded state={r.state} reload={r.reload} skeleton={<Skeleton kind="table" rows={4}/>}>{d => {
    const rows = d.items.filter(x => tab === 'all' || (tab === 'queue' ? x.profile.kyc_status === 'submitted' || x.pending_checks > 0 : tab === 'expiring' ? x.licences.some(l => l.expiring_soon) : x.profile.kyc_status === tab));
    const sel = d.items.find(x => x.id === pick);
    return <>
      <Stats items={[{label: 'در صف احراز', value: d.summary.in_queue.toLocaleString('fa-IR')}, {label: 'نزدیک انقضا (۳۰ روز)', value: d.summary.expiring_30d.toLocaleString('fa-IR')}, {label: 'آژانس معلق', value: d.summary.suspended.toLocaleString('fa-IR')}]}/>
      <Card><div className="pn-chips" role="group" aria-label="فیلتر">{[['queue', 'در صف'], ['expiring', 'نزدیک انقضا'], ['active', 'فعال'], ['suspended', 'معلق'], ['all', 'همه']].map(([k, l]) => <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
        <Table rows={rows} rowKey={x => x.id} empty="موردی در این فهرست نیست." cols={[{label: 'آژانس', cell: x => x.name}, {label: 'وضعیت حساب', cell: x => <KycChip status={x.profile.kyc_status}/>},
          {label: 'مجوزها', cell: x => x.licences.length ? x.licences.map(l => <span key={l.id} style={{display: 'block'}}>{l.type_label} <Ref>{l.number}</Ref> <LicenceChip status={l.status}/></span>) : '—'},
          {label: 'بررسی منتظر', cell: x => x.pending_checks.toLocaleString('fa-IR')}, {label: 'اقدام', cell: x => <button className="as-btn ghost" type="button" onClick={() => setPick(x.id)}>باز کردن</button>}]}/></Card>
      {sel && <AgencyReview key={sel.id} a={sel} canVerify={d.can_verify} onChange={r.reload}/>}
    </>;}}</Loaded>;
}
function AgencyReview({a, canVerify, onChange}: {a: StaffAgency; canVerify: boolean; onChange: () => void}) {
  const audit = useLoad<{audit: {action: string; at: string}[]}>(`/staff/agencies/${a.id}`); const act = useAction(); const [reason, setReason] = useState('');
  const decide = (decision: string) => act.run(api => api.post(`/staff/agencies/${a.id}/kyc`, {decision, reason: reason || null}), 'تصمیم ثبت شد.').then(x => {if (x) {onChange(); audit.reload();}});
  const st = a.profile.kyc_status;
  return <div className="b2b-split">
    <Card title={`${a.name}`} action={<KycChip status={st}/>}>
      <dl className="b2b-kv"><dt>نام حقوقی</dt><dd>{a.profile.legal_name ?? '—'}</dd><dt>شناسهٔ ملی</dt><dd>{a.profile.national_id ? <Ref>{a.profile.national_id}</Ref> : '—'}</dd><dt>شمارهٔ اقتصادی</dt><dd>{a.profile.economic_code ? <Ref>{a.profile.economic_code}</Ref> : '—'}</dd>
        <dt>کد پستی</dt><dd>{a.profile.postal_code ? <Ref>{a.profile.postal_code}</Ref> : '—'}</dd><dt>مدیرعامل</dt><dd>{a.profile.ceo_name ?? '—'}</dd><dt>شبا</dt><dd>{a.profile.iban ? <Ref>{a.profile.iban}</Ref> : '—'}</dd></dl>
      {a.licences.map(l => <section key={l.id} className="b2b-section" style={{borderTop: '1px solid var(--pn-line,#eadfd2)', paddingTop: 12}}>
        <b>{l.type_label} · <Ref>{l.number}</Ref> <LicenceChip status={l.status}/></b><small className="as-muted">صدور {jalali(l.issued_on)} · انقضا {jalali(l.expires_on)}</small>
        <Table rows={l.registries} rowKey={x => x.registry} empty="—" cols={[{label: 'مرجع', cell: x => x.label}, {label: 'نتیجه', cell: x => <CheckChip result={x.result}/>}, {label: 'مرجع استعلام', cell: x => x.reference ? <Ref>{x.reference}</Ref> : '—'}, {label: 'زمان', cell: x => jalali(x.checked_at, true)}]}/>
        {canVerify && <CheckForm agencyId={a.id} licence={l} onDone={() => {onChange(); audit.reload();}}/>}</section>)}
      {a.licences.length === 0 && <EmptyState title="مجوزی ثبت نشده است"/>}</Card>
    <Card title="تصمیم">
      <Unavail title="استعلام خودکار در دسترس نیست">API رسمی مراجع وصل نیست؛ نتیجه فقط با بررسی انسانی و ثبت تأییدکننده ذخیره می‌شود.</Unavail>
      {canVerify ? <>
        <Field label="دلیل یا یادداشت (برای رد و تعلیق اجباری)"><textarea rows={3} value={reason} onChange={e => setReason(e.target.value)}/></Field>
        <div className="as-actions">{st === 'submitted' && <><button className="as-btn" type="button" disabled={act.busy} onClick={() => void decide('approve')}>تأیید و فعال‌سازی آژانس</button><button className="as-btn danger" type="button" disabled={act.busy} onClick={() => void decide('reject')}>رد با دلیل</button></>}
          {st === 'active' && <button className="as-btn danger" type="button" disabled={act.busy} onClick={() => void decide('suspend')}>تعلیق آژانس</button>}
          {st === 'suspended' && <button className="as-btn" type="button" disabled={act.busy} onClick={() => void decide('reinstate')}>رفع تعلیق</button>}</div>
        <Feedback error={act.error} done={act.done}/>
        <div className="as-note info"><b>ثبت در سوابق</b><br/>هر بررسی و تصمیم با نام تأییدکننده و زمان در ممیزی ثبت می‌شود. تأیید آژانس فقط با پروفایل کامل و دست‌کم یک مجوز احرازشده در همهٔ مراجع ممکن است.</div></>
        : <p className="as-muted">این حساب مجوز احراز (license:verify) ندارد؛ فقط مشاهده.</p>}
      <b>سوابق</b><Loaded state={audit.state}>{x => x.audit.length ? <ul className="pn-list">{x.audit.map((e, i) => <li key={i}><Ref>{e.action}</Ref> · {jalali(e.at, true)}</li>)}</ul> : <p className="as-muted">سابقه‌ای نیست.</p>}</Loaded>
    </Card></div>;
}
function CheckForm({agencyId, licence, onDone}: {agencyId: string; licence: Licence; onDone: () => void}) {
  const [f, setF] = useState({registry: licence.registries.find(r => !r.result)?.registry ?? licence.registries[0]?.registry ?? 'national_portal', result: 'confirmed', method: 'registry_lookup', reference: '', note: ''}); const act = useAction();
  const send = () => act.run(api => api.post(`/staff/agencies/${agencyId}/licences/${licence.id}/checks`, {...f, reference: f.reference || null, note: f.note || null}), 'نتیجه ثبت شد.').then(x => {if (x) {setF({...f, reference: '', note: ''}); onDone();}});
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void send();}}><div className="b2b-grid">
    <Field label="مرجع"><select value={f.registry} onChange={e => setF({...f, registry: e.target.value})}>{licence.registries.map(r => <option key={r.registry} value={r.registry}>{r.label}</option>)}</select></Field>
    <Field label="نتیجه"><select value={f.result} onChange={e => setF({...f, result: e.target.value})}><option value="confirmed">منطبق</option><option value="mismatch">نامنطبق</option><option value="not_found">یافت نشد</option></select></Field>
    <Field label="روش"><select value={f.method} onChange={e => setF({...f, method: e.target.value})}><option value="registry_lookup">استعلام از مرجع</option><option value="document_review">بررسی مدرک</option></select></Field>
    <Field label="شمارهٔ پیگیری استعلام"><input value={f.reference} required={f.method === 'registry_lookup'} onChange={e => setF({...f, reference: e.target.value})} dir="ltr"/></Field>
    <Field label="یادداشت داخلی"><input value={f.note} onChange={e => setF({...f, note: e.target.value})}/></Field></div>
    <Feedback error={act.error} done={act.done}/><div className="as-actions"><button className="as-btn ghost" type="submit" disabled={act.busy}>ثبت نتیجهٔ احراز</button></div></form>;
}

/* ---------------------------------------------------------------- charter review (OPS-08 for charter) */
export function StaffCharterBlocks() {
  const [status, setStatus] = useState('submitted');
  const r = useLoad<{items: Block[]; domestic_charter_sale: boolean; can_publish: boolean}>(`/staff/charter/blocks${status ? `?status=${status}` : ''}`);
  const caps = useLoad<{items: {id: string; origin: string; destination: string; valid_from: string; valid_to: string; cap_unit_irr: number; legal_reference: string}[]; can_edit: boolean}>('/staff/charter/price-caps');
  const [open, setOpen] = useState(''); const [notice, setNotice] = useState('');
  return <>
    {notice && <p className="as-note ok" role="status">{notice}</p>}
    <Loaded state={r.state} reload={r.reload} skeleton={<Skeleton kind="table" rows={4}/>}>{d => <Card title="بلوک‌های صندلی چارتر" action={<span className={`as-chip ${d.domestic_charter_sale ? 'ok' : ''}`}>چارتر داخلی: {d.domestic_charter_sale ? 'فعال' : 'خاموش'}</span>}>
      <div className="pn-chips" role="group" aria-label="وضعیت">{[['submitted', 'در انتظار بازبینی'], ['published', 'منتشرشده'], ['cancelled', 'لغوشده'], ['rejected', 'ردشده'], ['draft', 'پیش‌نویس'], ['', 'همه']].map(([k, l]) => <button key={k || 'all'} type="button" aria-pressed={status === k} onClick={() => setStatus(k)}>{l}</button>)}</div>
      <Table rows={d.items} rowKey={b => b.id} empty="بلوکی در این وضعیت نیست." cols={[{label: 'آژانس', cell: b => b.owner_agency_name ?? '—'}, {label: 'مسیر', cell: b => route(b)}, {label: 'پرواز', cell: b => <Ref>{b.airline_code}{b.flight_number}</Ref>},
        {label: 'حرکت', cell: b => jalali(b.departure_at, true)}, {label: 'صندلی', cell: b => `${b.seats.sold.toLocaleString('fa-IR')} / ${b.seats_total.toLocaleString('fa-IR')}`}, {label: 'نرخ ADT', cell: b => rial(b.net_adult_irr)},
        {label: 'سقف', cell: b => b.price_cap_unit_irr !== null ? rial(b.price_cap_unit_irr) : 'ثبت نشده'}, {label: 'وضعیت', cell: b => <>{b.domestic_sale_disabled && <span className="as-chip">داخلی: خاموش</span>} <BlockChip status={b.status}/></>},
        {label: 'اقدام', cell: b => b.status === 'published' || b.status === 'cancelled' ? <Link className="as-btn ghost" href={`/backoffice/charter-blocks/${b.id}`}>{b.status === 'cancelled' ? 'سوابق' : 'تغییر یا لغو'}</Link>
          : <button className="as-btn ghost" type="button" onClick={() => setOpen(open === b.id ? '' : b.id)}>{open === b.id ? 'بستن' : 'بررسی'}</button>}]}/>
      {d.items.filter(b => b.id === open).map(b => <BlockReview key={b.id} b={b} canPublish={d.can_publish} onDone={msg => {setNotice(`${b.airline_code}${b.flight_number}: ${msg}`); setOpen(''); r.reload();}}/>)}</Card>}</Loaded>
    <Card title="سقف قیمت سازمان هواپیمایی (price_cap)"><Loaded state={caps.state} reload={caps.reload}>{c => <>
      <Table rows={c.items} rowKey={x => x.id} empty="سقفی ثبت نشده است؛ تا ثبت سقف، کنترل سقف برای آن مسیر انجام نمی‌شود." cols={[{label: 'مسیر', cell: x => <Ref>{x.origin}-{x.destination}</Ref>}, {label: 'از', cell: x => jalali(x.valid_from)}, {label: 'تا', cell: x => jalali(x.valid_to)},
        {label: 'سقف بزرگسال', cell: x => rial(x.cap_unit_irr)}, {label: 'مرجع قانونی', cell: x => x.legal_reference}]}/>
      {c.can_edit ? <CapForm onDone={caps.reload}/> : <p className="as-muted">ثبت سقف با مدیر مجموعه است.</p>}</>}</Loaded></Card>
  </>;
}
function BlockReview({b, canPublish, onDone}: {b: Block; canPublish: boolean; onDone: (message: string) => void}) {
  const audit = useLoad<{items: {action: string; actor: string | null; at: string}[]}>(`/staff/charter/blocks/${b.id}/audit`); const act = useAction(); const [fee, setFee] = useState(''); const [reason, setReason] = useState('');
  const decide = (decision: string) => act.run(api => api.post(`/staff/charter/blocks/${b.id}/decision`, {decision, reason: reason || null, platform_fee_bps: fee ? parseRial(fee) : null})).then(x => {if (x) onDone(decision === 'approve' ? 'منتشر شد.' : 'رد شد.');});
  return <div className="b2b-split" style={{marginTop: 12}}>
    <div className="b2b-section"><dl className="b2b-kv"><dt>منبع</dt><dd>{b.source}{b.external_ref && <> · <Ref>{b.external_ref}</Ref></>}</dd><dt>release</dt><dd>{jalali(b.release_at, true)}</dd>
      <dt>نرخ ADT/CHD/INF</dt><dd>{rial(b.net_adult_irr)} / {rial(b.net_child_irr)} / {rial(b.net_infant_irr)}</dd><dt>نقش مالیاتی</dt><dd>{b.tax_role} (نیازمند تأیید حسابدار)</dd>
      <dt>کارمزد پلتفرم</dt><dd>{pct(b.platform_fee_bps)}</dd></dl>
      <b>سوابق</b><Loaded state={audit.state}>{x => <ul className="pn-list">{x.items.map((e, i) => <li key={i}><Ref>{e.action}</Ref> · {e.actor ?? '—'} · {jalali(e.at, true)}</li>)}</ul>}</Loaded></div>
    <div className="b2b-section">{canPublish && b.status === 'submitted' ? <>
      <Field label="کارمزد پلتفرم طبق قرارداد (bps، اختیاری)" hint="۱۰۰ bps = ۱٪"><input inputMode="numeric" value={fee} onChange={e => setFee(e.target.value)} dir="ltr"/></Field>
      <Field label="یادداشت / دلیل رد"><textarea rows={2} value={reason} onChange={e => setReason(e.target.value)}/></Field>
      {b.domestic_sale_disabled && <p className="as-note warn">چارتر داخلی است و فروش آن خاموش است؛ انتشار رد می‌شود (CHARTER_DOMESTIC_DISABLED).</p>}
      <div className="as-actions"><button className="as-btn" type="button" disabled={act.busy} onClick={() => void decide('approve')}>تأیید و انتشار</button><button className="as-btn danger" type="button" disabled={act.busy} onClick={() => void decide('reject')}>رد با دلیل</button></div></>
      : <p className="as-muted">{b.status === 'submitted' ? 'این حساب مجوز انتشار موجودی ندارد.' : 'تصمیمی لازم نیست.'}</p>}
      <Feedback error={act.error} done={act.done}/></div></div>;
}
function CapForm({onDone}: {onDone: () => void}) {
  const [f, setF] = useState({origin: '', destination: '', valid_from: '', valid_to: '', cap: '', ref: ''}); const act = useAction();
  const send = () => act.run(api => api.post('/staff/charter/price-caps', {origin: f.origin, destination: f.destination, valid_from: f.valid_from, valid_to: f.valid_to, cap_unit_irr: parseRial(f.cap), legal_reference: f.ref}), 'سقف ثبت شد.').then(x => {if (x) onDone();});
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void send();}}><b>ثبت سقف از اطلاعیهٔ سازمان هواپیمایی</b><div className="b2b-grid3">
    <Field label="مبدأ"><input required maxLength={3} value={f.origin} onChange={e => setF({...f, origin: e.target.value})} dir="ltr"/></Field><Field label="مقصد"><input required maxLength={3} value={f.destination} onChange={e => setF({...f, destination: e.target.value})} dir="ltr"/></Field>
    <Field label="سقف بزرگسال (ریال)"><input required inputMode="numeric" value={f.cap} onChange={e => setF({...f, cap: e.target.value})} dir="ltr"/></Field>
    <DateField label="از تاریخ" required value={f.valid_from} onChange={v => setF({...f, valid_from: v})}/><DateField label="تا تاریخ" required value={f.valid_to} onChange={v => setF({...f, valid_to: v})}/>
    <Field label="مرجع قانونی (شماره و تاریخ اطلاعیه)"><input required minLength={4} value={f.ref} onChange={e => setF({...f, ref: e.target.value})}/></Field></div>
    <Feedback error={act.error} done={act.done}/><div className="as-actions"><button className="as-btn ghost" type="submit" disabled={act.busy}>ثبت سقف</button></div></form>;
}

/* ---------------------------------------------------------------- finance: agency accounts (maker-checker) */
type FinRow = {agency_id: string; name: string; kyc_status: string} & Account;
type McReq = {id: string; kind: string; kind_label: string; status: string; summary: string; amount: number | null; payload: Record<string, unknown>; mine: boolean; can_decide: boolean; created_at: string};
export function FinanceAgencyAccounts() {
  const r = useLoad<{items: FinRow[]; requests: McReq[]; can_request: boolean}>('/finance/agency-accounts'); const [pick, setPick] = useState(''); const act = useAction();
  const decide = (id: string, ok: boolean) => act.run(api => api.post(`/maker-checker/requests/${id}/${ok ? 'approve' : 'reject'}`, {}), ok ? 'تأیید و اعمال شد.' : 'رد شد.').then(x => {if (x) r.reload();});
  return <Loaded state={r.state} reload={r.reload} skeleton={<Skeleton kind="table" rows={4}/>}>{d => <>
    <Card title="درخواست‌های اعتبار آژانس (دو نفره)"><Feedback error={act.error} done={act.done}/>
      <Table rows={d.requests} rowKey={x => x.id} empty="درخواستی نیست." cols={[{label: 'نوع', cell: x => x.kind_label}, {label: 'شرح', cell: x => x.summary}, {label: 'مبلغ', cell: x => rial(x.amount)},
        {label: 'منبع', cell: x => x.payload.source === 'agency_request' ? 'درخواست آژانس' : 'مالی'}, {label: 'مرجع بانکی', cell: x => x.payload.bank_reference ? <Ref>{String(x.payload.bank_reference)}</Ref> : '—'},
        {label: 'وضعیت', cell: x => <StatusChip status={x.status === 'pending' ? 'submitted' : x.status === 'executed' ? 'approved' : 'rejected'} label={x.status === 'pending' ? 'منتظر تأیید نفر دوم' : x.status === 'executed' ? 'اعمال‌شده' : x.status === 'rejected' ? 'ردشده' : 'منقضی'}/>},
        {label: 'اقدام', cell: x => x.can_decide ? <span className="as-actions"><button className="as-btn" type="button" disabled={act.busy} onClick={() => void decide(x.id, true)}>تأیید</button><button className="as-btn ghost" type="button" disabled={act.busy} onClick={() => void decide(x.id, false)}>رد</button></span> : x.mine && x.status === 'pending' ? 'ثبت شما؛ نفر دوم تأیید می‌کند' : '—'}]}/></Card>
    <Card title="حساب آژانس‌ها"><Table rows={d.items} rowKey={x => x.agency_id} empty="آژانسی نیست." cols={[{label: 'آژانس', cell: x => x.name}, {label: 'احراز', cell: x => <KycChip status={x.kyc_status}/>},
      {label: 'سقف', cell: x => x.exists ? rial(x.credit_limit_irr) : '—'}, {label: 'مانده', cell: x => x.exists ? rial(x.balance_irr) : '—'}, {label: 'hold', cell: x => x.exists ? rial(x.held_irr) : '—'}, {label: 'قابل استفاده', cell: x => x.exists ? rial(x.available_irr) : '—'},
      {label: 'اقدام', cell: x => d.can_request && x.kyc_status === 'active' ? <button className="as-btn ghost" type="button" onClick={() => setPick(x.agency_id)}>شارژ / سقف</button> : '—'}]}/></Card>
    {pick && <Card title={`عملیات حساب: ${d.items.find(x => x.agency_id === pick)?.name ?? ''}`}><FinanceForms agencyId={pick} onDone={() => {setPick(''); r.reload();}}/></Card>}
  </>}</Loaded>;
}
function FinanceForms({agencyId, onDone}: {agencyId: string; onDone: () => void}) {
  const [f, setF] = useState({direction: 'topup', amount: '', reason: '', ref: '', limit: '', limit_reason: ''}); const act = useAction(); const [k1] = useState(() => newKey('fin-adj')); const [k2] = useState(() => newKey('fin-lim'));
  const adjust = () => act.run(api => api.post(`/finance/agency-accounts/${agencyId}/adjustments`, {direction: f.direction, amount_irr: parseRial(f.amount), reason: f.reason, bank_reference: f.ref || null}, k1), 'درخواست ثبت شد؛ نفر دوم مالی باید تأیید کند.').then(x => {if (x) onDone();});
  const limit = () => act.run(api => api.post(`/finance/agency-accounts/${agencyId}/credit-limit`, {new_limit_irr: parseRial(f.limit), reason: f.limit_reason}, k2), 'درخواست تغییر سقف ثبت شد؛ نفر دوم مالی باید تأیید کند.').then(x => {if (x) onDone();});
  return <div className="b2b-split"><form className="b2b-section" onSubmit={e => {e.preventDefault(); void adjust();}}><b>شارژ یا کاهش دستی</b>
    <Field label="نوع"><select value={f.direction} onChange={e => setF({...f, direction: e.target.value})}><option value="topup">شارژ</option><option value="decrease">کاهش</option></select></Field>
    <Field label="مبلغ (ریال)" hint={parseRial(f.amount) > 0 ? rial(parseRial(f.amount)) : undefined}><input required inputMode="numeric" value={f.amount} onChange={e => setF({...f, amount: e.target.value})} dir="ltr"/></Field>
    <Field label="دلیل"><input required minLength={3} value={f.reason} onChange={e => setF({...f, reason: e.target.value})}/></Field><Field label="مرجع بانکی"><input value={f.ref} onChange={e => setF({...f, ref: e.target.value})} dir="ltr"/></Field>
    <div className="as-actions"><button className="as-btn" type="submit" disabled={act.busy}>ثبت درخواست (maker)</button></div></form>
    <form className="b2b-section" onSubmit={e => {e.preventDefault(); void limit();}}><b>تغییر سقف اعتبار</b>
      <Field label="سقف تازه (ریال)" hint={parseRial(f.limit) >= 0 ? rial(parseRial(f.limit)) : undefined}><input required inputMode="numeric" value={f.limit} onChange={e => setF({...f, limit: e.target.value})} dir="ltr"/></Field>
      <Field label="دلیل"><input required minLength={3} value={f.limit_reason} onChange={e => setF({...f, limit_reason: e.target.value})}/></Field>
      <div className="as-actions"><button className="as-btn ghost" type="submit" disabled={act.busy}>ثبت درخواست سقف (maker)</button></div></form>
    <Feedback error={act.error} done={act.done}/></div>;
}
