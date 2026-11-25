'use client';
/* Organization requests: new request, the requests this person may see, and the quick approval card (Stitch _26).
   Every value on the approval card is a field of GET /enterprise/requests/{id}; the official tax invoice of the Stitch
   mockup is not drawn here, because an invoice exists only after a booking is linked (see /organization/billing). */
import '../panel/stitch-org-2026-11.css';
import Link from 'next/link';
import {EnterpriseBookingHandoff} from './EnterpriseBookingHandoff';
import {Fragment, FormEvent, useEffect, useRef, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {newId} from '../../lib/api/karenseir-client';
import {ErrorState} from './ConnectedViews';
type Org = {id: string; name: string; permissions: string[]};
type Requirements = {origin?: string; destination?: string; starts_at?: string; ends_at?: string; headcount?: number; budget_amount?: number; services?: string[]; purpose?: string};
type Quote = {id: string; supplier_id: string; revision: number; amount: number; currency: string; valid_until: string};
type Detail = {id: string; organization_id: string; requester_id: number; title: string; use_case: string; status: string; policy_result: string; policy_reasons: string[]; policy_version: number | null; current_step: number; approver_ids: number[]; selected_quote_id: string | null; requirements: Requirements; events: Array<{type: string; at: string}>; quotes: Quote[]};
type Member = {id: number; name: string};
type Row = {id: string; title?: string; name?: string; status: string; use_case?: string; policy_result?: string; requirements?: Requirements; proposed_total?: number; recipient_count?: number};
const cases: Record<string, string> = {business_travel: 'سفر کاری', workforce_accommodation: 'اقامت نیروهای پروژه', relocation: 'جابجایی کارکنان', team_retreat: 'سفر و برنامهٔ تیمی', incentive: 'سفر تشویقی', organizational_guests: 'مهمان سازمان', employee_welfare: 'رفاه کارکنان', organizational_event: 'رویداد سازمانی', travel_credit: 'اعتبار سفر'};
const statuses: Record<string, string> = {DRAFT: 'پیش‌نویس؛ تأمین مالی نشده', approval_required: 'در انتظار تأیید', approved: 'تأیید درخواست؛ هنوز رزرو نشده', policy_required: 'نیازمند تنظیم سیاست سازمان', not_allowed: 'خارج از خدمات مجاز', withdrawn: 'انصراف داده‌شده', rejected: 'رد شده', rfq_open: 'در انتظار پیشنهاد تأمین‌کننده', quoted: 'پیشنهاد دریافت شده', quote_selected: 'پیشنهاد انتخاب شده؛ هنوز قرارداد نیست'};
const tone: Record<string, string> = {approval_required: 'gold', policy_required: 'gold', rfq_open: 'gold', quoted: 'gold', DRAFT: 'gold', approved: 'ok', quote_selected: 'ok', rejected: 'bad', not_allowed: 'bad', withdrawn: 'soft'};
const policyFa: Record<string, string> = {IN_POLICY: 'منطبق با سیاست سفر سازمان', OUT_OF_POLICY: 'خارج از سیاست سفر سازمان', APPROVAL_REQUIRED: 'نیازمند تأیید طبق سیاست سازمان', NOT_ALLOWED: 'خدمت در سیاست سازمان مجاز نیست', BLOCKED: 'ممنوع طبق سیاست سازمان'};
const eventFa: Record<string, string> = {'request.created': 'ثبت درخواست', 'approval.approve': 'تأیید', 'approval.reject': 'رد درخواست', 'request.withdrawn': 'پس‌گرفتن درخواست', 'booking.linked': 'اتصال رزرو', 'quote.submitted': 'دریافت پیشنهاد', 'quote.selected': 'انتخاب پیشنهاد', 'invitation.sent': 'دعوت تأمین‌کننده'};
const serviceFa: Record<string, string> = {hotel: 'هتل', flight: 'پرواز', tour: 'تور', vacation_rental: 'اقامتگاه', event_hall: 'سالن رویداد', pool_sport: 'ورزش و استخر', tourist_transportation: 'حمل‌ونقل گردشگری'};
const fa = (n: number) => n.toLocaleString('fa-IR');
const rial = (n: number, c = 'IRR') => `${fa(n)} ${c === 'IRR' ? 'ریال' : c}`;
const day = (iso?: string) => {if (!iso) return '—'; const d = new Date(iso); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fa-IR', {year: 'numeric', month: 'long', day: 'numeric'});};
const KEY = 'karenseir-panel-organization';

export function EnterpriseWorkspace() {
  const {api, session} = useAuth(); const [orgs, setOrgs] = useState<Org[] | null>(null), [org, setOrg] = useState(''), [rows, setRows] = useState<Row[]>([]), [campaigns, setCampaigns] = useState<Row[]>([]), [members, setMembers] = useState<Member[]>([]), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false), [detail, setDetail] = useState<Detail | null>(null), [me, setMe] = useState<number | null>(null);
  // A deep link from the dashboard (?request=<id>) opens that request once its organization's list is loaded.
  const wanted = useRef<string | null>(null); const cardRef = useRef<HTMLElement | null>(null);
  const selected = orgs?.find(o => o.id === org); const benefits = selected?.permissions.includes('benefits.manage');
  const policyManage = selected?.permissions.includes('policy.manage'); const readMembers = !!selected?.permissions.some(p => ['roles.manage', 'policy.manage', 'requests.on_behalf', 'benefits.manage'].includes(p));
  useEffect(() => {if (org && readMembers && !benefits) api.get<Member[]>('/enterprise/organizations/' + org + '/members').then(setMembers).catch(() => setNotice('فهرست اعضا دریافت نشد.'));}, [api, org, readMembers, benefits]);
  useEffect(() => {if (session) api.get<{user_id: number}>('/me/profile').then(p => setMe(p.user_id)).catch(() => undefined);}, [api, session]);
  async function open(id: string) {try {setDetail(await api.get<Detail>('/enterprise/requests/' + id)); requestAnimationFrame(() => cardRef.current?.scrollIntoView({block: 'start'}));} catch {setNotice('جزئیات دریافت نشد.');}}
  async function decide(event: FormEvent<HTMLFormElement>) {event.preventDefault(); if (!detail || busy) return; const f = new FormData(event.currentTarget); setBusy(true); try {const result = await api.post<Row>('/enterprise/requests/' + detail.id + '/decision', {command_id: newId(), decision: f.get('decision'), reason: f.get('reason')}); setRows(old => old.map(r => r.id === result.id ? result : r)); setDetail(await api.get<Detail>('/enterprise/requests/' + detail.id)); setNotice('تصمیم ثبت شد.');} catch (e) {setNotice(e instanceof Error ? e.message : 'تصمیم ثبت نشد.');} finally {setBusy(false);}}
  async function savePolicy(event: FormEvent<HTMLFormElement>) {event.preventDefault(); const f = new FormData(event.currentTarget); setBusy(true); try {const approver = Number(f.get('approver')); await api.put('/enterprise/organizations/' + org + '/policy', {command_id: newId(), rules: {allowed_services: [String(f.get('service'))], maximum_budget: Number(f.get('maximum')), approval_required: true, approver_ids: [approver]}}); setNotice('نسخهٔ جدید سیاست برای درخواست‌های بعدی ذخیره شد.');} catch (e) {setNotice(e instanceof Error ? e.message : 'سیاست ذخیره نشد.');} finally {setBusy(false);}}
  useEffect(() => {
    if (!session) return; let target: string | null = null; try {target = new URLSearchParams(window.location.search).get('request');} catch {/* no location */}
    wanted.current = target;
    api.get<{organizations: Org[]}>('/enterprise/context').then(async d => {
      setOrgs(d.organizations); let start = '';
      if (target) {try {start = (await api.get<Detail>('/enterprise/requests/' + target)).organization_id;} catch {setNotice('درخواست موردنظر پیدا نشد یا در محدودهٔ دسترسی شما نیست.'); wanted.current = null;}}
      if (!start) {try {start = sessionStorage.getItem(KEY) ?? '';} catch {/* storage unavailable */}}
      setOrg(d.organizations.some(o => o.id === start) ? start : d.organizations[0]?.id ?? '');
    }).catch(() => setNotice('اطلاعات سازمان دریافت نشد؛ صفحه را دوباره بارگذاری کنید.'));
  }, [api, session]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- intentionally clears the previous result when the request inputs change, so stale data is never shown while the new fetch is in flight
  useEffect(() => {let active = true; setRows([]); setCampaigns([]); setMembers([]); setDetail(null); if (org) {api.get<Row[]>('/enterprise/requests?org=' + org).then(d => {if (!active) return; setRows(d); const w = wanted.current; if (w && d.some(r => r.id === w)) {wanted.current = null; void open(w);}}).catch(() => setNotice('دریافت درخواست‌ها ناموفق بود.')); if (benefits) {Promise.all([api.get<Row[]>('/enterprise/organizations/' + org + '/campaigns'), api.get<Member[]>('/enterprise/organizations/' + org + '/members')]).then(([c, m]) => {if (active) {setCampaigns(c); setMembers(m);}}).catch(() => setNotice('دریافت کمپین‌ها ناموفق بود.'));}} return () => {active = false;};
  // eslint-disable-next-line react-hooks/exhaustive-deps -- open() only reads api, which is already a dependency
  }, [api, org, benefits]);
  async function submit(event: FormEvent<HTMLFormElement>, campaign = false) {
    event.preventDefault(); if (busy) return; setBusy(true); setNotice(''); const form = event.currentTarget; const f = new FormData(form); const text = (key: string) => String(f.get(key) ?? ''); let body: Record<string, unknown>;
    try {
      body = campaign ? {name: text('name'), product_type: 'EMPLOYEE_BENEFIT', amount_per_recipient: Number(text('amount')), maximum_contribution: Number(text('amount')), recipient_ids: f.getAll('recipient').map(Number), valid_from: new Date(text('from')).toISOString(), valid_until: new Date(text('until')).toISOString(), services: [text('service')], message: text('message'), occasion: text('occasion')}
        : {title: text('title'), use_case: text('use_case'), purpose: text('purpose'), origin: text('origin'), destination: text('destination'), starts_at: new Date(text('from')).toISOString(), ends_at: new Date(text('until')).toISOString(), headcount: Number(text('headcount')), services: [text('service')], budget_amount: Number(text('budget'))};
      const path = '/enterprise/organizations/' + org + (campaign ? '/campaigns' : '/requests'); const storageKey = 'enterprise-pending-' + org + (campaign ? '-campaign' : '-request'); const signature = JSON.stringify(body); let pending: {signature: string; id: string} | null = null; try {pending = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null');} catch {/* corrupt browser state */}
      const command = pending?.signature === signature ? pending.id : newId(); sessionStorage.setItem(storageKey, JSON.stringify({signature, id: command})); const row = await api.post<Row>(path, {...body, command_id: command}); sessionStorage.removeItem(storageKey);
      if (campaign) setCampaigns(old => [row, ...old.filter(r => r.id !== row.id)]); else setRows(old => [row, ...old.filter(r => r.id !== row.id)]);
      setNotice(campaign ? 'پیش‌نویس ذخیره شد. هیچ اعتبار قابل مصرفی صادر نشده است.' : 'درخواست ذخیره شد. وضعیت سیاست و تأیید را در فهرست دنبال کنید.'); form.reset();
    } catch (e) {setNotice(e instanceof Error ? e.message : 'ثبت انجام نشد؛ با همان اطلاعات دوباره تلاش کنید.');} finally {setBusy(false);}
  }
  if (!session) return <ErrorState status={401} message="برای مشاهدهٔ درخواست‌های سازمانی وارد حساب شوید."/>;
  const nameOf = (id: number) => id === me ? 'شما' : members.find(m => m.id === id)?.name ?? null;
  const canDecide = !!detail && detail.status === 'approval_required' && !!selected?.permissions.includes('requests.approve') && detail.requester_id !== me && (me === null || detail.approver_ids[detail.current_step] === me);
  return <div dir="rtl" className="so" data-stitch="_26">
    <section className="so-hero" aria-label="درخواست سفر سازمانی"><div className="so-hero-id"><span className="so-hero-ic" aria-hidden="true">✅</span><div><h2>درخواست سفر و مزایای سازمانی</h2><p>ثبت درخواست با رزرو یا پرداخت متفاوت است. تأیید سازمان و موجودی واقعی خدمت پیش از خرید بررسی می‌شوند.</p></div></div>
      {orgs && orgs.length > 1 && <div className="so-form" style={{gridTemplateColumns: 'minmax(0,1fr)'}}><label>سازمان<select value={org} onChange={e => {setOrg(e.target.value); try {sessionStorage.setItem(KEY, e.target.value);} catch {/* ignore */}}}>{orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label></div>}</section>
    {notice && <p className="so-note" role="status">{notice}</p>}
    {orgs === null ? <p className="pn-muted" role="status">در حال دریافت سازمان‌ها…</p> : orgs.length === 0 ? <div className="so-empty">عضویت سازمانی برای این حساب ثبت نشده است. <Link className="pn-link" href="/support">پیگیری عضویت</Link></div> : <>
      {detail && <section className="so-appr" ref={cardRef} aria-labelledby="so-appr-title" data-request={detail.id}>
        <div className="so-appr-head"><div><h3 id="so-appr-title">{detail.status === 'approval_required' ? 'تأیید سریع درخواست' : 'پروندهٔ درخواست'}: {detail.title}</h3>
          <div className="so-appr-meta"><span>کد پیگیری: <span className="so-ltr">{detail.id.slice(0, 8).toUpperCase()}</span></span>{nameOf(detail.requester_id) && <span>متقاضی: {nameOf(detail.requester_id)}</span>}<span>{cases[detail.use_case] ?? detail.use_case}</span>{detail.approver_ids.length > 0 && <span>مرحلهٔ تأیید: {fa(Math.min(detail.current_step + 1, detail.approver_ids.length))} از {fa(detail.approver_ids.length)}</span>}</div></div>
          <div className="so-hero-act"><span className={`so-chip ${tone[detail.status] ?? 'soft'}`}>{statuses[detail.status] ?? 'نیازمند بررسی'}</span><button type="button" className="so-btn ghost sm" onClick={() => setDetail(null)}>بستن</button></div></div>
        <div className={`so-policy ${detail.policy_result === 'IN_POLICY' ? '' : ['NOT_ALLOWED', 'BLOCKED'].includes(detail.policy_result) ? 'bad' : 'warn'}`}><span aria-hidden="true">{detail.policy_result === 'IN_POLICY' ? '✔' : '⚠'}</span><div><b>وضعیت انطباق: {policyFa[detail.policy_result] ?? detail.policy_result}</b>{detail.policy_version !== null && <span> — سنجیده‌شده با نسخهٔ {fa(detail.policy_version)} سیاست سفر</span>}
          {detail.policy_reasons.length > 0 && <ul>{detail.policy_reasons.map(x => <li key={x}>{x}</li>)}</ul>}</div></div>
        <div className="so-appr-grid">
          <div className="so-box"><h4>مشخصات سفر</h4><dl className="so-kv">
            <dt>مسیر</dt><dd>{[detail.requirements.origin, detail.requirements.destination].filter(Boolean).join(' ← ') || '—'}</dd>
            <dt>شروع</dt><dd>{day(detail.requirements.starts_at)}</dd><dt>پایان</dt><dd>{day(detail.requirements.ends_at)}</dd>
            {detail.requirements.headcount ? <><dt>تعداد نفرات</dt><dd>{fa(detail.requirements.headcount)} نفر</dd></> : null}
            {(detail.requirements.services ?? []).length > 0 && <><dt>خدمات</dt><dd>{(detail.requirements.services ?? []).map(s => serviceFa[s] ?? s).join('، ')}</dd></>}
            {detail.requirements.purpose && <><dt>هدف سفر</dt><dd>{detail.requirements.purpose}</dd></>}</dl></div>
          <div className="so-box"><h4>تفکیک مالی درخواست</h4>
            {detail.quotes.length > 0 && <dl className="so-kv">{detail.quotes.map(q => <Fragment key={q.id}><dt>پیشنهاد تأمین‌کننده (نسخهٔ {fa(q.revision)}){q.id === detail.selected_quote_id ? ' — انتخاب‌شده' : ''}</dt><dd>{rial(q.amount, q.currency)}</dd></Fragment>)}</dl>}
            {typeof detail.requirements.budget_amount === 'number' ? <div className="so-sum"><span>بودجهٔ پیشنهادی درخواست</span><strong>{rial(detail.requirements.budget_amount)}</strong></div> : <p className="pn-muted">بودجه‌ای برای این درخواست ثبت نشده است.</p>}
            <p className="pn-muted">فاکتور رسمی پس از رزرو و اتصال آن به همین درخواست صادر می‌شود و در «صورتحساب و تسویه» می‌آید.</p></div>
        </div>
        <div className="so-appr-actions">
          {canDecide ? <form onSubmit={e => void decide(e)}><label>تصمیم<select name="decision"><option value="approve">تأیید درخواست</option><option value="reject">رد درخواست و ارجاع با ذکر دلیل</option></select></label><label>دلیل تصمیم<input name="reason" required minLength={3} maxLength={500}/></label><button className="so-btn" disabled={busy}>ثبت تصمیم</button></form>
            : detail.status === 'approval_required' ? <p className="pn-muted">این درخواست در انتظار تصمیم تأییدکنندهٔ همین مرحله است.</p> : null}
          <div className="enterprise-workspace"><EnterpriseBookingHandoff key={detail.id} requestId={detail.id}/></div></div>
        <div><h4 className="pn-muted" style={{margin: '0 0 6px'}}>سابقهٔ درخواست ({fa(detail.events.length)} رویداد)</h4><ul className="so-timeline">{detail.events.map((e, i) => <li key={i}>{eventFa[e.type] ?? e.type} — {new Date(e.at).toLocaleString('fa-IR')}</li>)}</ul></div>
      </section>}
      <div className="so-grid">
        <section className="so-card" aria-labelledby="so-reqs"><div className="so-card-head"><h2 id="so-reqs">درخواست‌های در دسترس شما</h2>{rows.length > 0 && <span className="so-chip soft">{fa(rows.length)} درخواست</span>}</div>
          {rows.length === 0 ? <div className="so-empty">هنوز درخواستی ثبت نشده است.</div> : <ul className="so-list">{rows.map(r => <li key={r.id} aria-current={detail?.id === r.id ? 'true' : undefined}><div><b>{r.title}</b><br/><span>{[r.use_case && (cases[r.use_case] ?? r.use_case), r.requirements?.destination, r.requirements?.starts_at && day(r.requirements.starts_at)].filter(Boolean).join(' · ')}</span></div>
            <div className="so-hero-act"><span className={`so-chip ${tone[r.status] ?? 'soft'}`}>{statuses[r.status] ?? 'نیازمند بررسی'}</span><button type="button" className="so-btn ghost sm" onClick={() => void open(r.id)}>مشاهدهٔ پیگیری</button></div></li>)}</ul>}</section>
        <section className="so-card" aria-labelledby="so-new"><div className="so-card-head"><h2 id="so-new">درخواست جدید</h2></div>
          <form onSubmit={e => void submit(e)} className="so-form"><label>نوع درخواست<select name="use_case">{Object.entries(cases).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label><label>عنوان<input name="title" required minLength={3} maxLength={200}/></label><label className="so-wide">هدف سفر<input name="purpose" required minLength={3} maxLength={2000}/></label><label>مبدأ<input name="origin" required minLength={2}/></label><label>مقصد<input name="destination" required minLength={2}/></label><label>شروع<input type="date" name="from" required/></label><label>پایان<input type="date" name="until" required/></label><label>تعداد نفرات<input type="number" name="headcount" min={1} max={10000} defaultValue={1} required/></label><label>بودجهٔ پیشنهادی (ریال)<input type="number" name="budget" min={1} required/></label><Service/><div className="so-wide"><button className="so-btn" disabled={busy}>ثبت درخواست</button></div></form></section>
      </div>
      {policyManage && <section className="so-card" aria-labelledby="so-policy"><div className="so-card-head"><h2 id="so-policy">سیاست درخواست‌های جدید</h2></div><p className="so-card-sub">این فرم یک خدمت مجاز و یک تأییدکننده تنظیم می‌کند. تغییر سیاست، درخواست‌های قبلی را تغییر نمی‌دهد.</p><form onSubmit={e => void savePolicy(e)} className="so-form"><Service/><label>سقف بودجه (ریال)<input name="maximum" type="number" min={1} required/></label><label>تأییدکننده<select name="approver" required><option value="">انتخاب عضو دارای مجوز تأیید</option>{members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label><div className="so-wide"><button className="so-btn" disabled={busy}>ذخیرهٔ سیاست</button></div></form></section>}
      {benefits && <section className="so-card" aria-labelledby="so-campaign"><div className="so-card-head"><h2 id="so-campaign">پیش‌نویس کمپین مزایای سفر</h2></div><p className="so-card-sub">مبلغ‌ها ریال هستند. انتخاب کارکنان و ذخیرهٔ پیش‌نویس، تعهد مالی یا اعتبار قابل خرج‌کردن ایجاد نمی‌کند.</p><form onSubmit={e => void submit(e, true)} className="so-form"><label>نام کمپین<input name="name" required minLength={3}/></label><label>مبلغ برای هر نفر (ریال)<input name="amount" type="number" min={1} max={1000000000000} required/></label><label>شروع اعتبار<input name="from" type="date" required/></label><label>پایان اعتبار<input name="until" type="date" required/></label><Service/><label>مناسبت<input name="occasion" maxLength={100}/></label><label className="so-wide">پیام هدیه<textarea name="message" maxLength={1000}/></label><fieldset><legend>دریافت‌کنندگان عضو سازمان</legend>{members.map(m => <label key={m.id}><input name="recipient" type="checkbox" value={m.id}/>{m.name}</label>)}</fieldset><div className="so-wide"><button className="so-btn" disabled={busy || members.length === 0}>ذخیرهٔ پیش‌نویس کمپین</button></div></form>
        {campaigns.length > 0 && <ul className="so-list">{campaigns.map(c => <li key={c.id}><b>{c.name}</b><span>{statuses[c.status]} · {c.recipient_count?.toLocaleString('fa-IR')} نفر · جمع پیشنهادی {c.proposed_total?.toLocaleString('fa-IR')} ریال</span></li>)}</ul>}</section>}
    </>}
  </div>;
}
function Service() {return <label>خدمت موردنیاز<select name="service"><option value="hotel">هتل</option><option value="flight">پرواز</option><option value="tour">تور</option><option value="vacation_rental">اقامتگاه</option><option value="event_hall">سالن رویداد</option><option value="pool_sport">ورزش و استخر</option><option value="tourist_transportation">حمل‌ونقل گردشگری</option></select></label>;}
