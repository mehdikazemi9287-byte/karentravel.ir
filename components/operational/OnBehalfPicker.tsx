'use client';
/* Booking on behalf of a colleague (رزرو برای همکار): only shown to a member holding `requests.on_behalf` in an organization
   (purchasing officer / organization admin). The API checks the permission, that the colleague is a member of the same
   organization and tenant, and the organization's travel policy; it records who booked for whom. */
import {useEffect, useRef, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {newId} from '../../lib/api/karenseir-client';
import {checkoutErrorMessage} from '../../lib/api-errors';
import type {SavedTraveller} from './TravellerForm';

type Org = {id: string; name: string; permissions: string[]};
type Member = {id: number; name: string; role: string};
type Designation = {id: string; reservation_id: string; beneficiary_user_id: number; beneficiary_name?: string | null; actor_name?: string | null; traveller_id?: string | null};

export function OnBehalfPicker({reservationId, onTraveller}: {reservationId: string; onTraveller: (row: SavedTraveller) => void}) {
  const {api, session} = useAuth();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [org, setOrg] = useState('');
  const [members, setMembers] = useState<Member[]>([]);
  const [member, setMember] = useState('');
  const [done, setDone] = useState<Designation | null>(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const key = useRef<string | null>(null);

  useEffect(() => {
    if (!session) return;
    let active = true;
    api.get<{organizations: Org[]}>('/enterprise/context').then(async ctx => {
      const allowed = ctx.organizations.filter(o => o.permissions.includes('requests.on_behalf'));
      if (!active) return;
      setOrgs(allowed);
      if (allowed.length === 1) setOrg(allowed[0].id);
      for (const o of allowed) {
        const rows = await api.get<Designation[]>(`/enterprise/organizations/${o.id}/on-behalf-bookings`).catch(() => [] as Designation[]);
        const hit = rows.find(r => r.reservation_id === reservationId);
        if (hit && active) { setDone(hit); break; }
      }
    }).catch(() => {});
    return () => { active = false; };
  }, [api, session, reservationId]);

  useEffect(() => {
    if (!org) return;
    let active = true;
    api.get<Member[]>(`/enterprise/organizations/${org}/members`).then(rows => { if (active) setMembers(rows); }).catch(() => { if (active) setNotice('فهرست همکاران دریافت نشد.'); });
    return () => { active = false; };
  }, [api, org]);

  if (!orgs.length) return null;
  async function submit() {
    if (busy || !org || !member) return;
    setBusy(true); setNotice('');
    key.current = key.current || newId();
    try {
      const row = await api.post<Designation>(`/enterprise/organizations/${org}/on-behalf-bookings`, {reservation_id: reservationId, beneficiary_user_id: Number(member), command_id: key.current});
      setDone(row); key.current = null;
      if (row.traveller_id) onTraveller({id: row.traveller_id, full_name: row.beneficiary_name || 'همکار سازمان'});
    } catch (e) { setNotice(checkoutErrorMessage(e)); key.current = null; } finally { setBusy(false); }
  }
  return <fieldset className="on-behalf">
    <legend>رزرو برای همکار سازمان</legend>
    {done ? <p role="status">این رزرو به نام «{done.beneficiary_name || 'همکار سازمان'}» ثبت شده است{done.actor_name ? ` (ثبت‌کننده: ${done.actor_name})` : ''}. مشخصات هویتی مسافر را در فهرست زیر تکمیل کنید؛ هزینه طبق سیاست سفر سازمان تأمین می‌شود.</p> : <>
      <p>اگر این رزرو برای همکار دیگری از سازمان است، او را انتخاب کنید. ثبت‌کننده و مسافر هر دو در سابقهٔ سازمان ثبت می‌شوند.</p>
      {orgs.length > 1 && <label>سازمان<select value={org} onChange={e => { setOrg(e.target.value); setMember(''); }}><option value="">انتخاب سازمان</option>{orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>}
      <label>همکار (مسافر)<select value={member} disabled={!org} onChange={e => setMember(e.target.value)}><option value="">انتخاب همکار</option>{(org ? members : []).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
      <button type="button" className="button secondary" disabled={busy || !member} onClick={() => void submit()}>{busy ? 'در حال ثبت…' : 'ثبت رزرو به نام این همکار'}</button>
    </>}
    {notice && <p role="alert" className="form-error">{notice}</p>}
  </fieldset>;
}
