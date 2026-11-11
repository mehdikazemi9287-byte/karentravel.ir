'use client';
/* Agency panel, Phase 2 (Figma P2: AG-01 today card, AG-02 profile & licences, AG-07 markup & commission, AG-15 account & credit,
   AG-05 bookings paid from the agency account, AG-20 users, invoices). The agency comes from the user's own memberships; every
   figure is returned by the API for that agency. Money movements are requests: finance approves them with a second person. */
import Link from 'next/link';
import {useState} from 'react';
import {AgencyScope} from '../AgencyPanel';
import {Card, Stats, Table, useLoad} from '../PanelKit';
import {ConfirmMoney, EmptyState, Loaded, Ref, Skeleton, Unavail, newKey, rial} from '../aftersales/kit';
import {BarMeter, CheckChip, DateField, Feedback, Field, KycChip, LicenceChip, MoneyBreakdown, StatusChip, jalali, parseRial, pct, useAction, type BuyerBreakdown} from './B2BKit';

type Agency = {id: string; name: string};
type Account = {exists: boolean; balance_irr: number; credit_limit_irr: number; held_irr: number; available_irr: number; used_irr: number; usage_bps: number};
type Ctx = {agency: {id: string; name: string; commission_bps: number}; member_role: string; member_role_label: string; kyc_status: string; valid_licence_types: string[]; can_book: boolean; can_charter: boolean; account: Account; vat: {rate_bps: number; legal_reference: string}};
type Registry = {registry: string; label: string; result: string | null; result_label: string; reference: string | null; checked_at: string | null};
export type Licence = {id: string; licence_type: string; type_label: string; authority: string | null; number: string; issued_on: string | null; expires_on: string; days_left: number; status: string; expiring_soon: boolean; registries: Registry[]};
type Profile = {legal_name?: string | null; brand_name?: string | null; national_id?: string | null; economic_code?: string | null; postal_code?: string | null; ceo_name?: string | null; technical_manager?: string | null; iban?: string | null; kyc_status: string; kyc_note?: string | null; complete: boolean};

const ROLE_FA: Record<string, string> = {owner: 'مدیر آژانس', agent: 'کارشناس فروش آژانس', staff: 'کارکنان مجموعه'};

/* ---------------------------------------------------------------- AG-01: status card on the agency home */
export function AgencyTodayB2B() {return <AgencyScope>{a => <TodayBody a={a}/>}</AgencyScope>;}
function TodayBody({a}: {a: Agency}) {
  const ctx = useLoad<Ctx>(`/agency/${a.id}/b2b`); const prof = useLoad<{licences: Licence[]}>(`/agency/${a.id}/profile`);
  return <Loaded state={ctx.state} reload={ctx.reload} skeleton={<Skeleton rows={3}/>}>{c => {
    const lic = prof.state.kind === 'ready' ? prof.state.data.licences : [];
    const todo: {level: string; text: string; href: string}[] = [];
    if (c.kyc_status !== 'active') todo.push({level: c.kyc_status === 'rejected' || c.kyc_status === 'suspended' ? 'bad' : 'warn', text: c.kyc_status === 'submitted' ? 'پروفایل و مجوزها در انتظار احراز عملیات است' : 'برای فروش، پروفایل حقوقی و مجوزها را تکمیل و برای احراز ارسال کنید', href: '/agency/profile'});
    for (const l of lic) if (l.expiring_soon) todo.push({level: l.days_left <= 15 ? 'bad' : 'warn', text: `${l.type_label} تا ${l.days_left.toLocaleString('fa-IR')} روز دیگر منقضی می‌شود`, href: '/agency/profile'});
    if (c.account.exists && c.account.usage_bps >= 8000) todo.push({level: 'warn', text: `${pct(c.account.usage_bps)} از سقف اعتبار استفاده شده است`, href: '/agency/credit'});
    return <Card title="وضعیت B2B آژانس" action={<KycChip status={c.kyc_status}/>}>
      <p className="as-muted">نقش شما: {c.member_role_label} · مجوزهای معتبر: {c.valid_licence_types.length ? c.valid_licence_types.join('، ') : 'ندارد'}</p>
      {c.account.exists ? <Stats items={[{label: 'مانده قابل استفاده', value: rial(c.account.available_irr)}, {label: 'بلوکه (hold)', value: rial(c.account.held_irr)}, {label: 'سقف اعتبار', value: rial(c.account.credit_limit_irr)}]}/>
        : <Unavail title="حساب اعتبار">حساب آژانس پس از احراز و فعال شدن ساخته می‌شود.</Unavail>}
      {todo.length ? <ul className="pn-list">{todo.map(t => <li key={t.text}><StatusChip status={t.level === 'bad' ? 'rejected' : 'submitted'} label={t.level === 'bad' ? 'فوری' : 'منتظر'}/> {t.text} — <Link className="pn-link" href={t.href}>رفتن</Link></li>)}</ul>
        : <p className="as-muted">کار منتظری ندارید.</p>}
      <div className="b2b-flags">{c.can_book && <Link className="as-btn" href="/agency/sell">فروش با اعتبار آژانس</Link>}{c.can_charter && <Link className="as-btn ghost" href="/agency/inventory/flights">پرواز و بلوک صندلی</Link>}</div>
    </Card>;}}</Loaded>;
}

/* ---------------------------------------------------------------- AG-02 profile & licences */
export function AgencyProfilePage() {return <AgencyScope>{a => <ProfileBody a={a}/>}</AgencyScope>;}
const PROFILE_FIELDS: [keyof Profile, string, string?][] = [['legal_name', 'نام حقوقی'], ['brand_name', 'نام تجاری (فقط داخلی)'], ['national_id', 'شناسهٔ ملی', '۱۱ رقم'], ['economic_code', 'شمارهٔ اقتصادی'],
  ['postal_code', 'کد پستی', '۱۰ رقم'], ['ceo_name', 'مدیرعامل'], ['technical_manager', 'مدیر فنی'], ['iban', 'شبا', 'IR و ۲۴ رقم']];
