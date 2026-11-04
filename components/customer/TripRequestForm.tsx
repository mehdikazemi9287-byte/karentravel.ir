'use client';
/* "Request a trip" — goes to the sales desk as a web_form case. The visitor only gets a receipt; the desk calls back. */
import {useState, type FormEvent} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';

type State = {kind: 'idle' | 'sending' | 'done'} | {kind: 'error'; message: string};
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
      await api.publicPost('/public/sales-desk/requests', {...v, travellers: Number(v.travellers) || 1, travel_date: v.travel_date || null, description: v.description || null, website: v.website || null});
      setState({kind: 'done'}); setV({...blank, ...initial});
    } catch (x) {
      const status = x instanceof ApiError ? x.status : 0;
      setState({kind: 'error', message: status === 503 ? 'ثبت آنلاین درخواست فعلاً فعال نیست؛ لطفاً با پشتیبانی تماس بگیرید.' : status === 422 ? 'نام، شماره‌ی موبایل و سفر موردنظر را درست وارد کنید و رضایت تماس را تأیید کنید.' : status === 429 ? 'درخواست‌ها زیاد بوده؛ کمی بعد دوباره تلاش کنید.' : 'ارسال انجام نشد؛ اتصال را بررسی کنید.'});
    }
  }
  if (state.kind === 'done') return <article className="panel" role="status"><h2>درخواست شما رسید</h2><p>کارشناس فروش برای پیشنهاد گزینه‌ها با شماره‌ی شما تماس می‌گیرد. این پیام به معنی رزرو یا تأیید قیمت نیست.</p><button className="button secondary" onClick={() => setState({kind: 'idle'})}>ثبت درخواست دیگر</button></article>;
  return <article className="panel" id="request"><h2>{title}</h2>
    {!compact && <p>{intro ?? 'مقصد، تاریخ و تعداد مسافران را بنویسید تا کارشناس فروش بهترین گزینه‌ها را برایتان آماده کند.'}</p>}
    <form onSubmit={submit} noValidate={false}>
      <label>نام و نام خانوادگی<input required minLength={2} maxLength={160} value={v.customer_name} onChange={set('customer_name')} autoComplete="name"/></label>
      <label>شماره‌ی موبایل<input required inputMode="tel" dir="ltr" placeholder="09xxxxxxxxx" value={v.mobile} onChange={set('mobile')} autoComplete="tel"/></label>
      <label>سفر موردنظر<input required minLength={2} maxLength={240} placeholder="مثلاً مشهد ۳ شب" value={v.trip} onChange={set('trip')}/></label>
      <label>تاریخ تقریبی<input type="date" dir="ltr" value={v.travel_date} onChange={set('travel_date')}/></label>
      <label>تعداد مسافر<input type="number" min={1} max={100} value={v.travellers} onChange={set('travellers')}/></label>
      <label style={{flexBasis: '100%'}}>توضیحات<input maxLength={1000} value={v.description} onChange={set('description')}/></label>
      <label aria-hidden="true" style={{position: 'absolute', left: '-10000px', width: 1, height: 1, overflow: 'hidden'}}>وب‌سایت<input tabIndex={-1} autoComplete="off" value={v.website} onChange={set('website')}/></label>
      <label style={{flexBasis: '100%', display: 'flex', gap: 8, alignItems: 'center'}}><input type="checkbox" required checked={v.consent} onChange={set('consent')} style={{width: 'auto'}}/>موافقم کارشناس کارن‌سیر برای همین درخواست با من تماس بگیرد.</label>
      <button className="button primary" disabled={state.kind === 'sending'}>{state.kind === 'sending' ? 'در حال ارسال…' : 'ارسال درخواست'}</button>
    </form>
    {state.kind === 'error' && <p role="alert" style={{color: '#b3261e'}}>{state.message}</p>}
  </article>;
}
