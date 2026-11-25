'use client';
import {JalaliDateInput} from '../forms/JalaliDateInput';
/* "Request a trip" — goes to the sales desk as a web_form case. The visitor only gets a receipt; the desk calls back. */
import {useState, type FormEvent} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';
import {INACTIVE_TEXT, INACTIVE_TITLE, requestOutcome, type RequestOutcome} from '../../lib/trip-request';
import {supportPhone} from '../../lib/site-contact';

type State = {kind: 'idle' | 'sending'} | RequestOutcome;
const blank = {customer_name: '', mobile: '', trip: '', travel_date: '', travellers: '1', description: '', consent: false, website: ''};

type Initial = Partial<Pick<typeof blank, 'trip' | 'travel_date' | 'travellers' | 'description'>>;

export function TripRequestForm({compact = false, initial, title = 'درخواست سفر و مشاوره', intro}: {compact?: boolean; initial?: Initial; title?: string; intro?: string}) {
  const {api} = useAuth();
  const [v, setV] = useState({...blank, ...initial});
  const [state, setState] = useState<State>({kind: 'idle'});
  const set = (k: keyof typeof blank) => (e: {target: {value: string; checked?: boolean; type?: string}}) => setV({...v, [k]: e.target.type === 'checkbox' ? !!e.target.checked : e.target.value});
  async function submit(e: FormEvent) {
    e.preventDefault(); setState({kind: 'sending'});
    try {
      const body = await api.publicPost<unknown>('/public/sales-desk/requests', {...v, travellers: Number(v.travellers) || 1, travel_date: v.travel_date || null, description: v.description || null, website: v.website || null});
      const outcome = requestOutcome({status: 200, body});
      setState(outcome); if (outcome.kind === 'done') setV({...blank, ...initial});
    } catch (x) {
      // The entered values stay in the form on every failure, so nothing has to be typed again.
      setState(requestOutcome({status: x instanceof ApiError ? x.status : 0}));
    }
  }
  if (state.kind === 'done') return <article className="panel" role="status"><h2>درخواست شما رسید</h2><p>کارشناس فروش برای پیشنهاد گزینه‌ها با شماره‌ی شما تماس می‌گیرد. این پیام به معنی رزرو یا تأیید قیمت نیست.</p><button className="button secondary" onClick={() => setState({kind: 'idle'})}>ثبت درخواست دیگر</button></article>;
  return <article className="panel" id="request"><h2>{title}</h2>
    {!compact && <p>{intro ?? 'مقصد، تاریخ و تعداد مسافران را بنویسید تا کارشناس فروش بهترین گزینه‌ها را برایتان آماده کند.'}</p>}
    <form onSubmit={submit} noValidate={false}>
      <label>نام و نام خانوادگی<input required minLength={2} maxLength={160} value={v.customer_name} onChange={set('customer_name')} autoComplete="name"/></label>
      <label>شماره‌ی موبایل<input required inputMode="tel" dir="ltr" placeholder="09xxxxxxxxx" value={v.mobile} onChange={set('mobile')} autoComplete="tel"/></label>
      <label>سفر موردنظر<input required minLength={2} maxLength={240} placeholder="مثلاً مشهد ۳ شب" value={v.trip} onChange={set('trip')}/></label>
      <label>تاریخ تقریبی<JalaliDateInput value={v.travel_date} onChange={set('travel_date')}/></label>
      <label>تعداد مسافر<input type="number" min={1} max={100} value={v.travellers} onChange={set('travellers')}/></label>
      <label style={{flexBasis: '100%'}}>توضیحات<input maxLength={1000} value={v.description} onChange={set('description')}/></label>
      <label aria-hidden="true" style={{position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0 0 0 0)', clipPath: 'inset(50%)', whiteSpace: 'nowrap', border: 0}}>وب‌سایت<input tabIndex={-1} autoComplete="off" value={v.website} onChange={set('website')}/></label>
      <label style={{flexBasis: '100%', display: 'flex', gap: 8, alignItems: 'center'}}><input type="checkbox" required checked={v.consent} onChange={set('consent')} style={{width: 'auto'}}/>موافقم کارشناس کارن تراول برای همین درخواست با من تماس بگیرد.</label>
      <button className="button primary" disabled={state.kind === 'sending'}>{state.kind === 'sending' ? 'در حال ارسال…' : 'ارسال درخواست'}</button>
    </form>
    {state.kind === 'error' && <p role="alert" style={{color: '#b3261e'}}>{state.message}</p>}
    {state.kind === 'inactive' && <div role="alert" data-request-state="inactive"><p><b>{INACTIVE_TITLE}</b></p><p>{INACTIVE_TEXT}</p><a className="button secondary" href={supportPhone.href}>تماس با پشتیبانی <span dir="ltr">{supportPhone.display}</span></a></div>}
  </article>;
}
