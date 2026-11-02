'use client';
/* Sales desk (میز گفتگو و فروش): one case per customer request, from first contact to trip and survey.
   Every figure comes from /sales-desk/*; an empty list stays empty. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Empty, Stats, Table, dateFa, errorOf, fa, money, useLoad} from './PanelKit';
import {FormFields, Note, Tabs, type Opt, type Row} from './CommercePanel';
import {LeadImport} from './DataExchangePanel';

const CHANNELS: Opt = [['web_form', 'فرم سایت'], ['whatsapp', 'واتس‌اپ'], ['bale', 'بله'], ['phone', 'تماس تلفنی'], ['manual', 'ثبت دستی'], ['rebook', 'خرید مجدد'], ['referral', 'معرفی'],
  ['abandoned', 'سبد رهاشده'], ['trip_request', 'درخواست سفر'], ['campaign', 'کمپین'], ['complaint', 'شکایت'], ['instagram', 'اینستاگرام'], ['walk_in', 'مراجعه حضوری']];
const STAGES: Opt = [['new', 'جدید'], ['contacted', 'تماس گرفته شد'], ['quoted', 'پیش‌فاکتور ارسال شد'], ['awaiting_payment', 'منتظر پرداخت'], ['paid', 'پرداخت شد'], ['issued', 'صادر شد'], ['travelled', 'سفر انجام شد'], ['lost', 'لغو / منصرف']];
const TEMPLATES: Opt = [['welcome', 'خوش‌آمد'], ['quote', 'پیش‌فاکتور'], ['pay_remind', 'یادآوری پرداخت'], ['confirm', 'تأیید رزرو'], ['pre_trip', 'پیش از سفر'], ['survey', 'نظرسنجی']];
const label = (opts: Opt, v?: string | null) => opts.find(o => o[0] === v)?.[1] ?? v ?? '—';
const ACT: Record<string, string> = {created: 'ثبت پرونده', note: 'یادداشت', call: 'تماس', message: 'پیام', stage: 'تغییر مرحله', assign: 'ارجاع', quote: 'پیش‌فاکتور', follow_up: 'پیگیری', reservation: 'اتصال رزرو'};
const time = (iso?: string | null) => {if (!iso) return '—'; const d = new Date(iso); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('fa-IR', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});};

function StageBadge({c}: {c: Row}) {
  const tone = c.stage === 'lost' ? 'bad' : ['paid', 'issued', 'travelled'].includes(c.stage) ? 'ok' : 'warn';
  return <span className={`pn-badge ${tone}`}>{c.stage_fa ?? label(STAGES, c.stage)}</span>;
}

function Presence() {
  const {state, reload, api} = useLoad<{present: boolean}>('/sales-desk/presence');
  const [err, setErr] = useState('');
  return <Async state={state}>{p => <span style={{display: 'inline-flex', gap: 8, alignItems: 'center'}}>
    <span className={`pn-badge ${p.present ? 'ok' : ''}`}>{p.present ? 'حاضر — درخواست‌ها به شما هم ارجاع می‌شود' : 'غایب'}</span>
    <button className="pn-btn ghost" onClick={async () => {setErr(''); try {await api.put('/sales-desk/presence', {present: !p.present}); reload();} catch (x) {setErr(errorOf(x).message);}}}>{p.present ? 'اعلام غیبت' : 'اعلام حضور'}</button>
    {err && <small className="pn-note error">{err}</small>}</span>}</Async>;
}

function Summary() {
  const {state} = useLoad<Row>('/sales-desk/summary');
  return <Async state={state}>{s => <Stats items={[
    {label: 'درخواست امروز', value: fa(s.requests_today)}, {label: 'بی‌پاسخ', value: fa(s.unanswered), hint: s.sla_breached ? `${fa(s.sla_breached)} مورد از مهلت گذشته` : undefined},
    {label: 'پیش‌فاکتور باز', value: fa(s.open_quotes)}, {label: 'پیگیری عقب‌افتاده', value: fa(s.overdue_follow_ups)},
    {label: 'فروش امروز', value: money(s.won_amount_today, 'IRR'), hint: `${fa(s.won_today)} پرونده`}, {label: 'کارشناس حاضر', value: fa(s.present_agents), hint: s.auto_assign ? 'ارجاع خودکار فعال' : 'ارجاع خودکار غیرفعال'}]}/>}</Async>;
}

function NewCase({done}: {done: () => void}) {
  const {api} = useLoad<unknown>(null);
  const blank = {customer_name: '', mobile: '', channel: 'phone', trip: '', travel_date: '', travellers: 1, organization_name: '', description: ''};
  const [v, setV] = useState<Row>(blank); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    try {
      const c = await api.post<Row>('/sales-desk/cases', {...v, travel_date: v.travel_date || null, organization_name: v.organization_name || null, description: v.description || null});
      setMsg({ok: true, text: `پرونده ${c.code} ثبت شد${c.agent_name ? ` و به ${c.agent_name} ارجاع شد` : ''}.`}); setV(blank); done();
    } catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  return <Card title="ثبت درخواست جدید"><form className="pn-form" onSubmit={submit}>
    <FormFields value={v} set={setV} fields={[{key: 'customer_name', label: 'نام مشتری', required: true}, {key: 'mobile', label: 'موبایل', required: true, hint: '09…'},
      {key: 'channel', label: 'کانال', type: 'select', options: CHANNELS}, {key: 'trip', label: 'سفر درخواستی', required: true, hint: 'مثلاً مشهد ۳ شب'},
      {key: 'travel_date', label: 'تاریخ سفر', type: 'date'}, {key: 'travellers', label: 'تعداد مسافر', type: 'number'}, {key: 'organization_name', label: 'سازمان'},
      {key: 'description', label: 'توضیحات', type: 'textarea', wide: true}]}/>
    <button className="pn-btn">ثبت و ارجاع</button></form><Note msg={msg}/></Card>;
}

function CaseDetail({id, close, changed}: {id: string; close: () => void; changed: () => void}) {
  const {state, reload, api} = useLoad<Row>(`/sales-desk/cases/${id}`);
  const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  const [note, setNote] = useState<Row>({kind: 'call', body: ''});
  const [quote, setQuote] = useState<Row>({amount: null, valid_hours: 24, note: ''});
  const [stage, setStage] = useState<Row>({stage: 'contacted', reason: ''});
  const [follow, setFollow] = useState(''); const [resId, setResId] = useState(''); const [tpl, setTpl] = useState('welcome'); const [text, setText] = useState('');
  async function act(path: string, body: unknown, ok: string) {
    setMsg(null);
    try {const r = await api.post<Row>(`/sales-desk/cases/${id}/${path}`, body); setMsg({ok: true, text: r?.message ? `${ok} — متن پیام: ${r.message}` : ok}); reload(); changed();}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  return <Card title="پرونده" action={<button className="pn-btn ghost" onClick={close}>بستن</button>}>
    <Async state={state}>{c => <>
      <Stats items={[{label: 'کد', value: c.code}, {label: 'مشتری', value: c.customer_name, hint: c.mobile}, {label: 'سفر', value: c.trip, hint: `${fa(c.travellers)} نفر${c.travel_date ? ` — ${dateFa(c.travel_date)}` : ''}`},
        {label: 'کانال', value: label(CHANNELS, c.channel)}, {label: 'کارشناس', value: c.agent_name ?? 'ارجاع‌نشده'}, {label: 'پیش‌فاکتور', value: c.quote_amount ? money(c.quote_amount, c.quote_currency) : '—', hint: c.quote_expires_at ? `اعتبار تا ${time(c.quote_expires_at)}` : undefined}]}/>
      <p><StageBadge c={c}/> {c.is_complaint && <span className="pn-badge bad">شکایت</span>} {c.sla_breached && <span className="pn-badge bad">از مهلت پاسخ گذشته</span>} {c.reservation_id && <span className="pn-badge ok">متصل به رزرو</span>}</p>
      <Note msg={msg}/>
      <form className="pn-form" onSubmit={e => {e.preventDefault(); act('activities', note, 'ثبت شد'); setNote({...note, body: ''});}}>
        <FormFields value={note} set={setNote} fields={[{key: 'kind', label: 'نوع', type: 'select', options: [['call', 'تماس'], ['message', 'پیام'], ['note', 'یادداشت']]}, {key: 'body', label: 'شرح', type: 'textarea', wide: true, required: true}]}/>
        <button className="pn-btn">ثبت فعالیت</button></form>
      <form className="pn-form" onSubmit={e => {e.preventDefault(); act('quote', {amount: quote.amount, valid_hours: quote.valid_hours || 24, note: quote.note || null}, 'پیش‌فاکتور ثبت شد');}}>
        <FormFields value={quote} set={setQuote} fields={[{key: 'amount', label: 'مبلغ (ریال)', type: 'money', required: true}, {key: 'valid_hours', label: 'اعتبار (ساعت)', type: 'number'}, {key: 'note', label: 'توضیح'}]}/>
        <button className="pn-btn">صدور پیش‌فاکتور</button></form>
      <form className="pn-form" onSubmit={e => {e.preventDefault(); act('stage', {stage: stage.stage, reason: stage.reason || null}, 'مرحله تغییر کرد');}}>
        <FormFields value={stage} set={setStage} fields={[{key: 'stage', label: 'مرحله‌ی بعد', type: 'select', options: STAGES}, {key: 'reason', label: 'دلیل (برای لغو لازم است)'}]}/>
        <button className="pn-btn">تغییر مرحله</button></form>
      <form className="pn-form" onSubmit={e => {e.preventDefault(); if (follow) act('follow-up', {at: new Date(follow).toISOString()}, 'پیگیری تنظیم شد');}}>
        <label htmlFor="f-follow">زمان پیگیری بعدی<input id="f-follow" type="datetime-local" dir="ltr" value={follow} onChange={e => setFollow(e.target.value)}/></label>
        <label htmlFor="f-res">شناسه رزرو<input id="f-res" dir="ltr" value={resId} onChange={e => setResId(e.target.value)}/></label>
        <button className="pn-btn">ثبت پیگیری</button>
        <button type="button" className="pn-btn ghost" disabled={!resId} onClick={() => act('reservation', {reservation_id: resId.trim()}, 'به رزرو وصل شد')}>اتصال رزرو</button></form>
      <form className="pn-form" onSubmit={async e => {e.preventDefault(); try {setText((await api.post<Row>(`/sales-desk/cases/${id}/render`, {template: tpl})).text);} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}}>
        <label htmlFor="f-tpl">قالب پیام<select id="f-tpl" value={tpl} onChange={e => setTpl(e.target.value)}>{TEMPLATES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <button className="pn-btn ghost">ساخت متن</button></form>
      {text && <p className="pn-note">{text}</p>}
      <h3>تاریخچه</h3>
      {(c.activities ?? []).length === 0 ? <Empty>فعالیتی ثبت نشده است.</Empty> :
        <ul className="pn-list">{c.activities.map((a: Row) => <li key={a.id}><b>{ACT[a.kind] ?? a.kind}</b> — {a.actor_name ?? 'سیستم'} — {time(a.at)}{a.body && <div>{a.body}</div>}
          {a.kind === 'stage' && a.detail?.to && <small> {label(STAGES, a.detail.from)} ← {label(STAGES, a.detail.to)}</small>}</li>)}</ul>}
    </>}</Async>
  </Card>;
}

function Cases() {
  const [filter, setFilter] = useState<Row>({stage: 'open', mine: false, overdue: false, q: ''});
  const qs = new URLSearchParams({...(filter.stage ? {stage: filter.stage} : {}), ...(filter.mine ? {mine: 'true'} : {}), ...(filter.overdue ? {overdue: 'true'} : {}), ...(filter.q ? {q: filter.q} : {})}).toString();
  const {state, reload} = useLoad<{items: Row[]}>(`/sales-desk/cases?${qs}`);
  const [open, setOpen] = useState<string | null>(null);
  return <>
    <NewCase done={reload}/>
    <Card title="پرونده‌ها">
      <div className="pn-form"><FormFields value={filter} set={setFilter} fields={[{key: 'stage', label: 'مرحله', type: 'select', options: [['open', 'همه‌ی باز'], ['', 'همه'], ...STAGES]},
        {key: 'mine', label: 'فقط پرونده‌های من', type: 'bool'}, {key: 'overdue', label: 'عقب‌افتاده', type: 'bool'}, {key: 'q', label: 'جستجو', hint: 'نام، موبایل، کد یا سفر'}]}/></div>
      <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="پرونده‌ای با این فیلتر نیست." cols={[
        {label: 'کد', cell: r => r.code}, {label: 'مشتری', cell: r => <>{r.customer_name}<br/><small dir="ltr">{r.mobile}</small></>}, {label: 'سفر', cell: r => r.trip},
        {label: 'کانال', cell: r => label(CHANNELS, r.channel)}, {label: 'مرحله', cell: r => <StageBadge c={r}/>}, {label: 'کارشناس', cell: r => r.agent_name ?? '—'},
        {label: 'هشدار', cell: r => r.sla_breached ? <span className="pn-badge bad">مهلت پاسخ</span> : r.follow_up_overdue ? <span className="pn-badge warn">پیگیری</span> : '—'},
        {label: 'ثبت', cell: r => time(r.created_at)}, {label: '', cell: r => <button className="pn-btn ghost" onClick={() => setOpen(r.id)}>باز کردن</button>}]}/>}</Async>
    </Card>
    {open && <CaseDetail id={open} close={() => setOpen(null)} changed={reload}/>}
  </>;
}

function Team() {
  const {state, reload, api} = useLoad<{items: Row[]}>('/sales-desk/team');
  const [target, setTarget] = useState<Row>({user_id: null, monthly_target: null}); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  return <Card title="تیم فروش">
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => String(r.user_id)} empty="هنوز کارشناسی حضور اعلام نکرده یا پرونده‌ای نگرفته است." cols={[
      {label: 'کارشناس', cell: r => r.name ?? r.user_id}, {label: 'حضور', cell: r => <span className={`pn-badge ${r.present ? 'ok' : ''}`}>{r.present ? 'حاضر' : 'غایب'}</span>},
      {label: 'درخواست امروز', cell: r => fa(r.requests_today)}, {label: 'میانه‌ی اولین پاسخ', cell: r => r.median_first_response_minutes === null ? '—' : `${fa(r.median_first_response_minutes)} دقیقه`},
      {label: 'پرونده‌ی باز', cell: r => fa(r.open_cases)}, {label: 'فروش ماه', cell: r => money(r.sales_month, 'IRR')},
      {label: 'هدف ماه', cell: r => r.monthly_target ? `${money(r.monthly_target, 'IRR')} (${fa(Math.round((r.sales_month / r.monthly_target) * 100))}٪)` : '—'}]}/>}</Async>
    <form className="pn-form" onSubmit={async e => {e.preventDefault(); setMsg(null); try {await api.put('/sales-desk/targets', target); setMsg({ok: true, text: 'هدف ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}}>
      <FormFields value={target} set={setTarget} fields={[{key: 'user_id', label: 'شناسه کارشناس', type: 'number', required: true}, {key: 'monthly_target', label: 'هدف فروش ماه (ریال)', type: 'money', required: true}]}/>
      <button className="pn-btn">ثبت هدف (مدیر)</button></form><Note msg={msg}/>
  </Card>;
}

function Settings() {
  const {state, reload, api} = useLoad<Row>('/sales-desk/settings');
  const [draft, setDraft] = useState<Row | null>(null); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  return <Async state={state}>{s => {
    const v = draft ?? {auto_assign: s.auto_assign, sla_alert_minutes: s.sla_alert_minutes, sla_reassign_minutes: s.sla_reassign_minutes, complaint_owner_user_id: s.complaint_owner_user_id, ...Object.fromEntries(Object.entries(s.templates).map(([k, t]) => [`t_${k}`, t]))};
    async function save(e: FormEvent) {
      e.preventDefault(); setMsg(null);
      const templates = Object.fromEntries(TEMPLATES.map(([k]) => [k, v[`t_${k}`] ?? '']));
      try {await api.put('/sales-desk/settings', {auto_assign: v.auto_assign, sla_alert_minutes: v.sla_alert_minutes, sla_reassign_minutes: v.sla_reassign_minutes, complaint_owner_user_id: v.complaint_owner_user_id || null, templates}); setDraft(null); setMsg({ok: true, text: 'تنظیمات ذخیره شد.'}); reload();}
      catch (x) {setMsg({ok: false, text: errorOf(x).message});}
    }
    return <Card title="قواعد ارجاع، مهلت پاسخ و قالب پیام‌ها">
      <form className="pn-form" onSubmit={save}><FormFields value={v} set={setDraft} fields={[{key: 'auto_assign', label: 'ارجاع خودکار نوبتی', type: 'bool'},
        {key: 'sla_alert_minutes', label: 'هشدار بی‌پاسخ (دقیقه)', type: 'number'}, {key: 'sla_reassign_minutes', label: 'انتقال خودکار (دقیقه)', type: 'number'},
        {key: 'complaint_owner_user_id', label: 'مسئول شکایت‌ها (شناسه کاربر)', type: 'number'},
        ...TEMPLATES.map(([k, l]) => ({key: `t_${k}`, label: `قالب «${l}»`, type: 'textarea' as const, wide: true}))]}/>
        <p className="pn-muted">جای‌نگه‌دارها: {s.placeholders.map((p: string) => `{${p}}`).join('، ')}</p>
        <button className="pn-btn">ذخیره (مدیر)</button>
        <button type="button" className="pn-btn ghost" onClick={async () => {setMsg(null); try {const r = await api.post<Row>('/sales-desk/sla/sweep', {}); setMsg({ok: true, text: `${fa(r.checked)} پرونده بررسی و ${fa(r.reassigned)} پرونده منتقل شد.`});} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}}>اجرای انتقال پرونده‌های بی‌پاسخ</button>
      </form><Note msg={msg}/></Card>;
  }}</Async>;
}

export function SalesDesk() {
  return <>
    <Card title="وضعیت من" action={<Presence/>}><Summary/></Card>
    <Tabs tabs={[['پرونده‌ها', <Cases key="c"/>], ['ورود اکسل', <LeadImport key="i"/>], ['تیم و هدف‌ها', <Team key="t"/>], ['تنظیمات', <Settings key="s"/>]]}/>
  </>;
}
