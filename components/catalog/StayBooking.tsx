'use client';
/* Online booking for hotels under a KarenSeir contract: dates + guests -> live availability from
   /stays/hotels/{slug}/availability -> chosen room becomes a normal offer (/offers/{id}) for checkout. */
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {useEffect, useState, type FormEvent} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';

type StayOffer = {room_id: string; room_name: string; board_fa: string; nights: number; rooms_left: number; total_per_room: number; total: number; currency: string; refundable: boolean; terms: string | null};
const fa = (n: number) => n.toLocaleString('fa-IR');
const iso = (d: Date) => d.toISOString().slice(0, 10);

export function StayBooking({slug}: {slug: string}) {
  const {api, session} = useAuth(); const router = useRouter();
  const t = new Date(); t.setDate(t.getDate() + 7); const t2 = new Date(t); t2.setDate(t.getDate() + 2);
  const [v, setV] = useState({checkin: iso(t), checkout: iso(t2), adults: 2, ages: '', rooms: 1});
  const [offers, setOffers] = useState<StayOffer[] | null>(null); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const [contracted, setContracted] = useState<boolean | null>(null);
  useEffect(() => {if (!session) return; let on = true; api.get<{contracted: boolean}>(`/stays/hotels/${encodeURIComponent(slug)}/contracted`).then(r => {if (on) setContracted(r.contracted);}).catch(() => {if (on) setContracted(false);}); return () => {on = false;};}, [api, session, slug]);
  const ages = () => v.ages.split(/[\s,،]+/).filter(Boolean).map(Number);
  async function search(e: FormEvent) {
    e.preventDefault(); setErr(''); setOffers(null); setBusy(true);
    const q = new URLSearchParams({checkin: v.checkin, checkout: v.checkout, adults: String(v.adults), rooms: String(v.rooms)}); if (v.ages.trim()) q.set('children_ages', ages().join(','));
    try {setOffers((await api.get<{offers: StayOffer[]}>(`/stays/hotels/${encodeURIComponent(slug)}/availability?${q}`)).offers);} catch (x) {setErr(x instanceof ApiError ? x.message : 'دریافت موجودی ممکن نشد');} finally {setBusy(false);}
  }
  async function book(o: StayOffer) {
    setBusy(true); setErr('');
    try {
      const r = await api.post<{offer_id: string}>(`/stays/hotels/${encodeURIComponent(slug)}/book`, {room_id: o.room_id, checkin: v.checkin, checkout: v.checkout, adults: v.adults, children_ages: ages(), rooms: v.rooms});
      const q = new URLSearchParams({vertical: 'hotel', depart: v.checkin, return: v.checkout, adults: String(v.adults * v.rooms), children: String(ages().length * v.rooms), rooms: String(v.rooms)});
      router.push(`/offers/${r.offer_id}?${q}`);
    } catch (x) {setErr(x instanceof ApiError ? x.message : 'رزرو ممکن نشد'); setBusy(false);}
  }
  if (!session) return <p className="cat-muted">برای دیدن نرخ‌های قراردادی و رزرو آنلاین <Link href={`/login?next=${encodeURIComponent(`/hotels/${slug}`)}`}>وارد شوید</Link>.</p>;
  if (!contracted) return null;
  return <div className="stay-booking">
    <form onSubmit={search} style={{display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', alignItems: 'end'}}>
      <label>ورود<input type="date" value={v.checkin} onChange={e => setV({...v, checkin: e.target.value})} dir="ltr" required/></label>
      <label>خروج<input type="date" value={v.checkout} onChange={e => setV({...v, checkout: e.target.value})} dir="ltr" required/></label>
      <label>بزرگسال در هر اتاق<input type="number" min={1} max={8} value={v.adults} onChange={e => setV({...v, adults: Number(e.target.value) || 1})}/></label>
      <label>سن کودکان هر اتاق<input value={v.ages} placeholder="مثلاً ۴، ۹" onChange={e => setV({...v, ages: e.target.value.replace(/[۰-۹]/g, d => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))})}/></label>
      <label>تعداد اتاق<input type="number" min={1} max={10} value={v.rooms} onChange={e => setV({...v, rooms: Number(e.target.value) || 1})}/></label>
      <button className="button primary" disabled={busy}>{busy ? 'در حال بررسی…' : 'بررسی موجودی'}</button>
    </form>
    {err && <p role="alert" className="cat-muted" style={{color: '#b3261e'}}>{err}</p>}
    {offers && (offers.length === 0 ? <p className="cat-muted">برای این تاریخ و ترکیب مهمانان اتاق آزاد قراردادی نداریم. می‌توانید استعلام بفرستید.</p> :
      <ul style={{listStyle: 'none', padding: 0, display: 'grid', gap: 10, marginTop: 12}}>{offers.map(o => <li key={o.room_id} style={{border: '1px solid #e6dccf', borderRadius: 14, padding: 12, display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', alignItems: 'center'}}>
        <span><b>{o.room_name}</b> — {o.board_fa}<br/><small>{fa(o.nights)} شب · {o.refundable ? 'قابل استرداد طبق قوانین' : 'غیرقابل استرداد'} · {o.rooms_left <= 3 ? `فقط ${fa(o.rooms_left)} اتاق باقی است` : 'موجود'}</small></span>
        <span style={{textAlign: 'left'}}><b>{fa(o.total)} ریال</b><br/><small>{v.rooms > 1 ? `${fa(o.total_per_room)} ریال هر اتاق` : 'برای کل اقامت'}</small></span>
        <button className="button primary" onClick={() => book(o)} disabled={busy}>رزرو</button></li>)}</ul>)}
  </div>;
}
