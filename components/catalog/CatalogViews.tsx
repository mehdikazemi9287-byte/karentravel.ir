'use client';
/* Master-data views. Everything rendered here is reference data (name, place, facilities, contact);
   price, availability and rooms come only from real supplier offers and are never shown from this catalog. */
import Link from 'next/link';
import {usePathname, useRouter, useSearchParams} from 'next/navigation';
import {useEffect, useState, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError, newId} from '../../lib/api/karenseir-client';

type Brief = {id: string; name: string; name_en?: string | null} | null;
type Hotel = {id: string; slug: string; name: string; name_fa: string | null; name_en: string | null; name_local: string | null; hotel_type: string; hotel_type_fa: string; stars: number | null; country_code: string;
  city: Brief; region: Brief; country?: Brief; address: string | null; latitude: number | null; longitude: number | null; amenities: {key: string; label: string}[]; image_url: string | null; image_credit: string | null; price_note: string;
  details?: {district?: string; room_count?: string; bed_count?: string; built_year_jalali?: string; floors?: string; hotel_view?: string; board_plans?: string[]; review?: string;
    nearby?: {place: string; distance: string | null; unit: string | null}[]; restaurants?: {name: string; capacity: string | null; hours: string | null}[]; map_link?: string; traffic?: string};
  request?: {mode: string; online_booking: boolean; reason: string}; state?: {rate_available: boolean; bookable: boolean; content_complete: boolean};
  rules_text?: string | null; stars_status?: string | null; stars_status_fa?: string | null; policies?: {key: string; label: string; value_fa: string}[];
  images?: {id: number; url: string; caption: string | null; author: string | null; license: string; license_url: string | null; source_url: string}[];
  room_types?: {id: number; name_fa: string; name_en: string | null; bed_type_fa: string | null; max_adults: number | null; max_children: number | null; size_m2: number | null; view_fa: string | null; description: string | null; image_url?: string | null; amenities: {key: string; label: string}[]}[];
  description?: string | null; checkin_time?: string | null; checkout_time?: string | null; phone?: string | null; website?: string | null; email?: string | null;
  provenance?: Provenance; nearby_airports?: Airport[]; nearby_rail_stations?: Station[]};
type Provenance = {source: string; source_ref: string | null; license: string | null; retrieved_on: string | null};
type Facets = {countries: {code: string; name: string; count: number}[]; cities: {id: string; name: string; count: number}[]; stars: {value: number; count: number}[]; types: {key: string; label: string; count: number}[]; amenities: {key: string; label: string; count: number}[]; policies?: {key: string; label: string; count: number}[]};
type Page<T> = {total: number; offset: number; limit: number; items: T[]; price_note: string};
type Venue = {id: string; kind: string; kind_fa: string; name: string; name_en: string | null; city: Brief; region: Brief; address: string | null; latitude: number; longitude: number; phone: string | null; website: string | null;
  opening_hours: string | null; detail: string | null; description: string | null; image_url: string | null; image_credit: string | null; price_note: string};
type Airport = {iata: string; icao: string | null; name: string; name_en: string; city_name: string | null; country_code: string; scope: string | null; timezone: string | null; scheduled_service: boolean | null};
type Station = {id: string; name: string; name_en: string | null; city_id: string | null; latitude: number; longitude: number};
type Airline = {id: string; iata: string; icao: string | null; name: string; name_en: string | null; country_code: string; airline_type: string | null; website: string | null; logo_url: string | null; logo_credit: string | null};
type Place = {id: string; kind: string; parent_id: string | null; country_code: string; name: string; name_fa: string | null; name_en: string | null; latitude: number | null; longitude: number | null; population: number | null;
  description: string | null; image_url: string | null; image_credit: string | null; hotel_count: number};
type PlaceDetail = Place & {details?: {capital?: string; currency?: string; official_language?: string; population_text?: string; voltage?: string; time_zone?: string; visa_note?: string; guide?: string; images?: string[]; map_link?: string; major_cities?: string};
  breadcrumbs?: {id: string; name: string}[]; related?: {id: string; name: string; hotel_count: number}[]; reference_tours?: TourBrief[]; parent: Place | null; children: Place[]; hotels: number; airports: Airport[]; rail_stations: Station[]; venue_counts: Record<string, number>};

