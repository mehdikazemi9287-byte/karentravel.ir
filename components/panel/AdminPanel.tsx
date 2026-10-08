'use client';
/* Tenant administration views that tie the four panels together: organizations (members, credit) and the tenant audit trail. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Empty, Table, dateFa, errorOf, fa, money, useLoad} from './PanelKit';
import {MembersBody} from './OrganizationPanel';

type OrgRow = {id: string; name: string; status: string; members: number};
type Account = {id: string; currency: string; limit_amount: number; available: number; reserved: number; consumed: number};
export function AdminOrganizations() {
  const orgs = useLoad<OrgRow[]>('/enterprise/organizations'); const [open, setOpen] = useState(''); const [name, setName] = useState(''); const [note, setNote] = useState<{ok: boolean; text: string} | null>(null);
  async function create(e: FormEvent) {e.preventDefault(); setNote(null); try {const row = await orgs.api.post<OrgRow>('/enterprise/organizations', {name}); setName(''); setOpen(row.id); orgs.reload(); setNote({ok: true, text: 'سازمان ایجاد شد.'});} catch (err) {setNote({ok: false, text: errorOf(err).message});}}
  return <>
    {note && <div className={`pn-note ${note.ok ? 'ok' : 'error'}`} role={note.ok ? 'status' : 'alert'}>{note.text}</div>}
    <Card title="ایجاد سازمان"><form className="pn-form" onSubmit={create}><label>نام سازمان<input value={name} onChange={e => setName(e.target.value)} minLength={2} maxLength={160} required/></label><button className="pn-btn">ایجاد</button></form></Card>
    <Card title="سازمان‌های این مجموعه"><Async state={orgs.state}>{rows => <Table rows={rows} rowKey={o => o.id} empty="سازمانی ثبت نشده است." cols={[{label: 'نام', cell: o => o.name}, {label: 'اعضا', cell: o => fa(o.members)}, {label: 'وضعیت', cell: o => o.status === 'active' ? 'فعال' : o.status},
      {label: '', cell: o => <button type="button" className="pn-btn ghost" aria-pressed={open === o.id} onClick={() => setOpen(open === o.id ? '' : o.id)}>{open === o.id ? 'بستن' : 'مدیریت اعضا و اعتبار'}</button>}]}/>}</Async></Card>
    {open && orgs.state.kind === 'ready' && orgs.state.data.filter(o => o.id === open).map(o => <div key={o.id} style={{display: 'grid', gap: 18}}><MembersBody org={{id: o.id, name: o.name, permissions: ['roles.manage']}}/><CreditAccounts org={o}/></div>)}
  </>;
}
function CreditAccounts({org}: {org: OrgRow}) {
  const acc = useLoad<Account[]>(`/enterprise/organizations/${org.id}/credit`); const [limit, setLimit] = useState(''); const [note, setNote] = useState<{ok: boolean; text: string} | null>(null);
  async function create(e: FormEvent) {
    e.preventDefault(); setNote(null);
    try {await acc.api.post(`/organizations/${org.id}/credit-accounts`, {organization_id: org.id, limit_amount: Number(limit), currency: 'IRR', command_id: `credit-${crypto.randomUUID()}`}); setLimit(''); acc.reload(); setNote({ok: true, text: 'حساب اعتباری ایجاد شد.'});}
    catch (err) {const x = errorOf(err); setNote({ok: false, text: x.status === 403 ? 'ایجاد حساب اعتباری فقط با مجوز مدیریت اعتبار (بخش مالی) ممکن است.' : x.message});}
  }
  return <Card title={`حساب اعتباری ${org.name}`}>
    {note && <div className={`pn-note ${note.ok ? 'ok' : 'error'}`} role={note.ok ? 'status' : 'alert'}>{note.text}</div>}
    <Async state={acc.state}>{rows => rows.length === 0 ? <Empty>حساب اعتباری تعریف نشده است.</Empty> : <Table rows={rows} rowKey={a => a.id} empty="" cols={[{label: 'سقف', cell: a => money(a.limit_amount, a.currency)}, {label: 'قابل استفاده', cell: a => money(a.available, a.currency)}, {label: 'رزروشده', cell: a => money(a.reserved, a.currency)}, {label: 'مصرف‌شده', cell: a => money(a.consumed, a.currency)}]}/>}</Async>
    <form className="pn-form" onSubmit={create}><label>سقف اعتبار طبق قرارداد (ریال)<input dir="ltr" inputMode="numeric" pattern="[0-9]+" value={limit} onChange={e => setLimit(e.target.value.replace(/\D/g, ''))} required/></label><button className="pn-btn">ایجاد حساب اعتباری</button></form>
    <p className="pn-muted">سقف را فقط بر اساس قرارداد امضاشده وارد کنید؛ موجودی از گردش‌های واقعی همین حساب محاسبه می‌شود.</p></Card>;
}
type Event = {id: number; action: string; entity: string; entity_id: number; detail: string; actor: string; at: string};
export function AdminAudit() {
  const [action, setAction] = useState(''); const [applied, setApplied] = useState(''); const ev = useLoad<Event[]>(`/admin/audit-events?limit=200${applied ? `&action=${encodeURIComponent(applied)}` : ''}`);
  return <Card title="سوابق ممیزی مجموعه"><form className="pn-form" onSubmit={e => {e.preventDefault(); setApplied(action.trim());}}><label>پیشوند عملیات<input dir="ltr" placeholder="catalog_ / booking." value={action} onChange={e => setAction(e.target.value)}/></label><button className="pn-btn ghost">اعمال</button></form>
    <Async state={ev.state}>{rows => <Table rows={rows} rowKey={e => String(e.id)} empty="رویدادی با این شرایط ثبت نشده است." cols={[{label: 'زمان', cell: e => dateFa(e.at)}, {label: 'کاربر', cell: e => e.actor}, {label: 'عملیات', cell: e => <span className="pn-ltr">{e.action}</span>}, {label: 'موجودیت', cell: e => <span className="pn-ltr">{e.entity}#{e.entity_id}</span>}, {label: 'جزئیات', cell: e => <span className="pn-ltr">{e.detail.slice(0, 90)}</span>}]}/>}</Async></Card>;
}
