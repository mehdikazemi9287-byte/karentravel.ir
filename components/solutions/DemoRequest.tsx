'use client';
/* Demo & price request: goes to the sales desk as a web_form case (same public intake as the trip request). */
import {useState, type FormEvent} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';

const PICKS = ['سایت', 'اتصال‌ها', 'قرارداد و صندوق', 'میز فروش', 'پیامک', 'حسابداری', 'باشگاه مشتریان', 'سفر سازمانی'];
type State = {kind: 'idle' | 'sending' | 'done'} | {kind: 'error'; message: string};

export function DemoRequest() {
  const {api} = useAuth();
  const [v, setV] = useState({customer_name: '', organization: '', mobile: '', city: '', consent: false, website: ''});
  const [picks, setPicks] = useState<string[]>(['سایت']);
  const [state, setState] = useState<State>({kind: 'idle'});
  async function submit(e: FormEvent) {
    e.preventDefault(); setState({kind: 'sending'});
    const description = [`مجموعه: ${v.organization}`, v.city && `شهر: ${v.city}`, `ماژول‌ها: ${picks.join('، ') || '—'}`].filter(Boolean).join(' | ');
    try {
      await api.publicPost('/public/sales-desk/requests', {customer_name: v.customer_name, mobile: v.mobile, trip: 'درخواست دمو و قیمت کارن تراول', travellers: 1, description, consent: v.consent, website: v.website || null});
      setState({kind: 'done'});
    } catch (x) {
      const s = x instanceof ApiError ? x.status : 0;
      setState({kind: 'error', message: s === 503 ? 'ثبت آنلاین فعلاً فعال نیست؛ لطفاً تماس بگیرید.' : s === 422 ? 'نام، موبایل و رضایت تماس را بررسی کنید.' : s === 429 ? 'امروز چند درخواست از این شماره ثبت شده است؛ کارشناس با شما تماس می‌گیرد.' : 'ثبت انجام نشد؛ دوباره تلاش کنید.'});
    }
  }
  if (state.kind === 'done') return <div className="so-form" role="status"><h3>درخواست شما رسید</h3><p>درخواست با کد پیگیری در میز گفتگو و فروش ثبت شد و کارشناس برای هماهنگی دمو تماس می‌گیرد.</p></div>;
  const set = (k: string) => (e: {target: {value: string}}) => setV({...v, [k]: e.target.value});
  return <form className="so-form" onSubmit={submit}>
    <h3>درخواست دمو و قیمت</h3>
    <div className="so-grid2">
      <label>نام و نام خانوادگی<input required minLength={2} value={v.customer_name} onChange={set('customer_name')} autoComplete="name"/></label>
      <label>نام آژانس یا سازمان<input required minLength={2} value={v.organization} onChange={set('organization')} autoComplete="organization"/></label>
      <label>موبایل<input required dir="ltr" inputMode="tel" placeholder="09xxxxxxxxx" value={v.mobile} onChange={set('mobile')} autoComplete="tel"/></label>
      <label>شهر<input value={v.city} onChange={set('city')}/></label>
    </div>
    <fieldset className="so-chips"><legend>به چه بخش‌هایی نیاز دارید؟</legend>{PICKS.map(p => <button type="button" key={p} aria-pressed={picks.includes(p)} onClick={() => setPicks(picks.includes(p) ? picks.filter(x => x !== p) : [...picks, p])}>{p}</button>)}</fieldset>
    <input className="so-hp" tabIndex={-1} autoComplete="off" aria-hidden="true" value={v.website} onChange={set('website')}/>
    <label className="so-consent"><input type="checkbox" checked={v.consent} onChange={e => setV({...v, consent: e.target.checked})} required/> با تماس کارشناس فروش موافقم.</label>
    <button className="so-btn" disabled={state.kind === 'sending'}>{state.kind === 'sending' ? 'در حال ارسال…' : 'ارسال درخواست'}</button>
    {state.kind === 'error' && <p className="so-err" role="alert">{state.message}</p>}
    <p className="so-muted">درخواست با کد پیگیری در میز گفتگو و فروش پرونده می‌شود.</p>
  </form>;
}
