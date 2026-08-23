'use client';

import Link from 'next/link';
import { FormEvent, useState } from 'react';
import { ApiError, newId } from '../../lib/api/karenseir-client';
import { useAuth } from '../../lib/api/auth-context';

type Hotel = { id:number; name:string; city:string; rating:number; nightly_price:number; cancellation:string; inventory:number };

export default function PilotPage() {
  const { api, devLogin, requestOtp: sendOtp, verifyOtp: confirmOtp } = useAuth();
  const [email, setEmail] = useState('employee@aftab.test');
  const [tenantSlug, setTenantSlug] = useState('aftab-bank');
  const [identifier, setIdentifier] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [otp, setOtp] = useState('');
  const [token, setToken] = useState('');
  const [hotels, setHotels] = useState<Hotel[]>([]);
  const [message, setMessage] = useState('برای ورود آزمایشی، یکی از حساب‌های demo را انتخاب کنید.');
  async function login(event: FormEvent) {
    event.preventDefault();
    try {
      const data = await devLogin(email);
      setToken(data.access_token); setMessage(`خوش آمدید ${data.user?.name} — ${data.user?.tenant}`);
      setHotels(await api.get<Hotel[]>('/hotels'));
    } catch (error) { setMessage(error instanceof ApiError ? error.message : 'ورود ناموفق بود.'); }
  }
  async function requestOtp(event: FormEvent) {
    event.preventDefault();
    try { const data = await sendOtp(tenantSlug, identifier); setChallengeId(data.challenge_id); setMessage('اگر حساب معتبر و سرویس پیامک متصل باشد، کد ورود ارسال شده است.'); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : 'درخواست ورود انجام نشد.'); }
  }
  async function verifyOtp(event: FormEvent) {
    event.preventDefault();
    try { const data = await confirmOtp(tenantSlug, challengeId, otp); setToken(data.access_token); setMessage(`خوش آمدید ${data.user?.name} — ${data.user?.tenant}`); setHotels(await api.get<Hotel[]>('/hotels')); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : 'کد ورود معتبر نیست.'); }
  }
  async function request(hotelId:number) {
    try { const data = await api.post<{id:number}>('/bookings', { hotel_id:hotelId, nights:2 }, newId()); setMessage(`درخواست #${data.id} ثبت شد و در انتظار تأیید است.`); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : 'ثبت درخواست ناموفق بود.'); }
  }
  return <main className="min-h-screen bg-mist p-5 text-ink sm:p-10" dir="rtl"><div className="mx-auto max-w-4xl"><span className="eyebrow">پایلوت عملیاتی · اتصال به API</span><h1 className="mt-2 text-3xl font-black sm:text-4xl">رزرو هتل با جریان سازمانی</h1><p className="mt-2 text-sm text-slate-600">ورود Production فقط از OTP adapter انجام می‌شود و بدون credential معتبر fail-closed است.</p><form onSubmit={requestOtp} className="mt-7 grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft sm:grid-cols-3"><label className="text-sm font-bold">سازمان<input value={tenantSlug} onChange={e=>setTenantSlug(e.target.value)} className="mt-2 block w-full rounded-xl border border-slate-300 p-3" autoComplete="organization"/></label><label className="text-sm font-bold">شماره همراه یا شناسه ورود<input value={identifier} onChange={e=>setIdentifier(e.target.value)} className="mt-2 block w-full rounded-xl border border-slate-300 p-3" autoComplete="username" required/></label><button className="button primary self-end" type="submit">دریافت کد ورود</button></form>{challengeId&&<form onSubmit={verifyOtp} className="mt-3 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 sm:flex-row"><label className="flex-1 text-sm font-bold">کد شش‌رقمی<input value={otp} onChange={e=>setOtp(e.target.value)} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" className="mt-2 block w-full rounded-xl border border-slate-300 p-3" required/></label><button className="button primary self-end" type="submit">تأیید و ورود</button></form>}<form onSubmit={login} className="mt-3 flex flex-col gap-3 rounded-2xl border border-dashed border-slate-300 bg-white p-5 sm:flex-row"><label className="flex-1 text-sm font-bold">حساب آزمایشی توسعه<select value={email} onChange={e=>setEmail(e.target.value)} className="mt-2 block w-full rounded-xl border border-slate-300 p-3"><option>employee@aftab.test</option><option>welfare@aftab.test</option><option>employee@faraz.test</option><option>org-admin@aftab.test</option><option>supplier@aftab.test</option><option>agency@aftab.test</option><option>backoffice@aftab.test</option><option>finance@aftab.test</option></select></label><button className="button primary self-end" type="submit">ورود و دریافت هتل‌ها</button></form><div role="status" className="mt-4 rounded-xl bg-cyan-50 p-4 text-sm text-cyan-900">{message}</div>{token&&<nav aria-label="پنل‌های متصل" className="mt-4 flex flex-wrap gap-2"><Link className="button secondary" href="/search/results">جست‌وجوی یکپارچه</Link><Link className="button secondary" href="/trips">سفرهای من</Link><Link className="button secondary" href="/compare">مقایسه</Link><Link className="button secondary" href="/organization">سازمان</Link><Link className="button secondary" href="/supplier">تأمین‌کننده</Link><Link className="button secondary" href="/agency">آژانس</Link><Link className="button secondary" href="/backoffice">عملیات</Link></nav>}{token && <section className="mt-6 grid gap-4 sm:grid-cols-3">{hotels.map(h=><article className="rounded-2xl border border-slate-200 bg-white p-5" key={h.id}><span className="tag">موجودی دستی: {h.inventory}</span><h2 className="mt-3 text-lg font-black">{h.name}</h2><p className="text-sm text-slate-600">{h.city} · امتیاز {h.rating}</p><p className="mt-3 font-bold">{h.nightly_price.toLocaleString('fa-IR')} ریال</p><p className="text-xs text-slate-500">{h.cancellation}</p><button onClick={()=>request(h.id)} className="button primary mt-4 w-full">درخواست ۲ شب</button></article>)}</section>}</div></main>;
}
