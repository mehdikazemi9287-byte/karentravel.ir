'use client';
import { FormEvent, Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError } from '../../lib/api/karenseir-client';
import { useAuth } from '../../lib/api/auth-context';
import { Shell } from '../page';

// Phase 6: only a same-origin, in-app path (starting with a single "/") is
// ever honored as a post-login destination -- an absolute or protocol-
// relative value is refused so a crafted "?redirect=" query can never turn
// this into an open redirect.
function safeRedirectTarget(raw: string | null): string | null {
  if (!raw) return null;
  if (!raw.startsWith('/') || raw.startsWith('//')) return null;
  return raw;
}

// Real public login entry point. Before this page existed, the site-wide "ورود /
// ثبت‌نام" button (and every other "please sign in" prompt across the app) linked
// straight to /employee, which itself gated to /pilot - an internal ops/dev page
// that, alongside the real OTP form, also exposes a "حساب آزمایشی توسعه" dropdown
// listing partner-tenant test emails (aftab-bank, faraz-industries, ...) with no
// auth wall on the page itself. That dev-login POST does correctly 404 in this
// environment (ENVIRONMENT=production on the live API, confirmed directly), so it
// was never a real auth bypass - but a public visitor should never be routed
// through an internal pilot/test screen just to sign in. This page reuses the
// exact same real OTP mechanism /pilot already used (useAuth().requestOtp /
// verifyOtp - unchanged, no new backend code), with the dev-login shortcut and the
// test-account list left out entirely. /pilot and /employee still exist unchanged
// for whoever already knows those URLs; only the public "please log in" paths
// (this button, the generic 401 gate, and the two anonymous-search-results CTAs)
// now point here instead.
export default function LoginPage() {
  return <Suspense fallback={null}><LoginPageInner/></Suspense>;
}

function LoginPageInner() {
  const { requestOtp, verifyOtp } = useAuth();
  const router = useRouter();
  const redirectTarget = safeRedirectTarget(useSearchParams().get('redirect'));
  const [tenantSlug, setTenantSlug] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [otp, setOtp] = useState('');
  const [message, setMessage] = useState('برای دریافت کد ورود، سازمان و شماره همراه یا شناسه ورود خود را وارد کنید.');
  async function requestCode(event: FormEvent) {
    event.preventDefault();
    try { const data = await requestOtp(tenantSlug, identifier); setChallengeId(data.challenge_id); setMessage('اگر حساب معتبر و سرویس پیامک متصل باشد، کد ورود ارسال شده است.'); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : 'درخواست ورود انجام نشد.'); }
  }
  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    try {
      await verifyOtp(tenantSlug, challengeId, otp);
      // Phase 6: return the caller to whatever it was doing (e.g. the
      // Assistant's pending action) instead of stranding them here --
      // only ever a same-origin in-app path, never an external one.
      if (redirectTarget) { router.push(redirectTarget); return; }
      setMessage('ورود موفق بود.');
    }
    catch (error) { setMessage(error instanceof ApiError ? error.message : 'کد ورود معتبر نیست.'); }
  }
  return <Shell>
    <div className="page-hero">
      <span className="eyebrow">ورود / ثبت‌نام</span>
      <h1>با کد یک‌بارمصرف وارد شوید.</h1>
      <p>ورود Production فقط از طریق OTP معتبر انجام می‌شود؛ بدون سرویس پیامک متصل، کد ارسال نمی‌شود.</p>
    </div>
    <div className="container" style={{ paddingBottom: 70, display: 'grid', gap: 12, maxWidth: 480 }}>
      <form onSubmit={requestCode} className="filters" style={{ display: 'grid', gap: 10 }}>
        <label>سازمان<input value={tenantSlug} onChange={e => setTenantSlug(e.target.value)} required autoComplete="organization" aria-label="سازمان" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <label>شماره همراه یا شناسه ورود<input value={identifier} onChange={e => setIdentifier(e.target.value)} required autoComplete="username" aria-label="شماره همراه یا شناسه ورود" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <button className="button primary" type="submit">دریافت کد ورود</button>
      </form>
      {challengeId && <form onSubmit={verifyCode} className="filters" style={{ display: 'grid', gap: 10 }}>
        <label>کد شش‌رقمی<input value={otp} onChange={e => setOtp(e.target.value)} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required aria-label="کد شش‌رقمی" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <button className="button primary" type="submit">تأیید و ورود</button>
      </form>}
      <p role="status">{message}</p>
    </div>
  </Shell>;
}
