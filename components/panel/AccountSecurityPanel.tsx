'use client';
/* Authenticator-app two-step login: setup with QR, enable with a code, one-time recovery codes, disable. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Stats, dateFa, errorOf, fa, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';

type Msg = {ok: boolean; text: string} | null;
const digits = (v: string) => v.replace(/[۰-۹]/g, c => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g, c => String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))).replace(/\D/g, '').slice(0, 6);

function RecoveryCodes({codes, done}: {codes: string[]; done: () => void}) {
  return <Card title="کدهای بازیابی (فقط همین یک بار نمایش داده می‌شوند)">
    <p className="pn-note">این ۱۰ کد را چاپ کنید یا جای امنی نگه دارید. اگر گوشی در دسترس نبود، با هر کد یک بار می‌توانید وارد شوید.</p>
    <ol className="sec-codes" dir="ltr">{codes.map(c => <li key={c}><code>{c}</code></li>)}</ol>
    <div className="sec-actions"><button className="pn-btn ghost" type="button" onClick={() => void navigator.clipboard?.writeText(codes.join('\n'))}>کپی</button><button className="pn-btn" type="button" onClick={done}>ذخیره کردم</button></div>
  </Card>;
}

export function AccountSecurity() {
  const {state, reload, api} = useLoad<Row>('/me/2fa');
  const [setup, setSetup] = useState<Row | null>(null);
  const [code, setCode] = useState(''); const [recovery, setRecovery] = useState('');
  const [codes, setCodes] = useState<string[] | null>(null);
  const [msg, setMsg] = useState<Msg>(null);
  async function run(fn: () => Promise<void>) {setMsg(null); try {await fn();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  const start = () => run(async () => {setSetup(await api.post<Row>('/me/2fa/setup', {})); setCode('');});
  const enable = (e: FormEvent) => {e.preventDefault(); void run(async () => {const r = await api.post<Row>('/me/2fa/enable', {code}); setSetup(null); setCode(''); setCodes(r.recovery_codes); setMsg({ok: true, text: 'ورود دومرحله‌ای فعال شد.'}); reload();});};
  const regen = (e: FormEvent) => {e.preventDefault(); void run(async () => {const r = await api.post<Row>('/me/2fa/recovery-codes', {code}); setCode(''); setCodes(r.recovery_codes); reload();});};
  const disable = (e: FormEvent) => {e.preventDefault(); void run(async () => {await api.post('/me/2fa/disable', recovery ? {recovery_code: recovery} : {code}); setCode(''); setRecovery(''); setMsg({ok: true, text: 'ورود دومرحله‌ای غیرفعال شد.'}); reload();});};
  if (codes) return <RecoveryCodes codes={codes} done={() => setCodes(null)}/>;
  return <Async state={state}>{s => <>
    <Stats items={[{label: 'وضعیت', value: s.enabled ? 'فعال' : 'غیرفعال', hint: s.enabled_at ? `از ${dateFa(s.enabled_at)}` : undefined}, {label: 'کد بازیابی باقی‌مانده', value: s.enabled ? fa(s.recovery_codes_left) : '—'}]}/>
    <Note msg={msg}/>
    {!s.enabled && !setup && <Card title="فعال‌سازی">
      <ol className="sec-steps"><li>برنامه‌ی Google Authenticator (یا هر برنامه‌ی سازگار) را روی گوشی نصب کنید.</li><li>کد QR را اسکن کنید.</li><li>کد شش‌رقمی برنامه را وارد کنید و کدهای بازیابی را نگه دارید.</li></ol>
      <div><button className="pn-btn" type="button" onClick={() => void start()}>شروع راه‌اندازی</button></div></Card>}
    {!s.enabled && setup && <Card title="اسکن کد QR">
      <div className="sec-setup"><div className="sec-qr" role="img" aria-label="کد QR برای برنامه‌ی Authenticator" dangerouslySetInnerHTML={{__html: setup.qr_svg}}/>
        <div className="sec-manual"><p className="pn-muted">اگر اسکن ممکن نیست، این کلید را دستی وارد کنید (نوع: بر پایه‌ی زمان):</p><code dir="ltr">{setup.secret}</code><p className="pn-muted">حساب: <span dir="ltr">{setup.account}</span></p>
          <form className="pn-form" onSubmit={enable}><label>کد شش‌رقمی برنامه<input className="pn-ltr" value={code} onChange={e => setCode(digits(e.target.value))} inputMode="numeric" autoComplete="one-time-code" required pattern="[0-9]{6}"/></label><button className="pn-btn">تأیید و فعال‌سازی</button></form></div></div>
    </Card>}
    {s.enabled && <div className="ops-grid">
      <Card title="کدهای بازیابی تازه"><form className="pn-form" onSubmit={regen}><p className="pn-muted">کدهای قبلی باطل می‌شوند.</p><label>کد شش‌رقمی برنامه<input className="pn-ltr" value={code} onChange={e => setCode(digits(e.target.value))} inputMode="numeric" required pattern="[0-9]{6}"/></label><button className="pn-btn">ساخت ۱۰ کد تازه</button></form></Card>
      <Card title="غیرفعال‌سازی"><form className="pn-form" onSubmit={disable}><p className="pn-muted">با کد برنامه یا یکی از کدهای بازیابی.</p>
        <label>کد برنامه<input className="pn-ltr" value={code} onChange={e => setCode(digits(e.target.value))} inputMode="numeric" pattern="[0-9]{6}"/></label>
        <label>یا کد بازیابی<input className="pn-ltr" value={recovery} onChange={e => setRecovery(e.target.value.trim())} maxLength={12}/></label>
        <button className="pn-btn ghost">غیرفعال کن</button></form></Card>
    </div>}
  </>}</Async>;
}
