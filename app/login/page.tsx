'use client';
import { FormEvent, Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ApiError } from '../../lib/api/karenseir-client';
import { useAuth } from '../../lib/api/auth-context';
import { ContactOptions } from '../../components/customer/CustomerHelp';
import { roleHome } from '../../lib/role-navigation';
import { Shell } from '../page';

// Phase 6: only a same-origin, in-app path (starting with a single "/") is
// ever honored as a post-login destination -- an absolute or protocol-
// relative value is refused so a crafted "?redirect=" query can never turn
// this into an open redirect.
function safeRedirectTarget(raw: string | null): string | null {
  if (!raw) return null;
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\') || /[\u0000-\u0020]/.test(raw)) return null;
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
  const [organizationLogin, setOrganizationLogin] = useState(false);
  const [organizationSlug, setOrganizationSlug] = useState('');
  const tenantSlug = organizationLogin ? organizationSlug : 'karenseir-consumer';
  const [identifier, setIdentifier] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [otp, setOtp] = useState('');
  const [busy,setBusy]=useState(false);
  const [message, setMessage] = useState('برای دریافت کد ورود، شماره همراه خود را وارد کنید.');
  async function requestCode(event: FormEvent) {
    event.preventDefault();
    if(busy)return;setBusy(true);
    try { const data = await requestOtp(tenantSlug, identifier); setChallengeId(data.challenge_id); setMessage('درخواست کد ثبت شد. کد دریافتی را وارد کنید؛ اگر پیامک نرسید، از پشتیبانی راهنمایی بگیرید.'); }
    catch (error) { setMessage(error instanceof ApiError ? 'درخواست ورود انجام نشد. کمی بعد دوباره تلاش کنید یا تماس بگیرید.' : 'درخواست ورود انجام نشد.'); } finally {setBusy(false)}
  }
  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    if(busy)return;setBusy(true);
    try {
      const authenticated = await verifyOtp(tenantSlug, challengeId, otp);
      // Phase 6: return the caller to whatever it was doing (e.g. the
      // Assistant's pending action) instead of stranding them here --
      // only ever a same-origin in-app path, never an external one.
      if (redirectTarget) { router.push(redirectTarget); return; }
      router.push(roleHome[authenticated.user?.role||'customer']||'/account');
    }
    catch (error) { setMessage(error instanceof ApiError ? 'کد ورود تأیید نشد؛ شماره و کد را بررسی کنید.' : 'کد ورود معتبر نیست.'); } finally {setBusy(false)}
  }
  return <Shell>
    <div className="page-hero">
      <span className="eyebrow">ورود / ثبت‌نام</span>
      <h1>با کد یک‌بارمصرف وارد شوید.</h1>
      <p>برای ورود به کد پیامکی نیاز دارید. اگر دریافت پیامک ممکن نشد، راه تماس با پشتیبانی در همین صفحه است.</p>
    </div>
    <div className="container" style={{ paddingBottom: 70, display: 'grid', gap: 12, maxWidth: 480 }}>
      <form onSubmit={requestCode} className="filters" style={{ display: 'grid', gap: 10 }}>
        <label><input type="checkbox" checked={organizationLogin} onChange={e => { setOrganizationLogin(e.target.checked); setChallengeId(''); }} /> ورود سازمانی</label>
        {organizationLogin && <label>سازمان<input value={organizationSlug} onChange={e => { setOrganizationSlug(e.target.value); setChallengeId(''); }} required autoComplete="organization" aria-label="سازمان" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>}
        <label>{organizationLogin?"شماره همراه یا شناسه ورود":"شماره همراه"}<input value={identifier} onChange={e => setIdentifier(e.target.value.replace(/[۰-۹]/g,c=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g,c=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))))} required inputMode={organizationLogin?"text":"tel"} pattern={organizationLogin?undefined:"09[0-9]{9}"} autoComplete="username" aria-label="شماره همراه یا شناسه ورود" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <button className="button primary" type="submit" disabled={busy}>دریافت کد ورود</button>
      </form>
      {challengeId && <form onSubmit={verifyCode} className="filters" style={{ display: 'grid', gap: 10 }}>
        <label>کد شش‌رقمی<input value={otp} onChange={e => setOtp(e.target.value.replace(/[۰-۹]/g, c => String("۰۱۲۳۴۵۶۷۸۹".indexOf(c))).replace(/[٠-٩]/g, c => String("٠١٢٣٤٥٦٧٨٩".indexOf(c))))} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required aria-label="کد شش‌رقمی" style={{ display: 'block', width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid var(--line)' }} /></label>
        <button className="button primary" type="submit" disabled={busy}>تأیید و ورود</button>
      </form>}
      <p role="status">{message}</p><p>اگر کد ورود به دستتان نرسید، برای راهنمایی تماس بگیرید.</p><ContactOptions/>
      <Link href={redirectTarget ? `/register?redirect=${encodeURIComponent(redirectTarget)}` : '/register'}>حساب ندارید؟ ثبت‌نام کنید</Link>
    </div>
  </Shell>;
}
