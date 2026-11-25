'use client';
/* Organization panel. The organization comes from the signed-in user's own memberships (/enterprise/context);
   every list below is scoped by the API to that organization and to the permissions the user holds in it. */
import Link from 'next/link';
import {useEffect, useState, type FormEvent, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {Async, Badge, Card, Empty, Failed, Loading, Stats, Table, Unavailable, dateFa, errorOf, fa, money, serviceFa, useLoad} from './PanelKit';
import './stitch-org-2026-11.css';

type Org = {id: string; name: string; permissions: string[]};
type Context = {organizations: Org[]; use_cases: string[]; services: string[]};
type Member = {id: number; name: string; email?: string; role: string; permissions?: string[]};
type Summary = {organization: {id: string; name: string}; members: number; departments: number; cost_centers: number; requests: {total: number; by_status: Record<string, number>; by_use_case: Record<string, number>; by_policy_result: Record<string, number>}; linked_bookings: number; credit_accounts: number};
type Request = {id: string; title: string; use_case: string; status: string; policy_result: string; requester_id: number; policy_reasons?: string[]; requirements: {origin?: string; destination?: string; starts_at?: string; ends_at?: string; headcount?: number; budget_amount?: number; services?: string[]}};
type Credit = {id: string; organization_id?: string | null; currency: string; limit_amount: number; available: number; reserved: number; consumed: number};
const ROLE_FA: Record<string, string> = {employee: 'کارمند', manager: 'مدیر', welfare_manager: 'مدیر رفاهی', organization_admin: 'مدیر سازمان', tenant_admin: 'مدیر مجموعه', platform_admin: 'مدیر سکو', finance_operator: 'کارشناس مالی', customer: 'مشتری'};
const USE_FA: Record<string, string> = {business_travel: 'سفر کاری', workforce_accommodation: 'اقامت نیروهای پروژه', organizational_guests: 'مهمان سازمان', employee_welfare: 'رفاه کارکنان', organizational_event: 'رویداد سازمانی', travel_credit: 'اعتبار سفر', business_trip: 'مأموریت کاری', team_retreat: 'سفر تیمی', conference: 'همایش', incentive: 'سفر تشویقی', welfare: 'سفر رفاهی', training: 'دورهٔ آموزشی', relocation: 'جابه‌جایی', client_visit: 'دیدار با مشتری', family_welfare: 'رفاهی خانواده'};
const POLICY_FA: Record<string, string> = {IN_POLICY: 'مطابق سیاست', OUT_OF_POLICY: 'خارج از سیاست', APPROVAL_REQUIRED: 'نیازمند تأیید', BLOCKED: 'ممنوع'};
const RULE_FA: Record<string, string> = {maximum_days: 'حداکثر مدت سفر (روز)', minimum_advance_days: 'حداقل فاصله تا سفر (روز)', allowed_services: 'خدمات مجاز', approval_required: 'نیاز به تأیید', approver_ids: 'تأییدکنندگان', maximum_budget: 'سقف بودجهٔ هر درخواست', allowed_destinations: 'مقصدهای مجاز', blocked_destinations: 'مقصدهای ممنوع', minimum_notice_days: 'حداقل فاصله تا سفر (روز)', maximum_trip_days: 'حداکثر مدت سفر (روز)'};
const TENANT_ADMINS = ['tenant_admin', 'platform_admin'];
const KEY = 'karenseir-panel-organization';

/** Resolves the organization this user works in; tenant administrators can also create one and pick any. */
export function OrgScope({children, need}: {children: (org: Org, ctx: Context) => ReactNode; need?: string[]}) {
  const {session} = useAuth(); const role = (session as {user?: {role?: string}} | null)?.user?.role ?? ''; const admin = TENANT_ADMINS.includes(role);
  const ctx = useLoad<Context>('/enterprise/context'); const all = useLoad<{id: string; name: string; members: number}[]>(admin ? '/enterprise/organizations' : null);
  const [picked, setPicked] = useState(''); const [name, setName] = useState(''); const [note, setNote] = useState('');
  // eslint-disable-next-line react-hooks/set-state-in-effect -- reads window.location/sessionStorage, which exist only after hydration (reading them during render would mismatch the server HTML)
  useEffect(() => {try {setPicked(sessionStorage.getItem(KEY) ?? '');} catch {/* storage unavailable */}}, []);
  if (ctx.state.kind === 'loading') return <Loading/>; if (ctx.state.kind === 'error') return <Failed status={ctx.state.status} message={ctx.state.message}/>;
  const mine = ctx.state.data.organizations; const extra: Org[] = admin && all.state.kind === 'ready' ? all.state.data.filter(o => !mine.some(x => x.id === o.id)).map(o => ({id: o.id, name: o.name, permissions: ['roles.manage']})) : [];
  const orgs = [...mine, ...extra];
  // Without a stored choice, open the first organization where this person holds what the page needs (a member of A and manager of B lands on B).
  const org = orgs.find(o => o.id === picked) ?? (need ? orgs.find(o => o.permissions.some(p => need.includes(p))) : undefined) ?? orgs[0];
  async function create(e: FormEvent) {e.preventDefault(); setNote(''); try {const row = await ctx.api.post<{id: string}>('/enterprise/organizations', {name}); setName(''); try {sessionStorage.setItem(KEY, row.id);} catch {/* ignore */} setPicked(row.id); all.reload(); ctx.reload();} catch (err) {setNote(errorOf(err).message);}}
  const creator = admin && <Card title="ایجاد سازمان"><form className="pn-form" onSubmit={create}><label>نام سازمان<input value={name} onChange={e => setName(e.target.value)} minLength={2} maxLength={160} required/></label><button className="pn-btn">ایجاد</button></form>{note && <div className="pn-note error" role="alert">{note}</div>}</Card>;
  if (!org) return <><Empty>{admin ? 'هنوز سازمانی در این مجموعه ثبت نشده است.' : 'حساب شما عضو هیچ سازمانی نیست. عضویت را مدیر سازمان یا مدیر مجموعه ثبت می‌کند.'}</Empty>{creator}</>;
  return <>{orgs.length > 1 && <div className="pn-form"><label>سازمان<select value={org.id} onChange={e => {setPicked(e.target.value); try {sessionStorage.setItem(KEY, e.target.value);} catch {/* ignore */}}}>{orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label></div>}
    {children(org, ctx.state.data)}{creator}</>;
}
const can = (org: Org, p: string) => org.permissions.includes(p);

export function OrgOverview() {return <OrgScope need={RECORDS}>{org => <OverviewBody org={org}/>}</OrgScope>;}
const RECORDS = ['requests.read_all', 'policy.manage', 'roles.manage'];
const PEOPLE = ['roles.manage', 'policy.manage', 'requests.on_behalf', 'benefits.manage'];
const pct = (part: number, whole: number) => whole > 0 ? Math.min(100, Math.max(0, Math.round(part / whole * 1000) / 10)) : 0;
const initials = (name: string) => name.trim().split(/\s+/).slice(0, 2).map(w => w[0] ?? '').join('‌') || '؟';
const SERVICE_GLYPH: Record<string, string> = {flight: '✈', hotel: '🏨', train: '🚆', bus: '🚌', tour: '🧭', vacation_rental: '🏡', car_rental: '🚗', transfer: '🚐'};
const glyphOf = (services?: string[] | null) => SERVICE_GLYPH[services?.[0] ?? ''] ?? '🧳';
/** Credit accounts summed per currency; the first currency (by account order) is the one shown in the KPI cards. */
function creditTotals(rows: Credit[]) {
  if (!rows.length) return null; const currency = rows[0].currency; const same = rows.filter(r => r.currency === currency);
  const sum = (k: 'limit_amount' | 'available' | 'reserved' | 'consumed') => same.reduce((s, r) => s + (r[k] ?? 0), 0);
  return {currency, accounts: same.length, other: rows.length - same.length, limit: sum('limit_amount'), available: sum('available'), reserved: sum('reserved'), consumed: sum('consumed')};
}
/** Who asked: «شما» for the signed-in user, the member name when the member list is readable, else nothing invented. */
function useRequesterNames(org: Org) {
  const members = useLoad<Member[]>(org.permissions.some(p => PEOPLE.includes(p)) ? `/enterprise/organizations/${org.id}/members` : null); const profile = useLoad<{user_id: number}>('/me/profile');
  const me = profile.state.kind === 'ready' ? profile.state.data.user_id : undefined;
  const names: Record<number, string> = members.state.kind === 'ready' ? Object.fromEntries(members.state.data.map(m => [m.id, m.name])) : {};
  return (id: number): string | null => id === me ? 'شما' : names[id] ?? null;
}
function Kpi({label, icon, tone = '', value, valueTone = '', foot, footTone = '', bar, barTone = ''}: {label: string; icon: string; tone?: string; value: ReactNode; valueTone?: string; foot?: ReactNode; footTone?: string; bar?: number; barTone?: string}) {
  return <div className="so-kpi"><div className="so-kpi-top"><small>{label}</small><span className={`so-kpi-ic ${tone}`} aria-hidden="true">{icon}</span></div>
    <strong className={valueTone}>{value}</strong>{bar !== undefined && <div className={`so-bar ${barTone}`} role="img" aria-label={`${fa(bar)} درصد`}><span style={{width: `${bar}%`}}/></div>}{foot && <div className={`so-kpi-foot ${footTone}`}>{foot}</div>}</div>;
}
const amountOf = (n: number, currency: string) => <>{fa(n)}<small>{currency === 'IRR' ? 'ریال' : currency}</small></>;

/* ---- Management dashboard (Stitch b2b_1 / b2b_2) */
function OverviewBody({org}: {org: Org}) {
  const sum = useLoad<Summary>(`/enterprise/organizations/${org.id}/summary`); const reqs = useLoad<Request[]>(`/enterprise/requests?org=${org.id}`);
  const records = org.permissions.some(p => RECORDS.includes(p));
  const credit = useLoad<Credit[]>(records ? `/enterprise/organizations/${org.id}/credit` : null);
  const policy = useLoad<{version: number | null; rules: Record<string, unknown> | null}>(`/enterprise/organizations/${org.id}/policy`);
  const who = useRequesterNames(org); const [tab, setTab] = useState('all');
  const c = credit.state.kind === 'ready' ? creditTotals(credit.state.data) : null; const s = sum.state.kind === 'ready' ? sum.state.data : null;
  const rows = reqs.state.kind === 'ready' ? reqs.state.data : [];
  const pending = rows.filter(r => r.status === 'approval_required');
  const TABS: [string, string, (r: Request) => boolean][] = [['all', 'همه', () => true], ['approval_required', 'در انتظار تأیید', r => r.status === 'approval_required'], ['approved', 'تأییدشده', r => ['approved', 'booked', 'completed', 'quote_selected'].includes(r.status)], ['rejected', 'ردشده یا لغو', r => ['rejected', 'withdrawn', 'not_allowed'].includes(r.status)]];
  const shown = rows.filter(TABS.find(t => t[0] === tab)?.[2] ?? (() => true)).slice(0, 8);
  const rules = policy.state.kind === 'ready' && policy.state.data.rules ? Object.entries(policy.state.data.rules).filter(([, v]) => !(v === null || v === undefined || (Array.isArray(v) && v.length === 0))) : [];
  return <div className="so" data-stitch="b2b_1 b2b_2">
    <section className="so-hero" aria-label="سازمان"><div className="so-hero-id"><span className="so-hero-ic" aria-hidden="true">🏢</span><div>
      <h2>{org.name}</h2>
      <div className="so-hero-meta">{org.permissions.includes('roles.manage') ? <span className="so-chip gold">مدیر سازمان</span> : org.permissions.length ? <span className="so-chip gold">{fa(org.permissions.length)} مجوز مدیریتی</span> : <span className="so-chip soft">عضو سازمان</span>}
        {s && <><span className="so-chip soft">{fa(s.members)} کارمند</span>{s.departments > 0 && <span className="so-chip soft">{fa(s.departments)} واحد</span>}{s.cost_centers > 0 && <span className="so-chip soft">{fa(s.cost_centers)} مرکز هزینه</span>}</>}
        {policy.state.kind === 'ready' && (policy.state.data.version ? <span className="so-chip ok">سیاست سفر نسخهٔ {fa(policy.state.data.version)}</span> : <span className="so-chip bad">سیاست سفر ثبت نشده</span>)}</div></div></div>
      <div className="so-hero-act"><Link className="so-btn" href="/organization/requests">＋ درخواست مأموریت جدید</Link></div></section>

    {sum.state.kind === 'error' && sum.state.status === 403 ? <Empty>آمار کل سازمان فقط برای مدیران سازمان نمایش داده می‌شود؛ درخواست‌های خودتان در پایین آمده است.</Empty> : sum.state.kind === 'error' ? <Failed status={sum.state.status} message={sum.state.message}/> : !s ? <Loading/> :
      <div className="so-kpis">
        {c ? <Kpi label="اعتبار کل مصوب" icon="🏛" value={amountOf(c.limit, c.currency)} foot={`${fa(c.accounts)} حساب اعتباری${c.other ? ` · ${fa(c.other)} حساب با ارز دیگر` : ''}`} bar={100} barTone="gold"/>
          : <Kpi label="اعتبار کل مصوب" icon="🏛" value="—" foot={credit.state.kind === 'loading' && records ? 'در حال دریافت…' : 'حساب اعتباری برای سازمان تعریف نشده است.'}/>}
        {c ? <Kpi label="اعتبار مصرف‌شده" icon="💳" tone="red" value={amountOf(c.consumed, c.currency)} valueTone="red" bar={pct(c.consumed, c.limit)} foot={`${fa(pct(c.consumed, c.limit))}٪ از سقف · مانده ${money(c.available, c.currency)}`}/>
          : <Kpi label="درخواست‌های سفر" icon="🧾" tone="red" value={fa(s.requests.total)} foot="مجموع درخواست‌های ثبت‌شده"/>}
        <Kpi label="درخواست‌های در انتظار تأیید" icon="⏳" tone="plum" value={<>{fa(s.requests.by_status.approval_required ?? 0)}<small>درخواست</small></>} valueTone="red" foot={(s.requests.by_status.approval_required ?? 0) > 0 ? 'نیازمند اقدام تأییدکننده' : 'درخواستی در انتظار نیست'} footTone={(s.requests.by_status.approval_required ?? 0) > 0 ? 'alert' : ''}/>
        <Kpi label="رزروهای متصل" icon="🧳" tone="cream" value={<>{fa(s.linked_bookings)}<small>رزرو</small></>} foot="رزروهای متصل به درخواست‌های تأییدشده"/>
      </div>}

    <div className="so-grid">
      <section className="so-card" aria-labelledby="so-kanban"><div className="so-card-head"><h2 id="so-kanban">کارتابل تأیید درخواست‌های سفر</h2>{pending.length > 0 && <span className="so-chip bad">{fa(pending.length)} مورد فعال</span>}</div>
        <Async state={reqs.state}>{() => pending.length === 0 ? <div className="so-empty">درخواستی در انتظار تأیید نیست.</div> : <>{pending.slice(0, 4).map(r => {const name = who(r.requester_id); const q = r.requirements;
          return <article className="so-req" key={r.id}><div className="so-req-head"><div className="so-req-who"><span className="so-av" aria-hidden="true">{name ? initials(name) : '؟'}</span><div><b>{r.title}</b><span>{name ? `متقاضی: ${name} · ` : ''}{USE_FA[r.use_case] ?? r.use_case}</span></div></div>
            <span className={`so-chip ${r.policy_result === 'IN_POLICY' ? 'ok' : r.policy_result === 'BLOCKED' || r.policy_result === 'NOT_ALLOWED' ? 'bad' : 'gold'}`}>{POLICY_FA[r.policy_result] ?? r.policy_result}</span></div>
            <div className="so-req-trip"><span className="so-glyph" aria-hidden="true">{glyphOf(q.services)}</span><div><b>{[q.origin, q.destination].filter(Boolean).join(' ← ') || 'مقصد ثبت نشده'}</b><span>{[q.starts_at && dateFa(q.starts_at), q.headcount && `${fa(q.headcount)} نفر`, (q.services ?? []).map(serviceFa).join('، ')].filter(Boolean).join(' · ')}</span></div>
              {typeof q.budget_amount === 'number' && <div className="so-req-amt"><small>بودجهٔ پیشنهادی</small><strong>{money(q.budget_amount, 'IRR')}</strong></div>}</div>
            {(r.policy_reasons ?? []).length > 0 && <ul className="so-req-reasons">{(r.policy_reasons ?? []).slice(0, 3).map(x => <li key={x}>⚠ {x}</li>)}</ul>}
            <div className="so-req-act"><Link className="so-btn sm" href={`/organization/requests?request=${encodeURIComponent(r.id)}`}>بررسی و تصمیم</Link></div></article>;})}
          {pending.length > 4 && <Link className="pn-link" href="/organization/requests">مشاهدهٔ همهٔ {fa(pending.length)} درخواست در انتظار</Link>}</>}</Async></section>

      <div className="so-col">
        {s && Object.keys(s.requests.by_use_case).length > 0 && <section className="so-card" aria-labelledby="so-mix"><div className="so-card-head"><h2 id="so-mix">ترکیب درخواست‌ها بر اساس نوع سفر</h2></div>
          <ul className="so-split">{Object.entries(s.requests.by_use_case).sort((a, b) => b[1] - a[1]).map(([k, v], i) => <li key={k}><div className="so-split-row"><span>{USE_FA[k] ?? k} ({fa(pct(v, s.requests.total))}٪)</span><span>{fa(v)} درخواست</span></div><div className={`so-bar ${['', 'plum', 'gold'][i % 3]}`}><span style={{width: `${pct(v, s.requests.total)}%`}}/></div></li>)}</ul>
          <div className="so-total"><small>مجموع درخواست‌های سازمان</small><strong>{fa(s.requests.total)}</strong></div></section>}
        <section className="so-card" aria-labelledby="so-rules"><div className="so-card-head"><h2 id="so-rules">سیاست فعال سفر سازمان</h2>{rules.length > 0 && <span className="so-chip soft">{fa(rules.length)} قاعدهٔ فعال</span>}</div>
          <Async state={policy.state}>{p => p.rules === null || rules.length === 0 ? <div className="so-empty">برای این سازمان هنوز سیاست سفری ثبت نشده است.</div>
            : <ul className="so-rules">{rules.slice(0, 5).map(([k, v]) => <li key={k}><div><b>{RULE_FA[k] ?? k}</b><span>{ruleValue(k, v)}</span></div></li>)}</ul>}</Async>
          <div className="so-hero-act"><Link className="so-btn ghost sm" href="/organization/policy">جزئیات سیاست سفر</Link>{records && <Link className="so-btn ghost sm" href="/organization/billing">صورتحساب و فاکتورها</Link>}</div></section>
      </div>
    </div>

    <section className="so-card" aria-labelledby="so-recent"><div className="so-card-head"><h2 id="so-recent">درخواست‌ها و سفرهای اخیر کارکنان</h2>
      <div className="so-tabs" role="group" aria-label="فیلتر وضعیت">{TABS.map(([k, label]) => <button type="button" key={k} aria-pressed={tab === k} onClick={() => setTab(k)}>{label}</button>)}</div></div>
      <Async state={reqs.state}>{() => shown.length === 0 ? <div className="so-empty">درخواست سفری در این دسته ثبت نشده است.</div> :
        <div className="so-table-wrap"><table className="so-table"><thead><tr><th scope="col">متقاضی</th><th scope="col">عنوان و نوع سفر</th><th scope="col">مسیر</th><th scope="col">تاریخ اعزام</th><th scope="col">بودجهٔ پیشنهادی</th><th scope="col">وضعیت</th></tr></thead>
          <tbody>{shown.map(r => {const name = who(r.requester_id); const q = r.requirements; return <tr key={r.id}>
            <td data-label="متقاضی">{name ?? <span className="pn-muted">—</span>}</td><td data-label="عنوان و نوع سفر">{r.title}<small>{USE_FA[r.use_case] ?? r.use_case}{q.headcount ? ` · ${fa(q.headcount)} نفر` : ''}</small></td>
            <td data-label="مسیر">{[q.origin, q.destination].filter(Boolean).join(' ← ') || '—'}</td><td data-label="تاریخ اعزام">{dateFa(q.starts_at)}</td>
            <td data-label="بودجهٔ پیشنهادی" className="so-amt">{typeof q.budget_amount === 'number' ? money(q.budget_amount, 'IRR') : '—'}</td><td data-label="وضعیت"><ReqBadge status={r.status}/></td></tr>;})}</tbody></table></div>}</Async>
      {rows.length > shown.length && <p className="pn-muted">نمایش {fa(shown.length)} درخواست از {fa(rows.length)} درخواست قابل مشاهده برای شما. <Link className="pn-link" href="/organization/requests">همهٔ درخواست‌ها</Link></p>}
    </section>
  </div>;
}
const REQ_EXTRA: Record<string, [string, string]> = {policy_required: ['نیازمند سیاست سازمان', 'warn'], not_allowed: ['خارج از خدمات مجاز', 'bad'], quote_selected: ['پیشنهاد انتخاب‌شده', 'ok'], draft: ['پیش‌نویس', 'warn']};
function ReqBadge({status}: {status: string}) {const x = REQ_EXTRA[status.toLowerCase()]; return x ? <span className={`pn-badge ${x[1]}`}>{x[0]}</span> : <Badge status={status}/>;}
function ruleValue(key: string, v: unknown): string {
  return typeof v === 'boolean' ? (v ? 'بله' : 'خیر') : key === 'maximum_budget' && typeof v === 'number' ? money(v, 'IRR') : key === 'approver_ids' && Array.isArray(v) ? `${fa(v.length)} تأییدکننده` : key === 'allowed_services' && Array.isArray(v) ? v.map(x => serviceFa(String(x))).join('، ') : Array.isArray(v) ? v.join('، ') : typeof v === 'number' ? fa(v) : String(v);
}

export function OrgMembers() {return <OrgScope need={PEOPLE}>{org => <MembersBody org={org}/>}</OrgScope>;}
export function MembersBody({org}: {org: Org}) {
  const members = useLoad<Member[]>(`/enterprise/organizations/${org.id}/members`); const profile = useLoad<{user_id: number}>('/me/profile'); const me = profile.state.kind === 'ready' ? profile.state.data.user_id : undefined;
  const [email, setEmail] = useState(''); const [note, setNote] = useState<{ok: boolean; text: string} | null>(null); const manage = can(org, 'roles.manage');
  async function run(action: () => Promise<unknown>, done: string) {setNote(null); try {await action(); members.reload(); setNote({ok: true, text: done});} catch (e) {setNote({ok: false, text: errorOf(e).message});}}
  return <>
    {note && <div className={`pn-note ${note.ok ? 'ok' : 'error'}`} role={note.ok ? 'status' : 'alert'}>{note.text}</div>}
    {manage && <Card title="افزودن عضو"><form className="pn-form" onSubmit={e => {e.preventDefault(); void run(() => members.api.post(`/enterprise/organizations/${org.id}/members`, {email}), 'عضو اضافه شد.').then(() => setEmail(''));}}>
      <label>ایمیل کاربر ثبت‌شده<input type="email" dir="ltr" value={email} onChange={e => setEmail(e.target.value)} required/></label><button className="pn-btn">افزودن</button></form>
      <p className="pn-muted">فقط کاربری که قبلاً در همین مجموعه حساب دارد اضافه می‌شود؛ ساخت حساب جدید از مسیر ثبت‌نام انجام می‌شود.</p></Card>}
    <Card title={`کارکنان ${org.name}`}>{members.state.kind === 'error' && members.state.status === 403 ? <Empty>فهرست کارکنان فقط برای مدیران سازمان نمایش داده می‌شود.</Empty> : <Async state={members.state}>{rows => <Table rows={rows} rowKey={m => String(m.id)} empty="عضوی ثبت نشده است."
      cols={[{label: 'نام', cell: m => m.name}, {label: 'ایمیل', cell: m => <span className="pn-ltr">{m.email ?? '—'}</span>}, {label: 'نقش', cell: m => ROLE_FA[m.role] ?? m.role}, {label: 'دسترسی‌ها', cell: m => manage ? <GrantEditor org={org} member={m} onSaved={(text, ok) => {setNote({ok, text}); if (ok) members.reload();}}/> : (m.permissions ?? []).length ? fa((m.permissions ?? []).length) : '—'},
        {label: '', cell: m => manage && m.id !== me ? <button type="button" className="pn-btn ghost" onClick={() => void run(() => members.api.post(`/enterprise/organizations/${org.id}/members/${m.id}/remove`, {}), 'عضویت حذف شد.')}>حذف عضویت</button> : null}]}/>}</Async>}</Card>
    <Unavailable title="مسافران همراه کارکنان">فهرست مسافران هر کارمند در حساب خود او نگهداری می‌شود و در اختیار سازمان قرار نمی‌گیرد.</Unavailable>
  </>;
}

export function OrgPolicy() {return <OrgScope>{org => <PolicyBody org={org}/>}</OrgScope>;}
function PolicyBody({org}: {org: Org}) {
  const policy = useLoad<{version: number | null; rules: Record<string, unknown> | null}>(`/enterprise/organizations/${org.id}/policy`); const members = useLoad<Member[]>(can(org, 'policy.manage') || can(org, 'roles.manage') ? `/enterprise/organizations/${org.id}/members` : null);
  const names = members.state.kind === 'ready' ? Object.fromEntries(members.state.data.map(m => [m.id, m.name])) : {};
  const show = (key: string, v: unknown): string => v === null || v === undefined || (Array.isArray(v) && v.length === 0) ? 'تعیین نشده' : typeof v === 'boolean' ? (v ? 'بله' : 'خیر') : key === 'maximum_budget' && typeof v === 'number' ? money(v, 'IRR') : key === 'approver_ids' && Array.isArray(v) ? v.map(id => names[id as number] ?? `کاربر ${id}`).join('، ')
    : key === 'allowed_services' && Array.isArray(v) ? v.map(s => serviceFa(String(s))).join('، ') : Array.isArray(v) ? v.join('، ') : typeof v === 'number' ? fa(v) : String(v);
  return <Card title="سیاست سفر جاری" action={can(org, 'policy.manage') ? <Link className="pn-btn ghost" href="/organization/requests">ویرایش سیاست</Link> : undefined}>
    <Async state={policy.state}>{p => p.rules === null ? <Empty>برای این سازمان هنوز سیاست سفری ثبت نشده است؛ تا آن زمان درخواست‌ها بدون قاعدهٔ سازمانی بررسی می‌شوند.</Empty>
      : <><p className="pn-muted">نسخهٔ {fa(p.version ?? 0)} — هر تغییر یک نسخهٔ جدید می‌سازد و درخواست‌های قبلی با نسخهٔ زمان ثبت خود سنجیده می‌شوند.</p><dl className="pn-dl">{Object.entries(p.rules).map(([k, v]) => <div key={k} style={{display: 'contents'}}><dt>{RULE_FA[k] ?? k}</dt><dd>{show(k, v)}</dd></div>)}</dl></>}</Async></Card>;
}

export function OrgCredit() {return <OrgScope need={RECORDS}>{org => <CreditBody org={org}/>}</OrgScope>;}
/* ---- Organizational credit & finance (Stitch _23, upper half) */
function CreditBody({org}: {org: Org}) {
  const credit = useLoad<Credit[]>(`/enterprise/organizations/${org.id}/credit`); const st = useLoad<Statement>(`/enterprise/organizations/${org.id}/statement`); const plans = useLoad<{id: string; title: string; status: string}[]>('/me/installment-plans');
  if (credit.state.kind === 'error' && credit.state.status === 403) return <Empty>اعتبار سازمان فقط برای مدیران سازمان نمایش داده می‌شود؛ اعتبار تخصیص‌یافته به خودتان در «حساب من ← کیف پول و اعتبار» است.</Empty>;
  const c = credit.state.kind === 'ready' ? creditTotals(credit.state.data) : null;
  const s = st.state.kind === 'ready' ? st.state.data : null; const currency = c?.currency ?? s?.items[0]?.currency ?? 'IRR';
  const byService = s ? Object.entries(s.items.filter(i => i.currency === currency).reduce<Record<string, number>>((acc, i) => ({...acc, [i.service_type]: (acc[i.service_type] ?? 0) + i.total_amount}), {})).sort((a, b) => b[1] - a[1]) : [];
  const spent = byService.reduce((t, [, v]) => t + v, 0);
  return <div className="so" data-stitch="_23">
    <section className="so-hero" aria-label="اعتبار و امور مالی"><div className="so-hero-id"><span className="so-hero-ic" aria-hidden="true">💼</span><div><h2>اعتبار و امور مالی سازمانی</h2><p>{org.name} — اعتبار سازمانی از دفتر حساب اعتباری و فاکتورها از رزروهای متصل به درخواست‌های سازمان.</p></div></div>
      <div className="so-hero-act"><Link className="so-btn" href="/organization/billing">صورتحساب و فاکتورها</Link></div></section>
    <Async state={credit.state}>{rows => !c ? <div className="so-empty">برای این سازمان حساب اعتباری تعریف نشده است. حساب اعتباری پس از قرارداد و توسط بخش مالی ایجاد می‌شود.</div> : <>
      <div className="so-kpis">
        <Kpi label="سقف اعتبار مصوب" icon="✅" value={amountOf(c.limit, c.currency)} foot={`${fa(c.accounts)} حساب اعتباری`}/>
        <Kpi label="ماندهٔ در دسترس" icon="🏛" tone="cream" value={amountOf(c.available, c.currency)} foot={`${fa(pct(c.available, c.limit))}٪ از سقف آزاد است`} bar={pct(c.available, c.limit)} barTone="gold"/>
        <Kpi label="مصرف‌شده (بدهی جاری)" icon="🧾" tone="red" value={amountOf(c.consumed, c.currency)} valueTone="red" bar={pct(c.consumed, c.limit)} foot={`${fa(pct(c.consumed, c.limit))}٪ از سقف`}/>
        <Kpi label="رزروشده (در جریان)" icon="⏳" tone="plum" value={amountOf(c.reserved, c.currency)} bar={pct(c.reserved, c.limit)} barTone="plum" foot="مبلغ نگه‌داشته برای رزروهای در جریان"/>
      </div>
      {rows.length > 1 && <section className="so-card" aria-labelledby="so-accounts"><div className="so-card-head"><h2 id="so-accounts">حساب‌های اعتباری</h2></div>
        <div className="so-table-wrap"><table className="so-table"><thead><tr><th scope="col">حساب</th><th scope="col">سقف</th><th scope="col">در دسترس</th><th scope="col">رزروشده</th><th scope="col">مصرف‌شده</th></tr></thead>
          <tbody>{rows.map(r => <tr key={r.id}><td data-label="حساب"><span className="so-ltr">{r.id.slice(0, 8)}</span></td><td data-label="سقف" className="so-amt">{money(r.limit_amount, r.currency)}</td><td data-label="در دسترس" className="so-amt">{money(r.available, r.currency)}</td><td data-label="رزروشده" className="so-amt">{money(r.reserved, r.currency)}</td><td data-label="مصرف‌شده" className="so-amt">{money(r.consumed, r.currency)}</td></tr>)}</tbody></table></div></section>}
    </>}</Async>
    <div className={byService.length > 0 ? 'so-grid' : 'so-col'}>
      <section className="so-card" aria-labelledby="so-status"><div className="so-card-head"><h2 id="so-status">وضعیت فاکتورهای سازمان</h2>{s && <span className="so-chip soft">{fa(s.linked_bookings)} رزرو متصل</span>}</div>
        <Async state={st.state}>{d => d.totals.length === 0 ? <div className="so-empty">هنوز فاکتوری برای رزروهای متصل به این سازمان صادر نشده است.</div> :
          <div className="so-table-wrap"><table className="so-table"><thead><tr><th scope="col">وضعیت فاکتور</th><th scope="col">ارز</th><th scope="col">جمع فاکتورها</th></tr></thead>
            <tbody>{d.totals.map(t => <tr key={`${t.currency}-${t.status}`}><td data-label="وضعیت فاکتور"><Badge status={t.status}/></td><td data-label="ارز">{t.currency === 'IRR' ? 'ریال' : t.currency}</td><td data-label="جمع فاکتورها" className="so-amt">{money(t.amount, t.currency)}</td></tr>)}</tbody></table></div>}</Async></section>
      {byService.length > 0 && <section className="so-card" aria-labelledby="so-services"><div className="so-card-head"><h2 id="so-services">تفکیک مخارج به تفکیک خدمات</h2></div><p className="so-card-sub">سهم هر خدمت از جمع فاکتورهای صادرشده برای رزروهای متصل.</p>
        <ul className="so-split">{byService.map(([k, v], i) => <li key={k}><div className="so-split-row"><span>{serviceFa(k)} ({fa(pct(v, spent))}٪)</span><span>{money(v, currency)}</span></div><div className={`so-bar ${['', 'plum', 'gold'][i % 3]}`}><span style={{width: `${pct(v, spent)}%`}}/></div></li>)}</ul>
        <div className="so-total"><small>جمع فاکتورها</small><strong>{money(spent, currency)}</strong></div></section>}
    </div>
    <section className="so-card" aria-labelledby="so-plans"><div className="so-card-head"><h2 id="so-plans">طرح‌های اقساط</h2></div><Async state={plans.state}>{rows => rows.length === 0 ? <div className="so-empty">طرح قسطی فعالی وجود ندارد.</div> :
      <ul className="so-list">{rows.map(p => <li key={p.id}><b>{p.title}</b><Badge status={p.status}/></li>)}</ul>}</Async></section>
    <Unavailable title="کسر از حقوق">سامانه مدل داده‌ای برای کسر از حقوق و اتصال به حقوق‌ودستمزد ندارد؛ این قابلیت تا تعریف قرارداد و مدل واقعی غیرفعال است.</Unavailable>
  </div>;
}


export function OrgBookings() {return <OrgScope need={RECORDS}>{org => <BookingsBody org={org}/>}</OrgScope>;}
type Linked = {reservation_id?: string; id?: string; booking_reference?: string | null; service_type?: string; status?: string; total_amount?: number | null; currency?: string | null};
function BookingsBody({org}: {org: Org}) {
  const reqs = useLoad<Request[]>(`/enterprise/requests?org=${org.id}`); const [rows, setRows] = useState<{request: Request; items: Linked[]}[] | null>(null); const [error, setError] = useState('');
  const ready = reqs.state.kind === 'ready' ? reqs.state.data : null; const api = reqs.api;
  useEffect(() => {
    if (!ready) return; let active = true; const eligible = ready.filter(r => ['approved', 'booked', 'completed'].includes(r.status)).slice(0, 40);
    Promise.all(eligible.map(r => api.get<{items: Linked[]}>(`/enterprise/requests/${r.id}/bookings`).then(b => ({request: r, items: b.items})))).then(all => {if (active) setRows(all);}).catch(e => {if (active) setError(errorOf(e).message);});
    return () => {active = false;};
  }, [ready, api]);
  if (reqs.state.kind !== 'ready') return <Async state={reqs.state}>{() => null}</Async>; if (error) return <div className="pn-note error" role="alert">{error}</div>; if (rows === null) return <Loading/>;
  const flat = rows.flatMap(r => r.items.map(i => ({...i, request: r.request})));
  return <Card title="رزروهای متصل به درخواست‌های تأییدشده"><p className="pn-muted">رزرو فقط وقتی اینجا می‌آید که درخواست‌دهنده آن را به درخواست تأییدشدهٔ خود متصل کرده باشد.</p>
    <Table rows={flat} rowKey={i => String(i.reservation_id ?? i.id)} empty={rows.length === 0 ? 'درخواست تأییدشده‌ای وجود ندارد.' : 'هنوز رزروی به درخواست‌های تأییدشده متصل نشده است.'} cols={[{label: 'درخواست', cell: i => i.request.title}, {label: 'کد پیگیری', cell: i => <span className="pn-ltr">{i.booking_reference ?? String(i.reservation_id ?? i.id ?? '').slice(0, 8)}</span>},
      {label: 'خدمت', cell: i => serviceFa(i.service_type)}, {label: 'وضعیت', cell: i => <Badge status={i.status}/>}, {label: 'مبلغ', cell: i => money(i.total_amount, i.currency)}]}/></Card>;
}

export function OrgReports() {return <OrgScope need={RECORDS}>{org => <ReportsBody org={org}/>}</OrgScope>;}
function ReportsBody({org}: {org: Org}) {
  const sum = useLoad<Summary>(`/enterprise/organizations/${org.id}/summary`);
  const table = (title: string, data: Record<string, number>, label: (k: string) => ReactNode) => <Card title={title}><Table rows={Object.entries(data)} rowKey={([k]) => k} empty="داده‌ای برای گزارش وجود ندارد." cols={[{label: 'دسته', cell: ([k]) => label(k)}, {label: 'تعداد', cell: ([, v]) => fa(v)}]}/></Card>;
  function download(s: Summary) {
    const lines = [['section', 'key', 'count'], ...Object.entries(s.requests.by_status).map(([k, v]) => ['status', k, v]), ...Object.entries(s.requests.by_use_case).map(([k, v]) => ['use_case', k, v]), ...Object.entries(s.requests.by_policy_result).map(([k, v]) => ['policy_result', k, v]), ['total', 'members', s.members], ['total', 'linked_bookings', s.linked_bookings]];
    const url = URL.createObjectURL(new Blob(['﻿' + lines.map(l => l.join(',')).join('\n')], {type: 'text/csv;charset=utf-8'})); const a = document.createElement('a'); a.href = url; a.download = `organization-report-${s.organization.id.slice(0, 8)}.csv`; a.click(); URL.revokeObjectURL(url);
  }
  if (sum.state.kind === 'error' && sum.state.status === 403) return <Empty>گزارش سازمان فقط برای مدیران سازمان در دسترس است.</Empty>;
  return <Async state={sum.state}>{s => <>
    <Stats items={[{label: 'درخواست‌ها', value: fa(s.requests.total)}, {label: 'کارکنان', value: fa(s.members)}, {label: 'رزروهای متصل', value: fa(s.linked_bookings)}]}/>
    {table('درخواست‌ها بر اساس وضعیت', s.requests.by_status, k => <Badge status={k}/>)}{table('درخواست‌ها بر اساس نوع سفر', s.requests.by_use_case, k => USE_FA[k] ?? k)}{table('نتیجهٔ سنجش با سیاست سفر', s.requests.by_policy_result, k => POLICY_FA[k] ?? k)}
    <div><button type="button" className="pn-btn ghost" onClick={() => download(s)}>دریافت گزارش (CSV)</button></div>
    <p className="pn-muted">جمع هزینه‌ها از فاکتورهای رزروهای متصل ساخته می‌شود و در «صورتحساب و تسویه» آمده است.</p></>}</Async>;
}

/* ---- permissions, audit trail, statement */
const PERM_FA: Record<string, string> = {'requests.read_all': 'دیدن همهٔ درخواست‌ها', 'requests.on_behalf': 'ثبت درخواست برای دیگران', 'requests.approve': 'تأیید درخواست', 'policy.manage': 'مدیریت سیاست سفر', 'roles.manage': 'مدیریت اعضا و دسترسی', 'rfq.manage': 'استعلام از تأمین‌کننده', 'benefits.manage': 'مدیریت مزایا'};
function GrantEditor({org, member, onSaved}: {org: Org; member: Member; onSaved: (text: string, ok: boolean) => void}) {
  const {api} = useAuth(); const [open, setOpen] = useState(false); const [perms, setPerms] = useState<string[]>(member.permissions ?? []); const [busy, setBusy] = useState(false);
  if (member.role === 'organization_admin') return <span className="pn-muted">همهٔ دسترسی‌ها (مدیر سازمان)</span>;
  async function save() {setBusy(true); try {await api.put(`/enterprise/organizations/${org.id}/grants`, {command_id: `grant-${crypto.randomUUID()}`, user_id: member.id, permissions: perms}); setOpen(false); onSaved('دسترسی‌ها ذخیره شد.', true);} catch (e) {onSaved(errorOf(e).message, false);} finally {setBusy(false);}}
  if (!open) return <button type="button" className="pn-btn ghost" onClick={() => {setPerms(member.permissions ?? []); setOpen(true);}}>{(member.permissions ?? []).length ? `${fa((member.permissions ?? []).length)} دسترسی — ویرایش` : 'بدون دسترسی مدیریتی — افزودن'}</button>;
  return <div style={{display: 'grid', gap: 8}}><div className="pn-chips" role="group" aria-label={`دسترسی‌های ${member.name}`}>{Object.entries(PERM_FA).map(([k, label]) => <button type="button" key={k} aria-pressed={perms.includes(k)} onClick={() => setPerms(perms.includes(k) ? perms.filter(p => p !== k) : [...perms, k])}>{label}</button>)}</div>
    <div><button type="button" className="pn-btn" disabled={busy} onClick={() => void save()}>ذخیرهٔ دسترسی‌ها</button> <button type="button" className="pn-btn ghost" onClick={() => setOpen(false)}>انصراف</button></div></div>;
}

export function OrgAudit() {return <OrgScope need={RECORDS}>{org => <AuditBody org={org}/>}</OrgScope>;}
const EVENT_FA: Record<string, string> = {'created': 'ثبت سازمان', 'member.added': 'افزودن عضو', 'member.removed': 'حذف عضویت', 'grant.changed': 'تغییر دسترسی', 'policy.changed': 'تغییر سیاست سفر', 'policy.updated': 'تغییر سیاست سفر', 'request.created': 'ثبت درخواست', 'request.decided': 'تصمیم درخواست', 'request.approved': 'تأیید درخواست', 'request.rejected': 'رد درخواست', 'request.withdrawn': 'پس‌گرفتن درخواست', 'booking.linked': 'اتصال رزرو', 'quote.submitted': 'دریافت پیشنهاد', 'quote.selected': 'انتخاب پیشنهاد', 'campaign.created': 'ایجاد مزایا', 'invitation.sent': 'دعوت تأمین‌کننده'};
const WORKFLOW_ROLES = ['manager', 'welfare_manager', 'organization_admin', 'finance_operator', 'tenant_admin', 'platform_admin'];
function AuditBody({org}: {org: Org}) {
  const trail = useLoad<{id: string; type: string; at: string; actor: string; request_title: string | null}[]>(`/enterprise/organizations/${org.id}/audit`); // /organization/overview (reservation approval workflows): tenant staff by role, everyone else by an org-records grant in this organization.
  const {session} = useAuth(); const role = (session as {user?: {role?: string}} | null)?.user?.role ?? ''; const flowRole = WORKFLOW_ROLES.includes(role) || org.permissions.some(p => RECORDS.includes(p)); // 8.3: managers are `customer` + org grants; /organization/overview accepts the same RECORDS grants (org_access.RECORDS)
  const flows = useLoad<{workflows: {id: string; status: string; current_step: number; escalation_count: number}[]}>(flowRole ? '/organization/overview' : null);
  return <>
    <Card title="سوابق تغییرات سازمان">{trail.state.kind === 'error' && trail.state.status === 403 ? <Empty>سوابق سازمان فقط برای مدیران سازمان نمایش داده می‌شود.</Empty> : <Async state={trail.state}>{rows => <Table rows={rows} rowKey={e => e.id} empty="رویدادی ثبت نشده است."
      cols={[{label: 'زمان', cell: e => dateFa(e.at)}, {label: 'کاربر', cell: e => e.actor}, {label: 'رویداد', cell: e => EVENT_FA[e.type] ?? <span className="pn-ltr">{e.type}</span>}, {label: 'درخواست', cell: e => e.request_title ?? '—'}]}/>}</Async>}</Card>
    {flowRole && <Card title="گردش‌های تأیید رزرو">{flows.state.kind === 'error' && flows.state.status === 403 ? <Empty>گردش‌های تأیید فقط برای مدیران نمایش داده می‌شود.</Empty> : <Async state={flows.state}>{d => <Table rows={d.workflows} rowKey={w => w.id} empty="گردش تأیید فعالی وجود ندارد."
      cols={[{label: 'وضعیت', cell: w => <Badge status={w.status}/>}, {label: 'گام فعلی', cell: w => fa(w.current_step)}, {label: 'ارجاع', cell: w => fa(w.escalation_count)}]}/>}</Async>}</Card>}
  </>;
}

/* ---- Statement & invoices (Stitch _23, «گردش ریز تراکنش‌ها و فاکتورها») */
type Statement = {linked_bookings: number; items: {invoice_number: string; request_title: string; booking_reference: string; service_type: string; subtotal_amount?: number; tax_amount: number; total_amount: number; currency: string; status: string; issued_at: string | null}[]; totals: {currency: string; status: string; amount: number}[]};
export function OrgBilling() {return <OrgScope need={RECORDS}>{org => <BillingBody org={org}/>}</OrgScope>;}
const INVOICE_STATUS_FA: Record<string, string> = {issued: 'صادرشده', paid: 'پرداخت‌شده'};
function BillingBody({org}: {org: Org}) {
  const st = useLoad<Statement>(`/enterprise/organizations/${org.id}/statement`); const [service, setService] = useState('all');
  if (st.state.kind === 'error' && st.state.status === 403) return <Empty>صورتحساب سازمان فقط برای مدیران سازمان نمایش داده می‌شود. فاکتورهای خودتان در «حساب من ← پرداخت و فاکتور» است.</Empty>;
  function download(rows: Statement['items']) {
    const lines = [['invoice_number', 'request_title', 'booking_reference', 'service_type', 'subtotal_amount', 'tax_amount', 'total_amount', 'currency', 'status', 'issued_at'], ...rows.map(i => [i.invoice_number, i.request_title, i.booking_reference, i.service_type, i.subtotal_amount ?? '', i.tax_amount, i.total_amount, i.currency, i.status, i.issued_at ?? ''])];
    const cell = (v: unknown) => {const t = String(v); return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;};
    const url = URL.createObjectURL(new Blob(['﻿' + lines.map(l => l.map(cell).join(',')).join('\n')], {type: 'text/csv;charset=utf-8'})); const a = document.createElement('a'); a.href = url; a.download = `organization-statement-${org.id.slice(0, 8)}.csv`; a.click(); URL.revokeObjectURL(url);
  }
  return <div className="so" data-stitch="_23"><Async state={st.state}>{s => {
    const services = Array.from(new Set(s.items.map(i => i.service_type))); const rows = s.items.filter(i => service === 'all' || i.service_type === service);
    return <>
      <section className="so-hero" aria-label="صورتحساب"><div className="so-hero-id"><span className="so-hero-ic plum" aria-hidden="true">🧾</span><div><h2>صورتحساب سفرهای سازمان</h2><p>فاکتور رزروهایی که به درخواست‌های تأییدشدهٔ {org.name} متصل شده‌اند ({fa(s.linked_bookings)} رزرو متصل). جمع‌ها فقط حاصل همین فاکتورهاست.</p></div></div>
        <div className="so-hero-act"><Link className="so-btn ghost" href="/organization/credit">اعتبار سازمانی</Link></div></section>
      {s.totals.length > 0 && <div className="so-kpis">{s.totals.map(t => <Kpi key={`${t.currency}-${t.status}`} label={`فاکتورهای ${INVOICE_STATUS_FA[t.status] ?? t.status}`} icon={t.status === 'paid' ? '✅' : '🧾'} tone={t.status === 'paid' ? '' : 'red'} value={amountOf(t.amount, t.currency)}/>)}</div>}
      <section className="so-card" aria-labelledby="so-tx"><div className="so-card-head"><h2 id="so-tx">گردش فاکتورهای رزروهای سازمان</h2>
        {services.length > 1 && <div className="so-tabs" role="group" aria-label="فیلتر خدمت"><button type="button" aria-pressed={service === 'all'} onClick={() => setService('all')}>همه ({fa(s.items.length)})</button>{services.map(k => <button type="button" key={k} aria-pressed={service === k} onClick={() => setService(k)}>{serviceFa(k)} ({fa(s.items.filter(i => i.service_type === k).length)})</button>)}</div>}</div>
        {rows.length === 0 ? <div className="so-empty">هنوز فاکتوری برای رزروهای متصل به این سازمان صادر نشده است.</div> :
          <ul className="so-tx">{rows.map(i => <li key={i.invoice_number}><span className="so-glyph" aria-hidden="true">{SERVICE_GLYPH[i.service_type] ?? '🧳'}</span>
            <div><b>{i.request_title}</b> <Badge status={i.status}/><div className="so-tx-meta"><span>خدمت: {serviceFa(i.service_type)}</span><span>کد رزرو: <span className="so-ltr">{i.booking_reference}</span></span><span>شمارهٔ فاکتور: <span className="so-ltr">{i.invoice_number}</span></span><span>صدور: {dateFa(i.issued_at)}</span></div></div>
            <div className="so-tx-amt"><strong>{money(i.total_amount, i.currency)}</strong><small>مالیات: {money(i.tax_amount, i.currency)}</small></div></li>)}</ul>}
        {s.items.length > 0 && <div><button type="button" className="so-btn ghost sm" onClick={() => download(rows)}>دریافت فهرست فاکتورها (CSV)</button></div>}</section>
      <Unavailable title="ثبت تسویه">تسویهٔ فاکتورها را بخش مالی مجموعه ثبت می‌کند؛ پرداخت آنلاین سازمانی به درگاه و حساب اعتباری فعال نیاز دارد.</Unavailable>
    </>;}}</Async></div>;
}