function ProfileBody({a}: {a: Agency}) {
  const p = useLoad<{member_role: string; profile: Profile; licences: Licence[]; licence_types: Record<string, string>}>(`/agency/${a.id}/profile`);
  return <Loaded state={p.state} reload={p.reload} skeleton={<Skeleton rows={6}/>}>{d => <>
    <div className="b2b-split">
      <Card title="پروفایل حقوقی" action={<KycChip status={d.profile.kyc_status}/>}><ProfileForm agencyId={a.id} profile={d.profile} owner={d.member_role === 'owner'} onSaved={p.reload}/></Card>
      <Card title="قواعد انتشار موجودی">
        <PublishRule what="پرواز و چارتر" needs="BAND_ALEF" licences={d.licences}/><PublishRule what="تور" needs="BAND_BE" licences={d.licences}/>
        <div className="as-note info"><b>فروشندهٔ رسمی در سایت کارن تراول: تاژبان</b><br/>نام، نشانی و شمارهٔ مجوز آژانس شما روی صفحهٔ عمومی تور و پرواز نمایش داده نمی‌شود (R-PUB-1). با انقضای مجوز، موجودی وابسته معلق می‌شود.</div>
      </Card>
    </div>
    <Card title="مجوزها"><p className="as-muted">احراز در هر مرجع لازم برای نوع مجوز: درگاه ملی مجوزها، سامانهٔ وزارت میراث، سامانهٔ سازمان هواپیمایی.</p>
      <Table rows={d.licences} rowKey={l => l.id} empty="هنوز مجوزی ثبت نشده است." cols={[
        {label: 'نوع مجوز', cell: l => l.type_label}, {label: 'شماره', cell: l => <Ref>{l.number}</Ref>}, {label: 'انقضا', cell: l => jalali(l.expires_on)},
        {label: 'احراز در مرجع', cell: l => <span className="b2b-reg">{l.registries.map(r => <span key={r.registry}>{r.label}: <CheckChip result={r.result}/></span>)}</span>},
        {label: 'وضعیت', cell: l => <><LicenceChip status={l.status}/>{l.expiring_soon && <span className="as-chip warn">انقضا در {l.days_left.toLocaleString('fa-IR')} روز</span>}</>}]}/>
      <Unavail title="احراز تا اتصال API رسمی مراجع دستی است">کارشناس عملیات مدرک را با مرجع استعلام می‌کند و نتیجه، روش و شمارهٔ پیگیری را ثبت می‌کند. شمارهٔ مجوز شما روی سایت عمومی نمایش داده نمی‌شود.</Unavail></Card>
    {d.member_role === 'owner' && <Card title="بارگذاری یا تمدید مجوز"><LicenceForm agencyId={a.id} types={d.licence_types} onSaved={p.reload}/></Card>}
    <div className="b2b-soon" data-state="coming-soon"><b>برند و وایت‌لیبل</b><span className="as-muted">تنظیم دامنه، لوگو و رنگ برند آژانس در فاز ۶ فعال می‌شود. تا آن زمان فروش شما با برند کارن تراول و فروشندهٔ رسمی تاژبان انجام می‌شود.</span></div>
  </>}</Loaded>;
}
function PublishRule({what, needs, licences}: {what: string; needs: string; licences: Licence[]}) {
  const l = licences.find(x => x.licence_type === needs && x.status === 'verified');
  return <p className="as-row" style={{justifyContent: 'space-between', display: 'flex'}}><span>{what} ← {needs === 'BAND_ALEF' ? 'بند الف' : 'بند ب'}</span>{l ? <span className="as-chip ok">معتبر تا {jalali(l.expires_on)}</span> : <span className="as-chip bad">ندارید</span>}</p>;
}
function ProfileForm({agencyId, profile, owner, onSaved}: {agencyId: string; profile: Profile; owner: boolean; onSaved: () => void}) {
  const editable = owner && (profile.kyc_status === 'draft' || profile.kyc_status === 'rejected');
  const [form, setForm] = useState<Record<string, string>>(() => Object.fromEntries(PROFILE_FIELDS.map(([k]) => [k, String(profile[k] ?? '')])));
  const act = useAction();
  if (!editable) return <><dl className="b2b-kv">{PROFILE_FIELDS.map(([k, label]) => <div key={k} style={{display: 'contents'}}><dt>{label}</dt><dd>{profile[k] ? (['national_id', 'economic_code', 'postal_code', 'iban'].includes(k) ? <Ref>{String(profile[k])}</Ref> : String(profile[k])) : '—'}</dd></div>)}</dl>
    {profile.kyc_note && <p className="as-note warn">یادداشت عملیات: {profile.kyc_note}</p>}
    <p className="as-muted">{profile.kyc_status === 'active' ? 'ویرایش فیلدهای حقوقی پس از فعال شدن فقط با درخواست تغییر و تأیید عملیات ممکن است.' : profile.kyc_status === 'submitted' ? 'پروفایل برای احراز ارسال شده است.' : 'فقط مدیر آژانس پروفایل را ویرایش می‌کند.'}</p></>;
  const save = () => act.run(api => api.put(`/agency/${agencyId}/profile`, Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]))), 'ذخیره شد.').then(r => {if (r) onSaved();});
  const submit = () => act.run(api => api.post(`/agency/${agencyId}/profile/submit`, {}), 'برای احراز ارسال شد.').then(r => {if (r) onSaved();});
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void save();}}>
    {profile.kyc_note && <p className="as-note bad">دلیل رد: {profile.kyc_note}</p>}
    <div className="b2b-grid">{PROFILE_FIELDS.map(([k, label, hint]) => <Field key={k} label={label} hint={hint}><input name={k} value={form[k]} onChange={e => setForm({...form, [k]: e.target.value})} dir={['national_id', 'economic_code', 'postal_code', 'iban'].includes(k) ? 'ltr' : undefined}/></Field>)}</div>
    <Feedback error={act.error} done={act.done}/>
    <div className="as-actions"><button className="as-btn ghost" type="submit" disabled={act.busy}>ذخیرهٔ پروفایل</button><button className="as-btn" type="button" disabled={act.busy || !profile.complete} onClick={() => void submit()}>ارسال برای احراز</button></div>
    {!profile.complete && <small className="as-muted">برای ارسال، همهٔ فیلدهای اجباری را ذخیره کنید و دست‌کم یک مجوز ثبت کنید.</small>}
  </form>;
}
function LicenceForm({agencyId, types, onSaved}: {agencyId: string; types: Record<string, string>; onSaved: () => void}) {
  const [f, setF] = useState({licence_type: 'BAND_ALEF', authority: 'cao', number: '', issued_on: '', expires_on: '', document_reference: '', attest: false}); const act = useAction();
  const send = () => act.run(api => api.post(`/agency/${agencyId}/licences`, {licence_type: f.licence_type, authority: f.licence_type === 'ONLINE_SALES' ? f.authority : null, number: f.number, issued_on: f.issued_on || null,
    expires_on: f.expires_on, document_reference: f.document_reference || null, attest: f.attest}), 'مجوز ثبت شد و در انتظار احراز است.').then(r => {if (r) {setF({...f, number: '', issued_on: '', expires_on: '', document_reference: '', attest: false}); onSaved();}});
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void send();}}>
    <div className="b2b-grid3">
      <Field label="نوع مجوز"><select value={f.licence_type} onChange={e => setF({...f, licence_type: e.target.value})}>{Object.entries(types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
      {f.licence_type === 'ONLINE_SALES' && <Field label="مرجع صدور"><select value={f.authority} onChange={e => setF({...f, authority: e.target.value})}><option value="cao">سازمان هواپیمایی کشوری</option><option value="mcth">وزارت میراث فرهنگی</option></select></Field>}
      <Field label="شمارهٔ مجوز"><input required value={f.number} onChange={e => setF({...f, number: e.target.value})} dir="ltr"/></Field>
      <DateField label="تاریخ صدور" value={f.issued_on} onChange={v => setF({...f, issued_on: v})}/>
      <DateField label="تاریخ انقضا" required value={f.expires_on} onChange={v => setF({...f, expires_on: v})}/>
      <Field label="مرجع مدرک (شمارهٔ نامه یا نام فایل)" hint="بارگذاری فایل اسکن در این نسخه فعال نیست؛ مدرک را به کارشناس عملیات تحویل دهید."><input value={f.document_reference} onChange={e => setF({...f, document_reference: e.target.value})}/></Field>
    </div>
    <label className="as-check"><input type="checkbox" checked={f.attest} onChange={e => setF({...f, attest: e.target.checked})}/> اطلاعات بالا با مدرک مطابقت دارد و مسئولیت صحت آن با آژانس است.</label>
    <div className="as-note info">پس از ارسال، وضعیت «منتظر احراز» می‌شود و مجوز فعلی تا تاریخ انقضای خودش معتبر می‌ماند.</div>
    <Feedback error={act.error} done={act.done}/>
    <div className="as-actions"><button className="as-btn" type="submit" disabled={act.busy || !f.attest}>ارسال برای احراز</button></div>
  </form>;
}

/* ---------------------------------------------------------------- AG-15 account & credit */
type Entry = {id: string; entry_type: string; amount_irr: number; signed_amount_irr: number | null; balance_after: number; held_after: number; limit_after: number; reference: string | null; note: string | null; created_at: string};
type Req = {id: string; kind: string; status: string; summary: string; amount_irr: number | null; created_at: string};
const ENTRY_FA: Record<string, string> = {TOPUP: 'شارژ', DECREASE: 'کاهش', HOLD: 'بلوکه', CAPTURE: 'کسر در صدور', RELEASE: 'آزادسازی', REFUND: 'استرداد به اعتبار', COMMISSION: 'کمیسیون', LIMIT_CHANGE: 'تغییر سقف'};
const REQ_FA: Record<string, string> = {pending: 'منتظر تأیید نفر دوم مالی', executed: 'تأییدشده و اعمال‌شده', rejected: 'ردشده', expired: 'منقضی'};
export function AgencyCreditPage() {return <AgencyScope>{a => <CreditBody a={a}/>}</AgencyScope>;}
function CreditBody({a}: {a: Agency}) {
  const [filter, setFilter] = useState('');
  const w = useLoad<{member_role: string; balances: Account; entries: Entry[]; entries_visible: boolean; requests: Req[]}>(`/agency/${a.id}/wallet${filter ? `?entry_type=${filter}` : ''}`);
  const ctx = useLoad<Ctx>(`/agency/${a.id}/b2b`);
  const act = useAction();
  const exportCsv = () => act.run(async api => {const blob = await api.getBlob(`/agency/${a.id}/wallet/statement.csv`); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `statement-${a.id.slice(0, 8)}.csv`; link.click(); URL.revokeObjectURL(url); return true;}, 'فایل CSV آماده شد.');
  return <Loaded state={w.state} reload={w.reload} skeleton={<Skeleton rows={5}/>}>{d => <>
    {!d.balances.exists ? <EmptyState title="حساب اعتبار آژانس هنوز ساخته نشده است">حساب پس از احراز پروفایل و مجوزها توسط عملیات ساخته می‌شود؛ سقف اعتبار را مالی با تأیید دونفره تعیین می‌کند.</EmptyState> : <>
      <Stats items={[{label: 'سقف اعتبار', value: rial(d.balances.credit_limit_irr)}, {label: 'مصرف‌شده', value: rial(Math.max(0, -d.balances.balance_irr))}, {label: 'بلوکه (hold)', value: rial(d.balances.held_irr)},
        {label: 'ماندهٔ قابل استفاده', value: rial(d.balances.available_irr)}, ...(d.balances.balance_irr > 0 ? [{label: 'موجودی پیش‌پرداخت', value: rial(d.balances.balance_irr)}] : [])]}/>
      {d.balances.credit_limit_irr > 0 && <Card><BarMeter value={d.balances.usage_bps} label={`${pct(d.balances.usage_bps)} از سقف استفاده شده (مصرف + hold) · هشدار از ۸۰٪`}/></Card>}
    </>}
    {d.member_role === 'owner' && ctx.state.kind === 'ready' && ctx.state.data.kyc_status === 'active' && <div className="b2b-split">
      <Card title="درخواست شارژ اعتبار"><TopupForm agencyId={a.id} onDone={w.reload}/></Card>
      <div className="b2b-section"><Card title="درخواست افزایش سقف"><LimitForm agencyId={a.id} current={d.balances.credit_limit_irr} onDone={w.reload}/></Card>
        <Card title="درخواست‌های در جریان">{d.requests.length ? <ul className="pn-list">{d.requests.map(r => <li key={r.id}><b>{r.summary}</b> {r.amount_irr !== null && <span>· {rial(r.amount_irr)}</span>}<br/><StatusChip status={r.status === 'pending' ? 'submitted' : r.status === 'executed' ? 'approved' : 'rejected'} label={REQ_FA[r.status] ?? r.status}/> <small className="as-muted">ثبت: {jalali(r.created_at)}</small></li>)}</ul> : <p className="as-muted">درخواست بازی ندارید.</p>}</Card></div>
    </div>}
    <Card title="صورت حساب (حرکات)" action={d.entries_visible ? <button type="button" className="as-btn ghost" onClick={() => void exportCsv()} disabled={act.busy}>خروجی CSV</button> : undefined}>
      <Feedback error={act.error}/>
      {!d.entries_visible ? <p className="as-muted">گردش حساب فقط برای مدیر آژانس نمایش داده می‌شود.</p> : <>
        <div className="pn-chips" role="group" aria-label="نوع حرکت">{['', 'HOLD', 'CAPTURE', 'RELEASE', 'REFUND', 'COMMISSION', 'TOPUP', 'LIMIT_CHANGE'].map(t => <button type="button" key={t || 'all'} aria-pressed={filter === t} onClick={() => setFilter(t)}>{t ? `${ENTRY_FA[t]} · ${t}` : 'همه'}</button>)}</div>
        <Table rows={d.entries} rowKey={e => e.id} empty="حرکتی ثبت نشده است." cols={[
          {label: 'تاریخ', cell: e => jalali(e.created_at, true)}, {label: 'نوع', cell: e => `${ENTRY_FA[e.entry_type] ?? e.entry_type} · ${e.entry_type}`},
          {label: 'شرح', cell: e => e.note ?? '—'}, {label: 'مرجع', cell: e => e.reference ? <Ref>{e.reference}</Ref> : '—'},
          {label: 'مبلغ', cell: e => e.signed_amount_irr === null ? rial(e.amount_irr) : `${e.signed_amount_irr < 0 ? '−' : '+'} ${rial(Math.abs(e.signed_amount_irr))}`},
          {label: 'مانده پس از حرکت', cell: e => rial(e.balance_after)}]}/></>}
    </Card>
  </>}</Loaded>;
}
function TopupForm({agencyId, onDone}: {agencyId: string; onDone: () => void}) {
  const [f, setF] = useState({amount: '', bank_reference: '', paid_on: '', note: ''}); const [open, setOpen] = useState(false); const [k, setK] = useState(() => newKey('topup')); const act = useAction();
  const amount = parseRial(f.amount);
  const send = () => act.run(api => api.post(`/agency/${agencyId}/topup-requests`, {amount_irr: amount, bank_reference: f.bank_reference, paid_on: f.paid_on || null, note: f.note || null}, k),
    'درخواست ثبت شد؛ پس از تأیید مالی (دو نفر) به حساب اضافه می‌شود.').then(r => {if (r) {setOpen(false); setF({amount: '', bank_reference: '', paid_on: '', note: ''}); setK(newKey('topup')); onDone();}});
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); if (amount > 0) setOpen(true);}}>
    <div className="b2b-choice" role="radiogroup" aria-label="روش شارژ"><label><input type="radio" name="method" defaultChecked/> <span><b>واریز بانکی</b><small>ثبت شمارهٔ پیگیری واریز</small></span></label>
      <label aria-disabled="true"><input type="radio" name="method" disabled/> <span><b>پرداخت آنلاین</b><small>درگاه آژانس هنوز وصل نیست</small></span></label></div>
    <div className="b2b-grid">
      <Field label="مبلغ (ریال)" hint={amount > 0 ? rial(amount) : 'عدد را به ریال وارد کنید'}><input inputMode="numeric" required value={f.amount} onChange={e => setF({...f, amount: e.target.value})} dir="ltr"/></Field>
      <Field label="شمارهٔ پیگیری بانکی"><input required minLength={4} value={f.bank_reference} onChange={e => setF({...f, bank_reference: e.target.value})} dir="ltr"/></Field>
      <DateField label="تاریخ واریز" value={f.paid_on} onChange={v => setF({...f, paid_on: v})}/>
      <Field label="توضیح"><input value={f.note} onChange={e => setF({...f, note: e.target.value})}/></Field>
    </div>
    <div className="as-note info"><b>شارژ پس از تأیید مالی در حساب می‌نشیند.</b> ثبت‌کننده و تأییدکنندهٔ مالی دو نفر متفاوت هستند (maker-checker)؛ تا تأیید، مبلغی به مانده اضافه نمی‌شود.</div>
    <Feedback error={act.error} done={act.done}/>
    <div className="as-actions"><button className="as-btn" type="submit" disabled={act.busy || !(amount > 0)}>ثبت درخواست شارژ</button></div>
    <ConfirmMoney open={open} title="ثبت درخواست شارژ" amount={amount > 0 ? amount : 0} destination="حساب اعتبار آژانس در کارن تراول" reason={<>واریز بانکی، شمارهٔ پیگیری <Ref>{f.bank_reference}</Ref></>}
      twoPerson="این درخواست پس از بررسی و تأیید کارشناس مالی (نفر دوم) اعمال می‌شود." busy={act.busy} error={act.error} confirmLabel="ثبت درخواست" idempotencyKey={k} onConfirm={() => void send()} onClose={() => setOpen(false)}/>
  </form>;
}
function LimitForm({agencyId, current, onDone}: {agencyId: string; current: number; onDone: () => void}) {
  const [f, setF] = useState({limit: '', reason: ''}); const [k, setK] = useState(() => newKey('limit')); const act = useAction(); const v = parseRial(f.limit);
  const send = () => act.run(api => api.post(`/agency/${agencyId}/credit-limit-requests`, {new_limit_irr: v, reason: f.reason}, k), 'درخواست ثبت شد و پس از تأیید مالی اعمال می‌شود.').then(r => {if (r) {setF({limit: '', reason: ''}); setK(newKey('limit')); onDone();}});
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void send();}}><p className="as-muted">سقف فعلی: {rial(current)}</p>
    <Field label="سقف پیشنهادی (ریال)" hint={v >= 0 ? rial(v) : undefined}><input inputMode="numeric" required value={f.limit} onChange={e => setF({...f, limit: e.target.value})} dir="ltr"/></Field>
    <Field label="دلیل"><input required minLength={3} value={f.reason} onChange={e => setF({...f, reason: e.target.value})}/></Field>
    <Feedback error={act.error} done={act.done}/><div className="as-actions"><button className="as-btn ghost" type="submit" disabled={act.busy || Number.isNaN(v)}>درخواست افزایش سقف</button></div></form>;
}

