'use client';
/* Sends a request to a partner site (Padvira or Gift Asan) through KarenSeir, so it is tracked under حساب من. */
import Link from 'next/link';
import {useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';

type Props = {partner: 'padvira' | 'giftasan'; service: string; city?: string; onClose?: () => void};

export function PartnerRequestForm({partner, service, city, onClose}: Props) {
  const {session, api} = useAuth();
  const [v, setV] = useState({full_name: '', contact: '', message: '', category: 'family', items: '', deliver_to: '', note: ''});
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [done, setDone] = useState<string | null>(null);
  const here = typeof window === 'undefined' ? '/' : window.location.pathname;
  if (!session) return <div className="prf"><p>برای ثبت درخواست و پیگیری آن در حسابتان، وارد شوید.</p><Link className="prf-btn" href={`/login?redirect=${encodeURIComponent(here)}`}>ورود یا ثبت‌نام</Link></div>;
  if (done) return <div className="prf prf-ok" role="status"><p>{done}</p><Link href="/account/partner-requests">پیگیری در حساب من ←</Link></div>;
  const set = (k: string, x: string) => setV({...v, [k]: x});
  async function send() {
    setBusy(true); setErr('');
    try {
      if (partner === 'padvira') {
        const r = await api.post<{reference: string}>('/partners/padvira/requests', {full_name: v.full_name, contact: v.contact, service, message: v.message, category: v.category});
        setDone(`درخواست در پادویرا ثبت شد (کد ${r.reference}). کارشناس پادویرا زمان، ظرفیت و هزینه را اعلام می‌کند.`);
      } else {
        const r = await api.post<{reference: string}>('/partners/giftasan/souvenir-requests', {full_name: v.full_name, contact: v.contact, city, items: v.items, deliver_to: v.deliver_to, note: v.note || null});
        setDone(`درخواست سوغات در گیفت آسان ثبت شد (سفارش ${r.reference}). قیمت و زمان تحویل را گیفت آسان اعلام می‌کند.`);
      }
    } catch (e) {setErr(e instanceof Error ? e.message : 'ثبت نشد؛ دوباره تلاش کنید.');} finally {setBusy(false);}
  }
  const ready = v.full_name.trim().length > 1 && v.contact.trim().length > 6 && (partner === 'padvira' ? v.message.trim().length > 4 : v.items.trim().length > 1 && v.deliver_to.trim().length > 1);
  return <form className="prf" onSubmit={e => {e.preventDefault(); if (ready) void send();}}>
    <b>{partner === 'padvira' ? service : `سوغات ${city}`}</b>
    <div className="prf-grid">
      <label>نام و نام خانوادگی<input value={v.full_name} onChange={e => set('full_name', e.target.value)} autoComplete="name"/></label>
      <label>موبایل یا ایمیل<input dir="ltr" value={v.contact} onChange={e => set('contact', e.target.value)} autoComplete="tel"/></label>
      {partner === 'padvira' ? <>
        <label>برای<select value={v.category} onChange={e => set('category', e.target.value)}><option value="family">خودم و خانواده‌ام</option><option value="org">سازمانم</option></select></label>
        <label className="prf-wide">چه می‌خواهید؟<textarea rows={3} value={v.message} onChange={e => set('message', e.target.value)} placeholder="تاریخ تقریبی، تعداد نفرات، شهر و هر نکته‌ی دیگر"/></label>
      </> : <>
        <label className="prf-wide">چه سوغاتی و چه مقدار؟<input value={v.items} onChange={e => set('items', e.target.value)} placeholder="مثلاً ۲ جعبه باقلوا"/></label>
        <label>ارسال به (شهر و محله)<input value={v.deliver_to} onChange={e => set('deliver_to', e.target.value)}/></label>
        <label>توضیح (اختیاری)<input value={v.note} onChange={e => set('note', e.target.value)}/></label>
      </>}
    </div>
    {err && <p className="prf-err" role="alert">{err}</p>}
    <div className="prf-actions"><button className="prf-btn" disabled={!ready || busy}>{busy ? 'در حال ثبت…' : 'ثبت درخواست'}</button>{onClose && <button type="button" className="prf-ghost" onClick={onClose}>بستن</button>}</div>
  </form>;
}