const fa = (n: number) => n.toLocaleString('fa-IR');
const COUNTRY_FA: Record<string, string> = {IR: 'ایران', TR: 'ترکیه', AE: 'امارات', AM: 'ارمنستان', GE: 'گرجستان', IQ: 'عراق', QA: 'قطر', OM: 'عمان', KW: 'کویت', AZ: 'جمهوری آذربایجان'};
const AIRLINE_TYPE_FA: Record<string, string> = {flag_carrier: 'حامل پرچم', low_cost: 'کم‌هزینه', charter: 'چارتر', cargo: 'باری', regional: 'منطقه‌ای'};
const VENUE_KIND_FA: Record<string, string> = {restaurant: 'رستوران', cafe: 'کافه', attraction: 'جاذبه', museum: 'موزه', historic: 'بنای تاریخی', pool_sport: 'استخر و ورزش', event_venue: 'تالار و رویداد', car_rental: 'اجاره خودرو', handicraft: 'صنایع‌دستی', travel_agency: 'آژانس و تور', tourist_info: 'اطلاعات گردشگری', transport_terminal: 'پایانه'};
const osmLink = (lat: number, lon: number) => `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
const ATTRIBUTION = <p className="cat-attrib">داده‌های مرجع: © مشارکت‌کنندگان <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> (ODbL)، Wikidata، OurAirports و Wikimedia Commons. این فهرست اطلاعات مرجع است و به معنی موجودی یا قیمت نیست.</p>;

function useCatalog<T>(path: string | null) {
  const {api} = useAuth();
  const [state, setState] = useState<{path: string | null; data: T | null; error: boolean}>({path: null, data: null, error: false});
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    api.publicGet<T>(path).then(data => {if (!cancelled) setState({path, data, error: false});}).catch(() => {if (!cancelled) setState({path, data: null, error: true});});
    return () => {cancelled = true;};
  }, [api, path]);
  const current = state.path === path;
  return {data: current ? state.data : null, stale: state.data, loading: !!path && !current, error: current && state.error};
}

function useQueryState() {
  const router = useRouter(); const pathname = usePathname(); const params = useSearchParams();
  const set = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) {if (v) next.set(k, v); else next.delete(k);}
    if (!('page' in changes)) next.delete('page');
    router.replace(`${pathname}${next.size ? '?' + next.toString() : ''}`, {scroll: false});
  };
  return {params, set};
}

function Stars({value}: {value: number | null}) {
  if (!value) return null;
  return <span className="cat-stars" aria-label={`${fa(value)} ستاره`}>{'★'.repeat(value)}</span>;
}
function Thumb({src, credit, alt, label}: {src: string | null; credit: string | null; alt: string; label: string}) {
  if (!src) return <div className="cat-thumb cat-thumb-empty" aria-hidden="true"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 10h3a1 1 0 0 1 1 1v10M3 21h18M8 7h4M8 11h4M8 15h4"/></svg><span>{label}</span></div>;
  // eslint-disable-next-line @next/next/no-img-element -- remote Wikimedia Commons file with per-image credit
  return <div className="cat-thumb"><img src={src} alt={alt} loading="lazy"/>{credit && <small title={credit}>{credit}</small>}</div>;
}
function Pager({total, limit, page, onPage}: {total: number; limit: number; page: number; onPage: (p: number) => void}) {
  const pages = Math.ceil(total / limit);
  if (pages <= 1) return null;
  return <nav className="cat-pager" aria-label="صفحه‌بندی"><button disabled={page <= 1} onClick={() => onPage(page - 1)}>→ قبلی</button><span>صفحهٔ {fa(page)} از {fa(pages)}</span><button disabled={page >= pages} onClick={() => onPage(page + 1)}>بعدی ←</button></nav>;
}
function Status({loading, error, empty, children}: {loading: boolean; error: boolean; empty: boolean; children?: ReactNode}) {
  if (error) return <p className="cat-state" role="alert">دریافت اطلاعات ممکن نشد. کمی بعد دوباره تلاش کنید.</p>;
  if (loading && empty) return <p className="cat-state" role="status">در حال دریافت…</p>;
  if (empty) return <p className="cat-state">{children ?? 'موردی با این شرایط ثبت نشده است.'}</p>;
  return null;
}
function SearchBox({value, onSubmit, placeholder}: {value: string; onSubmit: (v: string) => void; placeholder: string}) {
  const [text, setText] = useState(value);
  useEffect(() => {setText(value);}, [value]);
  return <form className="cat-search" role="search" onSubmit={e => {e.preventDefault(); onSubmit(text.trim());}}><input value={text} onChange={e => setText(e.target.value)} placeholder={placeholder} aria-label={placeholder}/><button type="submit">جست‌وجو</button></form>;
}

export function InquiryRequest({subject, context, reason}: {subject: string; context: string; reason: string}) {
  const {api, session} = useAuth();
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [done, setDone] = useState<string | null>(null), [error, setError] = useState<string | null>(null), [note, setNote] = useState('');
  async function send() {
    setBusy(true); setError(null);
    try {const made = await api.post<{id: string}>('/support/cases', {subject: subject.slice(0, 200), case_type: 'SERVICE_INQUIRY', body: `${context}${note.trim() ? `\n\nتوضیح مسافر: ${note.trim()}` : ''}`}, newId()); setDone(made.id);}
    catch (e) {setError(e instanceof ApiError && e.status === 401 ? 'برای ثبت درخواست وارد شوید.' : 'ثبت درخواست انجام نشد؛ دوباره تلاش کنید.');} finally {setBusy(false);}
  }
  return <div className="cat-request" data-request-state="inquiry">
    <dl className="cat-dl"><dt>نرخ و موجودی</dt><dd>متصل نیست</dd><dt>رزرو آنلاین</dt><dd>غیرفعال</dd></dl><p className="cat-muted">{reason}</p>
    {done ? <p role="status" className="cat-price">درخواست استعلام شما ثبت شد. پاسخ کارشناس را در <Link href="/support">پشتیبانی</Link> ببینید.</p>
      : !session ? <><Link className="button primary" href="/login">ورود و ثبت درخواست استعلام</Link><Link className="button secondary" href={`/contact?subject=${encodeURIComponent(subject)}`}>تماس با پشتیبانی</Link></>
      : !open ? <button type="button" className="button primary" onClick={() => setOpen(true)}>ثبت درخواست استعلام</button>
      : <><label className="cat-request-note">تاریخ سفر، تعداد نفرات یا توضیح دیگر<textarea rows={3} maxLength={1500} value={note} onChange={e => setNote(e.target.value)}/></label>
        <button type="button" className="button primary" disabled={busy} onClick={() => void send()}>{busy ? 'در حال ثبت…' : 'ارسال درخواست'}</button></>}
    {error && <p role="alert" className="cat-muted">{error}</p>}
  </div>;
}

export function HotelCard({h}: {h: Hotel}) {
  const where = [h.city?.name, h.region?.name !== h.city?.name ? h.region?.name : null, COUNTRY_FA[h.country_code]].filter(Boolean).join('، ');
  return <Link href={`/hotels/${h.slug}`} className="cat-card">
    <Thumb src={h.image_url} credit={h.image_credit} alt={h.name} label={h.hotel_type_fa}/>
    <div className="cat-card-body">
      <div className="cat-card-top"><span className="cat-tag">{h.hotel_type_fa}</span><Stars value={h.stars}/></div>
      <h3>{h.name}</h3>
      {h.name_en && h.name_en !== h.name && <p className="cat-en" dir="ltr" lang="en">{h.name_en}</p>}
      <p className="cat-where">{where}</p>
      {h.amenities.length > 0 && <ul className="cat-amen">{h.amenities.slice(0, 4).map(a => <li key={a.key}>{a.label}</li>)}</ul>}
      <p className="cat-price">{h.price_note}</p>
    </div>
  </Link>;
}

const PAGE = 24;
export function HotelCatalog({presetTypes, title = 'هتل‌ها و اقامتگاه‌های ثبت‌شده', intro}: {presetTypes?: string[]; title?: string; intro?: string}) {
  const {params, set} = useQueryState();
  const country = params.get('country') || '', city = params.get('city') || '', region = params.get('region') || '', stars = params.get('stars') || '';
  const type = params.get('hotel_type') || '', amenity = params.get('amenity') || '', policy = params.get('policy') || '', q = params.get('q') || '', page = Math.max(1, Number(params.get('page')) || 1);
  const scope = new URLSearchParams();
  if (country) scope.set('country', country);
  const facets = useCatalog<Facets>(`/catalog/hotels/facets${scope.size ? '?' + scope : ''}`);
  const query = new URLSearchParams(scope);
  if (city) query.set('city', city); if (region) query.set('region', region); if (stars) query.set('stars', stars);
  if (type || presetTypes) query.set('hotel_type', type || presetTypes!.join(',')); if (amenity) query.set('amenity', amenity); if (policy) query.set('policy', policy); if (q) query.set('q', q);
  query.set('limit', String(PAGE)); query.set('offset', String((page - 1) * PAGE));
  const list = useCatalog<Page<Hotel>>(`/catalog/hotels?${query}`);
  const data = list.data ?? list.stale; const f = facets.data ?? facets.stale;
  const amen = amenity ? amenity.split(',') : [];
  const types = f?.types.filter(t => !presetTypes || presetTypes.includes(t.key)) ?? [];
  const active = city || region || stars || type || amenity || policy || q;
  return <section className="cat" id="catalog" aria-labelledby="cat-hotels-title">
    <header className="cat-head"><div><h2 id="cat-hotels-title">{title}</h2><p>{intro ?? 'نام، موقعیت، درجه و امکانات هر اقامتگاه از منابع مرجع ثبت شده است. قیمت و ظرفیت پس از انتخاب تاریخ و استعلام از تأمین‌کننده اعلام می‌شود.'}</p></div>
      <SearchBox value={q} onSubmit={v => set({q: v || null})} placeholder="نام هتل، شهر یا کشور"/></header>
    <div className="cat-chips" role="group" aria-label="کشور"><button className={!country ? 'on' : ''} onClick={() => set({country: null, city: null, region: null})}>همهٔ کشورها</button>
      {f?.countries.map(c => <button key={c.code} className={country === c.code ? 'on' : ''} onClick={() => set({country: c.code, city: null, region: null})}>{c.name} <small>{fa(c.count)}</small></button>)}</div>
    <div className="cat-filters">
      <label>شهر<select value={city} onChange={e => set({city: e.target.value || null, region: null})}><option value="">همهٔ شهرها</option>{f?.cities.map(c => <option key={c.id} value={c.id}>{c.name} ({fa(c.count)})</option>)}</select></label>
      <label>درجه<select value={stars} onChange={e => set({stars: e.target.value || null})}><option value="">همه</option>{f?.stars.map(s => <option key={s.value} value={s.value}>{fa(s.value)} ستاره ({fa(s.count)})</option>)}</select></label>
      <label>نوع اقامتگاه<select value={type} onChange={e => set({hotel_type: e.target.value || null})}><option value="">همه</option>{types.map(t => <option key={t.key} value={t.key}>{t.label} ({fa(t.count)})</option>)}</select></label>
      <fieldset><legend>امکانات</legend>{f?.amenities.slice(0, 8).map(a => <label key={a.key} className={amen.includes(a.key) ? 'on' : ''}><input type="checkbox" checked={amen.includes(a.key)} onChange={() => set({amenity: (amen.includes(a.key) ? amen.filter(x => x !== a.key) : [...amen, a.key]).join(',') || null})}/>{a.label}</label>)}</fieldset>
    </div>
    <div className="cat-meta"><span aria-live="polite">{data ? `${fa(data.total)} اقامتگاه` : ''}</span>{active && <button onClick={() => set({city: null, region: null, stars: null, hotel_type: null, amenity: null, policy: null, q: null})}>حذف فیلترها</button>}</div>
    <Status loading={list.loading} error={list.error} empty={!data || data.items.length === 0}>اقامتگاهی با این شرایط ثبت نشده است. فیلترها را تغییر دهید.</Status>
    {data && data.items.length > 0 && <div className={`cat-grid${list.loading ? ' is-loading' : ''}`}>{data.items.map(h => <HotelCard key={h.id} h={h}/>)}</div>}
    {data && <Pager total={data.total} limit={PAGE} page={page} onPage={p => {set({page: p > 1 ? String(p) : null}); document.getElementById('catalog')?.scrollIntoView();}}/>}
    {ATTRIBUTION}
  </section>;
}

export function HotelDetail({slug}: {slug: string}) {
  const {data: h, loading, error} = useCatalog<Hotel>(`/catalog/hotels/${encodeURIComponent(slug)}`);
  if (!h) return <main className="journey-main cat-detail"><Status loading={loading} error={false} empty>{error ? 'این هتل در فهرست مرجع پیدا نشد.' : undefined}</Status><Link className="button secondary" href="/hotels">بازگشت به هتل‌ها</Link></main>;
  const where = [h.city?.name, h.region?.name !== h.city?.name ? h.region?.name : null, h.country?.name].filter(Boolean).join('، ');
  const summary = `${h.hotel_type_fa}${h.stars ? ` ${fa(h.stars)} ستاره` : ''}${where ? ` در ${where}` : ''}`;
  return <main className="journey-main cat-detail">
    <nav className="cat-crumbs" aria-label="مسیر"><Link href="/hotels">هتل‌ها</Link>{h.country && <Link href={`/hotels?country=${h.country_code}`}>{h.country.name}</Link>}{h.city && <Link href={`/hotels?country=${h.country_code}&city=${h.city.id}`}>{h.city.name}</Link>}</nav>
    <header className="cat-detail-head"><div><span className="cat-tag">{h.hotel_type_fa}</span><Stars value={h.stars}/></div><h1>{h.name}</h1>{h.stars && h.stars_status_fa ? <p className="cat-muted">درجه: {h.stars_status_fa}</p> : null}
      {h.name_en && h.name_en !== h.name && <p className="cat-en" dir="ltr" lang="en">{h.name_en}</p>}{h.name_local && h.name_local !== h.name && <p className="cat-en">{h.name_local}</p>}<p className="cat-where">{summary}</p></header>
    <div className="cat-detail-grid">
      <div>
        {h.images?.length ? <div className="cat-gallery">{h.images.map((im, i) => <figure key={im.id} className={i === 0 ? 'lead' : ''}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={im.url} alt={im.caption || h.name} loading={i ? 'lazy' : 'eager'}/><figcaption>{im.caption ? `${im.caption} — ` : ''}<a href={im.source_url} target="_blank" rel="noreferrer">{im.author || 'منبع'}</a> · {im.license_url ? <a href={im.license_url} target="_blank" rel="noreferrer">{im.license}</a> : im.license}</figcaption></figure>)}</div> : h.image_url ? <Thumb src={h.image_url} credit={h.image_credit} alt={h.name} label=""/> : <div className="cat-noimage">برای این اقامتگاه هنوز تصویر تأییدشده‌ای ثبت نشده است.</div>}
        {h.description && <section><h2>دربارهٔ اقامتگاه</h2>{h.description.split('\n').map((line, i) => <p key={i}>{line}</p>)}</section>}
        <section><h2>امکانات ثبت‌شده</h2>{h.amenities.length ? <ul className="cat-amen">{h.amenities.map(a => <li key={a.key}>{a.label}</li>)}</ul> : <p className="cat-muted">امکانات این اقامتگاه در منبع مرجع ثبت نشده است؛ هنگام استعلام اعلام می‌شود.</p>}</section>
        {h.room_types?.length ? <section><h2>انواع اتاق</h2><ul className="cat-rooms">{h.room_types.map(r => <li key={r.id}>{r.image_url && /* eslint-disable-next-line @next/next/no-img-element */ <img className="cat-room-img" src={r.image_url} alt={r.name_fa} loading="lazy"/>}<strong>{r.name_fa}</strong>{r.name_en && <span dir="ltr" lang="en"> {r.name_en}</span>}<p>{[r.bed_type_fa, r.max_adults ? `${fa(r.max_adults)} بزرگسال` : null, r.max_children ? `${fa(r.max_children)} کودک` : null, r.size_m2 ? `${fa(r.size_m2)} متر مربع` : null, r.view_fa ? `منظره: ${r.view_fa}` : null].filter(Boolean).join(' · ')}</p>{r.description && <p>{r.description}</p>}{r.amenities.length > 0 && <ul className="cat-amen">{r.amenities.map(a => <li key={a.key}>{a.label}</li>)}</ul>}</li>)}</ul><p className="cat-muted">این فهرست توصیف انواع اتاق است و به معنی موجودی یا قیمت نیست.</p></section> : null}
        <section><h2>ورود و خروج</h2><p className={h.checkin_time || h.checkout_time ? '' : 'cat-muted'}>{h.checkin_time || h.checkout_time ? <>ورود: {h.checkin_time ?? '—'} · خروج: {h.checkout_time ?? '—'}</> : 'ساعت ورود و خروج و قوانین اقامت هنگام استعلام از اقامتگاه تأیید می‌شود.'}</p>{h.policies?.length ? <dl className="cat-dl">{h.policies.map(p => <span key={p.key} style={{display: 'contents'}}><dt>{p.label}</dt><dd>{p.value_fa}</dd></span>)}</dl> : null}{h.rules_text && <p>{h.rules_text}</p>}</section>
        {h.details && Object.keys(h.details).length > 0 && <section><h2>مشخصات اقامتگاه</h2><dl className="cat-dl">
          {([['محدوده', h.details.district], ['تعداد اتاق', h.details.room_count], ['تعداد تخت', h.details.bed_count], ['سال ساخت', h.details.built_year_jalali], ['تعداد طبقه', h.details.floors], ['چشم‌انداز', h.details.hotel_view], ['وعدهٔ قابل ارائه', h.details.board_plans?.join('، ')]] as [string, string | undefined][]).filter(([, v]) => v).map(([k, v]) => <span key={k} style={{display: 'contents'}}><dt>{k}</dt><dd>{v}</dd></span>)}</dl>
          {h.details.nearby?.length ? <><h3>فاصله تا مکان‌های مهم</h3><ul className="cat-access">{h.details.nearby.map((n, i) => <li key={i}>{n.place}{n.distance ? ` — ${n.distance}${n.unit === 'km' ? ' کیلومتر' : n.unit === 'm' ? ' متر' : n.unit ? ` ${n.unit}` : ''}` : ''}</li>)}</ul></> : null}
          {h.details.restaurants?.length ? <><h3 className="cat-h3">رستوران و کافه</h3><ul className="cat-access">{h.details.restaurants.map((r, i) => <li key={i}>{r.name}{r.hours ? ` — ${r.hours}` : ''}</li>)}</ul></> : null}
          {h.details.traffic && <p>{h.details.traffic}</p>}{h.details.review && h.details.review.split('\n').map((line, i) => <p key={i}>{line}</p>)}
          {h.details.map_link && <p><a href={h.details.map_link} target="_blank" rel="noreferrer nofollow">جست‌وجوی این اقامتگاه روی نقشه</a> <span className="cat-muted">(مختصات دقیق در منبع ثبت نشده است)</span></p>}</section>}
        <section><h2>موقعیت و تماس</h2><dl className="cat-dl">
          {h.address && <><dt>نشانی</dt><dd>{h.address}</dd></>}
          {h.latitude !== null && h.longitude !== null && <><dt>مختصات</dt><dd><a href={osmLink(h.latitude, h.longitude)} target="_blank" rel="noreferrer" dir="ltr">{h.latitude.toFixed(5)}, {h.longitude.toFixed(5)}</a> (نمایش روی نقشه)</dd></>}
          {h.phone && <><dt>تلفن</dt><dd><a href={`tel:${h.phone.replace(/[^\d+]/g, '')}`} dir="ltr">{h.phone}</a></dd></>}
          {h.website && <><dt>وب‌سایت</dt><dd><a href={h.website} target="_blank" rel="noreferrer nofollow" dir="ltr">{h.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}</a></dd></>}
          {h.email && <><dt>ایمیل</dt><dd><a href={`mailto:${h.email}`} dir="ltr">{h.email}</a></dd></>}
        </dl></section>
        {(h.nearby_airports?.length || h.nearby_rail_stations?.length) ? <section><h2>دسترسی</h2><ul className="cat-access">{h.nearby_airports?.map(a => <li key={a.iata}>فرودگاه {a.name} <span dir="ltr">({a.iata})</span></li>)}{h.nearby_rail_stations?.map(s => <li key={s.id}>ایستگاه راه‌آهن {s.name}</li>)}</ul></section> : null}
      </div>
      <aside className="cat-inquiry"><h2>قیمت و رزرو</h2><p className="cat-price">{h.price_note}</p><p>برای این اقامتگاه هنوز نرخ تأییدشده‌ای از تأمین‌کننده ثبت نشده است. تاریخ و تعداد مهمان را مشخص کنید یا از پشتیبانی استعلام بگیرید.</p>
        <Link className="button primary" href={`/search/results?vertical=hotel&destination=${encodeURIComponent(h.city?.name ?? h.name)}`}>جست‌وجوی اقامت در {h.city?.name ?? 'این مقصد'}</Link>
        <InquiryRequest subject={`استعلام اقامت: ${h.name}`} context={`درخواست استعلام نرخ و موجودی برای «${h.name}»${h.city ? ` در ${h.city.name}` : ''} (شناسهٔ فهرست: ${h.id}).`} reason={h.request?.reason ?? 'نرخ تأییدشده‌ای ثبت نشده است.'}/></aside>
    </div>
    {h.provenance && <p className="cat-attrib">منبع دادهٔ این صفحه: {h.provenance.source === 'openstreetmap' ? <a href={`https://www.openstreetmap.org/${h.provenance.source_ref}`} target="_blank" rel="noreferrer">OpenStreetMap</a> : h.provenance.source} — {h.provenance.license}{h.provenance.retrieved_on ? ` — دریافت: ${h.provenance.retrieved_on}` : ''}. این صفحه اطلاعات مرجع است و قیمت یا موجودی را نشان نمی‌دهد.</p>}
  </main>;
}

