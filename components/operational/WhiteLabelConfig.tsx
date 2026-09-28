'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError } from '../../lib/api/karenseir-client';

type WL = {
  display_name: string; logo_reference?: string | null; primary_color: string; secondary_color: string;
  custom_domain?: string | null; domain_status?: string | null;
  support: Record<string, unknown>; enabled_services: string[]; organization_policy: Record<string, unknown>;
  feature_flags: Record<string, unknown>;
};
const ALL_SERVICES = ['flight', 'hotel', 'train', 'bus', 'tour', 'accommodation', 'visa', 'car_rental'];
const SVC_FA: Record<string, string> = { flight: 'پرواز', hotel: 'هتل', train: 'قطار', bus: 'اتوبوس', tour: 'تور', accommodation: 'اقامتگاه', visa: 'ویزا', car_rental: 'اجاره خودرو' };
const msgOf = (e: unknown) => (e instanceof ApiError ? e.message : 'خطای پیش‌بینی‌نشده رخ داد.');

export function WhiteLabelConfig() {
  const { api, session } = useAuth();
  const canEdit = session?.user?.role === 'tenant_admin' || session?.user?.role === 'platform_admin';
  const [wl, setWl] = useState<WL | null>(null);
  const [missing, setMissing] = useState(false);
  const [err, setErr] = useState<{ status: number; message: string } | null>(null);
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState<Partial<WL>>({ primary_color: '#0E7490', secondary_color: '#B65C2D', enabled_services: [] });

  const load = useCallback(async () => {
    try {
      const row = await api.get<WL>('/tenant/white-label');
      setWl(row); setForm(row); setMissing(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) { setMissing(true); }
      else setErr(e instanceof ApiError ? { status: e.status, message: e.message } : { status: 0, message: msgOf(e) });
    }
  }, [api]);
  useEffect(() => { if (session) load(); }, [session, load]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setNotice('در حال ذخیره پیکربندی…');
    try {
      const body = {
        display_name: form.display_name, logo_reference: form.logo_reference || null,
        primary_color: form.primary_color, secondary_color: form.secondary_color,
        custom_domain: form.custom_domain || null,
        support: form.support || {}, enabled_services: form.enabled_services || [],
        organization_policy: form.organization_policy || {}, feature_flags: form.feature_flags || {},
      };
      const row = await api.put<WL>('/tenant/white-label', body);
      setWl(row); setForm(row); setMissing(false); setNotice('پیکربندی White Label ذخیره شد.');
    } catch (e) { setNotice(msgOf(e)); }
  }

  if (!session) return <div className="container"><div className="page-hero"><span className="eyebrow">White Label</span><h1>پرتال اختصاصی سازمان</h1><p>برای مشاهده یا پیکربندی هویت برند، دامنه و خدمات مجاز، وارد شوید.</p><a className="button primary" href="/login?redirect=/white-label">ورود سازمانی</a></div></div>;
  if (err) return <div className="container"><p role="alert" className="rounded-2xl bg-rose-50 p-6 text-rose-700">خطای {err.status}: {err.message}</p></div>;

  const services = form.enabled_services || [];
  const toggleSvc = (svc: string) => setForm(f => ({ ...f, enabled_services: (f.enabled_services || []).includes(svc) ? (f.enabled_services || []).filter(x => x !== svc) : [...(f.enabled_services || []), svc] }));

  return <div className="container" style={{ maxWidth: 820 }}>
    <div className="page-hero"><span className="eyebrow">White Label · پیکربندی tenant</span>
      <h1>هویت برند و خدمات پرتال اختصاصی</h1>
      <p>{missing ? 'برای این tenant هنوز پیکربندی White Label ثبت نشده است.' : 'پیکربندی واقعی از سرویس tenant دریافت شد.'}
        {!canEdit && ' — فقط مدیر tenant می‌تواند تغییر دهد.'}</p></div>
    {notice && <p role="status" className="mb-4 rounded-xl bg-cyan-50 p-4 text-sm">{notice}</p>}

    {!missing && wl && <section className="panel mb-5">
      <h2 className="font-black">پیکربندی فعلی</h2>
      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <p><b>نام نمایشی:</b> {wl.display_name}</p>
        <p><b>دامنه اختصاصی:</b> {wl.custom_domain || '—'} {wl.domain_status && <span className="rounded bg-slate-200 px-2 text-xs">{wl.domain_status}</span>}</p>
        <p className="flex items-center gap-2"><b>رنگ اصلی:</b> <span className="inline-block h-4 w-4 rounded" style={{ background: wl.primary_color }} /> {wl.primary_color}</p>
        <p className="flex items-center gap-2"><b>رنگ دوم:</b> <span className="inline-block h-4 w-4 rounded" style={{ background: wl.secondary_color }} /> {wl.secondary_color}</p>
        <p><b>لوگو:</b> {wl.logo_reference || '—'}</p>
        <p><b>خدمات مجاز:</b> {wl.enabled_services.length ? wl.enabled_services.map(s => SVC_FA[s] || s).join('، ') : 'همه'}</p>
      </div>
    </section>}

    {canEdit
      ? <form onSubmit={save} className="panel">
          <h2 className="font-black">{missing ? 'ایجاد پیکربندی' : 'ویرایش پیکربندی'}</h2>
          <label className="mt-3 block font-bold">نام نمایشی
            <input className="mt-2 block w-full rounded-xl border p-3" required minLength={2} value={form.display_name || ''} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} /></label>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="font-bold">رنگ اصلی
              <input type="color" className="mt-2 block h-10 w-full rounded-xl border" value={form.primary_color || '#0E7490'} onChange={e => setForm(f => ({ ...f, primary_color: e.target.value }))} /></label>
            <label className="font-bold">رنگ دوم
              <input type="color" className="mt-2 block h-10 w-full rounded-xl border" value={form.secondary_color || '#B65C2D'} onChange={e => setForm(f => ({ ...f, secondary_color: e.target.value }))} /></label>
          </div>
          <label className="mt-3 block font-bold">دامنه اختصاصی (اختیاری)
            <input className="mt-2 block w-full rounded-xl border p-3" placeholder="travel.example.ir" value={form.custom_domain || ''} onChange={e => setForm(f => ({ ...f, custom_domain: e.target.value }))} /></label>
          <label className="mt-3 block font-bold">مرجع لوگو (asset:// یا https://)
            <input className="mt-2 block w-full rounded-xl border p-3" value={form.logo_reference || ''} onChange={e => setForm(f => ({ ...f, logo_reference: e.target.value }))} /></label>
          <fieldset className="mt-3"><legend className="font-bold">خدمات مجاز</legend>
            <div className="mt-2 flex flex-wrap gap-3">{ALL_SERVICES.map(svc => <label key={svc} className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm">
              <input type="checkbox" checked={services.includes(svc)} onChange={() => toggleSvc(svc)} />{SVC_FA[svc]}</label>)}</div>
          </fieldset>
          <button className="button primary mt-4">ذخیره پیکربندی</button>
        </form>
      : <p className="rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-600">
          پیکربندی White Label فقط توسط مدیر tenant قابل تغییر است. این نسخه‌ی نمایش‌محور، پیکربندی واقعی tenant را نشان می‌دهد و هیچ مقدار ساختگی ندارد.
        </p>}
  </div>;
}