/* ---------------------------------------------------------------- AG-07 markup & commission */
type Rule = {id: string; priority: number; service_scope: string; route: string | null; kind: string; value_bps: number; fixed_irr: number; min_irr: number | null; max_irr: number | null; valid_from: string | null; valid_to: string | null; status: string};
const SCOPE_FA: Record<string, string> = {any: 'همه', flight: 'پرواز (سیستمی و چارتر)', flight_charter: 'پرواز چارتر', hotel: 'هتل', tour: 'تور'};
export function AgencyPricingPage() {return <AgencyScope>{a => <PricingBody a={a}/>}</AgencyScope>;}
function PricingBody({a}: {a: Agency}) {
  const r = useLoad<{member_role: string; contract: {commission_bps: number; platform_markup_bps: number; vat_rate_bps: number; vat_rate_id: string; vat_legal_reference: string}; items: Rule[]}>(`/agency/${a.id}/markup-rules`);
  const [edit, setEdit] = useState<Rule | 'new' | null>(null);
  return <Loaded state={r.state} reload={r.reload}>{d => <>
    <Card title="قرارداد کارن تراول با شما" action={<span className="as-chip">فقط خواندنی</span>}><dl className="b2b-kv">
      <dt>کمیسیون شما (commission_bps)</dt><dd>{pct(d.contract.commission_bps)} از قیمت خالص</dd><dt>markup قراردادی پلتفرم</dt><dd>{pct(d.contract.platform_markup_bps)}</dd>
      <dt>ارزش افزودهٔ کمیسیون</dt><dd>{pct(d.contract.vat_rate_bps)} — {d.contract.vat_legal_reference}</dd></dl>
      <p className="as-muted">تغییر این مقادیر فقط از طریق مدیر حساب و قرارداد انجام می‌شود.</p></Card>
    <Card title="قواعد markup من" action={d.member_role === 'owner' ? <button className="as-btn" type="button" onClick={() => setEdit('new')}>قاعدهٔ جدید</button> : undefined}>
      <p className="as-muted">اولویت از کم به زیاد؛ اولین قاعدهٔ منطبق اعمال می‌شود. قیمت مشتری هرگز از سقف سازمان هواپیمایی بالاتر نمی‌رود.</p>
      <Table rows={d.items} rowKey={x => x.id} empty="قاعده‌ای تعریف نشده است؛ markup پیش‌فرض صفر است." cols={[
        {label: 'اولویت', cell: x => x.priority.toLocaleString('fa-IR')}, {label: 'نوع محصول', cell: x => SCOPE_FA[x.service_scope] ?? x.service_scope}, {label: 'مسیر', cell: x => x.route ? <Ref>{x.route}</Ref> : 'همه'},
        {label: 'بازهٔ تاریخ', cell: x => x.valid_from || x.valid_to ? `${jalali(x.valid_from)} تا ${jalali(x.valid_to)}` : 'بدون محدودیت'},
        {label: 'نوع و مقدار', cell: x => x.kind === 'pct' ? `درصدی ${pct(x.value_bps)}` : `ثابت ${rial(x.fixed_irr)} برای هر مسافر`},
        {label: 'حداقل / حداکثر', cell: x => `${x.min_irr !== null ? rial(x.min_irr) : '—'} / ${x.max_irr !== null ? rial(x.max_irr) : '—'}`},
        {label: 'وضعیت', cell: x => <StatusChip status={x.status === 'active' ? 'approved' : 'withdrawn'} label={x.status === 'active' ? 'فعال' : 'غیرفعال'}/>},
        {label: 'اقدام', cell: x => d.member_role === 'owner' ? <button className="as-btn ghost" type="button" onClick={() => setEdit(x)}>ویرایش</button> : '—'}]}/></Card>
    {edit && <Card title={edit === 'new' ? 'قاعدهٔ جدید' : `ویرایش قاعدهٔ ${edit.priority.toLocaleString('fa-IR')}`}><RuleForm agencyId={a.id} rule={edit === 'new' ? null : edit} onDone={() => {setEdit(null); r.reload();}} onCancel={() => setEdit(null)}/></Card>}
    <Card title="پیش‌نمایش روی قیمت واقعی"><OfferQuote agencyId={a.id} canBook={false}/></Card>
  </>}</Loaded>;
}
function RuleForm({agencyId, rule, onDone, onCancel}: {agencyId: string; rule: Rule | null; onDone: () => void; onCancel: () => void}) {
  const [f, setF] = useState({priority: String(rule?.priority ?? 100), service_scope: rule?.service_scope ?? 'flight', route: rule?.route ?? '', kind: rule?.kind ?? 'fixed', value: rule ? String(rule.kind === 'pct' ? rule.value_bps : rule.fixed_irr) : '',
    min: rule?.min_irr !== null && rule?.min_irr !== undefined ? String(rule.min_irr) : '', max: rule?.max_irr !== null && rule?.max_irr !== undefined ? String(rule.max_irr) : '', valid_from: rule?.valid_from ?? '', valid_to: rule?.valid_to ?? '', status: rule?.status ?? 'active'});
  const act = useAction();
  const body = () => ({priority: Number(f.priority) || 100, service_scope: f.service_scope, route: f.route.trim().toUpperCase() || null, kind: f.kind, value_bps: f.kind === 'pct' ? parseRial(f.value) || 0 : 0, fixed_irr: f.kind === 'fixed' ? parseRial(f.value) || 0 : 0,
    min_irr: f.min ? parseRial(f.min) : null, max_irr: f.max ? parseRial(f.max) : null, valid_from: f.valid_from || null, valid_to: f.valid_to || null, status: f.status});
  const save = () => act.run(api => rule ? api.put(`/agency/${agencyId}/markup-rules/${rule.id}`, body()) : api.post(`/agency/${agencyId}/markup-rules`, body()), 'ذخیره شد.').then(r => {if (r) onDone();});
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void save();}}>
    <div className="b2b-grid3">
      <Field label="نوع محصول"><select value={f.service_scope} onChange={e => setF({...f, service_scope: e.target.value})}>{Object.entries(SCOPE_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
      <Field label="مسیر (اختیاری)" hint="مثل IKA-IST"><input value={f.route} onChange={e => setF({...f, route: e.target.value})} dir="ltr" pattern="[A-Za-z]{3}-[A-Za-z]{3}"/></Field>
      <Field label="اولویت"><input inputMode="numeric" value={f.priority} onChange={e => setF({...f, priority: e.target.value})} dir="ltr"/></Field>
      <DateField label="از تاریخ" value={f.valid_from} onChange={v => setF({...f, valid_from: v})}/><DateField label="تا تاریخ" value={f.valid_to} onChange={v => setF({...f, valid_to: v})}/>
      <Field label="وضعیت"><select value={f.status} onChange={e => setF({...f, status: e.target.value})}><option value="active">فعال</option><option value="disabled">غیرفعال</option></select></Field>
    </div>
    <div className="b2b-choice" role="radiogroup" aria-label="نوع markup"><label><input type="radio" checked={f.kind === 'fixed'} onChange={() => setF({...f, kind: 'fixed'})}/> <span><b>مبلغ ثابت</b><small>به ازای هر مسافر (ریال)</small></span></label>
      <label><input type="radio" checked={f.kind === 'pct'} onChange={() => setF({...f, kind: 'pct'})}/> <span><b>درصدی (bps)</b><small>از قیمت خالص؛ ۱۰۰ bps = ۱٪</small></span></label></div>
    <div className="b2b-grid3"><Field label={f.kind === 'pct' ? 'مقدار (bps)' : 'مقدار (ریال)'}><input inputMode="numeric" required value={f.value} onChange={e => setF({...f, value: e.target.value})} dir="ltr"/></Field>
      <Field label="حداقل (ریال، هر مسافر)"><input inputMode="numeric" value={f.min} onChange={e => setF({...f, min: e.target.value})} dir="ltr"/></Field>
      <Field label="حداکثر (ریال، هر مسافر)"><input inputMode="numeric" value={f.max} onChange={e => setF({...f, max: e.target.value})} dir="ltr"/></Field></div>
    <Feedback error={act.error} done={act.done}/>
    <div className="as-actions"><button className="as-btn" type="submit" disabled={act.busy}>ذخیرهٔ قاعده</button><button className="as-btn ghost" type="button" onClick={onCancel}>انصراف</button></div>
  </form>;
}

/* ---------------------------------------------------------------- sell on credit (AG-03 minimal) */
type Offer = {id: string; title: string; service_type: string; amount: number; currency: string; valid_until: string};
type Preview = {title: string; breakdown: BuyerBreakdown & {markup_source: string}; account: Account; sufficient_credit: boolean};
type Line = {id: string; reservation_id: string | null; booking_reference: string | null; reservation_status: string | null; service_type: string; title: string; units: number; status: string; breakdown: BuyerBreakdown; failure_reason: string | null; created_at: string};
export function AgencySellPage() {return <AgencyScope>{a => <SellBody a={a}/>}</AgencyScope>;}
function SellBody({a}: {a: Agency}) {
  const ctx = useLoad<Ctx>(`/agency/${a.id}/b2b`);
  return <Loaded state={ctx.state} reload={ctx.reload}>{c => <>
    {!c.can_book && <Unavail title="خرید از حساب آژانس فعال نیست">{c.kyc_status !== 'active' ? 'آژانس هنوز احراز و فعال نشده است.' : 'حساب اعتبار آژانس هنوز ساخته نشده است.'}</Unavail>}
    {c.account.exists && <Stats items={[{label: 'ماندهٔ قابل استفاده', value: rial(c.account.available_irr)}, {label: 'بلوکه (hold)', value: rial(c.account.held_irr)}]}/>}
    <Card title="انتخاب عرضه و پرداخت از حساب آژانس"><OfferQuote agencyId={a.id} canBook={c.can_book}/></Card>
  </>}</Loaded>;
}
export function OfferQuote({agencyId, canBook}: {agencyId: string; canBook: boolean}) {
  const [q, setQ] = useState(''); const [search, setSearch] = useState('');
  const offers = useLoad<{items: Offer[]}>(`/agency/${agencyId}/offers${search ? `?q=${encodeURIComponent(search)}` : ''}`);
  const [check, setCheck] = useState<{id: string; title: string} | null>(null); const [units, setUnits] = useState('1'); const [markup, setMarkup] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null); const [booked, setBooked] = useState<Line | null>(null); const [cmd, setCmd] = useState(() => newKey('agb'));
  const act = useAction();
  const quote = (offer: Offer) => act.run(async api => {
    const pc = await api.post<{id: string}>(`/offers/${offer.id}/price-check`, {units: Number(units) || 1, command_id: newKey('pc')});
    const pv = await api.post<Preview>(`/agency/${agencyId}/credit-bookings/preview`, {price_check_id: pc.id}); setCheck({id: pc.id, title: offer.title}); setPreview(pv); setMarkup(String(pv.breakdown.markup_irr)); setBooked(null); setCmd(newKey('agb')); return pv;});
  const repreview = () => check && act.run(async api => {const pv = await api.post<Preview>(`/agency/${agencyId}/credit-bookings/preview`, {price_check_id: check.id, markup_irr: parseRial(markup)}); setPreview(pv); return pv;});
  const book = () => check && act.run(async api => {const r = await api.post<Line>(`/agency/${agencyId}/credit-bookings`, {price_check_id: check.id, markup_irr: parseRial(markup), command_id: cmd}); setBooked(r); return r;}, 'رزرو ثبت و از حساب آژانس پرداخت شد.');
  return <div className="b2b-section">
    <form className="pn-form" onSubmit={e => {e.preventDefault(); setSearch(q.trim());}}><label>جست‌وجو در عرضه‌های فعال<input value={q} onChange={e => setQ(e.target.value)} placeholder="عنوان پرواز، هتل یا تور"/></label>
      <label>تعداد<input inputMode="numeric" value={units} onChange={e => setUnits(e.target.value)} style={{width: 80}} dir="ltr"/></label><button className="pn-btn ghost" type="submit">جست‌وجو</button></form>
    <Loaded state={offers.state} reload={offers.reload} skeleton={<Skeleton kind="table" rows={3}/>}>{o => <Table rows={o.items.slice(0, 12)} rowKey={x => x.id} empty="عرضهٔ فعالی پیدا نشد." cols={[
      {label: 'عنوان', cell: x => x.title}, {label: 'قیمت هر واحد', cell: x => rial(x.amount)}, {label: 'معتبر تا', cell: x => jalali(x.valid_until, true)},
      {label: 'اقدام', cell: x => <button className="as-btn ghost" type="button" disabled={act.busy} onClick={() => void quote(x)}>استعلام و پیش‌نمایش</button>}]}/>}</Loaded>
    {preview && check && <div className="b2b-split" data-testid="agency-quote">
      <div className="b2b-section"><b>{check.title}</b><MoneyBreakdown view="agency_buyer" data={preview.breakdown}/></div>
      <div className="b2b-section">
        <Field label="markup این سفارش (ریال)" hint={preview.breakdown.markup_source === 'rule' ? 'از قاعدهٔ شما؛ در محدودهٔ حداقل و حداکثر قاعده قابل تغییر است' : 'قاعده‌ای منطبق نشد'}><input inputMode="numeric" value={markup} onChange={e => setMarkup(e.target.value)} dir="ltr"/></Field>
        <button className="as-btn ghost" type="button" onClick={() => void repreview()} disabled={act.busy}>محاسبهٔ دوباره</button>
        {!preview.sufficient_credit && <p className="as-note bad">ماندهٔ قابل استفادهٔ حساب برای این خرید کافی نیست.</p>}
        {canBook && !booked && <button className="as-btn" type="button" disabled={act.busy || !preview.sufficient_credit || preview.breakdown.price_cap_status === 'exceeded'} onClick={() => void book()}>رزرو و پرداخت از حساب آژانس</button>}
        {booked && <div className="as-note ok" role="status">کد رزرو: <Ref>{booked.booking_reference}</Ref> · وضعیت: <StatusChip status={booked.reservation_status}/> <Link className="pn-link" href="/agency/bookings">رزروها</Link></div>}
      </div></div>}
    <Feedback error={act.error} done={booked ? undefined : act.done}/>
  </div>;
}

