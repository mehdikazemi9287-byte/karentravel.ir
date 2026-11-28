'use client';
import '../../components/marketplace/stitch-pages-2026-11.css';
import { FormEvent, Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ApiError, MfaRequiredError } from '../../lib/api/karenseir-client';
import { useAuth } from '../../lib/api/auth-context';
import { ContactOptions } from '../../components/customer/CustomerHelp';
import { roleHome } from '../../lib/role-navigation';
import { Shell } from '../root-pages';
import { MOBILE_VALIDITY, OTP_VALIDITY, persianValidity } from '../../lib/form-validity';
import { supportPhone } from '../../lib/site-contact';

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
  const { requestOtp, verifyOtp, verifyMfa, passwordLogin } = useAuth();
  const router = useRouter();
  const redirectTarget = safeRedirectTarget(useSearchParams().get('redirect'));
  const [organizationLogin, setOrganizationLogin] = useState(false);
  const [organizationSlug, setOrganizationSlug] = useState('');
  const tenantSlug = organizationLogin ? organizationSlug : 'karenseir-consumer';
  const [identifier, setIdentifier] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [otp, setOtp] = useState('');
  const [busy,setBusy]=useState(false);
  const [mfaTicket, setMfaTicket] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const [message, setMessage] = useState('برای دریافت کد ورود، شماره همراه خود را وارد کنید.');
  // Staff fixed-password login (owner request 1405-09-08; docs/ops/STAFF_PASSWORD_LOGIN.md). The password is set only
  // from the server console; the session is stored exactly like an OTP login (passwordLogin -> setSession).
  const [passwordMode, setPasswordMode] = useState(false);
  const [password, setPassword] = useState('');
  async function loginWithPassword(event: FormEvent) {
    event.preventDefault();
    if(busy)return;setBusy(true);
    try { const authenticated = await passwordLogin(organizationSlug.trim(), identifier.trim(), password); setPassword(''); finish(authenticated.user?.role); }
    catch (error) {
      if (error instanceof MfaRequiredError) { setPassword(''); setMfaTicket(error.ticket); setMessage('رمز تأیید شد. حالا کد شش‌رقمی برنامه‌ی Google Authenticator را وارد کنید.'); return; }
      setMessage(error instanceof ApiError && error.status === 429 ? 'تعداد تلاش‌ها زیاد است؛ یک دقیقه بعد دوباره تلاش کنید.' : 'ورود انجام نشد: نام کاربری یا رمز درست نیست، یا حساب موقتاً قفل است.');
    } finally {setBusy(false)}
  }
  function togglePasswordMode() {
    setPasswordMode(!passwordMode); setChallengeId(''); setOtp(''); setPassword('');
    setMessage(passwordMode ? 'برای دریافت کد ورود، شماره همراه خود را وارد کنید.' : 'ورود با رمز فقط برای حساب‌های کارکنان است که رمزشان از سرور تنظیم شده است.');
  }
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
      finish(authenticated.user?.role);
    }
    catch (error) {
      if (error instanceof MfaRequiredError) { setMfaTicket(error.ticket); setMessage('کد پیامکی تأیید شد. حالا کد شش‌رقمی برنامه‌ی Google Authenticator را وارد کنید.'); return; }
      setMessage(error instanceof ApiError ? 'کد ورود تأیید نشد؛ شماره و کد را بررسی کنید.' : 'کد ورود معتبر نیست.');
    } finally {setBusy(false)}
  }
  function finish(role?: string) {
    // Phase 6: return the caller to whatever it was doing (e.g. the
    // Assistant's pending action) instead of stranding them here --
    // only ever a same-origin in-app path, never an external one.
    if (redirectTarget) { router.push(redirectTarget); return; }
    router.push(roleHome[role||'customer']||'/account');
  }
  async function verifySecondStep(event: FormEvent) {
    event.preventDefault();
    if(busy)return;setBusy(true);
    try { const authenticated = await verifyMfa(tenantSlug, mfaTicket, useRecovery ? { recovery_code: mfaCode.trim() } : { code: mfaCode }); finish(authenticated.user?.role); }
    catch (error) {
      const status = error instanceof ApiError ? error.status : 0;
      if (status === 423) setMessage('به‌خاطر کدهای اشتباه، حساب تا ۱۵ دقیقه قفل است.');
      else if (status === 401 && /مهلت/.test(error instanceof Error ? error.message : '')) { setMfaTicket(''); setChallengeId(''); setMessage('مهلت ورود تمام شد؛ دوباره کد پیامکی بگیرید.'); }
      else setMessage(useRecovery ? 'کد بازیابی درست نیست یا قبلاً استفاده شده است.' : 'کد برنامه درست نیست؛ ساعت گوشی را بررسی کنید.');
    } finally {setBusy(false)}
  }
  const step = mfaTicket ? 'mfa' : passwordMode ? 'password' : challengeId ? 'otp' : 'phone';
  // Stitch 2026-11 screen _17 (design/stitch/screens/_17): two-column card — brand panel + form.
  // Content is factual only: no invented traveller counts, ratings or guarantees.
  return <Shell>
    <section className="ks-login" aria-labelledby="ks-login-title">
      <div className="ks-login-card">
        <aside className="ks-login-brand">
          <div className="ks-login-brand-top"><span className="ks-login-chip">یزد، شهر بادگیرها</span></div>
          <div className="ks-login-brand-copy">
            <span className="ks-login-rule" aria-hidden="true"/>
            <span className="ks-login-kicker">کارن تراول</span>
            <h2>«سفرت را یک‌جا برنامه‌ریزی کن؛ پرواز، هتل، تور و قطار»</h2>
            <p>با یک حساب، خریدها، بلیت‌ها و درخواست‌های سفرت را در «حساب من» پیگیری کن.</p>
          </div>
          <ul className="ks-login-perks">
            <li><span aria-hidden="true">☎</span><b>پشتیبانی کارشناس</b><small>پیش و پس از خرید</small></li>
            <li><span aria-hidden="true">✓</span><b>قوانین هر نرخ</b><small>پیش از پرداخت دیده می‌شود</small></li>
            <li><span aria-hidden="true">⌂</span><b>پیگیری در حساب من</b><small>وضعیت پرداخت و صدور</small></li>
          </ul>
        </aside>
        <div className="ks-login-form">
          <header className="ks-login-head">
            <span className="ks-login-logo" aria-hidden="true">✈</span>
            <div><strong>کارن تراول</strong><small>ورود امن با کد یک‌بارمصرف</small></div>
          </header>
          <h1 id="ks-login-title">ورود یا ثبت‌نام</h1>
          <p className="ks-login-lead">{step==='phone' ? 'برای رزرو و پیگیری بلیت‌ها، شماره همراه خود را وارد کنید. کد تأیید با پیامک فرستاده می‌شود.' : step==='otp' ? 'کد شش‌رقمی پیامک‌شده را وارد کنید.' : step==='password' ? 'ورود کارکنان با نام کاربری و رمز.' : 'ورود دومرحله‌ای حساب شما فعال است.'}</p>
          {step==='password' && <form onSubmit={loginWithPassword} className="ks-login-fields" aria-label="ورود با رمز">
            <label className="ks-field"><span>سازمان</span><input value={organizationSlug} onChange={e => setOrganizationSlug(e.target.value)} required {...persianValidity({missing:'نام کاربری سازمان را وارد کنید.'})} autoComplete="organization" aria-label="سازمان" dir="ltr"/></label>
            <label className="ks-field"><span>شماره همراه یا ایمیل</span><input value={identifier} onChange={e => setIdentifier(e.target.value.replace(/[۰-۹]/g, c => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g, c => String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))))} required {...persianValidity({missing:'شماره همراه یا ایمیل را وارد کنید.'})} autoComplete="username" aria-label="شماره همراه یا ایمیل" dir="ltr"/></label>
            <label className="ks-field"><span>رمز</span><input type="password" value={password} onChange={e => setPassword(e.target.value)} required maxLength={256} {...persianValidity({missing:'رمز را وارد کنید.'})} autoComplete="current-password" aria-label="رمز" dir="ltr"/></label>
            <button className="ks-login-submit" type="submit" disabled={busy}>ورود <span aria-hidden="true">←</span></button>
          </form>}
          {(step==='phone' || step==='otp') && <form onSubmit={challengeId ? verifyCode : requestCode} className="ks-login-fields">
            <label className="ks-login-check"><input type="checkbox" checked={organizationLogin} onChange={e => { setOrganizationLogin(e.target.checked); setChallengeId(''); }} /> ورود شرکتی و سازمانی</label>
            {organizationLogin && <label className="ks-field"><span>سازمان</span><input value={organizationSlug} onChange={e => { setOrganizationSlug(e.target.value); setChallengeId(''); }} required {...persianValidity({missing:'نام کاربری سازمان را وارد کنید.'})} autoComplete="organization" aria-label="سازمان"/></label>}
            <label className="ks-field"><span>{organizationLogin?"شماره همراه یا شناسه ورود":"شماره موبایل"}{!organizationLogin && <small>مثال: ۰۹۱۲۳۴۵۶۷۸۹</small>}</span>
              <span className="ks-phone">{!organizationLogin && <span className="ks-phone-cc" dir="ltr">+98</span>}<input value={identifier} readOnly={!!challengeId} onChange={e => setIdentifier(e.target.value.replace(/[۰-۹]/g, c => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g, c => String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))))} required inputMode={organizationLogin?"text":"tel"} pattern={organizationLogin?undefined:"09[0-9]{9}"} {...persianValidity(organizationLogin?{missing:'شماره همراه یا شناسه ورود را وارد کنید.'}:MOBILE_VALIDITY)} autoComplete="username" aria-label="شماره همراه یا شناسه ورود" dir="ltr"/></span></label>
            {challengeId && <>
              <div className="ks-otp-head"><span>کد تأیید پیامک‌شده</span><button type="button" className="ks-link" onClick={() => { setChallengeId(''); setOtp(''); }}>ویرایش شماره</button></div>
              <input className="ks-otp" value={otp} onChange={e => setOtp(e.target.value.replace(/[۰-۹]/g, c => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g, c => String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))))} inputMode="numeric" pattern="[0-9]{6}" {...persianValidity(OTP_VALIDITY)} maxLength={6} autoComplete="one-time-code" required aria-label="کد شش‌رقمی" dir="ltr" autoFocus/>
              <button type="button" className="ks-link ks-resend" disabled={busy} onClick={e => void requestCode(e as unknown as FormEvent)}>ارسال دوباره پیامک</button>
            </>}
            <p className="ks-login-terms">ورود شما به معنای پذیرش <Link href="/terms">قوانین و مقررات</Link> و <Link href="/privacy">حریم خصوصی</Link> کارن تراول است.</p>
            <button className="ks-login-submit" type="submit" disabled={busy}>{challengeId ? 'تأیید و ورود' : 'دریافت رمز یک‌بارمصرف'} <span aria-hidden="true">←</span></button>
          </form>}
          {step==='mfa' && <form onSubmit={verifySecondStep} className="ks-login-fields" aria-label="ورود دومرحله‌ای">
            <label className="ks-field"><span>{useRecovery ? 'کد بازیابی (مثل ABCD-EF23)' : 'کد شش‌رقمی برنامه‌ی Authenticator'}</span><input className={useRecovery ? undefined : 'ks-otp'} value={mfaCode} onChange={e => setMfaCode(useRecovery ? e.target.value : e.target.value.replace(/[۰-۹]/g, c => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g, c => String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))))} inputMode={useRecovery ? 'text' : 'numeric'} pattern={useRecovery ? undefined : '[0-9]{6}'} {...persianValidity(useRecovery?{missing:'کد بازیابی را وارد کنید.'}:{missing:'کد شش‌رقمی برنامه را وارد کنید.',pattern:'کد برنامه باید ۶ رقم باشد.'})} maxLength={useRecovery ? 12 : 6} autoComplete="one-time-code" required aria-label={useRecovery ? 'کد بازیابی' : 'کد برنامه'} dir="ltr"/></label>
            <button className="ks-login-submit" type="submit" disabled={busy}>تأیید و ورود <span aria-hidden="true">←</span></button>
            <button className="ks-link" type="button" onClick={() => { setUseRecovery(!useRecovery); setMfaCode(''); }}>{useRecovery ? 'استفاده از کد برنامه' : 'گوشی در دسترس نیست؟ کد بازیابی'}</button>
          </form>}
          <p role="status" className="ks-login-status">{message}</p>
          {step!=='mfa' && <div className="ks-login-alt"><button type="button" className="ks-link" onClick={togglePasswordMode}>{passwordMode ? 'ورود با کد پیامکی' : 'ورود کارکنان با رمز'}</button></div>}
          <div className="ks-login-alt"><Link href={redirectTarget ? `/register?redirect=${encodeURIComponent(redirectTarget)}` : '/register'}>حساب ندارید؟ ثبت‌نام کنید</Link></div>
          <footer className="ks-login-foot"><a href={supportPhone.href}><span aria-hidden="true">☎</span> پشتیبانی <b dir="ltr">{supportPhone.display}</b></a><span>اگر پیامک نرسید، تماس بگیرید.</span></footer>
          <details className="ks-login-help"><summary>راه‌های دیگر تماس</summary><ContactOptions/></details>
        </div>
      </div>
    </section>
  </Shell>;
}
