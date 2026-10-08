'use client';
/* Organization panel. The organization comes from the signed-in user's own memberships (/enterprise/context);
   every list below is scoped by the API to that organization and to the permissions the user holds in it. */
import Link from 'next/link';
import {useEffect, useState, type FormEvent, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {Async, Badge, Card, Empty, Failed, Loading, Stats, Table, Unavailable, dateFa, errorOf, fa, money, serviceFa, useLoad} from './PanelKit';

type Org = {id: string; name: string; permissions: string[]};
type Context = {organizations: Org[]; use_cases: string[]; services: string[]};
type Member = {id: number; name: string; email?: string; role: string; permissions?: string[]};
type Summary = {organization: {id: string; name: string}; members: number; departments: number; cost_centers: number; requests: {total: number; by_status: Record<string, number>; by_use_case: Record<string, number>; by_policy_result: Record<string, number>}; linked_bookings: number; credit_accounts: number};
type Request = {id: string; title: string; use_case: string; status: string; policy_result: string; requester_id: number; requirements: {destination?: string; starts_at?: string; ends_at?: string; headcount?: number; budget_amount?: number; services?: string[]}};
type Credit = {id: string; organization_id?: string | null; currency: string; limit_amount: number; available: number; reserved: number; consumed: number};
const ROLE_FA: Record<string, string> = {employee: 'کارمند', manager: 'مدیر', welfare_manager: 'مدیر رفاهی', organization_admin: 'مدیر سازمان', tenant_admin: 'مدیر مجموعه', platform_admin: 'مدیر سکو', finance_operator: 'کارشناس مالی', customer: 'مشتری'};
const USE_FA: Record<string, string> = {business_trip: 'مأموریت کاری', team_retreat: 'سفر تیمی', conference: 'همایش', incentive: 'سفر تشویقی', welfare: 'سفر رفاهی', training: 'دورهٔ آموزشی', relocation: 'جابه‌جایی', client_visit: 'دیدار با مشتری', family_welfare: 'رفاهی خانواده'};
const POLICY_FA: Record<string, string> = {IN_POLICY: 'مطابق سیاست', OUT_OF_POLICY: 'خارج از سیاست', APPROVAL_REQUIRED: 'نیازمند تأیید', BLOCKED: 'ممنوع'};
const RULE_FA: Record<string, string> = {allowed_services: 'خدمات مجاز', approval_required: 'نیاز به تأیید', approver_ids: 'تأییدکنندگان', maximum_budget: 'سقف بودجهٔ هر درخواست', allowed_destinations: 'مقصدهای مجاز', blocked_destinations: 'مقصدهای ممنوع', minimum_notice_days: 'حداقل فاصله تا سفر (روز)', maximum_trip_days: 'حداکثر مدت سفر (روز)'};
const TENANT_ADMINS = ['tenant_admin', 'platform_admin'];
const KEY = 'karenseir-panel-organization';

/** Resolves the organization this user works in; tenant administrators can also create one and pick any. */
export function OrgScope({children}: {children: (org: Org, ctx: Context) => ReactNode}) {
  const {session} = useAuth(); const role = (session as {user?: {role?: string}} | null)?.user?.role ?? ''; const admin = TENANT_ADMINS.includes(role);
  const ctx = useLoad<Context>('/enterprise/context'); const all = useLoad<{id: string; name: string; members: number}[]>(admin ? '/enterprise/organizations' : null);
  const [picked, setPicked] = useState(''); const [name, setName] = useState(''); const [note, setNote] = useState('');
  useEffect(() => {try {setPicked(sessionStorage.getItem(KEY) ?? '');} catch {/* storage unavailable */}}, []);
  if (ctx.state.kind === 'loading') return <Loading/>; if (ctx.state.kind === 'error') return <Failed status={ctx.state.status} message={ctx.state.message}/>;
  const mine = ctx.state.data.organizations; const extra: Org[] = admin && all.state.kind === 'ready' ? all.state.data.filter(o => !mine.some(x => x.id === o.id)).map(o => ({id: o.id, name: o.name, permissions: ['roles.manage']})) : [];
  const orgs = [...mine, ...extra]; const org = orgs.find(o => o.id === picked) ?? orgs[0];
  async function create(e: FormEvent) {e.preventDefault(); setNote(''); try {const row = await ctx.api.post<{id: string}>('/enterprise/organizations', {name}); setName(''); try {sessionStorage.setItem(KEY, row.id);} catch {/* ignore */} setPicked(row.id); all.reload(); ctx.reload();} catch (err) {setNote(errorOf(err).message);}}
  const creator = admin && <Card title="ایجاد سازمان"><form className="pn-form" onSubmit={create}><label>نام سازمان<input value={name} onChange={e => setName(e.target.value)} minLength={2} maxLength={160} required/></label><button className="pn-btn">ایجاد</button></form>{note && <div className="pn-note error" role="alert">{note}</div>}</Card>;
  if (!org) return <><Empty>{admin ? 'هنوز سازمانی در این مجموعه ثبت نشده است.' : 'حساب شما عضو هیچ سازمانی نیست. عضویت را مدیر سازمان یا مدیر مجموعه ثبت می‌کند.'}</Empty>{creator}</>;
  return <>{orgs.length > 1 && <div className="pn-form"><label>سازمان<select value={org.id} onChange={e => {setPicked(e.target.value); try {sessionStorage.setItem(KEY, e.target.value);} catch {/* ignore */}}}>{orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label></div>}
    {children(org, ctx.state.data)}{creator}</>;
}
const can = (org: Org, p: string) => org.permissions.includes(p);

export function OrgOverview() {return <OrgScope>{org => <OverviewBody org={org}/>}</OrgScope>;}
function OverviewBody({org}: {org: Org}) {
  const sum = useLoad<Summary>(`/enterprise/organizations/${org.id}/summary`); const reqs = useLoad<Request[]>(`/enterprise/requests?org=${org.id}`);
  return <>
    <p className="pn-muted">{org.name}</p>
    {sum.state.kind === 'ready' ? <Stats items={[{label: 'کارکنان', value: fa(sum.state.data.members)}, {label: 'واحدها', value: fa(sum.state.data.departments)}, {label: 'مراکز هزینه', value: fa(sum.state.data.cost_centers)}, {label: 'درخواست‌های سفر', value: fa(sum.state.data.requests.total)},
      {label: 'در انتظار تأیید', value: fa(sum.state.data.requests.by_status.approval_required ?? 0)}, {label: 'رزروهای متصل', value: fa(sum.state.data.linked_bookings)}, {label: 'حساب اعتباری', value: fa(sum.state.data.credit_accounts)}]}/>
      : sum.state.kind === 'error' && sum.state.status === 403 ? <Empty>آمار کل سازمان فقط برای مدیران سازمان نمایش داده می‌شود؛ درخواست‌های خودتان در پایین آمده است.</Empty> : sum.state.kind === 'error' ? <Failed status={sum.state.status} message={sum.state.message}/> : <Loading/>}
    <Card title="آخرین درخواست‌های سفر" action={<Link className="pn-link" href="/organization/requests">ثبت و پیگیری درخواست</Link>}><Async state={reqs.state}>{rows => <RequestTable rows={rows.slice(0, 6)}/>}</Async></Card>
  </>;
}
function RequestTable({rows}: {rows: Request[]}) {
  return <Table rows={rows} rowKey={r => r.id} empty="درخواست سفری ثبت نشده است." cols={[{label: 'عنوان', cell: r => r.title}, {label: 'نوع', cell: r => USE_FA[r.use_case] ?? r.use_case}, {label: 'مقصد', cell: r => r.requirements.destination ?? '—'}, {label: 'تاریخ', cell: r => dateFa(r.requirements.starts_at)},
    {label: 'نفرات', cell: r => r.requirements.headcount ? fa(r.requirements.headcount) : '—'}, {label: 'سیاست', cell: r => POLICY_FA[r.policy_result] ?? r.policy_result}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}/>;
}

export function OrgMembers() {return <OrgScope>{org => <MembersBody org={org}/>}</OrgScope>;}
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

export function OrgCredit() {return <OrgScope>{org => <CreditBody org={org}/>}</OrgScope>;}
function CreditBody({org}: {org: Org}) {
  const credit = useLoad<Credit[]>(`/enterprise/organizations/${org.id}/credit`); const plans = useLoad<{id: string; title: string; status: string}[]>('/me/installment-plans');
  return <>
    <Card title="اعتبار سازمانی">{credit.state.kind === 'error' && credit.state.status === 403 ? <Empty>اعتبار سازمان فقط برای مدیران سازمان نمایش داده می‌شود؛ اعتبار تخصیص‌یافته به خودتان در «حساب من ← کیف پول و اعتبار» است.</Empty> : <Async state={credit.state}>{rows => {const own = rows; return own.length === 0 ? <Empty>برای این سازمان حساب اعتباری تعریف نشده است. حساب اعتباری پس از قرارداد و توسط بخش مالی ایجاد می‌شود.</Empty>
      : <>{own.map(c => <dl className="pn-dl" key={c.id}><dt>سقف اعتبار</dt><dd>{money(c.limit_amount, c.currency)}</dd><dt>قابل استفاده</dt><dd>{money(c.available, c.currency)}</dd><dt>رزروشده</dt><dd>{money(c.reserved, c.currency)}</dd><dt>مصرف‌شده</dt><dd>{money(c.consumed, c.currency)}</dd></dl>)}</>;}}</Async>}</Card>
    <Card title="طرح‌های اقساط"><Async state={plans.state}>{rows => <Table rows={rows} rowKey={p => p.id} empty="طرح قسطی فعالی وجود ندارد." cols={[{label: 'عنوان', cell: p => p.title}, {label: 'وضعیت', cell: p => <Badge status={p.status}/>}]}/>}</Async></Card>
    <Unavailable title="کسر از حقوق">سامانه مدل داده‌ای برای کسر از حقوق و اتصال به حقوق‌ودستمزد ندارد؛ این قابلیت تا تعریف قرارداد و مدل واقعی غیرفعال است.</Unavailable>
  </>;
}

export function OrgBookings() {return <OrgScope>{org => <BookingsBody org={org}/>}</OrgScope>;}
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

export function OrgReports() {return <OrgScope>{org => <ReportsBody org={org}/>}</OrgScope>;}
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

export function OrgAudit() {return <OrgScope>{org => <AuditBody org={org}/>}</OrgScope>;}
const EVENT_FA: Record<string, string> = {'grant.changed': 'تغییر دسترسی', 'policy.changed': 'تغییر سیاست سفر', 'policy.updated': 'تغییر سیاست سفر', 'request.created': 'ثبت درخواست', 'request.decided': 'تصمیم درخواست', 'request.approved': 'تأیید درخواست', 'request.rejected': 'رد درخواست', 'request.withdrawn': 'پس‌گرفتن درخواست', 'booking.linked': 'اتصال رزرو', 'quote.submitted': 'دریافت پیشنهاد', 'quote.selected': 'انتخاب پیشنهاد', 'campaign.created': 'ایجاد مزایا', 'invitation.sent': 'دعوت تأمین‌کننده'};
function AuditBody({org}: {org: Org}) {
  const trail = useLoad<{id: string; type: string; at: string; actor: string; request_title: string | null}[]>(`/enterprise/organizations/${org.id}/audit`); const flows = useLoad<{workflows: {id: string; status: string; current_step: number; escalation_count: number}[]}>('/organization/overview');
  return <>
    <Card title="سوابق تغییرات سازمان">{trail.state.kind === 'error' && trail.state.status === 403 ? <Empty>سوابق سازمان فقط برای مدیران سازمان نمایش داده می‌شود.</Empty> : <Async state={trail.state}>{rows => <Table rows={rows} rowKey={e => e.id} empty="رویدادی ثبت نشده است."
      cols={[{label: 'زمان', cell: e => dateFa(e.at)}, {label: 'کاربر', cell: e => e.actor}, {label: 'رویداد', cell: e => EVENT_FA[e.type] ?? <span className="pn-ltr">{e.type}</span>}, {label: 'درخواست', cell: e => e.request_title ?? '—'}]}/>}</Async>}</Card>
    <Card title="گردش‌های تأیید رزرو">{flows.state.kind === 'error' && flows.state.status === 403 ? <Empty>گردش‌های تأیید فقط برای مدیران نمایش داده می‌شود.</Empty> : <Async state={flows.state}>{d => <Table rows={d.workflows} rowKey={w => w.id} empty="گردش تأیید فعالی وجود ندارد."
      cols={[{label: 'وضعیت', cell: w => <Badge status={w.status}/>}, {label: 'گام فعلی', cell: w => fa(w.current_step)}, {label: 'ارجاع', cell: w => fa(w.escalation_count)}]}/>}</Async>}</Card>
  </>;
}

type Statement = {linked_bookings: number; items: {invoice_number: string; request_title: string; booking_reference: string; service_type: string; tax_amount: number; total_amount: number; currency: string; status: string; issued_at: string | null}[]; totals: {currency: string; status: string; amount: number}[]};
export function OrgBilling() {return <OrgScope>{org => <BillingBody org={org}/>}</OrgScope>;}
function BillingBody({org}: {org: Org}) {
  const st = useLoad<Statement>(`/enterprise/organizations/${org.id}/statement`);
  if (st.state.kind === 'error' && st.state.status === 403) return <Empty>صورتحساب سازمان فقط برای مدیران سازمان نمایش داده می‌شود. فاکتورهای خودتان در «حساب من ← پرداخت و فاکتور» است.</Empty>;
  return <Async state={st.state}>{s => <>
    {s.totals.length > 0 && <Stats items={s.totals.map(t => ({label: `فاکتورهای ${t.status === 'issued' ? 'صادرشده' : t.status === 'paid' ? 'پرداخت‌شده' : t.status}`, value: money(t.amount, t.currency)}))}/>}
    <Card title="صورتحساب سفرهای سازمان"><p className="pn-muted">فاکتور رزروهایی که به درخواست‌های تأییدشدهٔ این سازمان متصل شده‌اند ({fa(s.linked_bookings)} رزرو متصل). جمع‌ها فقط حاصل همین فاکتورهاست.</p>
      <Table rows={s.items} rowKey={i => i.invoice_number} empty="هنوز فاکتوری برای رزروهای متصل به این سازمان صادر نشده است." cols={[{label: 'شمارهٔ فاکتور', cell: i => <span className="pn-ltr">{i.invoice_number}</span>}, {label: 'درخواست', cell: i => i.request_title}, {label: 'کد رزرو', cell: i => <span className="pn-ltr">{i.booking_reference}</span>}, {label: 'خدمت', cell: i => serviceFa(i.service_type)},
        {label: 'مالیات', cell: i => money(i.tax_amount, i.currency)}, {label: 'قابل پرداخت', cell: i => money(i.total_amount, i.currency)}, {label: 'وضعیت', cell: i => <Badge status={i.status}/>}, {label: 'صدور', cell: i => dateFa(i.issued_at)}]}/></Card>
    <Unavailable title="ثبت تسویه">تسویهٔ فاکتورها را بخش مالی مجموعه ثبت می‌کند؛ پرداخت آنلاین سازمانی به درگاه و حساب اعتباری فعال نیاز دارد.</Unavailable></>}</Async>;
}