/* ---------------------------------------------------------------- AG-05: bookings paid from the agency account */
export function AgencyCreditBookings() {return <AgencyScope>{a => <CreditBookingsBody a={a}/>}</AgencyScope>;}
function CreditBookingsBody({a}: {a: Agency}) {
  const r = useLoad<{items: Line[]}>(`/agency/${a.id}/credit-bookings`); const [open, setOpen] = useState('');
  return <Card title="رزروهای پرداخت‌شده از حساب آژانس"><Loaded state={r.state} reload={r.reload} skeleton={<Skeleton kind="table" rows={3}/>}>{d => <>
    <Table rows={d.items} rowKey={x => x.id} empty="هنوز رزروی از حساب آژانس پرداخت نشده است." cols={[
      {label: 'کد رزرو', cell: x => x.booking_reference ? <Ref>{x.booking_reference}</Ref> : '—'}, {label: 'عنوان', cell: x => x.title}, {label: 'تعداد', cell: x => x.units.toLocaleString('fa-IR')},
      {label: 'کسر از حساب', cell: x => rial(x.breakdown.net_irr)}, {label: 'قیمت به مشتری شما', cell: x => rial(x.breakdown.customer_price_irr)}, {label: 'کمیسیون', cell: x => rial(x.breakdown.commission_irr)},
      {label: 'وضعیت', cell: x => x.status === 'captured' ? <StatusChip status={x.reservation_status ?? 'confirmed'}/> : <StatusChip status="failed" label={x.status === 'released' ? 'ثبت نشد؛ مبلغ آزاد شد' : 'در حال ثبت'}/>},
      {label: 'تفکیک', cell: x => <button className="as-btn ghost" type="button" onClick={() => setOpen(open === x.id ? '' : x.id)}>{open === x.id ? 'بستن' : 'نمایش'}</button>}]}/>
    {d.items.filter(x => x.id === open).map(x => <MoneyBreakdown key={x.id} view="agency_buyer" data={x.breakdown}/>)}</>}</Loaded></Card>;
}