export function VenueDirectory({kinds, title, intro}: {kinds: string[]; title: string; intro?: string}) {
  const {params, set} = useQueryState();
  const city = params.get('vcity') || '', q = params.get('vq') || '', kind = params.get('vkind') || '', page = Math.max(1, Number(params.get('vpage')) || 1);
  const kindParam = kind && kinds.includes(kind) ? kind : kinds.join(',');
  const facets = useCatalog<{cities: {id: string; name: string; count: number}[]}>(`/catalog/venues/facets?kind=${kindParam}`);
  const query = new URLSearchParams({kind: kindParam, limit: String(PAGE), offset: String((page - 1) * PAGE)});
  if (city) query.set('city', city); if (q) query.set('q', q);
  const list = useCatalog<Page<Venue>>(`/catalog/venues?${query}`);
  const data = list.data ?? list.stale;
  return <section className="cat" id="directory" aria-labelledby="cat-venues-title">
    <header className="cat-head"><div><h2 id="cat-venues-title">{title}</h2><p>{intro ?? 'فهرست مرجع مکان‌های ثبت‌شده. ساعت کار، ظرفیت و قیمت را پیش از مراجعه یا رزرو استعلام کنید.'}</p></div>
      <SearchBox value={q} onSubmit={v => set({vq: v || null, vpage: null})} placeholder="نام یا شهر"/></header>
    <div className="cat-filters">
      {kinds.length > 1 && <label>نوع<select value={kind} onChange={e => set({vkind: e.target.value || null, vpage: null})}><option value="">همه</option>{kinds.map(k => <option key={k} value={k}>{VENUE_KIND_FA[k] ?? k}</option>)}</select></label>}
      <label>شهر<select value={city} onChange={e => set({vcity: e.target.value || null, vpage: null})}><option value="">همهٔ شهرها</option>{(facets.data ?? facets.stale)?.cities.map(c => <option key={c.id} value={c.id}>{c.name} ({fa(c.count)})</option>)}</select></label>
    </div>
    <div className="cat-meta"><span aria-live="polite">{data ? `${fa(data.total)} مورد` : ''}</span></div>
    <Status loading={list.loading} error={list.error} empty={!data || data.items.length === 0}/>
    {data && data.items.length > 0 && <div className={`cat-grid cat-grid-venue${list.loading ? ' is-loading' : ''}`}>{data.items.map(v => <article className="cat-card cat-venue" key={v.id}>
      {v.image_url && <Thumb src={v.image_url} credit={v.image_credit} alt={v.name} label=""/>}
      <div className="cat-card-body"><div className="cat-card-top"><span className="cat-tag">{v.kind_fa}</span>{v.detail && <span className="cat-detail-tag" dir="auto">{v.detail.replace(/[_;]/g, ' ')}</span>}</div>
        <h3>{v.name}</h3>{v.name_en && v.name_en !== v.name && <p className="cat-en" dir="ltr" lang="en">{v.name_en}</p>}
        <p className="cat-where">{[v.city?.name, v.region?.name].filter(Boolean).join('، ')}{v.address ? ` — ${v.address}` : ''}</p>
        {v.opening_hours && <p className="cat-muted" dir="ltr">{v.opening_hours}</p>}
        <p className="cat-links"><a href={osmLink(v.latitude, v.longitude)} target="_blank" rel="noreferrer">نقشه</a>{v.phone && <a href={`tel:${v.phone.replace(/[^\d+]/g, '')}`} dir="ltr">{v.phone}</a>}{v.website && <a href={v.website} target="_blank" rel="noreferrer nofollow">وب‌سایت</a>}</p>
        <p className="cat-price">{v.price_note}</p></div></article>)}</div>}
    {data && <Pager total={data.total} limit={PAGE} page={page} onPage={p => {set({vpage: p > 1 ? String(p) : null}); document.getElementById('directory')?.scrollIntoView();}}/>}
    {ATTRIBUTION}
  </section>;
}

