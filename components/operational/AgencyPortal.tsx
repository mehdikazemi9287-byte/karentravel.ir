'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ErrorState } from './ConnectedViews';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError, newId } from '../../lib/api/karenseir-client';

type SubAgency = { id: string; name: string; parent_agency_id?: string | null; markup_bps: number; commission_bps: number };
type Dash = { agencies: SubAgency[] };
const bps = (v: number) => `${(v / 100).toLocaleString('fa-IR', { maximumFractionDigits: 2 })}٪`;
const msgOf = (e: unknown) => (e instanceof ApiError ? e.message : 'خطای پیش‌بینی‌نشده رخ داد.');

export function AgencyPortal() {
  const { api, session } = useAuth();
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<{ status: number; message: string } | null>(null);
  const [notice, setNotice] = useState('');const [busy,setBusy]=useState(false);const createKey=useRef(newId());
  const [name, setName] = useState('');

  const load = useCallback(async () => {
    try { setDash(await api.get<Dash>('/agency/dashboard')); }
    catch (e) { setErr(e instanceof ApiError ? { status: e.status, message: e.message } : { status: 0, message: msgOf(e) }); }
  }, [api]);
  useEffect(() => {if(!session)return;let active=true;api.get<Dash>('/agency/dashboard').then(value=>{if(active)setDash(value)}).catch(e=>{if(active)setErr(e instanceof ApiError?{status:e.status,message:e.message}:{status:0,message:msgOf(e)})});return()=>{active=false}},[session,api]);

  async function mutate(fn: () => Promise<unknown>, ok: string) {
    if(busy)return false;setBusy(true);setNotice('در حال ثبت امن…');
    try { await fn(); setNotice(ok); await load();return true; } catch (e) { setNotice(msgOf(e));return false; } finally {setBusy(false)}
  }
  async function createSub(e: FormEvent) {
    e.preventDefault();
    const done=await mutate(() => api.post('/agency/sub-agencies', { display_name: name, markup_bps: 0, commission_bps: 0 }, createKey.current), 'زیرآژانس ثبت شد.');
    if(done){setName('');createKey.current=newId()}
  }

  if (!session) return <ErrorState status={401} message="برای ادامه وارد حساب شوید."/>;
  if (err) return <div className="dashboard container"><p role="alert" className="rounded-2xl bg-rose-50 p-6 text-rose-700">خطای {err.status}: {err.message}</p></div>;
  if (!dash) return <div className="dashboard container"><p role="status" className="my-8 animate-pulse rounded-2xl bg-white p-8 text-center text-slate-600">در حال دریافت اطلاعات معتبر…</p></div>;

  const subs = dash.agencies;
  const avgCommission = subs.length ? subs.reduce((s, a) => s + a.commission_bps, 0) / subs.length : 0;
  const avgMarkup = subs.length ? subs.reduce((s, a) => s + a.markup_bps, 0) / subs.length : 0;

  return <div className="dashboard container">
    <div className="dashboard-title"><div>
      <span className="eyebrow">پنل آژانس · داده احرازشده tenant</span>
      <h1>شبکه زیرآژانس، ساختار کمیسیون و عملیات</h1>
      <p>همه‌ی داده‌ها و اقدام‌ها فقط از API مجاز همان tenant انجام می‌شوند.</p>
    </div></div>
    {notice && <p role="status" className="mb-4 rounded-xl bg-cyan-50 p-4">{notice}</p>}

    <section className="metrics">
      <div><small>زیرآژانس‌ها</small><strong>{subs.length.toLocaleString('fa-IR')}</strong><span>ساختار واقعی شبکه</span></div>
      <div><small>میانگین کمیسیون پیکربندی‌شده</small><strong>{bps(avgCommission)}</strong><span>نرخ قرارداد، نه درآمد کسب‌شده</span></div>
      <div><small>میانگین markup پیکربندی‌شده</small><strong>{bps(avgMarkup)}</strong><span>روی نرخ خالص</span></div>
    </section>

    <section className="dashboard-grid">
      <article className="panel">
        <div className="panel-head"><h3>شبکه زیرآژانس و کمیسیون</h3></div>
        <form onSubmit={createSub} className="mt-3 flex flex-wrap gap-3">
          <input className="min-w-56 flex-1 rounded-xl border p-3" placeholder="نام زیرآژانس جدید" value={name} onChange={e => setName(e.target.value)} required minLength={2} />
          <button disabled={busy} className="button primary">ثبت زیرآژانس</button>
        </form>
        {subs.length === 0
          ? <p className="mt-3 text-sm text-slate-600">هنوز زیرآژانسی تعریف نشده است.</p>
          : subs.map(a => <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3" key={a.id}>
              <span><b className="block">{a.name}</b>
                <small className="text-slate-600">markup {bps(a.markup_bps)} · کمیسیون {bps(a.commission_bps)}{a.parent_agency_id ? ' · زیرمجموعه' : ''}</small></span>
              <button disabled={busy} className="button secondary" onClick={() => mutate(() => api.put(`/agency/agencies/${a.id}`, { markup_bps: a.markup_bps + 25 }), 'markup به‌روزرسانی شد.')}>+۲۵ bps markup</button>
            </div>)}
      </article>

      <article className="panel">
        <div className="panel-head"><h3>رزروهای آژانس</h3></div>
        <p className="mt-3 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-600">
          فهرست رزروهای آژانس در API فعلی به‌صورت فهرست‌شده در دسترس نیست. عملیات fulfillment (صدور واچر، اعتبارسنجی بلیت) از طریق شناسه رزرو انجام می‌شود و در همین tenant محدود می‌ماند.
        </p>
      </article>
    </section>

    <section className="panel mt-5">
      <div className="panel-head"><h3>تسویه و کمیسیون کسب‌شده</h3></div>
      <p className="mt-3 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-600">
        داده‌ی تسویه و کمیسیون کسب‌شده‌ی هر رزرو هنوز از سرویس مالی در دسترس نیست؛ تا اتصال معتبر، فقط نرخ‌های پیکربندی‌شده‌ی بالا واقعی‌اند و هیچ مبلغ درآمدی ساخته نمی‌شود.
      </p>
    </section>
  </div>;
}