/* ---------------------------------------------------------------- invoices (commission, B2B type 1) */
export function AgencyInvoicesPage() {return <AgencyScope>{a => <InvoicesBody a={a}/>}</AgencyScope>;}
function InvoicesBody({a}: {a: Agency}) {
  const r = useLoad<{pattern: string; moadian: string; items: {line_id: string; booking_reference: string | null; title: string; date: string; commission_irr: number; vat_rate_bps: number; vat_irr: number; total_irr: number; status_label: string}[]; totals: {commission_irr: number; vat_irr: number; total_irr: number}}>(`/agency/${a.id}/invoices`);
  return <Loaded state={r.state} reload={r.reload}>{d => <>
    <Stats items={[{label: 'جمع کمیسیون', value: rial(d.totals.commission_irr)}, {label: 'ارزش افزودهٔ کمیسیون', value: rial(d.totals.vat_irr)}, {label: 'جمع صورتحساب‌ها', value: rial(d.totals.total_irr)}]}/>
    <Card title={`صورتحساب‌ها — ${d.pattern}`}><Unavail title="ارسال به سامانهٔ مودیان">این صورتحساب‌ها پیش‌نویس‌اند و هنوز به سامانهٔ مودیان ارسال نمی‌شوند (فاز ۵). ارزش افزوده فقط روی کمیسیون است.</Unavail>
      <Table rows={d.items} rowKey={x => x.line_id} empty="صورتحسابی نیست." cols={[{label: 'کد رزرو', cell: x => x.booking_reference ? <Ref>{x.booking_reference}</Ref> : '—'}, {label: 'شرح', cell: x => x.title}, {label: 'تاریخ', cell: x => jalali(x.date)},
        {label: 'کمیسیون', cell: x => rial(x.commission_irr)}, {label: 'ارزش افزوده', cell: x => `${rial(x.vat_irr)} (${pct(x.vat_rate_bps)})`}, {label: 'جمع', cell: x => rial(x.total_irr)}, {label: 'وضعیت', cell: x => <StatusChip status="submitted" label={x.status_label}/>}]}/></Card></>}</Loaded>;
}