export function AirlineDirectory() {
  const [country, setCountry] = useState('IR');
  const {data, loading, error} = useCatalog<{items: Airline[]}>(`/catalog/airlines${country ? '?country=' + country : ''}`);
  return <section className="cat" aria-labelledby="cat-airlines-title">
    <header className="cat-head"><div><h2 id="cat-airlines-title">شرکت‌های هواپیمایی</h2><p>مشخصات مرجع ایرلاین‌ها (نام، کد یاتا و ایکائو، وب‌سایت رسمی). برنامهٔ پرواز، ظرفیت و قیمت فقط از نتیجهٔ جست‌وجوی پرواز اعلام می‌شود.</p></div></header>
    <div className="cat-chips" role="group" aria-label="کشور">{['IR', 'TR', 'AE', 'IQ', 'AM', 'GE', 'QA', 'OM', 'KW', 'AZ', ''].map(c => <button key={c || 'all'} className={country === c ? 'on' : ''} onClick={() => setCountry(c)}>{c ? COUNTRY_FA[c] : 'همه'}</button>)}</div>
    <Status loading={loading} error={error} empty={!data || data.items.length === 0}/>
    {data && <div className="cat-grid cat-grid-ref">{data.items.map(a => <article className="cat-ref" key={a.id}>
      {/* eslint-disable-next-line @next/next/no-img-element -- airline logo from Wikimedia Commons, credited in title */}
      <div className="cat-logo">{a.logo_url ? <img src={a.logo_url} alt={`نشان ${a.name}`} title={a.logo_credit ?? undefined} loading="lazy"/> : <b dir="ltr">{a.iata}</b>}</div>
      <div><h3>{a.name}</h3>{a.name_en && <p className="cat-en" dir="ltr" lang="en">{a.name_en}</p>}
        <p className="cat-codes" dir="ltr"><span>IATA {a.iata}</span>{a.icao && <span>ICAO {a.icao}</span>}</p>
        <p className="cat-where">{COUNTRY_FA[a.country_code] ?? a.country_code}{a.airline_type && AIRLINE_TYPE_FA[a.airline_type] ? ` · ${AIRLINE_TYPE_FA[a.airline_type]}` : ''}</p>
        {a.website && <a href={a.website} target="_blank" rel="noreferrer nofollow">وب‌سایت رسمی</a>}</div></article>)}</div>}
  </section>;
}

