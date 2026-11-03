'use client';
/* Platform tenant management (platform admin only): tenants with brand, domain, services and live counts; create and edit. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Table, errorOf, fa, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;
const DOMAIN_FA: Record<string, [string, string]> = {unverified: ['تأیید نشده', 'warn'], verified: ['تأییدشده', 'ok'], failed: ['ناموفق', 'bad']};

function TenantForm({initial, services, onSave, onCancel, create}: {initial: Row; services: Row[]; onSave: (v: Row) => Promise<void>; onCancel: () => void; create: boolean}) {
  const [v, setV] = useState<Row>(initial);
  const toggle = (k: string) => setV({...v, enabled_services: v.enabled_services.includes(k) ? v.enabled_services.filter((x: string) => x !== k) : [...v.enabled_services, k]});
  const submit = (e: FormEvent) => {e.preventDefault(); void onSave(v);};
  return <form className="pn-form" onSubmit={submit}>
    {create && <label>نامک (انگلیسی، یکتا)<input className="pn-ltr" value={v.slug} onChange={e => setV({...v, slug: e.target.value.toLowerCase()})} required pattern="[a-z][a-z0-9-]{2,40}[a-z0-9]"/></label>}
    <label>نام<input value={v.name} onChange={e => setV({...v, name: e.target.value})} required minLength={2}/></label>
    <div className="tn-colors"><label>رنگ اصلی<input type="color" value={v.primary_color} onChange={e => setV({...v, primary_color: e.target.value})}/></label>
      <label>رنگ دوم<input type="color" value={v.secondary_color} onChange={e => setV({...v, secondary_color: e.target.value})}/></label></div>
    <label>دامنه‌ی اختصاصی (اختیاری)<input className="pn-ltr" value={v.custom_domain ?? ''} onChange={e => setV({...v, custom_domain: e.target.value})} placeholder="www.example.ir"/></label>
    <fieldset className="tn-services"><legend>خدمات فعال</legend>{services.map(s => <label key={s.key}><input type="checkbox" checked={v.enabled_services.includes(s.key)} onChange={() => toggle(s.key)}/> {s.label}</label>)}</fieldset>
    {create && <><label>ایمیل مدیر مستأجر<input className="pn-ltr" type="email" value={v.admin_email} onChange={e => setV({...v, admin_email: e.target.value})} required/></label>
      <label>نام مدیر<input value={v.admin_name} onChange={e => setV({...v, admin_name: e.target.value})} required/></label></>}
    <div className="sec-actions"><button className="pn-btn">{create ? 'ساخت مستأجر' : 'ذخیره'}</button><button type="button" className="pn-btn ghost" onClick={onCancel}>انصراف</button></div>
  </form>;
}

export function PlatformTenants() {
  const {state, reload, api} = useLoad<Row>('/platform/tenants');
  const [edit, setEdit] = useState<Row | null>(null); const [creating, setCreating] = useState(false); const [msg, setMsg] = useState<Msg>(null);
  async function save(v: Row, id?: number) {
    setMsg(null);
    const body = {...v, custom_domain: v.custom_domain || null};
    try {if (id) await api.put(`/platform/tenants/${id}`, body); else await api.post('/platform/tenants', body);
      setEdit(null); setCreating(false); setMsg({ok: true, text: id ? 'مستأجر به‌روز شد.' : 'مستأجر و مدیر آن ساخته شد؛ مدیر با ایمیل خود وارد می‌شود.'}); reload();}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  return <Async state={state}>{d => <>
    <Note msg={msg}/>
    {creating && <Card title="مستأجر تازه"><TenantForm create services={d.services} onCancel={() => setCreating(false)} onSave={v => save(v)}
      initial={{slug: '', name: '', primary_color: '#3a1b3d', secondary_color: '#ef5b3d', custom_domain: '', enabled_services: ['flight', 'hotel', 'tour'], admin_email: '', admin_name: ''}}/></Card>}
    {edit && <Card title={`ویرایش ${edit.name}`}><TenantForm create={false} services={d.services} onCancel={() => setEdit(null)} onSave={v => save(v, edit.id)}
      initial={{name: edit.name, primary_color: edit.primary_color?.toLowerCase() ?? '#3a1b3d', secondary_color: edit.secondary_color?.toLowerCase() ?? '#ef5b3d', custom_domain: edit.custom_domain ?? '', enabled_services: edit.enabled_services}}/></Card>}
    <Card title="مستأجرها" action={!creating && <button className="pn-btn" onClick={() => {setCreating(true); setEdit(null);}}>مستأجر تازه</button>}>
      <p className="pn-muted">داده‌ی هر مستأجر جداست؛ این صفحه فقط برند، دامنه، خدمات و شمار کاربران و رزروها را نشان می‌دهد.</p>
      <Table rows={d.items} rowKey={(r: Row) => String(r.id)} empty="مستأجری نیست." cols={[
        {label: 'مستأجر', cell: (r: Row) => <span className="tn-name"><i style={{background: r.primary_color}} aria-hidden="true"/>{r.name}<small className="pn-muted pn-ltr"> {r.slug}</small></span>},
        {label: 'دامنه', cell: (r: Row) => r.custom_domain ? <><span className="pn-ltr">{r.custom_domain}</span> <span className={`pn-badge ${DOMAIN_FA[r.domain_status]?.[1] ?? ''}`}>{DOMAIN_FA[r.domain_status]?.[0] ?? r.domain_status}</span></> : '—'},
        {label: 'خدمات', cell: (r: Row) => r.enabled_services.length ? r.enabled_services.map((k: string) => d.services.find((s: Row) => s.key === k)?.label ?? k).join('، ') : '—'},
        {label: 'کاربر', cell: (r: Row) => fa(r.counts.users)}, {label: 'رزرو', cell: (r: Row) => fa(r.counts.reservations)}, {label: 'تأمین‌کننده', cell: (r: Row) => fa(r.counts.suppliers)},
        {label: 'مدیر', cell: (r: Row) => r.admins.length ? <span className="pn-ltr">{r.admins.join(', ')}</span> : '—'},
        {label: '', cell: (r: Row) => <button className="pn-btn ghost" onClick={() => {setEdit(r); setCreating(false);}}>ویرایش</button>}]}/>
    </Card>
  </>}</Async>;
}
