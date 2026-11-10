'use client';
/* Approved traveller reviews of a published tour. Reviewer identity is never shown; verified bookings come first. */
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {resolveApiBase} from '../../lib/api/karenseir-client';

type Review = {id: string; rating: number; title: string; body: string; verified_booking: boolean; created_at: string | null; reply: string | null};
type Data = {summary: {average: number | null; count: number}; items: Review[]; page: number; pages: number};
const fa = (n: number) => n.toLocaleString('fa-IR');
const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('fa-IR', {timeZone: 'Asia/Tehran', year: 'numeric', month: 'long', day: 'numeric'}) : '');
const stars = (n: number) => '★'.repeat(Math.round(n)) + '☆'.repeat(5 - Math.round(n));

export function TourReviews({tourId}: {tourId: string}) {
  const [data, setData] = useState<Data | null>(null);
  const [page, setPage] = useState(1);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    const base = resolveApiBase(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000');
    fetch(`${base}/public/tour-products/${encodeURIComponent(tourId)}/reviews?page=${page}`)
      .then(r => {if (!r.ok) throw new Error(String(r.status)); return r.json();})
      .then((d: Data) => {if (!live) return; setFailed(false); setData(prev => (page > 1 && prev ? {...d, items: [...prev.items, ...d.items]} : d));})
      .catch(() => live && setFailed(true));
    return () => {live = false;};
  }, [tourId, page]);
  if (failed && !data) return null;
  if (!data) return <section className="tour-reviews" aria-busy="true"><h2>نظر مسافران</h2><p role="status">در حال دریافت نظرها…</p></section>;
  const s = data.summary;
  return <section className="tour-reviews" aria-labelledby="tour-reviews-title">
    <header><h2 id="tour-reviews-title">نظر مسافران</h2>
      {s.count > 0 && s.average !== null && <p className="tour-reviews-score"><b>{fa(s.average)}</b><span aria-hidden="true">{stars(s.average)}</span><small>از {fa(s.count)} نظر تأییدشده</small></p>}</header>
    {s.count === 0 ? <p className="tour-reviews-empty">هنوز نظری برای این تور منتشر نشده است. اگر با این تور سفر کرده‌اید، پس از سفر از <Link href="/account">حساب کاربری</Link> نظرتان را ثبت کنید.</p>
      : <ul>{data.items.map(r => <li key={r.id} className="tour-review">
        <div className="tour-review-head"><span className="tour-review-stars" aria-label={`${fa(r.rating)} از ۵`}>{stars(r.rating)}</span><b>{r.title}</b>
          {r.verified_booking && <span className="tour-review-verified">خرید تأییدشده</span>}<small>{date(r.created_at)}</small></div>
        <p>{r.body}</p>
        {r.reply && <blockquote><b>پاسخ برگزارکننده:</b> {r.reply}</blockquote>}
      </li>)}</ul>}
    {data.page < data.pages && <button type="button" className="button secondary" onClick={() => setPage(p => p + 1)}>نظرهای بیشتر</button>}
  </section>;
}