export function AirportDirectory() {
  const [country, setCountry] = useState('IR');
  const {data, loading, error} = useCatalog<{items: Airport[]}>(`/catalog/airports?country=${country}`);
  return <section className="cat" aria-labelledby="cat-airports-title">
    <header className="cat-head"><div><h2 id="cat-airports-title">فرودگاه‌ها</h2><p>فرودگاه‌های دارای کد یاتا در ایران و مقاصد اصلی منطقه.</p></div></header>
    <div className="cat-chips" role="group" aria-label="کشور">{['IR', 'TR', 'AE', 'IQ', 'AM', 'GE'].map(c => <button key={c} className={country === c ? 'on' : ''} onClick={() => setCountry(c)}>{COUNTRY_FA[c]}</button>)}</div>
    <Status loading={loading} error={error} empty={!data || data.items.length === 0}/>
    {data && <div className="cat-table-wrap"><table className="cat-table"><thead><tr><th>فرودگاه</th><th>شهر</th><th>IATA</th><th>ICAO</th><th>منطقهٔ زمانی</th></tr></thead>
      <tbody>{data.items.map(a => <tr key={a.iata}><td>{a.name}{a.scope === 'international' && <small> · بین‌المللی</small>}<span className="cat-en" dir="ltr" lang="en">{a.name_en}</span></td><td>{a.city_name ?? '—'}</td><td dir="ltr">{a.iata}</td><td dir="ltr">{a.icao ?? '—'}</td><td dir="ltr">{a.timezone ?? '—'}</td></tr>)}</tbody></table></div>}
  </section>;
}

export function RailDirectory() {
  const ops = useCatalog<{items: {id: string; name_fa: string; name_en: string | null; operator_kind: string | null; website: string | null}[]}>('/catalog/rail/operators');
  const [q, setQ] = useState('');
  const stations = useCatalog<{items: Station[]}>(`/catalog/rail/stations?limit=1000${q ? '&q=' + encodeURIComponent(q) : ''}`);
  const items = (stations.data ?? stations.stale)?.items ?? [];
  return <section className="cat" aria-labelledby="cat-rail-title">
    <header className="cat-head"><div><h2 id="cat-rail-title">شرکت‌ها و ایستگاه‌های ریلی</h2><p>اطلاعات مرجع راه‌آهن. ساعت حرکت، ظرفیت و قیمت بلیت فقط از نتیجهٔ جست‌وجوی قطار اعلام می‌شود.</p></div><SearchBox value={q} onSubmit={setQ} placeholder="نام ایستگاه یا شهر"/></header>
    {ops.data && <div className="cat-grid cat-grid-ref">{ops.data.items.map(o => <article className="cat-ref" key={o.id}><div className="cat-logo"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M7 4h10a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM5 11h14M9 14h.01M15 14h.01M8 21l2-4M16 21l-2-4"/></svg></div>
      <div><h3>{o.name_fa}</h3>{o.name_en && <p className="cat-en" dir="ltr" lang="en">{o.name_en}</p>}<p className="cat-where">{o.operator_kind === 'national_infrastructure' ? 'شبکهٔ ملی راه‌آهن' : 'شرکت مسافری ریلی'}</p>{o.website && <a href={o.website} target="_blank" rel="noreferrer nofollow">وب‌سایت رسمی</a>}</div></article>)}</div>}
    <h3 className="cat-sub">ایستگاه‌ها {items.length ? <small>({fa(items.length)})</small> : null}</h3>
    <Status loading={stations.loading} error={stations.error} empty={items.length === 0}/>
    <ul className="cat-station-list">{items.map(s => <li key={s.id}><a href={osmLink(s.latitude, s.longitude)} target="_blank" rel="noreferrer">{s.name}</a>{s.name_en && s.name_en !== s.name && <span className="cat-en" dir="ltr" lang="en">{s.name_en}</span>}</li>)}</ul>
    {ATTRIBUTION}
  </section>;
}

export function DestinationDirectory() {
  const [country, setCountry] = useState('IR');
  const {data, loading, error} = useCatalog<{items: Place[]}>(`/catalog/places?kind=city&country=${country}&with_hotels=true&limit=48`);
  return <section className="cat" aria-labelledby="cat-dest-title">
    <header className="cat-head"><div><h2 id="cat-dest-title">مقصدها</h2><p>شهرها و مقصدهای ایران و کشورهای پرسفر منطقه، همراه با اقامتگاه‌ها، فرودگاه‌ها و ایستگاه‌های ثبت‌شده.</p></div></header>
    <div className="cat-chips" role="group" aria-label="کشور">{['IR', 'TR', 'AE', 'AM', 'GE', 'IQ'].map(c => <button key={c} className={country === c ? 'on' : ''} onClick={() => setCountry(c)}>{COUNTRY_FA[c]}</button>)}</div>
    <Status loading={loading} error={error} empty={!data || data.items.length === 0}/>
    {data && <div className="cat-grid cat-grid-dest">{data.items.map(p => <Link className="cat-card cat-dest" key={p.id} href={`/destinations/${p.id}`}>
      {p.image_url ? <Thumb src={p.image_url} credit={p.image_credit} alt={p.name} label=""/> : null}
      <div className="cat-card-body"><h3>{p.name}</h3>{p.name_en && <p className="cat-en" dir="ltr" lang="en">{p.name_en}</p>}<p className="cat-where">{fa(p.hotel_count)} اقامتگاه ثبت‌شده</p></div></Link>)}</div>}
    {ATTRIBUTION}
  </section>;
}

