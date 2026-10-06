'use client';
/* «چه چیزی در سفر من تغییر کرده؟» (customer) and the Trip Operations Center (staff).
   Both render the same recorded trip events; nothing on this screen is inferred or generated. */
import Link from 'next/link';
import {FormEvent, useCallback, useEffect, useRef, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError, newId} from '../../lib/api/karenseir-client';
import {ErrorState} from './ConnectedViews';

type Values = Record<string, string> | null;
type Change = {id: string; trip_id: string; category: string | null; category_fa: string | null; severity: string; source: string; title: string; message: string; old_value: Values; new_value: Values;
  affected_reference: string | null; requires_action: boolean; created_at: string; acknowledged: boolean; acknowledged_at: string | null; visibility?: string; actor?: {name: string; role: string} | null};
type State<T> = {kind: 'loading'} | {kind: 'ready'; data: T} | {kind: 'error'; status: number};
const SOURCE_FA: Record<string, string> = {human_agent: 'کارشناس کارن‌سیر', supplier: 'تأمین‌کننده', provider: 'سامانهٔ تأمین‌کننده', system: 'سیستم', support: 'پشتیبانی'};
const SEVERITY_FA: Record<string, string> = {info: 'اطلاع', warning: 'مهم', critical: 'فوری'};
const tone = (s: string) => s === 'critical' ? 'border-rose-300 bg-rose-50' : s === 'warning' ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-slate-50';
const chip = (s: string) => s === 'critical' ? 'bg-rose-600 text-white' : s === 'warning' ? 'bg-amber-600 text-white' : 'bg-slate-200 text-slate-700';
const when = (iso: string) => new Date(iso).toLocaleString('fa-IR', {dateStyle: 'medium', timeStyle: 'short'});
const statusOf = (e: unknown) => e instanceof ApiError ? e.status : 503;

function Diff({oldValue, newValue}: {oldValue: Values; newValue: Values}) {
  const keys = Array.from(new Set([...Object.keys(oldValue ?? {}), ...Object.keys(newValue ?? {})]));
  if (!keys.length) return null;
  return <dl className="mt-3 grid gap-2 text-sm">{keys.map(k => <div key={k} className="grid grid-cols-1 gap-1 rounded-lg bg-white p-3 sm:grid-cols-[8rem_1fr_1fr]">
    <dt className="font-bold text-slate-700">{k}</dt>
    <dd className="min-w-0 break-words text-slate-500"><span className="text-xs">قبلی: </span>{oldValue?.[k] ? <span className="line-through">{oldValue[k]}</span> : '—'}</dd>
    <dd className="min-w-0 break-words font-bold text-slate-900"><span className="text-xs font-normal text-slate-500">جدید: </span>{newValue?.[k] ?? '—'}</dd></div>)}</dl>;
}

function ChangeCard({c, children}: {c: Change; children?: React.ReactNode}) {
  return <article className={`rounded-xl border p-4 ${tone(c.severity)}`} data-change-id={c.id}>
    <div className="flex flex-wrap items-center gap-2 text-xs"><span className={`rounded px-2 py-0.5 ${chip(c.severity)}`}>{SEVERITY_FA[c.severity] ?? c.severity}</span>
      <span className="rounded bg-white px-2 py-0.5 text-slate-700">منبع: {SOURCE_FA[c.source] ?? c.source}</span>{c.requires_action && <span className="rounded bg-amber-600 px-2 py-0.5 text-white">نیاز به اقدام</span>}
      {c.visibility === 'internal' && <span className="rounded bg-slate-700 px-2 py-0.5 text-white">داخلی</span>}<time className="text-slate-500" dateTime={c.created_at}>{when(c.created_at)}</time></div>
    <h3 className="mt-2 font-bold">{c.category_fa ?? c.title}</h3>
    <Diff oldValue={c.old_value} newValue={c.new_value}/>
    {c.affected_reference && <p className="mt-2 text-xs text-slate-500">رزرو مرتبط: <span dir="ltr">{c.affected_reference}</span></p>}
    {c.actor && <p className="mt-1 text-xs text-slate-500">ثبت‌کننده: {c.actor.name}</p>}
    {children}
  </article>;
}

