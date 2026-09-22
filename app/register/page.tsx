'use client';
import { FormEvent, Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError } from '../../lib/api/karenseir-client';
import { useAuth } from '../../lib/api/auth-context';
import { Shell } from '../page';

function safeRedirectTarget(raw: string | null): string | null {
  if (!raw) return null;
  if (!raw.startsWith('/') || raw.startsWith('//')) return null;
  return raw;
}

// Public B2C self-service registration. Mobile-first, OTP-verified, always
// assigned the fixed consumer tenant with role=customer server-side -- this
// page never chooses a tenant or role, it only collects a mobile number and
// an optional display name. Verification reuses the exact same OTP-verify
// step /login already uses (useAuth().verifyOtp), just fed the tenant_slug
// the register step returns instead of one typed by the user.
export default function RegisterPage() {
  return <Suspense fallback={null}><RegisterPageInner/></Suspense>;
}

function RegisterPageInner() {
  const { register, verifyOtp } = useAuth();
  const router = useRouter();
  const redirectTarget = safeRedirectTarget(useSearchParams().get('redirect'));
  const [mobile, setMobile] = useState('');
  const [name, setName] = useState('');
  const [tenantSlug, setTenantSlug] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [otp, setOtp] = useState('');
  const [message, setMessage] = useState('برای ساخت حساب کاربری، شماره همراه خود را وارد کنید.');

  async function requestCode(event: FormEvent) {
    event.preventDefault();
    try {
      const data = await register(mobile, name || undefined);
      setChallengeId(data.challenge_id);
      setTenantSlug(data.tenant_slug);
      setMessage('اگر شماره معتبر و سرویس پیامک متصل باشد، کد تأیید ارسال شده است.');
    } catch (error) { setMessage(error instanceof ApiError ? error.message : 'ثبت‌نام انجام نشد.'); }
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    try {
      await verifyOtp(tenantSlug, challengeId, otp);
      if (redirectTarget) { router.push(redirectTarget); return; }
      router.push('/account');
    } catch (error) { setMessage(error instanceof ApiError ? error.message : 'کد تأیید معتبر نیست.'); }
  }

  return <Shell>
    <div className="page-hero">
      <span className="eyebrow">ثبت‌نام</span>
      <h1>ساخت حساب کاربری جدید.</h1>
      <p>ثبت‌نام Production فقط از طریق کد پیامکی معتبر انجام می‌شود؛ بدون سرویس پیامک متصل، کد ارسال نمی‌شود.</p>
    </div>
    <div className="container" style={{ paddingBottom: 70, display: 'grid', gap: 12, maxWidth: 480 }}>
      <form onSubmit={requestCode} className="filters" style={{ display: 'grid', gap: 10 }}>
        <label>شماره همراه<input value={mobile} onChange={e => setMobile(e.target.value)} required autoComplete="tel" inputMode="tel" aria-label="شماره همراه" placeholder="09xxxxxxxxx" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <label>نام (اختیاری)<input value={name} onChange={e => setName(e.target.value)} autoComplete="name" aria-label="نام" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <button className="button primary" type="submit">دریافت کد تأیید</button>
      </form>
      {challengeId && <form onSubmit={verifyCode} className="filters" style={{ display: 'grid', gap: 10 }}>
        <label>کد شش‌رقمی<input value={otp} onChange={e => setOtp(e.target.value)} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required aria-label="کد شش‌رقمی" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <button className="button primary" type="submit">تأیید و ساخت حساب</button>
      </form>}
      <p role="status">{message}</p>
      <p><a href="/login">حساب دارید؟ ورود</a></p>
    </div>
  </Shell>;
}