const PLACE_VENUE_LINKS: [string, string, string][] = [['restaurant', 'رستوران', '/restaurants'], ['cafe', 'کافه', '/restaurants'], ['attraction', 'جاذبه', '/attractions'], ['museum', 'موزه', '/attractions'], ['historic', 'بنای تاریخی', '/attractions'], ['pool_sport', 'استخر و ورزش', '/pools-sports'], ['event_venue', 'تالار و رویداد', '/events-venues'], ['handicraft', 'صنایع‌دستی', '/handicrafts'], ['car_rental', 'اجاره خودرو', '/car-rental']];
export function CatalogPlaceView({slug, fallback}: {slug: string; fallback: ReactNode}) {
  const {data: p, loading, error} = useCatalog<PlaceDetail>(`/catalog/places/${encodeURIComponent(slug)}`);
  if (error) return <>{fallback}</>;
  if (!p) return <Status loading={loading} error={false} empty/>;
  const hotelsHref = `/hotels?country=${p.country_code}${p.kind === 'city' ? '&city=' + p.id : p.kind === 'region' ? '&region=' + p.id : ''}`;
  return <div className="cat cat-place">
    {p.breadcrumbs && p.breadcrumbs.length > 0 && <nav className="cat-crumbs" aria-label="مسیر"><Link href="/destinations">مقصدها</Link>{p.breadcrumbs.map(b => <Link key={b.id} href={`/destinations/${b.id}`}>{b.name}</Link>)}</nav>}
    <header className="cat-detail-head"><h1>سفر به {p.name}</h1>{p.name_en && <p className="cat-en" dir="ltr" lang="en">{p.name_en}</p>}<p className="cat-where">{[p.parent?.name, COUNTRY_FA[p.country_code]].filter(x => x && x !== p.name).join('، ')}{p.population ? ` · جمعیت ${fa(p.population)}` : ''}</p></header>
    {p.image_url && <Thumb src={p.image_url} credit={p.image_credit} alt={p.name} label=""/>}
    {p.description && p.description.split('\n').map((line, i) => <p key={i}>{line}</p>)}
    {p.details && Object.keys(p.details).length > 0 && <section><h2>اطلاعات مقصد</h2><dl className="cat-dl">{([['پایتخت', p.details.capital], ['واحد پول', p.details.currency], ['زبان رسمی', p.details.official_language], ['جمعیت', p.details.population_text], ['برق شهری', p.details.voltage], ['اختلاف ساعت', p.details.time_zone]] as [string, string | undefined][]).filter(([, v]) => v).map(([k, v]) => <span key={k} style={{display: 'contents'}}><dt>{k}</dt><dd>{v}</dd></span>)}</dl>
      {p.details.guide && p.details.guide.split('\n').map((line, i) => <p key={i}>{line}</p>)}{p.details.visa_note && <><h3 className="cat-h3">ویزا</h3>{p.details.visa_note.split('\n').map((line, i) => <p key={i}>{line}</p>)}</>}</section>}
    {p.details?.images && p.details.images.length > 1 && <div className="cat-gallery" aria-label="تصاویر مقصد">{p.details.images.slice(0, 6).map((src, i) => <figure key={src}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={src} alt={`${p.name} ${i + 1}`} loading="lazy"/></figure>)}</div>}
    {p.details?.map_link && <p><a href={p.details.map_link} target="_blank" rel="noreferrer nofollow">نمایش {p.name} روی نقشه</a></p>}
    {p.details?.visa_note && <p><Link className="button secondary" href={`/visa/cl-visa-country-${p.country_code.toLowerCase()}`}>راهنمای کامل ویزای {p.name}</Link></p>}
    {p.reference_tours && p.reference_tours.length > 0 && <section><h2>تورهای برگزارشده به این مقصد</h2><div className="cat-grid">{p.reference_tours.map(t => <TourCard key={t.id} t={t}/>)}</div></section>}
    <div className="cat-place-stats"><Link href={hotelsHref}><b>{fa(p.hotels)}</b> هتل و اقامتگاه</Link>
      {PLACE_VENUE_LINKS.filter(([k]) => p.venue_counts[k]).map(([k, label, href]) => <Link key={k} href={`${href}?vcity=${p.kind === 'city' ? p.id : ''}&vkind=${k}`}><b>{fa(p.venue_counts[k])}</b> {label}</Link>)}</div>
    {p.airports.length > 0 && <section><h2>فرودگاه‌ها</h2><ul className="cat-access">{p.airports.map(a => <li key={a.iata}>{a.name} <span dir="ltr">({a.iata})</span></li>)}</ul></section>}
    {p.rail_stations.length > 0 && <section><h2>ایستگاه‌های راه‌آهن</h2><ul className="cat-access">{p.rail_stations.map(s => <li key={s.id}>{s.name}</li>)}</ul></section>}
    {p.children.filter(c => c.hotel_count > 0).length > 0 && <section><h2>شهرها و مقصدهای این منطقه</h2><div className="cat-chips">{p.children.filter(c => c.hotel_count > 0).map(c => <Link key={c.id} href={`/destinations/${c.id}`}>{c.name} <small>{fa(c.hotel_count)}</small></Link>)}</div></section>}
    {p.reference_tours && p.reference_tours.length > 0 && <p><Link className="button secondary" href={`/tours/destination/${p.id}`}>همهٔ تورهای {p.name}</Link></p>}
    {p.related && p.related.length > 0 && <section><h2>مقصدهای مرتبط</h2><div className="cat-chips">{p.related.map(r => <Link key={r.id} href={`/destinations/${r.id}`}>{r.name}{r.hotel_count ? <small> {fa(r.hotel_count)}</small> : null}</Link>)}</div></section>}
    <p className="cat-price">قیمت و ظرفیت خدمات این مقصد پس از انتخاب تاریخ و استعلام اعلام می‌شود.</p>
    <div className="customer-actions"><Link className="button primary" href={hotelsHref}>اقامتگاه‌های {p.name}</Link><Link className="button secondary" href={`/search/results?vertical=hotel&destination=${encodeURIComponent(p.name)}`}>جست‌وجوی اقامت با تاریخ</Link></div>
    {ATTRIBUTION}
  </div>;
}

/* ---- Reference tours carried over from the previous catalogue: descriptive only, never sellable from here ---- */
type TourBrief = {id: string; slug: string; href: string; categories: string[]; title: string; destination: Brief; duration_nights: number | null; duration_days: number | null; transport_fa: string | null; image_url: string | null; image_credit: string | null;
  departures_recorded: number; latest_departure: string | null; state_note: string};
type TourFull = TourBrief & {description: string | null; guide_included: boolean | null; transfer_included: boolean | null; documents_required: string | null; cancellation_policy_text: string | null; board_fa: string | null;
  details: {long_title?: string; services_text?: string; inclusions?: string[]; leave_duration?: string; difficulty?: string; age_range?: string; moving_point?: string; roadmap?: string; notice?: string;
    transport_legs?: {mode: string | null; origin: string | null; destination: string | null; departs: string | null; arrives: string | null; carrier: string | null}[]; images?: string[]; carriers?: string[]; ribbon?: string; booking_note?: string; hotel_notes?: string[]};
  origin: string | null; travel_requirements: {country_id: string; country: string; visa_note: string} | null; request: {reason: string};
  itinerary: {day_no: number; title: string; description: string | null}[]; hotels: {id: string; name: string; stars: number | null; slug: string | null; nights: number | null}[];
  departures: {starts_jalali: string | null; ends_jalali: string | null; past: boolean}[]};
const duration = (t: {duration_nights: number | null; duration_days: number | null}) => t.duration_nights !== null && t.duration_days !== null ? `${fa(t.duration_nights)} شب و ${fa(t.duration_days)} روز` : t.duration_nights !== null ? `${fa(t.duration_nights)} شب` : t.duration_days !== null ? `${fa(t.duration_days)} روز` : null;

export function TourCard({t}: {t: TourBrief}) {
  return <Link className="cat-card" href={t.href}><Thumb src={t.image_url} credit={null} alt={t.title} label="تور"/>
    <div className="cat-card-body"><h3>{t.title}</h3><p className="cat-where">{[t.destination?.name, duration(t), t.transport_fa].filter(Boolean).join(' · ')}</p>
      <p className="cat-price">قیمت و تاریخ جدید با استعلام</p></div></Link>;
}

