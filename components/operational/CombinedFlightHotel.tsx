'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ContactOptions } from '../customer/CustomerHelp';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError, newId } from '../../lib/api/karenseir-client';

type SearchOffer = { id: string; title: string; amount: number; currency: string; service_type: string };
type Leg = { offer_id: string; price_check_id: string; amount: number; expires_at: string; expired: boolean };
type Quote = {
  id: string; status: string; stored_status: string; currency: string;
  legs: { flight: Leg; hotel: Leg }; package_total: number; expires_at: string;
  itinerary: Record<string, unknown>; reservation_id?: string | null; bookable: boolean;
};

const fa = (n: number, c = 'IRR') => `${(n ?? 0).toLocaleString('fa-IR')} ${c === 'IRR' ? 'ریال' : c}`;
const detailOf = (e: unknown) => (e instanceof ApiError ? e.detail : null) as Record<string, unknown> | null;
const msgOf = (e: unknown) => (e instanceof ApiError ? e.message : 'خطای پیش‌بینی‌نشده رخ داد.');

function Countdown({ iso, label }: { iso: string; label: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const left = Math.max(0, Math.floor((new Date(iso).getTime() - now) / 1000));
  const mm = String(Math.floor(left / 60)).padStart(2, '0');
  const ss = String(left % 60).padStart(2, '0');
  return <span className={left === 0 ? 'text-rose-600 font-bold' : left < 60 ? 'text-amber-600 font-bold' : 'text-slate-600'}>
    {label}: {left === 0 ? 'منقضی شد' : `${mm}:${ss}`}
  </span>;
}

export function CombinedFlightHotel() {
  const { api, session } = useAuth();
  const [flights, setFlights] = useState<SearchOffer[]>([]);
  const [hotels, setHotels] = useState<SearchOffer[]>([]);
  const [flightId, setFlightId] = useState('');
  const [hotelId, setHotelId] = useState('');
  const [passengers, setPassengers] = useState(1);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [notice, setNotice] = useState<{ tone: 'info' | 'warn' | 'error' | 'ok'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [booked, setBooked] = useState<{ id: string; reference?: string } | null>(null);

  const loadOffers = useCallback(async () => {
    try {
      const [f, h] = await Promise.all([
        api.post<SearchOffer[]>('/search/offers', { service_type: 'flight' }),
        api.post<SearchOffer[]>('/search/offers', { service_type: 'hotel' }),
      ]);
      setFlights(f); setHotels(h);
      setFlightId(f[0]?.id || ''); setHotelId(h[0]?.id || '');
    } catch (e) { setNotice({ tone: 'error', text: msgOf(e) }); }
  }, [api]);
  useEffect(() => { if (session) loadOffers(); }, [session, loadOffers]);

  const flight = useMemo(() => flights.find(o => o.id === flightId), [flights, flightId]);
  const hotel = useMemo(() => hotels.find(o => o.id === hotelId), [hotels, hotelId]);

  async function getQuote(reprice = false) {
    if (!flightId || !hotelId) return;
    setBusy(true); setBooked(null);
    setNotice({ tone: 'info', text: reprice ? 'در حال قیمت‌گیری مجدد…' : 'در حال دریافت کوت ترکیبی…' });
    try {
      const q = await api.post<Quote>('/combined/flight-hotel/quote', {
        flight_offer_id: flightId, hotel_offer_id: hotelId,
        flight_units: passengers, hotel_units: passengers,
        itinerary: { passengers }, command_id: newId(),
      });
      setQuote(q);
      setNotice({ tone: 'ok', text: 'کوت ترکیبی معتبر است. مبلغ بسته = جمع شفاف دو نرخ (بدون تخفیف ساختگی).' });
    } catch (e) {
      const d = detailOf(e);
      if (d?.code === 'LEG_UNAVAILABLE') {
        setNotice({ tone: 'error', text: `ظرفیت لِگ «${d.leg === 'flight' ? 'پرواز' : 'هتل'}» موجود نیست. لطفاً گزینه دیگری انتخاب کنید.` });
      } else if (d?.code === 'PACKAGE_PRICE_CHANGED') {
        setNotice({ tone: 'warn', text: `قیمت بسته تغییر کرد: از ${fa(d.old_total as number)} به ${fa(d.new_total as number)} (اختلاف ${fa(d.delta as number)}). دوباره قیمت‌گیری کنید.` });
      } else if (d?.code === 'CURRENCY_MISMATCH') {
        setNotice({ tone: 'error', text: 'ارز پرواز و هتل یکسان نیست.' });
      } else {
        setNotice({ tone: 'error', text: msgOf(e) });
      }
      setQuote(null);
    } finally { setBusy(false); }
  }

  async function book() {
    if (!quote) return;
    setBusy(true); setNotice({ tone: 'info', text: 'در حال رزرو بسته…' });
    try {
      const r = await api.post<{ id: string; booking_reference?: string; package_total: number }>(
        `/combined/flight-hotel/${quote.id}/book`, { command_id: newId() });
      setBooked({ id: r.id, reference: r.booking_reference });
      setNotice({ tone: 'ok', text: 'بسته پرواز و هتل رزرو شد.' });
      setQuote(q => (q ? { ...q, status: 'consumed', bookable: false, reservation_id: r.id } : q));
    } catch (e) {
      const d = detailOf(e);
      if (d?.code === 'QUOTE_EXPIRED') {
        setNotice({ tone: 'warn', text: `کوت منقضی شده است (لِگ‌های منقضی: ${(d.expired_legs as string[] || []).join('، ')}). دوباره قیمت‌گیری کنید.` });
      } else if (d?.code === 'LEG_UNAVAILABLE') {
        setNotice({ tone: 'error', text: `لِگ «${d.leg === 'flight' ? 'پرواز' : 'هتل'}» هنگام رزرو موجود نبود؛ هیچ رزروی ثبت نشد. دوباره انتخاب کنید.` });
        setQuote(null);
      } else {
        setNotice({ tone: 'error', text: msgOf(e) });
      }
    } finally { setBusy(false); }
  }

  if (!session) return <div className="container" role="alert"><p className="rounded-2xl bg-rose-50 p-6 text-rose-700">رزرو آنلاین پرواز و هتل به‌صورت یک‌جا هنوز در دسترس نیست. برای راهنمایی انتخاب خدمات تماس بگیرید.</p><h1>پرواز و هتل</h1><Link className="button secondary" href="/services">انتخاب خدمات سفر</Link><ContactOptions/></div>;

  const toneClass = { info: 'bg-cyan-50 text-cyan-800', ok: 'bg-emerald-50 text-emerald-800', warn: 'bg-amber-50 text-amber-800', error: 'bg-rose-50 text-rose-700' };
  const legExpired = quote && (quote.legs.flight.expired || quote.legs.hotel.expired || quote.status === 'expired');

  return <div className="container" style={{ maxWidth: 900 }}>
    <div className="page-hero"><span className="eyebrow">پرواز + هتل · موتور ترکیبی واقعی</span>
      <h1>بسته پرواز و هتل را شفاف بساز</h1>
      <p>هر لِگ نرخ و موجودی مستقل دارد؛ مبلغ بسته دقیقاً جمع دو نرخ معتبر است و هیچ تخفیف یا موجودی ساختگی وجود ندارد.</p></div>

    <section className="panel mb-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="font-bold">پرواز
          <select className="mt-2 block w-full rounded-xl border p-3" value={flightId} onChange={e => { setFlightId(e.target.value); setQuote(null); }}>
            {flights.length === 0 && <option value="">پروازی موجود نیست</option>}
            {flights.map(o => <option key={o.id} value={o.id}>{o.title} — {fa(o.amount, o.currency)}</option>)}
          </select></label>
        <label className="font-bold">هتل
          <select className="mt-2 block w-full rounded-xl border p-3" value={hotelId} onChange={e => { setHotelId(e.target.value); setQuote(null); }}>
            {hotels.length === 0 && <option value="">هتلی موجود نیست</option>}
            {hotels.map(o => <option key={o.id} value={o.id}>{o.title} — {fa(o.amount, o.currency)}</option>)}
          </select></label>
      </div>
      <label className="mt-4 block font-bold">تعداد مسافر / اتاق
        <input type="number" min={1} max={9} value={passengers} className="mt-2 block w-32 rounded-xl border p-2"
          onChange={e => { setPassengers(Math.max(1, Math.min(9, Number(e.target.value) || 1))); setQuote(null); }} /></label>
      <button disabled={busy || !flightId || !hotelId} className="button primary mt-4" onClick={() => getQuote(false)}>دریافت کوت ترکیبی</button>
    </section>

    {notice && <p role="status" className={`mb-4 rounded-xl p-4 text-sm ${toneClass[notice.tone]}`}>{notice.text}</p>}

    {quote && <section className="panel mb-5">
      <h2 className="font-black">مقایسه و کوت بسته</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <article className="rounded-xl bg-slate-50 p-4">
          <span className="tag">پرواز</span>
          <h3 className="mt-2 font-bold">{flight?.title}</h3>
          <p className="mt-1">{fa(quote.legs.flight.amount, quote.currency)}</p>
          <small className="block text-slate-600"><Countdown iso={quote.legs.flight.expires_at} label="اعتبار نرخ پرواز" /></small>
          {quote.legs.flight.expired && <strong className="block text-rose-600">این لِگ منقضی شده است.</strong>}
        </article>
        <article className="rounded-xl bg-slate-50 p-4">
          <span className="tag">هتل</span>
          <h3 className="mt-2 font-bold">{hotel?.title}</h3>
          <p className="mt-1">{fa(quote.legs.hotel.amount, quote.currency)}</p>
          <small className="block text-slate-600"><Countdown iso={quote.legs.hotel.expires_at} label="اعتبار نرخ هتل" /></small>
          {quote.legs.hotel.expired && <strong className="block text-rose-600">این لِگ منقضی شده است.</strong>}
        </article>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-cyan-50 p-4">
        <span><b className="text-lg">مبلغ کل بسته: {fa(quote.package_total, quote.currency)}</b>
          <small className="block text-slate-600">= {fa(quote.legs.flight.amount)} + {fa(quote.legs.hotel.amount)} · بدون تخفیف ساختگی · {passengers.toLocaleString('fa-IR')} مسافر</small></span>
        <Countdown iso={quote.expires_at} label="اعتبار کوت بسته (لِگ الزام‌آور)" />
      </div>
      {booked
        ? <p className="mt-4 rounded-xl bg-emerald-50 p-4">بسته با شناسه <b>{booked.reference || booked.id}</b> رزرو شد. <Link className="text-link" href={`/manage-booking/${booked.id}`}>مدیریت رزرو ←</Link></p>
        : legExpired
          ? <button disabled={busy} className="button primary mt-4" onClick={() => getQuote(true)}>قیمت‌گیری مجدد و انتخاب دوباره</button>
          : <div className="mt-4 flex gap-3">
              <button disabled={busy || !quote.bookable} className="button primary" onClick={book}>رزرو بسته</button>
              <button disabled={busy} className="button secondary" onClick={() => getQuote(true)}>بازبینی نرخ/موجودی</button>
            </div>}
    </section>}

    <p className="text-xs text-slate-500">جست‌وجوی مستقل پرواز و هتل بدون تغییر است؛ این موتور فقط دو Offer معتبر را در یک بسته با انقضای مستقل کنار هم می‌گذارد.</p>
  </div>;
}