export function TripChanges({tripId}: {tripId: string}) {
  const {api, session} = useAuth();
  const [state, setState] = useState<State<{unacknowledged: number; changes: Change[]}>>({kind: 'loading'});
  const [busy, setBusy] = useState('');
  const load = useCallback(() => api.get<{unacknowledged: number; changes: Change[]}>(`/trips/${tripId}/changes`), [api, tripId]);
  useEffect(() => {
    if (!session) return;
    let active = true;
    load().then(data => {if (active) setState({kind: 'ready', data});}).catch(e => {if (active) setState({kind: 'error', status: statusOf(e)});});
    return () => {active = false;};
  }, [session, load]);
  async function acknowledge(id: string) {
    setBusy(id);
    try {await api.post(`/trips/${tripId}/events/${id}/acknowledge`, {}); setState({kind: 'ready', data: await load()});} catch (e) {setState({kind: 'error', status: statusOf(e)});} finally {setBusy('');}
  }
  if (!session) return null;
  return <section className="container customer-page" aria-labelledby="trip-changes-title">
    <h2 id="trip-changes-title" className="text-xl font-bold">تغییرهای ثبت‌شدهٔ سفر</h2>
    <p className="mt-1 text-sm text-slate-600">فقط تغییرهایی که از سوی تأمین‌کننده یا کارشناسان ثبت شده‌اند، با مقدار قبلی و جدید. چیزی در این بخش حدس زده نمی‌شود.</p>
    {state.kind === 'loading' && <div role="status" className="mt-4 animate-pulse rounded-2xl bg-white p-6 text-center text-slate-600">در حال دریافت تغییرهای ثبت‌شده…</div>}
    {state.kind === 'error' && <div role="alert" className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-800">{state.status === 404 ? 'این سفر در حساب شما نیست.' : state.status === 403 ? 'نقش شما به این بخش دسترسی ندارد.' : 'دریافت تغییرها انجام نشد. دوباره تلاش کنید.'}</div>}
    {state.kind === 'ready' && state.data.changes.length === 0 && <div role="status" className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-slate-600">تا این لحظه تغییری برای این سفر ثبت نشده است.</div>}
    {state.kind === 'ready' && state.data.changes.length > 0 && <>
      <p className="mt-3 text-sm font-bold" aria-live="polite">{state.data.unacknowledged > 0 ? `${state.data.unacknowledged.toLocaleString('fa-IR')} تغییر دیده‌نشده` : 'همهٔ تغییرها را دیده‌اید.'}</p>
      <div className="mt-3 grid gap-3">{state.data.changes.map(c => <ChangeCard key={c.id} c={c}>
        {c.acknowledged ? <p className="mt-3 text-xs text-emerald-700">دیده شد — {c.acknowledged_at ? when(c.acknowledged_at) : ''}</p>
          : <button type="button" className="button secondary mt-3" disabled={busy === c.id} onClick={() => void acknowledge(c.id)}>{busy === c.id ? 'در حال ثبت…' : 'دیدم و متوجه شدم'}</button>}
      </ChangeCard>)}</div></>}
  </section>;
}

type Center = {total: number; summary: {all: number; unacknowledged: number; critical_unacknowledged: number}; categories: Record<string, string>; items: Change[]};
type TripRow = {id: string; title: string; destination: string; customer_id: number};
const NEEDS_BOTH = ['schedule_change', 'hotel_change', 'room_change', 'transfer_change', 'tour_change', 'document_change'];

export function TripOpsCenter() {
  const {api, session} = useAuth();
  const [state, setState] = useState<State<Center>>({kind: 'loading'});
  const [trips, setTrips] = useState<TripRow[]>([]);
  const [filter, setFilter] = useState({category: '', severity: '', unacknowledged: false});
  const [notice, setNotice] = useState<{ok: boolean; text: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [category, setCategory] = useState('schedule_change');
  const key = useRef(newId());
  const load = useCallback((f = filter) => {
    const q = new URLSearchParams(); if (f.category) q.set('category', f.category); if (f.severity) q.set('severity', f.severity); if (f.unacknowledged) q.set('unacknowledged', 'true');
    return api.get<Center>(`/operations/trip-events?${q}`);
  }, [api, filter]);
  useEffect(() => {
    if (!session) return;
    let active = true;
    load().then(data => {if (active) setState({kind: 'ready', data});}).catch(e => {if (active) setState({kind: 'error', status: statusOf(e)});});
    api.get<TripRow[]>('/backoffice/trips').then(t => {if (active) setTrips(t);}).catch(() => {});
    return () => {active = false;};
  }, [api, session, load]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (busy) return;
    const form = e.currentTarget, v = Object.fromEntries(new FormData(form)) as Record<string, string>;
    const pair = (text: string) => text.trim() ? {[v.field.trim() || 'مقدار']: text.trim()} : null;
    setBusy(true); setNotice(null);
    try {
      await api.post(`/operations/trips/${v.trip}/events`, {command_id: key.current, category: v.category, severity: v.severity, source: v.source, old_value: pair(v.old_value), new_value: pair(v.new_value), reason: v.reason,
        requires_action: v.requires_action === 'on', visibility: v.internal === 'on' ? 'internal' : 'customer'});
      key.current = newId(); form.reset(); setCategory('schedule_change'); setState({kind: 'ready', data: await load()});
      setNotice({ok: true, text: 'تغییر ثبت شد و در خط زمانی سفر، پشتیبانی و اعلان‌های مشتری از همین رکورد خوانده می‌شود. تحویل پیامک یا پوش تضمین نشده است.'});
    } catch (err) {
      const raw = err instanceof ApiError ? err.detail : null; const detail = raw && typeof raw === "object" && "detail" in (raw as object) ? (raw as {detail?: unknown}).detail : raw ?? (err instanceof ApiError ? err.message : null);
      setNotice({ok: false, text: err instanceof ApiError && err.status === 403 ? 'اجازهٔ ثبت تغییر برای این حساب وجود ندارد.' : typeof detail === 'string' ? detail : 'ثبت تغییر تأیید نشد؛ ورودی‌ها را بررسی کنید.'});
      if (err instanceof ApiError && err.status < 500 && err.status !== 409) key.current = newId();
    } finally {setBusy(false);}
  }
  if (!session) return <ErrorState status={401} message="برای دسترسی به مرکز عملیات سفر وارد شوید."/>;
  if (state.kind === 'error') return <ErrorState status={state.status} message="دسترسی به مرکز عملیات سفر ممکن نیست."/>;
  const field = 'mt-1 w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2 text-sm';
  return <section className="container customer-page">
    <Link href="/backoffice">بازگشت به پنل عملیات</Link>
    <h1>مرکز عملیات سفر</h1>
    <p>هر تغییر سفر با زمان، ثبت‌کننده، منبع، مقدار قبلی و جدید ثبت می‌شود و مشتری، پشتیبانی و عملیات همان رکورد را می‌بینند.</p>
    {state.kind === 'loading' ? <div role="status" className="my-6 animate-pulse rounded-2xl bg-white p-6 text-center text-slate-600">در حال دریافت رویدادهای سفر…</div> : <>
      <dl className="my-4 grid grid-cols-3 gap-2 text-center text-sm">{[['همهٔ تغییرها', state.data.summary.all], ['دیده‌نشده توسط مشتری', state.data.summary.unacknowledged], ['فوریِ دیده‌نشده', state.data.summary.critical_unacknowledged]].map(([label, n]) =>
        <div key={label as string} className="rounded-xl bg-white p-3"><dt className="text-slate-500">{label}</dt><dd className="text-xl font-bold">{(n as number).toLocaleString('fa-IR')}</dd></div>)}</dl>
      <form className="my-4 grid gap-3 rounded-2xl bg-white p-4 sm:grid-cols-2" onSubmit={submit} aria-label="ثبت تغییر سفر">
        <h2 className="font-bold sm:col-span-2">ثبت تغییر تأییدشده</h2>
        <label className="text-sm">سفر مشتری<select name="trip" required className={field} defaultValue=""><option value="" disabled>انتخاب سفر</option>{trips.map(t => <option key={t.id} value={t.id}>{t.title} — {t.destination} — مشتری {t.customer_id}</option>)}</select></label>
        <label className="text-sm">نوع تغییر<select name="category" className={field} value={category} onChange={e => setCategory(e.target.value)}>{Object.entries(state.data.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="text-sm">اهمیت<select name="severity" className={field} defaultValue="warning">{Object.entries(SEVERITY_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="text-sm">منبع خبر<select name="source" className={field} defaultValue="supplier">{Object.entries(SOURCE_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="text-sm sm:col-span-2">عنوان مورد تغییریافته<input name="field" className={field} placeholder="مثلاً ساعت حرکت، نام هتل، نوع اتاق" maxLength={60}/></label>
        <label className="text-sm">مقدار قبلی<input name="old_value" className={field} maxLength={300} required={NEEDS_BOTH.includes(category) || category === 'cancellation'}/></label>
        <label className="text-sm">مقدار جدید<input name="new_value" className={field} maxLength={300} required={NEEDS_BOTH.includes(category)}/></label>
        <label className="text-sm sm:col-span-2">دلیل / مرجع<input name="reason" className={field} required minLength={3} maxLength={500}/></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="requires_action"/>مشتری باید اقدامی انجام دهد</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="internal"/>فقط داخلی (به مشتری نمایش داده نشود)</label>
        <button className="button primary sm:col-span-2" disabled={busy}>{busy ? 'در حال ثبت…' : 'ثبت تغییر'}</button>
        {notice && <p role={notice.ok ? 'status' : 'alert'} className={`rounded-xl p-3 text-sm sm:col-span-2 ${notice.ok ? 'bg-emerald-50 text-emerald-800' : 'bg-rose-50 text-rose-800'}`}>{notice.text}</p>}
      </form>
      <div className="my-4 flex flex-wrap items-end gap-3 text-sm" role="group" aria-label="فیلتر رویدادها">
        <label>نوع<select className={field} value={filter.category} onChange={e => setFilter({...filter, category: e.target.value})}><option value="">همه</option>{Object.entries(state.data.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>اهمیت<select className={field} value={filter.severity} onChange={e => setFilter({...filter, severity: e.target.value})}><option value="">همه</option>{Object.entries(SEVERITY_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="flex items-center gap-2 pb-2"><input type="checkbox" checked={filter.unacknowledged} onChange={e => setFilter({...filter, unacknowledged: e.target.checked})}/>فقط دیده‌نشده</label>
        <span className="pb-2 text-slate-500" aria-live="polite">{state.data.total.toLocaleString('fa-IR')} رویداد</span></div>
      {state.data.items.length === 0 ? <div role="status" className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-slate-600">رویدادی با این شرایط ثبت نشده است.</div>
        : <div className="grid gap-3">{state.data.items.map(c => <ChangeCard key={c.id} c={c}><p className="mt-2 text-xs text-slate-500">{c.visibility === 'internal' ? 'رویداد داخلی' : c.acknowledged ? `مشتری دیده است — ${c.acknowledged_at ? when(c.acknowledged_at) : ''}` : 'مشتری هنوز ندیده است'} · <Link href={`/backoffice/trips`}>سفر</Link></p></ChangeCard>)}</div>}
    </>}
  </section>;
}