export function TourCatalog({title = 'برنامهٔ تورهای برگزارشده', intro, limit, presetDestination}: {title?: string; intro?: string; limit?: number; presetDestination?: string}) {
  const {params, set} = useQueryState();
  const destination = presetDestination || params.get('destination') || '', q = params.get('tq') || '', page = Math.max(1, Number(params.get('tpage')) || 1);
  const category = params.get('category') || '', nights = params.get('nights') || '', year = params.get('year') || '';
  const size = limit ?? PAGE;
  const query = new URLSearchParams(); if (destination) query.set('destination', destination); if (q) query.set('q', q); if (category) query.set('category', category); if (nights) query.set('nights', nights); if (year) query.set('year', year); query.set('limit', String(size)); query.set('offset', String((page - 1) * size));
  const list = useCatalog<{total: number; items: TourBrief[]; destinations: {id: string; name: string; count: number}[]; categories: {name: string; count: number}[]; years: number[]}>(`/catalog/tours?${query}`);
  const data = list.data ?? list.stale;
  return <section className="cat" id="tour-catalog" aria-labelledby="cat-tours-title">
    <header className="cat-head"><div><h2 id="cat-tours-title">{title}</h2><p>{intro ?? 'برنامه، مقصد، مدت، خدمات و هتل‌های تورهایی که پیش‌تر برگزار شده‌اند. تاریخ حرکت و قیمت جدید فقط با استعلام از برگزارکننده اعلام می‌شود و از این فهرست رزرو انجام نمی‌شود.'}</p></div>
      <SearchBox value={q} onSubmit={v => set({tq: v || null, tpage: null})} placeholder="نام تور یا مقصد"/></header>
    {data && !presetDestination && data.destinations.length > 0 && <div className="cat-chips" role="group" aria-label="مقصد تور"><button className={!destination ? 'on' : ''} onClick={() => set({destination: null, tpage: null})}>همهٔ مقصدها</button>
      {data.destinations.map(d => <button key={d.id} className={destination === d.id ? 'on' : ''} onClick={() => set({destination: d.id, tpage: null})}>{d.name} <small>{fa(d.count)}</small></button>)}</div>}
    {data && !limit && <div className="cat-filters"><label>دسته‌بندی<select value={category} onChange={e => set({category: e.target.value || null, tpage: null})}><option value="">همه</option>{data.categories.map(c => <option key={c.name} value={c.name}>{c.name} ({fa(c.count)})</option>)}</select></label>
      <label>مدت<select value={nights} onChange={e => set({nights: e.target.value || null, tpage: null})}><option value="">همه</option><option value="1-3">۱ تا ۳ شب</option><option value="4-6">۴ تا ۶ شب</option><option value="7+">۷ شب و بیشتر</option></select></label>
      <label>سال برگزاری<select value={year} onChange={e => set({year: e.target.value || null, tpage: null})}><option value="">همه</option>{data.years.map(y => <option key={y} value={y}>{fa(y).replace(/٬/g, '')}</option>)}</select></label></div>}
    <div className="cat-meta"><span aria-live="polite">{data ? `${fa(data.total)} تور` : ''}</span>{((destination && !presetDestination) || q || category || nights || year) && <button onClick={() => set({destination: null, tq: null, tpage: null, category: null, nights: null, year: null})}>حذف فیلترها</button>}</div>
    <Status loading={list.loading} error={list.error} empty={!data || data.items.length === 0}>توری با این شرایط ثبت نشده است.</Status>
    {data && data.items.length > 0 && <div className={`cat-grid${list.loading ? ' is-loading' : ''}`}>{data.items.map(t => <TourCard key={t.id} t={t}/>)}</div>}
    {data && !limit && <Pager total={data.total} limit={size} page={page} onPage={p => {set({tpage: p > 1 ? String(p) : null}); document.getElementById('tour-catalog')?.scrollIntoView();}}/>}
    {limit && data && data.total > data.items.length ? <Link className="button secondary" href="/tours/search">جست‌وجو در همهٔ برنامه‌های تور</Link> : null}
  </section>;
}

export function TourReferenceDetail({id}: {id: string}) {
  const {data: t, loading, error} = useCatalog<TourFull>(`/catalog/tours/${encodeURIComponent(id)}`);
  if (!t) return <main className="journey-main cat-detail"><Status loading={loading} error={false} empty>{error ? 'این تور در فهرست پیدا نشد.' : undefined}</Status><Link className="button secondary" href="/tours/search">بازگشت به برنامهٔ تورها</Link></main>;
  const d = t.details;
  const facts = [['مبدأ', t.origin], ['مقصد', t.destination?.name], ['مدت', duration(t)], ['شرکت حمل‌ونقل', d.carriers?.join('، ')], ['حمل‌ونقل', t.transport_fa], ['وعده', t.board_fa], ['راهنما', t.guide_included ? 'دارد' : null], ['ترانسفر', t.transfer_included ? 'دارد' : null], ['محل حرکت', d.moving_point], ['مدت مرخصی لازم', d.leave_duration], ['سطح دشواری', d.difficulty], ['ردهٔ سنی', d.age_range]].filter(([, v]) => v) as [string, string][];
  return <main className="journey-main cat-detail">
    <nav className="cat-crumbs" aria-label="مسیر"><Link href="/tours">تورها</Link><Link href="/tours/search">برنامهٔ تورهای برگزارشده</Link>{t.destination && <Link href={`/tours/destination/${t.destination.id}`}>{t.destination.name}</Link>}</nav>
    <header className="cat-detail-head"><div><span className="cat-tag">تور برگزارشده</span></div><h1>{t.title}</h1>{d.long_title && d.long_title !== t.title && <p className="cat-where">{d.long_title}</p>}</header>
    <div className="cat-detail-grid">
      <div>
        {d.images && d.images.length > 0 ? <div className="cat-gallery">{[...(t.image_url && !d.images.includes(t.image_url) ? [t.image_url] : []), ...d.images].map((src, i) => <figure key={src} className={i === 0 ? 'lead' : ''}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={src} alt={`${t.title} ${i + 1}`} loading={i ? 'lazy' : 'eager'}/></figure>)}</div>
          : t.image_url ? <Thumb src={t.image_url} credit={t.image_credit} alt={t.title} label=""/> : <div className="cat-noimage">برای این تور تصویری ثبت نشده است.</div>}
        {t.categories.length > 0 && <ul className="cat-amen" aria-label="دسته‌بندی">{t.categories.map(c => <li key={c}><Link href={`/tours/search?category=${encodeURIComponent(c)}`}>{c}</Link></li>)}</ul>}
        {t.description && <section><h2>دربارهٔ تور</h2>{t.description.split('\n').map((line, i) => <p key={i}>{line}</p>)}</section>}
        <section><h2>مشخصات</h2>{facts.length ? <dl className="cat-dl">{facts.map(([k, v]) => <span key={k} style={{display: 'contents'}}><dt>{k}</dt><dd>{v}</dd></span>)}</dl> : <p className="cat-muted">مشخصات این تور در منبع ثبت نشده است.</p>}</section>
        {(d.inclusions?.length || d.services_text) ? <section><h2>خدمات تور</h2>{d.inclusions?.length ? <ul className="cat-amen">{d.inclusions.map(x => <li key={x}>{x}</li>)}</ul> : null}{d.services_text && d.services_text.split('\n').map((line, i) => <p key={i}>{line}</p>)}</section> : null}
        {d.transport_legs?.length ? <section><h2>برنامهٔ حمل‌ونقل</h2><ul className="cat-access">{d.transport_legs.map((l, i) => <li key={i}>{[l.mode, [l.origin, l.destination].filter(Boolean).join(' ← '), l.carrier, l.departs && `حرکت ${l.departs}`, l.arrives && `رسیدن ${l.arrives}`].filter(Boolean).join(' · ')}</li>)}</ul></section> : null}
        {t.itinerary.length > 0 && <section><h2>برنامهٔ سفر</h2><ul className="cat-rooms">{t.itinerary.map(i => <li key={i.day_no}><strong>روز {fa(i.day_no)}: {i.title}</strong>{i.description && <p>{i.description}</p>}</li>)}</ul></section>}
        {t.hotels.length > 0 && <section><h2>هتل‌های این تور</h2><ul className="cat-access">{t.hotels.map(h => <li key={h.id}>{h.slug ? <Link href={`/hotels/${h.slug}`}>{h.name}</Link> : h.name}{h.stars ? ` · ${fa(h.stars)} ستاره` : ''}{h.nights ? ` · ${fa(h.nights)} شب` : ''}</li>)}</ul></section>}
        {t.departures.length > 0 && <section><h2>تاریخ‌های برگزارشده</h2><ul className="cat-amen">{t.departures.map((x, i) => <li key={i} dir="ltr">{x.starts_jalali}{x.ends_jalali ? ` → ${x.ends_jalali}` : ''}</li>)}</ul><p className="cat-muted">این تاریخ‌ها سابقهٔ برگزاری است و قابل رزرو نیست.</p></section>}
        {d.hotel_notes?.length ? <section><h2>توضیح هتل‌ها</h2>{d.hotel_notes.map((n, i) => <p key={i}>{n}</p>)}</section> : null}
        {(t.travel_requirements || t.documents_required) && <section><h2>مدارک و ویزا</h2>{t.documents_required && <p>{t.documents_required}</p>}{t.travel_requirements && <><p>{t.travel_requirements.visa_note.split('\n')[0]}</p><Link href={`/visa/cl-visa-country-${t.travel_requirements.country_id}`}>راهنمای کامل ویزای {t.travel_requirements.country}</Link></>}</section>}
        {d.booking_note && <section><h2>یادداشت برگزارکننده</h2><p>{d.booking_note}</p></section>}
        {t.cancellation_policy_text && <section><h2>قوانین لغو</h2>{t.cancellation_policy_text.split('\n').map((line, i) => <p key={i}>{line}</p>)}</section>}
        {d.notice && <section><h2>توضیحات</h2><p>{d.notice}</p></section>}
      </div>
      <aside className="cat-inquiry"><h2>قیمت و تاریخ حرکت</h2><p className="cat-price">قیمت و تاریخ جدید با استعلام</p><p>{t.state_note}</p>
        <InquiryRequest subject={`استعلام تور: ${t.title}`} context={`درخواست استعلام تاریخ حرکت و قیمت جدید برای «${t.title}» (شناسهٔ فهرست: ${t.id}).`} reason={t.request.reason}/>
        <Link className="button secondary" href="/tours">تورهای قابل رزرو</Link></aside>
    </div>
    <p className="cat-attrib">منبع این صفحه: فهرست تورهای چک‌لاین (سابقهٔ برگزاری). این صفحه قیمت، ظرفیت یا تاریخ قابل رزرو نشان نمی‌دهد.</p>
  </main>;
}


