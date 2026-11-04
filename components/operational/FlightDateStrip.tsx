'use client';
/* Flight results: neighbouring departure dates (±3 days). Each day is a link that reruns the same search.
   Prices are fetched only when the signed-in user asks, by running the same /search/v3 query for each day,
   so every figure is the engine's own final price — nothing is estimated. Days without offers show «—». */
import {useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';

type Payload = Record<string, unknown> & {filters: Record<string, unknown>};
type Res = {entities: {best_offer: {final_price: number}}[]};
const shift = (iso: string, d: number) => {const t = new Date(iso + 'T12:00:00Z'); t.setUTCDate(t.getUTCDate() + d); return t.toISOString().slice(0, 10);};
const dayFa = (iso: string) => new Date(iso + 'T12:00:00Z').toLocaleDateString('fa-IR', {weekday: 'short', day: 'numeric', month: 'short'});

export function FlightDateStrip({depart, returnDate, payload, onPick}: {depart: string; returnDate?: string; payload: Payload; onPick: (depart: string, ret?: string) => void}) {
  const {api, session} = useAuth();
  const [prices, setPrices] = useState<Record<string, number | null | 'loading'>>({});
  if (!depart || Number.isNaN(new Date(depart + 'T12:00:00Z').getTime())) return null;
  const days = [-3, -2, -1, 0, 1, 2, 3].map(o => ({o, date: shift(depart, o)})).filter(d => d.date >= new Date().toISOString().slice(0, 10));
  async function load() {
    const todo = days.filter(d => d.o !== 0);
    setPrices(Object.fromEntries(todo.map(d => [d.date, 'loading'])));
    await Promise.all(todo.map(async d => {
      try {
        const ret = returnDate ? shift(returnDate, d.o) : undefined;
        const r = await api.post<Res>('/search/v3', {...payload, filters: {...payload.filters, depart: d.date, ...(ret ? {return: ret} : {})}});
        const min = r.entities.reduce<number | null>((m, e) => (m === null || e.best_offer.final_price < m ? e.best_offer.final_price : m), null);
        setPrices(p => ({...p, [d.date]: min}));
      } catch {setPrices(p => ({...p, [d.date]: null}));}
    }));
  }
  return <nav className="flight-date-strip" aria-label="روزهای مجاور">
    {days.map(d => {const v = prices[d.date]; return <button type="button" key={d.date} aria-current={d.o === 0 ? 'date' : undefined}
      onClick={() => d.o !== 0 && onPick(d.date, returnDate ? shift(returnDate, d.o) : undefined)}>
      <span>{dayFa(d.date)}</span><small>{d.o === 0 ? 'تاریخ انتخابی' : v === 'loading' ? '…' : typeof v === 'number' ? `از ${v.toLocaleString('fa-IR')} ریال` : v === null ? '—' : ''}</small></button>;})}
    {session && Object.keys(prices).length === 0 && <button type="button" className="flight-date-load" onClick={() => void load()}>نمایش قیمت روزهای مجاور</button>}
  </nav>;
}

/* "Send purchase link": share the offer's detail link (same search parameters) by the device share sheet, WhatsApp or copy. */
export function SharePurchaseLink({href, title}: {href: string; title: string}) {
  const [done, setDone] = useState('');
  async function share() {
    const url = new URL(href, window.location.origin).toString();
    const text = `${title} — کارن تراول`;
    try {
      if (navigator.share) {await navigator.share({title: text, url}); return;}
      await navigator.clipboard.writeText(`${text}\n${url}`); setDone('لینک کپی شد');
    } catch {window.open(`https://wa.me/?text=${encodeURIComponent(`${text}\n${url}`)}`, '_blank', 'noopener');}
  }
  return <button type="button" className="share-purchase-link" onClick={() => void share()}>{done || 'ارسال لینک خرید'}</button>;
}
