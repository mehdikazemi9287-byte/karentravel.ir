'use client';
/* Places from ShahrShad (sister business): restaurants, cafés, pools, sports, events and attractions.
   Each opens an in-site page with a booking request; a price shows only when ShahrShad has published it. */
import Link from 'next/link';
import {useEffect, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';

type Venue = {id: string; name: string; category_fa: string; description: string | null; city: string | null; district: string | null; cuisine: string | null;
  admission: string[]; facilities: string[]; price_from_irr: number | null; facts_checked_on: string | null; image_url: string | null; image_alt: string;
  map_url: string | null; book_url: string};
type Page = {items: Venue[]; total: number; cities: {name: string; count: number}[]; categories: {key: string; label: string; count: number}[]};
const fa = (n: number) => n.toLocaleString('fa-IR');
const PAGE = 18;

export function PartnerVenues({section, title}: {section: 'restaurants' | 'attractions' | 'pools-sports' | 'events-venues'; title: string}) {
  const {api} = useAuth();
  const [city, setCity] = useState(''); const [cat, setCat] = useState(''); const [q, setQ] = useState(''); const [term, setTerm] = useState(''); const [page, setPage] = useState(0);
  const [data, setData] = useState<Page | null>(null); const [error, setError] = useState(false);
  useEffect(() => {
    let live = true; const p = new URLSearchParams({section, limit: String(PAGE), offset: String(page * PAGE)});
    if (city) p.set('city', city); if (cat) p.set('category', cat); if (term) p.set('q', term);
    api.publicGet<Page>(`/public/partner-venues?${p}`).then(d => {if (live) {setData(d); setError(false);}}).catch(() => {if (live) setError(true);});
    return () => {live = false;};
  }, [api, section, city, cat, term, page]);
  if (error && !data) return null;
  if (data && data.total === 0 && !city && !cat && !term) return null;
  const pages = data ? Math.ceil(data.total / PAGE) : 0;
  return <section className="pv" aria-labelledby={`pv-${section}`}>
    <header className="pv-head"><h2 id={`pv-${section}`}>{title}</h2>{data && <small>{fa(data.total)} مجموعه · با همکاری شهرشاد</small>}</header>
    <form className="pv-tools" onSubmit={e => {e.preventDefault(); setTerm(q.trim()); setPage(0);}}>
      <input aria-label="جست‌وجو" placeholder="نام یا نوع غذا و خدمت" value={q} onChange={e => setQ(e.target.value)}/>
      <select aria-label="شهر" value={city} onChange={e => {setCity(e.target.value); setPage(0);}}><option value="">همه‌ی شهرها</option>{data?.cities.map(c => <option key={c.name} value={c.name}>{c.name} ({fa(c.count)})</option>)}</select>
      {data && data.categories.length > 1 && <select aria-label="دسته" value={cat} onChange={e => {setCat(e.target.value); setPage(0);}}><option value="">همه‌ی دسته‌ها</option>{data.categories.map(c => <option key={c.key} value={c.key}>{c.label} ({fa(c.count)})</option>)}</select>}
      <button type="submit">جست‌وجو</button>
    </form>
    {!data ? <p role="status" className="pv-muted">در حال دریافت…</p> : data.items.length === 0 ? <p className="pv-muted">موردی با این شرایط پیدا نشد.</p> :
      <div className="pv-grid">{data.items.map(v => <article key={v.id} className="pv-card">
        <div className="pv-img">{/* eslint-disable-next-line @next/next/no-img-element */}{v.image_url ? <img src={v.image_url} alt={v.image_alt} loading="lazy"/> : <span aria-hidden="true">{v.name.slice(0, 1)}</span>}<em>{v.category_fa}</em></div>
        <div className="pv-body">
          <h3>{v.name}</h3>
          <p className="pv-where">{[v.city, v.district].filter(Boolean).join('، ')}{v.cuisine ? ` · ${v.cuisine}` : ''}</p>
          {v.description && <p className="pv-desc">{v.description}</p>}
          {(v.admission.length > 0 || v.facilities.length > 0) && <ul className="pv-tags">{[...v.admission, ...v.facilities].slice(0, 5).map(t => <li key={t}>{t}</li>)}</ul>}
          <footer>{v.price_from_irr ? <span className="pv-price">از {fa(Math.round(v.price_from_irr / 10))} تومان</span> : <span className="pv-muted">قیمت در شهرشاد</span>}
            <span className="pv-links"><Link className="pv-book" href={`/places/${encodeURIComponent(v.id)}`}>مشاهده و رزرو</Link></span></footer>
        </div></article>)}</div>}
    {pages > 1 && <nav className="pv-pager" aria-label="صفحه‌بندی"><button disabled={page === 0} onClick={() => setPage(page - 1)}>قبلی</button><span>صفحه‌ی {fa(page + 1)} از {fa(pages)}</span><button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>بعدی</button></nav>}
  </section>;
}