/* ---- Travel requirements (visa guidance carried over from the source) ---- */
type VisaGuideData = {countries: {id: string; country_code: string; name: string; visa_note: string; flag_url?: string | null}[]; articles: {id: string; title: string; excerpt: string}[]; disclaimer: string};
export function VisaGuide() {
  const {data, loading, error} = useCatalog<VisaGuideData>('/catalog/visa');
  return <section className="cat" aria-labelledby="visa-guide-title"><header className="cat-head"><div><h2 id="visa-guide-title">راهنمای ویزا و مدارک سفر</h2><p>{data?.disclaimer ?? 'راهنمای عمومی ویزا به تفکیک مقصد.'}</p></div></header>
    <Status loading={loading} error={error} empty={!data || (data.countries.length === 0 && data.articles.length === 0)}>راهنمایی برای نمایش ثبت نشده است.</Status>
    {data && data.countries.length > 0 && <><h3 className="cat-h3">به تفکیک کشور</h3><div className="cat-chips">{data.countries.map(c => <Link key={c.id} href={`/visa/cl-visa-country-${c.id}`}>ویزای {c.name}</Link>)}</div></>}
    {data && data.articles.length > 0 && <><h3 className="cat-h3">مقاله‌های راهنما</h3><ul className="cat-rooms">{data.articles.map(a => <li key={a.id}><Link href={`/visa/${a.id}`}><strong>{a.title}</strong></Link><p>{a.excerpt}…</p></li>)}</ul></>}
  </section>;
}
export function VisaArticle({id}: {id: string}) {
  const {data: c, loading, error} = useCatalog<{id: string; kind: string; title: string; body: string}>(`/catalog/content/${encodeURIComponent(id)}`);
  if (!c) return <main className="journey-main cat-detail"><Status loading={loading} error={false} empty>{error ? 'این راهنما پیدا نشد.' : undefined}</Status><Link className="button secondary" href="/visa">بازگشت به راهنمای ویزا</Link></main>;
  const country = c.kind === 'visa_country' ? c.id.replace('cl-visa-country-', '') : null;
  return <main className="journey-main cat-detail"><nav className="cat-crumbs" aria-label="مسیر"><Link href="/visa">ویزا و مدارک سفر</Link>{country && <Link href={`/destinations/${country}`}>راهنمای مقصد</Link>}</nav>
    <header className="cat-detail-head"><h1>{c.title}</h1></header><section>{c.body.split('\n').map((line, i) => <p key={i}>{line}</p>)}</section>
    <p className="cat-muted">این متن راهنمای عمومی است؛ شرایط، مدارک و هزینه را سفارت مقصد تعیین می‌کند و هیچ نتیجه‌ای تضمین نمی‌شود.</p>
    {country && <p><Link className="button secondary" href={`/hotels?country=${country.toUpperCase()}`}>هتل‌های این کشور</Link> <Link className="button secondary" href={`/tours/destination/${country}`}>تورهای این کشور</Link></p>}
    <Link className="button secondary" href="/visa">همهٔ راهنماهای ویزا</Link></main>;
}

/* ---- Old-site URLs: look the path up in the legacy route map and move on ---- */
export function LegacyRedirect() {
  const {api} = useAuth(); const router = useRouter(); const pathname = usePathname();
  const [target, setTarget] = useState<string | null>(null);
  useEffect(() => {
    let active = true; const path = decodeURIComponent(pathname || '').replace(/^\/+|\/+$/g, '');
    if (!path) return;
    api.publicGet<{target_path: string | null}>(`/catalog/legacy-route?path=${encodeURIComponent(path)}`).then(r => {if (active && r.target_path) {setTarget(r.target_path); router.replace(r.target_path);}}).catch(() => {});
    return () => {active = false;};
  }, [api, pathname, router]);
  return target ? <p role="status" className="cat-muted">این نشانی جابه‌جا شده است؛ در حال انتقال به <Link href={target}>صفحهٔ جدید</Link>…</p> : null;
}


/* ---- Unified hotel results: the registered hotels of the searched destination (no rate yet, inquiry only) ---- */
export function CatalogHotelsForSearch() {
  const params = useSearchParams();
  const vertical = params.get('vertical'), destination = (params.get('destination') || '').trim();
  const show = (vertical === 'hotel' || vertical === 'package') && destination.length >= 2;
  const {data, loading} = useCatalog<Page<Hotel>>(show ? `/catalog/hotels?q=${encodeURIComponent(destination)}&limit=6` : null);
  if (!show || loading || !data || data.items.length === 0) return null;
  return <section className="cat container" id="catalog-for-search" aria-labelledby="cat-search-title">
    <header className="cat-head"><div><h2 id="cat-search-title">اقامتگاه‌های ثبت‌شده برای «{destination}»</h2><p>این اقامتگاه‌ها در فهرست کارن‌سیر ثبت شده‌اند ولی هنوز نرخ و موجودی متصل ندارند؛ برای هر کدام می‌توانید درخواست استعلام ثبت کنید.</p></div></header>
    <div className="cat-grid">{data.items.map(h => <HotelCard key={h.id} h={h}/>)}</div>
    {data.total > data.items.length && <Link className="button secondary" href={`/hotels?q=${encodeURIComponent(destination)}`}>همهٔ {fa(data.total)} اقامتگاه ثبت‌شده</Link>}
  </section>;
}