/* ---------------------------------------------------------------- AG-20 users */
export function AgencyUsersPage() {return <AgencyScope>{a => <UsersBody a={a}/>}</AgencyScope>;}
function UsersBody({a}: {a: Agency}) {
  const r = useLoad<{member_role: string; items: {user_id: number; name: string | null; role: string; role_label: string; is_me: boolean}[]}>(`/agency/${a.id}/members`); const act = useAction();
  const setRole = (uid: number, role: string) => act.run(api => api.put(`/agency/${a.id}/members/${uid}/role`, {role}), 'نقش به‌روز شد.').then(x => {if (x) r.reload();});
  return <Card title="کاربران آژانس"><Loaded state={r.state} reload={r.reload}>{d => <>
    <Table rows={d.items} rowKey={x => String(x.user_id)} empty="کاربری نیست." cols={[{label: 'نام', cell: x => `${x.name ?? '—'}${x.is_me ? ' (شما)' : ''}`}, {label: 'نقش', cell: x => ROLE_FA[x.role] ?? x.role_label},
      {label: 'تغییر نقش', cell: x => d.member_role === 'owner' && !x.is_me ? <select aria-label={`نقش ${x.name ?? ''}`} value={x.role} disabled={act.busy} onChange={e => void setRole(x.user_id, e.target.value)}><option value="owner">مدیر آژانس</option><option value="agent">کارشناس فروش آژانس</option></select> : '—'}]}/>
    <Feedback error={act.error} done={act.done}/>
    <p className="as-muted">مدیر آژانس همه‌چیز (پروفایل، مالی، کاربران، قواعد قیمت و موجودی) را می‌بیند؛ کارشناس فروش فقط فروش و رزرو انجام می‌دهد و گردش حساب را نمی‌بیند. افزودن کاربر تازه با مدیر مجموعهٔ کارن تراول است.</p></>}</Loaded></Card>;
}
