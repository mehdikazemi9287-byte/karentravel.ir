'use client';
/* A ShahrShad place inside KarenSeir: details and an in-site booking request. */
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {PartnerRequestForm} from './PartnerRequestForm';

type Place = {id: string; name: string; category_fa: string; description: string | null; city: string | null; district: string | null; cuisine: string | null;
  admission: string[]; facilities: string[]; price_from_irr: number | null; facts_checked_on: string | null; image_url: string | null; image_alt: string};
const fa = (n: number) => n.toLocaleString('fa-IR');

export function PlaceDetail({id}: {id: string}) {
  const {api} = useAuth();
  const [p, setP] = useState<Place | null>(null); const [missing, setMissing] = useState(false);
  useEffect(() => {api.publicGet<Place>(`/public/partner-venues/${encodeURIComponent(id)}`).then(setP).catch(() => setMissing(true));}, [api, id]);
  if (missing) return <section className="pl"><h1>این مجموعه پیدا نشد</h1><p><Link href="/experiences">بازگشت به تجربه‌ها</Link></p></section>;
  if (!p) return <p role="status">در حال دریافت…</p>;
  return <section className="pl">
    <nav className="pl-crumbs"><Link href="/experiences">تجربه‌ها</Link> ← <span>{p.category_fa}</span></nav>
    <div className="pl-head">
      <div className="pv-img pl-img">{/* eslint-disable-next-line @next/next/no-img-element */}{p.image_url ? <img src={p.image_url} alt={p.image_alt}/> : <span aria-hidden="true">{p.name.slice(0, 1)}</span>}<em>{p.category_fa}</em></div>
      <div className="pl-info">
        <h1>{p.name}</h1>
        <p className="pv-where">{[p.city, p.district].filter(Boolean).join('، ')}{p.cuisine ? ` · ${p.cuisine}` : ''}</p>
        {p.description && <p>{p.description}</p>}
        {(p.admission.length > 0 || p.facilities.length > 0) && <ul className="pv-tags">{[...p.admission, ...p.facilities].map(t => <li key={t}>{t}</li>)}</ul>}
        <p className="pv-price">{p.price_from_irr ? `از ${fa(Math.round(p.price_from_irr / 10))} تومان` : 'قیمت پس از بررسی درخواست اعلام می‌شود'}</p>
      </div>
    </div>
    <h2>درخواست رزرو</h2>
    <PartnerRequestForm partner="shahrshad" service={p.name} venueId={p.id}/>
  </section>;
}
