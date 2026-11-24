'use client';
import '../marketplace/stitch-pages-2026-11.css';
/* Master-data views. Everything rendered here is reference data (name, place, facilities, contact);
   price, availability and rooms come only from real supplier offers and are never shown from this catalog. */
import Link from 'next/link';
import {GiftasanSouvenir} from './GiftasanSouvenir';
import {usePathname, useRouter, useSearchParams} from 'next/navigation';
import {useEffect, useState, type ReactNode} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError, newId} from '../../lib/api/karenseir-client';
import {StayBooking} from './StayBooking';
import {OfflineRequest} from '../customer/OfflineRequest';
import {supportPhone} from '../../lib/site-contact';

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
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <div className="cat-thumb cat-thumb-empty" aria-hidden="true"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 10h3a1 1 0 0 1 1 1v10M3 21h18M8 7h4M8 11h4M8 15h4"/></svg><span>{label}</span></div>;
  // eslint-disable-next-line @next/next/no-img-element -- remote Wikimedia Commons file with per-image credit
  return <div className="cat-thumb"><img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)}/>{credit && !credit.startsWith('کارن تراول') && <small title={credit}>{credit}</small>}</div>;
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
  const [text, setText] = useState(value); const [synced, setSynced] = useState(value);
  if (synced !== value) {setSynced(value); setText(value);}
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
      <p className="cat-where">{where}</p>
      {h.amenities.length > 0 && <ul className="cat-amen">{h.amenities.slice(0, 4).map(a => <li key={a.key}>{a.label}</li>)}</ul>}
      <p className="cat-price">{h.price_note}</p>
    </div>
  </Link>;
}

const PAGE = 24;
export function HotelCatalog({presetTypes, title = 'هتل‌ها و اقامتگاه‌های ثبت‌شده', intro}: {presetTypes?: string[]; title?: string; intro?: string}) {
  const {params, set} = useQueryState();
  const countryParam = params.get('country') ?? 'IR', country = countryParam === 'all' ? '' : countryParam, city = params.get('city') || '', region = params.get('region') || '', stars = params.get('stars') || '';
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
    <div className="cat-chips" role="group" aria-label="کشور"><button className={!country ? 'on' : ''} onClick={() => set({country: 'all', city: null, region: null})}>همهٔ کشورها</button>
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

// Every image of the record is available; the page starts with the first ones so a long gallery does not push the content away.
function ExpandableGallery({figures, limit, label}: {figures: ReactNode[]; limit: number; label?: string}) {
  const [all, setAll] = useState(false);
  return <><div className="cat-gallery" aria-label={label}>{all ? figures : figures.slice(0, limit)}</div>{!all && figures.length > limit && <button type="button" className="button secondary cat-gallery-more" onClick={() => setAll(true)}>نمایش همهٔ {fa(figures.length)} تصویر</button>}</>;
}

export function HotelDetail({slug}: {slug: string}) {
  const {data: h, loading, error} = useCatalog<Hotel>(`/catalog/hotels/${encodeURIComponent(slug)}`);
  const [allPhotos, setAllPhotos] = useState(false);
  if (!h) return <main className="journey-main cat-detail"><Status loading={loading} error={false} empty>{error ? 'این هتل در فهرست مرجع پیدا نشد.' : undefined}</Status><Link className="button secondary" href="/hotels">بازگشت به هتل‌ها</Link></main>;
  // Layout = Stitch screen _19 (design/stitch/screens/_19): title row, photo mosaic, section tabs, sticky booking box,
  // room cards, amenity tiles, policy cards, location + distances. Only catalogue facts: no invented price, score or review.
  const where = [h.city?.name, h.region?.name !== h.city?.name ? h.region?.name : null, h.country?.name].filter(Boolean).join('، ');
  const title = `${h.hotel_type_fa}${h.stars ? ` ${fa(h.stars)} ستاره` : ''} ${h.name}`;
  const photos = h.images?.length ? h.images : h.image_url ? [{id: 0, url: h.image_url, caption: null, author: h.image_credit, license: '', license_url: null, source_url: ''}] : [];
  const shown = allPhotos ? photos : photos.slice(0, 5);
  const unit = (u: string | null) => u === 'km' ? ' کیلومتر' : u === 'm' ? ' متر' : u ? ` ${u}` : '';
  const facts = h.details ? ([['محدوده', h.details.district], ['تعداد اتاق', h.details.room_count], ['تعداد تخت', h.details.bed_count], ['سال ساخت', h.details.built_year_jalali], ['تعداد طبقه', h.details.floors], ['چشم‌انداز', h.details.hotel_view], ['وعدهٔ قابل ارائه', h.details.board_plans?.join('، ')]] as [string, string | undefined][]).filter(([, v]) => v) : [];
  const tabs: [string, string][] = [['hd-rooms', 'انتخاب اتاق‌ها'], ['hd-amen', 'امکانات و خدمات'], ['hd-rules', 'قوانین اقامت'], ['hd-loc', 'موقعیت و دسترسی']];
  return <main className="journey-main cat-detail hd">
    <nav className="cat-crumbs" aria-label="مسیر"><Link href="/">خانه</Link><Link href="/hotels">هتل‌ها</Link>{h.country && <Link href={`/hotels?country=${h.country_code}`}>{h.country.name}</Link>}{h.city && <Link href={`/hotels?country=${h.country_code}&city=${h.city.id}`}>{h.city.name}</Link>}</nav>
    <header className="hd-head">
      <div className="hd-title"><h1>{title}{h.name_en && h.name_en !== h.name && <small dir="ltr" lang="en"> [{h.name_en}]</small>}</h1><Stars value={h.stars}/></div>
      <p className="hd-where"><span aria-hidden="true">⌖</span> {[h.address, where].filter(Boolean).join(' — ')}{h.nearby_airports?.[0] ? ` · نزدیک فرودگاه ${h.nearby_airports[0].name}` : ''}</p>
      {h.stars && h.stars_status_fa ? <p className="cat-muted">درجه: {h.stars_status_fa}</p> : null}
    </header>
    {photos.length ? <section className={`hd-gallery n${Math.min(shown.length, 5)}${allPhotos ? ' all' : ''}`} aria-label="تصاویر اقامتگاه">
      {shown.map((im, i) => <figure key={im.id || i} className={i === 0 ? 'lead' : ''}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={im.url} alt={im.caption || h.name} loading={i ? 'lazy' : 'eager'}/>
        <figcaption>{im.caption ? `${im.caption} — ` : ''}{im.source_url ? <a href={im.source_url} target="_blank" rel="noreferrer">{im.author || 'منبع'}</a> : im.author}{im.license ? <> · {im.license_url ? <a href={im.license_url} target="_blank" rel="noreferrer">{im.license}</a> : im.license}</> : null}</figcaption>
        {!allPhotos && i === 4 && photos.length > 5 && <button type="button" className="hd-more" onClick={() => setAllPhotos(true)}>مشاهدهٔ همهٔ {fa(photos.length)} تصویر</button>}</figure>)}
    </section> : <div className="cat-noimage">برای این اقامتگاه هنوز تصویر تأییدشده‌ای ثبت نشده است.</div>}
    <nav className="hd-tabs" aria-label="بخش‌های صفحه">{tabs.map(([id, l]) => <a key={id} href={`#${id}`}>{l}</a>)}</nav>
    <div className="hd-grid">
      <div className="hd-main">
        {h.description && <section className="hd-card"><h2>دربارهٔ اقامتگاه</h2>{h.description.split('\n').map((line, i) => <p key={i}>{line}</p>)}</section>}
        <section className="hd-card" id="hd-rooms"><h2><span aria-hidden="true">▤</span> اتاق‌ها</h2>
          {h.room_types?.length ? <><div className="hd-rooms">{h.room_types.map(r => <article key={r.id} className="hd-room">
            <div className="hd-room-img">{r.image_url ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={r.image_url} alt={r.name_fa} loading="lazy"/> : <span aria-hidden="true">🛏</span>}</div>
            <div className="hd-room-body"><h3>{r.name_fa}{r.name_en && <small dir="ltr" lang="en"> ({r.name_en})</small>}</h3>
              <ul className="hd-room-facts">{[r.bed_type_fa, r.max_adults ? `تا ${fa(r.max_adults)} بزرگسال` : null, r.max_children ? `${fa(r.max_children)} کودک` : null, r.size_m2 ? `${fa(r.size_m2)} متر مربع` : null, r.view_fa ? `منظره: ${r.view_fa}` : null].filter(Boolean).map((t, i) => <li key={i}>{t}</li>)}</ul>
              {r.description && <p>{r.description}</p>}{r.amenities.length > 0 && <ul className="cat-amen">{r.amenities.map(a => <li key={a.key}>{a.label}</li>)}</ul>}</div>
            <div className="hd-room-cta"><small>قیمت</small><b>پس از استعلام</b><a href="#hd-book">استعلام این اتاق</a></div>
          </article>)}</div><p className="cat-muted">این فهرست توصیف انواع اتاق است و به معنی موجودی یا قیمت نیست.</p></>
            : <p className="cat-muted">انواع اتاق این اقامتگاه هنوز در فهرست ثبت نشده است؛ کارشناس هنگام استعلام اتاق‌های موجود را اعلام می‌کند.</p>}
        </section>
        <section className="hd-card" id="hd-amen"><h2><span aria-hidden="true">✦</span> امکانات و خدمات اقامتگاه</h2>{h.amenities.length ? <ul className="hd-amen">{h.amenities.map(a => <li key={a.key}><span aria-hidden="true">✓</span>{a.label}</li>)}</ul> : <p className="cat-muted">امکانات این اقامتگاه در منبع مرجع ثبت نشده است؛ هنگام استعلام اعلام می‌شود.</p>}
          {facts.length > 0 && <dl className="hd-facts">{facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}</section>
        <section className="hd-card" id="hd-rules"><h2><span aria-hidden="true">⚑</span> شرایط اقامت و مقررات</h2>
          <div className="hd-rules"><div><h3>ساعات تحویل و تخلیه اتاق</h3><p>ورود (Check-in): <b>{h.checkin_time ?? 'هنگام استعلام'}</b></p><p>خروج (Check-out): <b>{h.checkout_time ?? 'هنگام استعلام'}</b></p></div>
            <div><h3>قوانین ثبت‌شده</h3>{h.policies?.length ? <dl className="cat-dl">{h.policies.map(p => <span key={p.key} style={{display: 'contents'}}><dt>{p.label}</dt><dd>{p.value_fa}</dd></span>)}</dl> : <p className="cat-muted">قوانین اقامت هنگام استعلام از اقامتگاه تأیید می‌شود.</p>}{h.rules_text && <p>{h.rules_text}</p>}</div></div></section>
        <section className="hd-card" id="hd-loc"><h2><span aria-hidden="true">⌖</span> موقعیت و فاصله تا جاهای دیدنی</h2>
          <dl className="cat-dl">{h.address && <><dt>نشانی</dt><dd>{h.address}</dd></>}{h.latitude !== null && h.longitude !== null && <><dt>موقعیت</dt><dd><a href={osmLink(h.latitude, h.longitude)} target="_blank" rel="noreferrer">نمایش روی نقشه</a></dd></>}{h.phone && <><dt>تلفن</dt><dd><a href={`tel:${h.phone.replace(/[^\d+]/g, '')}`} dir="ltr">{h.phone}</a></dd></>}{h.email && <><dt>ایمیل</dt><dd><a href={`mailto:${h.email}`} dir="ltr">{h.email}</a></dd></>}</dl>
          {(h.details?.nearby?.length || h.nearby_airports?.length || h.nearby_rail_stations?.length) ? <ul className="hd-near">
            {h.details?.nearby?.map((n, i) => <li key={'n' + i}><b>{n.place}</b>{n.distance && <small>{n.distance}{unit(n.unit)}</small>}</li>)}
            {h.nearby_airports?.map(a => <li key={a.iata}><b>فرودگاه {a.name}</b><small dir="ltr">{a.iata}</small></li>)}
            {h.nearby_rail_stations?.map(st => <li key={st.id}><b>ایستگاه راه‌آهن {st.name}</b></li>)}</ul> : null}
          {h.details?.restaurants?.length ? <><h3>رستوران و کافه</h3><ul className="cat-access">{h.details.restaurants.map((r, i) => <li key={i}>{r.name}{r.hours ? ` — ${r.hours}` : ''}</li>)}</ul></> : null}
          {h.details?.traffic && <p>{h.details.traffic}</p>}{h.details?.review && h.details.review.split('\n').map((line, i) => <p key={i}>{line}</p>)}
          {h.details?.map_link && <p><a href={h.details.map_link} target="_blank" rel="noreferrer nofollow">جست‌وجوی این اقامتگاه روی نقشه</a> <span className="cat-muted">(مختصات دقیق در منبع ثبت نشده است)</span></p>}
        </section>
      </div>
      <aside className="cat-inquiry hd-book" id="hd-book"><div className="hd-book-price"><small>قیمت هر شب</small><b>پس از انتخاب تاریخ و استعلام</b></div><StayBooking slug={h.slug}/><p className="cat-muted">برای این اقامتگاه هنوز نرخ تأییدشده‌ای از تأمین‌کننده ثبت نشده است. تاریخ و تعداد مهمان را مشخص کنید یا از پشتیبانی استعلام بگیرید.</p>
        <Link className="button primary" href={`/search/results?vertical=hotel&destination=${encodeURIComponent(h.city?.name ?? h.name)}`}>جست‌وجوی اقامت در {h.city?.name ?? 'این مقصد'}</Link>
        <InquiryRequest subject={`استعلام اقامت: ${h.name}`} context={`درخواست استعلام نرخ و موجودی برای «${h.name}»${h.city ? ` در ${h.city.name}` : ''} (شناسهٔ فهرست: ${h.id}).`} reason={h.request?.reason ?? 'نرخ تأییدشده‌ای ثبت نشده است.'}/>
        <a className="hd-call" href={supportPhone.href}><span aria-hidden="true">☎</span> مشاورهٔ رزرو هتل <b dir="ltr">{supportPhone.display}</b></a></aside>
    </div>
    {!h.request?.online_booking && <OfflineRequest service="این اقامتگاه" trip={`اقامت در ${h.name}${h.city ? ` (${h.city.name})` : ''}`}/>}
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
        <h3>{faName(v.name)}</h3>
        <p className="cat-where">{[v.city?.name, v.region?.name].filter(Boolean).join('، ')}{v.address ? ` — ${v.address}` : ''}</p>
        {v.opening_hours && <p className="cat-muted" dir="ltr">{v.opening_hours}</p>}
        <p className="cat-links"><a href={osmLink(v.latitude, v.longitude)} target="_blank" rel="noreferrer">نقشه</a>{v.phone && <a href={`tel:${v.phone.replace(/[^\d+]/g, '')}`} dir="ltr">{v.phone}</a>}{v.website && <a href={v.website} target="_blank" rel="noreferrer nofollow">وب‌سایت</a>}</p>
        <p className="cat-price">{v.price_note}</p></div></article>)}</div>}
    {data && <Pager total={data.total} limit={PAGE} page={page} onPage={p => {set({vpage: p > 1 ? String(p) : null}); document.getElementById('directory')?.scrollIntoView();}}/>}
    {ATTRIBUTION}
  </section>;
}

/* Persian spacing fixes for names imported from open data (missing zero-width non-joiners). */
export const faName = (s?: string | null) => (s ?? '').replace(/بین ?المللی/g, 'بین‌المللی').replace(/هاشمی ?نژاد/g, 'هاشمی‌نژاد').replace(/\s+/g, ' ').trim();
const IR_AIRPORT_CITY: Record<string, string> = {ABD: 'آبادان', AWZ: 'اهواز', BND: 'بندرعباس', GSM: 'قشم', IFN: 'اصفهان', IKA: 'تهران', THR: 'تهران', KER: 'کرمان', KIH: 'کیش', MHD: 'مشهد', PYK: 'کرج',
  SYZ: 'شیراز', TBZ: 'تبریز', XBJ: 'بیرجند', ZAH: 'زاهدان', ACZ: 'زابل', ADU: 'اردبیل', AEU: 'ابوموسی', AFZ: 'سبزوار', AKW: 'آغاجاری', AZD: 'یزد', BDH: 'بندر لنگه', BJB: 'بجنورد', BUZ: 'بوشهر',
  BXR: 'بم', CKT: 'سرخس', CQD: 'شهرکرد', DEF: 'دزفول', FAZ: 'فسا', GBT: 'گرگان', GCH: 'گچساران', GZW: 'قزوین', HDM: 'همدان', IHR: 'ایرانشهر', IIL: 'ایلام', JAR: 'جهرم', JWN: 'زنجان', JYR: 'جیرفت',
  KHD: 'خرم‌آباد', KHK: 'خارک', KHY: 'خوی', KSH: 'کرمانشاه', LFM: 'لامرد', LRR: 'لار', LVP: 'لاوان', MRX: 'ماهشهر', NSH: 'نوشهر', OMH: 'ارومیه', PFQ: 'پارس‌آباد', RAS: 'رشت', RJN: 'رفسنجان',
  RUD: 'شاهرود', RZR: 'رامسر', SDG: 'سنندج', SRY: 'ساری', SYJ: 'سیرجان', TCX: 'طبس', ZBR: 'چابهار', KNR: 'کنگان', YES: 'یاسوج', JSK: 'جاسک', PGU: 'عسلویه', YEH: 'عسلویه', IAQ: 'بهرگان', AJK: 'اراک',
  SXI: 'سیری', ACP: 'مراغه', IMQ: 'ماکو', KLM: 'کلاله', SNX: 'سمنان'};
const hasLatin = (s?: string | null) => !!s && /[A-Za-z]/.test(s);
const airportCity = (a: Airport) => (a.country_code === 'IR' || !a.country_code) && IR_AIRPORT_CITY[a.iata] ? IR_AIRPORT_CITY[a.iata] : hasLatin(a.city_name) ? null : a.city_name ?? null;

function AirlineLogo({a}: {a: Airline}) {
  const [failed, setFailed] = useState(false);
  const mark = (a.iata || a.name.replace(/^هواپیمایی\s*/, '').slice(0, 2)).toUpperCase();
  // eslint-disable-next-line @next/next/no-img-element -- airline logo from Wikimedia Commons, credited in title; falls back to a code mark when blocked
  return <div className="cat-logo">{a.logo_url && !failed ? <img src={a.logo_url} alt={`نشان ${a.name}`} title={a.logo_credit ?? undefined} loading="lazy" onError={() => setFailed(true)}/> : <b dir="ltr">{mark}</b>}</div>;
}

export function AirlineDirectory() {
  const [country, setCountry] = useState('IR');
  const {data, loading, error} = useCatalog<{items: Airline[]}>(`/catalog/airlines${country ? '?country=' + country : ''}`);
  return <section className="cat" aria-labelledby="cat-airlines-title">
    <header className="cat-head"><div><h2 id="cat-airlines-title">شرکت‌های هواپیمایی</h2><p>ایرلاین‌هایی که در جست‌وجوی پرواز می‌بینی. ساعت پرواز، ظرفیت و قیمت در نتیجه‌ی جست‌وجو نمایش داده می‌شود.</p></div></header>
    <div className="cat-chips" role="group" aria-label="کشور">{['IR', 'TR', 'AE', 'IQ', 'AM', 'GE', 'QA', 'OM', 'KW', 'AZ', ''].map(c => <button key={c || 'all'} className={country === c ? 'on' : ''} onClick={() => setCountry(c)}>{c ? COUNTRY_FA[c] : 'همه'}</button>)}</div>
    <Status loading={loading} error={error} empty={!data || data.items.length === 0}/>
    {data && <div className="cat-grid cat-grid-ref">{data.items.map(a => <article className="cat-ref" key={a.id}>
      <AirlineLogo a={a}/>
      <div><h3>{faName(a.name)}</h3>
        <p className="cat-where">{COUNTRY_FA[a.country_code] ?? a.country_code}{a.airline_type && AIRLINE_TYPE_FA[a.airline_type] ? ` · ${AIRLINE_TYPE_FA[a.airline_type]}` : ''} · <span dir="ltr">{a.iata}</span></p></div></article>)}</div>}
  </section>;
}

export function AirportDirectory() {
  const [country, setCountry] = useState('IR');
  const {data, loading, error} = useCatalog<{items: Airport[]}>(`/catalog/airports?country=${country}`);
  const items = (data?.items ?? []).map(a => ({...a, city: airportCity(a)}));
  const main = items.filter(a => a.scope === 'international');
  const rest = items.filter(a => a.scope !== 'international');
  const searchHref = (city: string) => `/flights?vertical=flight&destination=${encodeURIComponent(city)}`;
  return <section className="cat" aria-labelledby="cat-airports-title">
    <header className="cat-head"><div><h2 id="cat-airports-title">فرودگاه‌ها</h2><p>فرودگاه مقصدت را انتخاب کن تا پروازهای آن مسیر را جست‌وجو کنی.</p></div></header>
    <div className="cat-chips" role="group" aria-label="کشور">{['IR', 'TR', 'AE', 'IQ', 'AM', 'GE'].map(c => <button key={c} className={country === c ? 'on' : ''} onClick={() => setCountry(c)}>{COUNTRY_FA[c]}</button>)}</div>
    <Status loading={loading} error={error} empty={!data || data.items.length === 0}/>
    {main.length > 0 && <><h3 className="cat-sub">فرودگاه‌های بین‌المللی</h3><div className="cat-grid cat-grid-airport">{main.map(a => <article className="cat-airport" key={a.iata}>
      <b className="cat-airport-code" dir="ltr">{a.iata}</b>
      <div><h4>{a.city ?? faName(a.name)}</h4><p>{faName(a.name)}</p>{a.city && <a href={searchHref(a.city)}>پرواز به {a.city} ←</a>}</div></article>)}</div></>}
    {rest.length > 0 && <><h3 className="cat-sub">سایر فرودگاه‌ها</h3><ul className="cat-airport-list">{rest.map(a => <li key={a.iata}>{a.city ? <a href={searchHref(a.city)}>{a.city}</a> : <span>{faName(a.name)}</span>}<small dir="ltr">{a.iata}</small></li>)}</ul></>}
  </section>;
}

const MAJOR_RAIL = ['تهران', 'مشهد', 'اصفهان', 'شیراز', 'تبریز', 'اهواز', 'یزد', 'کرمان', 'قم', 'کاشان', 'رشت', 'قزوین', 'زنجان', 'سمنان', 'ساری', 'گرگان', 'بندرعباس', 'اراک', 'همدان', 'کرمانشاه', 'زاهدان', 'بجنورد', 'ارومیه', 'اردبیل', 'میانه', 'گرمسار', 'نیشابور', 'سبزوار', 'شاهرود', 'دامغان', 'خرمشهر', 'اندیمشک', 'بافق', 'سیرجان'];
/* Station names from open data → the town a traveller would search for; drops emergency, freight and unfinished stops. */
function stationTown(name: string): string | null {
  if (/اضطراری|در حال ساخت|باری|صنعتی|[A-Za-z]/.test(name)) return null;
  const t = name.replace(/^ا[یب]ستگاه\s*(راه[\s‌]*آهن)?\s*/, '').replace(/\(.*?\)/g, '').replace(/\s+/g, ' ').trim();
  return t.length >= 2 ? t.replace(/ي/g, 'ی').replace(/ہ/g, 'ه') : null;
}

export function RailDirectory() {
  const ops = useCatalog<{items: {id: string; name_fa: string; name_en: string | null; operator_kind: string | null; website: string | null}[]}>('/catalog/rail/operators');
  const [q, setQ] = useState('');
  const stations = useCatalog<{items: Station[]}>(`/catalog/rail/stations?limit=1000${q ? '&q=' + encodeURIComponent(q) : ''}`);
  const towns = Array.from(new Set(((stations.data ?? stations.stale)?.items ?? []).map(s => stationTown(s.name)).filter((t): t is string => !!t))).sort((a, b) => a.localeCompare(b, 'fa'));
  const major = MAJOR_RAIL.filter(t => towns.includes(t)); const rest = towns.filter(t => !MAJOR_RAIL.includes(t));
  const href = (t: string) => `/trains?vertical=train&destination=${encodeURIComponent(t)}`;
  return <section className="cat" aria-labelledby="cat-rail-title">
    <header className="cat-head"><div><h2 id="cat-rail-title">شرکت‌های ریلی و ایستگاه‌ها</h2><p>شهر مقصدت را انتخاب کن تا قطارهای آن مسیر را جست‌وجو کنی. ساعت حرکت، نوع واگن و قیمت در نتیجه‌ی جست‌وجو نمایش داده می‌شود.</p></div><SearchBox value={q} onSubmit={setQ} placeholder="نام شهر یا ایستگاه"/></header>
    {ops.data && <div className="cat-grid cat-grid-ref">{ops.data.items.map(o => <article className="cat-ref" key={o.id}><div className="cat-logo"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M7 4h10a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM5 11h14M9 14h.01M15 14h.01M8 21l2-4M16 21l-2-4"/></svg></div>
      <div><h3>{o.name_fa}</h3><p className="cat-where">{o.operator_kind === 'national_infrastructure' ? 'شبکهٔ ملی راه‌آهن' : 'شرکت مسافری ریلی'}</p></div></article>)}</div>}
    <Status loading={stations.loading} error={stations.error} empty={towns.length === 0}/>
    {major.length > 0 && <><h3 className="cat-sub">ایستگاه‌های اصلی</h3><div className="cat-grid cat-grid-airport">{major.map(t => <article className="cat-airport" key={t}>
      <b className="cat-airport-code" aria-hidden="true"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M7 4h10a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM5 11h14M8 21l2-4M16 21l-2-4"/></svg></b>
      <div><h4>{t}</h4><p>ایستگاه راه‌آهن {t}</p><a href={href(t)}>قطار به {t} ←</a></div></article>)}</div></>}
    {rest.length > 0 && <><h3 className="cat-sub">سایر ایستگاه‌ها <small>({fa(rest.length)})</small></h3><ul className="cat-airport-list">{rest.map(t => <li key={t}><a href={href(t)}>{t}</a></li>)}</ul></>}
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
      <div className="cat-card-body"><h3>{p.name}</h3><p className="cat-where">{fa(p.hotel_count)} اقامتگاه ثبت‌شده</p></div></Link>)}</div>}
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
    <header className="cat-detail-head"><h1>سفر به {p.name}</h1>{p.name_en && <p className="cat-en" dir="ltr" lang="en">{p.name_en}</p>}<p className="cat-where">{[p.parent?.name, COUNTRY_FA[p.country_code]].filter((x, i, all) => x && x !== p.name && all.indexOf(x) === i).join('، ')}{p.population ? ` · جمعیت ${fa(p.population)}` : ''}</p></header>
    {p.image_url && <Thumb src={p.image_url} credit={p.image_credit} alt={p.name} label=""/>}
    {p.description && p.description.split('\n').map((line, i) => <p key={i}>{line}</p>)}
    {p.details && Object.keys(p.details).length > 0 && <section><h2>اطلاعات مقصد</h2><dl className="cat-dl">{([['پایتخت', p.details.capital], ['واحد پول', p.details.currency], ['زبان رسمی', p.details.official_language], ['جمعیت', p.details.population_text], ['برق شهری', p.details.voltage], ['اختلاف ساعت', p.details.time_zone]] as [string, string | undefined][]).filter(([, v]) => v).map(([k, v]) => <span key={k} style={{display: 'contents'}}><dt>{k}</dt><dd>{v}</dd></span>)}</dl>
      {p.details.guide && p.details.guide.split('\n').map((line, i) => <p key={i}>{line}</p>)}{p.details.visa_note && <><h3 className="cat-h3">ویزا</h3>{p.details.visa_note.split('\n').map((line, i) => <p key={i}>{line}</p>)}</>}</section>}
    {p.details?.images && p.details.images.length > 1 && <ExpandableGallery limit={6} label="تصاویر مقصد" figures={p.details.images.map((src, i) => <figure key={src}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={src} alt={`${p.name} ${i + 1}`} loading="lazy"/></figure>)}/>}
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
    <GiftasanSouvenir city={p.name}/>
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
    <div className="cat-card-body"><h3>{t.title.replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[Number(d)])}</h3><p className="cat-where">{[t.destination?.name, duration(t), t.transport_fa].filter(Boolean).join(' · ')}</p>
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
    {data && data.items.length > 0 && <div className={`cat-grid${list.loading ? ' is-loading' : ''}`}>{data.items.filter((t, i, all) => all.findIndex(o => o.title === t.title && o.destination?.name === t.destination?.name && duration(o) === duration(t)) === i).map(t => <TourCard key={t.id} t={t}/>)}</div>}
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
        {d.images && d.images.length > 0 ? <ExpandableGallery limit={11} figures={[...(t.image_url && !d.images.includes(t.image_url) ? [t.image_url] : []), ...d.images].map((src, i) => <figure key={src} className={i === 0 ? 'lead' : ''}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={src} alt={`${t.title} ${i + 1}`} loading={i ? 'lazy' : 'eager'}/></figure>)}/>
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
    <p className="cat-attrib">منبع این صفحه: فهرست تورهای کارن تراول (سابقهٔ برگزاری). این صفحه قیمت، ظرفیت یا تاریخ قابل رزرو نشان نمی‌دهد.</p>
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


/* ---- Unified hotel results: the registered hotels of the searched destination (no rate yet, inquiry only) ----
   mode="primary": no priced offer exists for the search -> the catalog IS the result (shown first, 12 cards).
   mode="complement": priced offers exist -> a short "more registered stays" strip under them.
   fallback: rendered when the catalog has nothing for this destination either. */
export function CatalogHotelsForSearch({mode = 'complement', fallback = null}: {mode?: 'primary' | 'complement'; fallback?: ReactNode}) {
  const params = useSearchParams();
  const vertical = params.get('vertical'), destination = (params.get('destination') || '').trim();
  const show = (vertical === 'hotel' || vertical === 'package' || vertical === 'vacation_rental') && destination.length >= 2;
  const limit = mode === 'primary' ? 36 : 6;
  const {data: raw, loading} = useCatalog<Page<Hotel>>(show ? `/catalog/hotels?q=${encodeURIComponent(destination)}&limit=${limit}` : null);
  let data = raw;
  if (!show) return <>{fallback}</>;
  if (loading) return mode === 'primary' ? <p className="cat-muted" role="status">در حال یافتن اقامتگاه‌های «{destination}»…</p> : null;
  if (!data || data.items.length === 0) return <>{fallback}</>;
  // Destination relevance: hotels located in the searched city/region first; drop name-only matches from other cities when local ones exist.
  const norm = (t: string) => t.replace(/[يى]/g, 'ی').replace(/ك/g, 'ک').replace(/\u200c/g, ' ').trim();
  const dest = norm(destination);
  const inDest = (h: Hotel) => [h.city?.name, h.region?.name].some(n => !!n && norm(String(n)).includes(dest));
  const local = data.items.filter(inDest);
  const items = local.length > 0 ? local : data.items;
  data = {...data, items, total: items.length < data.items.length ? items.length : data.total};
  const all = <Link className="button secondary" href={`/hotels?q=${encodeURIComponent(destination)}`}>دیدن همهٔ {fa(data.total)} اقامتگاه «{destination}»</Link>;
  if (mode === 'primary') return <HotelResultsStitch destination={destination} total={data.total} items={data.items} all={all}/>;
  return <section className="cat container" id="catalog-for-search" aria-labelledby="cat-search-title">
    <header className="cat-head"><div><h2 id="cat-search-title">اقامتگاه‌های بیشتر در «{destination}»</h2><p>این اقامتگاه‌ها در فهرست کارن تراول ثبت شده‌اند ولی هنوز نرخ آنلاین ندارند؛ برای هر کدام می‌توانید استعلام قیمت بگیرید.</p></div></header>
    <div className="cat-grid">{data.items.map(h => <HotelCard key={h.id} h={h}/>)}</div>
    {data.total > data.items.length && all}
  </section>;
}

/* Hotel results = Stitch screen _35 (design/stitch/screens/_35): title + sort pills, sidebar filters, horizontal cards.
   Registered hotels without an online rate: filters/sort run on the loaded list only; no price, rating or discount is invented. */
const HR_SORTS = [['recommended', 'پیشنهاد کارن تراول'], ['stars_desc', 'بیشترین ستاره'], ['stars_asc', 'کمترین ستاره'], ['name', 'نام اقامتگاه']] as const;
function HotelResultsStitch({destination, total, items, all}: {destination: string; total: number; items: Hotel[]; all: ReactNode}) {
  const [sort, setSort] = useState<string>('recommended');
  const [name, setName] = useState('');
  const [stars, setStars] = useState<number[]>([]);
  const [amen, setAmen] = useState<string[]>([]);
  const amenCounts = new Map<string, {label: string; n: number}>();
  for (const h of items) for (const a of h.amenities) { const c = amenCounts.get(a.key); amenCounts.set(a.key, {label: a.label, n: (c?.n ?? 0) + 1}); }
  const topAmen = Array.from(amenCounts.entries()).sort((a, b) => b[1].n - a[1].n).slice(0, 6);
  const starCounts = [5, 4, 3, 2, 1].map(v => ({v, n: items.filter(h => h.stars === v).length})).filter(x => x.n > 0);
  const toggle = <T,>(list: T[], v: T) => list.includes(v) ? list.filter(x => x !== v) : [...list, v];
  let rows = items.filter(h => (!name.trim() || h.name.includes(name.trim())) && (!stars.length || (h.stars != null && stars.includes(h.stars))) && amen.every(k => h.amenities.some(a => a.key === k)));
  if (sort === 'stars_desc') rows = [...rows].sort((a, b) => (b.stars ?? 0) - (a.stars ?? 0));
  else if (sort === 'stars_asc') rows = [...rows].sort((a, b) => (a.stars ?? 9) - (b.stars ?? 9));
  else if (sort === 'name') rows = [...rows].sort((a, b) => a.name.localeCompare(b.name, 'fa'));
  else rows = [...rows].sort((a, b) => Number(!!b.image_url) - Number(!!a.image_url) || (b.stars ?? 0) - (a.stars ?? 0));
  const reset = () => { setName(''); setStars([]); setAmen([]); };
  return <section className="hr" id="catalog-for-search" aria-labelledby="cat-search-title">
    <div className="hr-top">
      <div><span className="hr-badge">اقامتگاه‌های ثبت‌شدهٔ کارن تراول</span><h2 id="cat-search-title">رزرو هتل در {destination} <small>({fa(total)} اقامتگاه یافت شد)</small></h2></div>
    </div>
    <div className="hr-sort" role="group" aria-label="مرتب‌سازی اقامتگاه‌ها"><small>مرتب‌سازی بر اساس:</small>{HR_SORTS.map(([v, l]) => <button key={v} type="button" aria-pressed={sort === v} onClick={() => setSort(v)}>{l}</button>)}</div>
    <p className="hr-note">قیمت آنلاین برای این تاریخ هنوز از تأمین‌کننده نرسیده است. اقامتگاه را انتخاب کن و استعلام قیمت بگیر؛ کارشناس ما قیمت و موجودی همین تاریخ را اعلام می‌کند.</p>
    <div className="hr-body">
      <aside className="hr-filters" aria-label="فیلترها">
        <div className="hr-filters-head"><b>فیلترهای پیشرفته</b>{(name || stars.length || amen.length) ? <button type="button" onClick={reset}>پاک کردن همه</button> : null}</div>
        <label className="hr-f"><span>نام هتل یا اقامتگاه</span><input value={name} onChange={e => setName(e.target.value)} placeholder="مثلاً: هتل بزرگ…"/></label>
        {starCounts.length > 0 && <fieldset className="hr-f"><legend>ردهٔ ستاره</legend>{starCounts.map(({v, n}) => <label key={v} className="hr-check"><input type="checkbox" checked={stars.includes(v)} onChange={() => setStars(toggle(stars, v))}/><span aria-label={`${fa(v)} ستاره`}>{'★'.repeat(v)}</span><small>{fa(n)}</small></label>)}</fieldset>}
        {topAmen.length > 0 && <fieldset className="hr-f"><legend>امکانات اقامتگاه</legend>{topAmen.map(([k, {label, n}]) => <label key={k} className="hr-check"><input type="checkbox" checked={amen.includes(k)} onChange={() => setAmen(toggle(amen, k))}/><span>{label}</span><small>{fa(n)}</small></label>)}</fieldset>}
        <div className="hr-help"><b>مشاورهٔ رزرو هتل</b><p>برای انتخاب اقامتگاه یا رزرو گروهی با کارشناس کارن تراول صحبت کنید.</p><Link href="/contact">تماس با پشتیبانی</Link></div>
      </aside>
      <div className="hr-list">
        {rows.length === 0 ? <div className="hr-empty"><p>با این فیلترها اقامتگاهی پیدا نشد.</p><button type="button" onClick={reset}>پاک کردن فیلترها</button></div>
          : rows.map(h => <HotelRowStitch key={h.id} h={h}/>)}
        {total > items.length && <div className="hr-more">{all}</div>}
      </div>
    </div>
  </section>;
}
function HotelRowStitch({h}: {h: Hotel}) {
  const where = [h.city?.name, h.details?.district, h.region?.name !== h.city?.name ? h.region?.name : null].filter(Boolean).join('، ');
  return <article className="hr-card">
    <Link href={`/hotels/${h.slug}`} className="hr-media" aria-hidden="true" tabIndex={-1}><Thumb src={h.image_url} credit={h.image_credit} alt={h.name} label={h.hotel_type_fa}/></Link>
    <div className="hr-main">
      <div className="hr-meta"><span className="hr-type">{h.hotel_type_fa}</span><Stars value={h.stars}/></div>
      <h3><Link href={`/hotels/${h.slug}`}>{h.name}</Link></h3>
      <p className="hr-where"><span aria-hidden="true">⌖</span> {where || COUNTRY_FA[h.country_code]}</p>
      {h.amenities.length > 0 && <ul className="hr-amen">{h.amenities.slice(0, 5).map(a => <li key={a.key}>{a.label}</li>)}</ul>}
      <div className="hr-foot"><div className="hr-price"><small>قیمت هر شب</small><b>پس از استعلام</b></div><Link className="hr-cta" href={`/hotels/${h.slug}`}>مشاهده اتاق‌ها و استعلام <span aria-hidden="true">←</span></Link></div>
    </div>
  </article>;
}

/* Flight landing after the pattern of Iranian booking sites (Alibaba, MrBilit) + Stitch home cards:
   popular routes with city photos (open the real search; no prices), airline logo strip, perks, FAQ.
   The full airline/airport directories stay available below, collapsed. */
const FLIGHT_ROUTES: [string, string][] = [['تهران', 'مشهد'], ['تهران', 'کیش'], ['تهران', 'شیراز'], ['تهران', 'اصفهان'], ['تهران', 'استانبول'], ['تهران', 'دبی'], ['تهران', 'نجف'], ['تهران', 'تفلیس'], ['تهران', 'یزد'], ['تهران', 'تبریز'], ['تهران', 'اهواز'], ['تهران', 'بندرعباس'], ['تهران', 'قشم'], ['تهران', 'رشت']];
const FLIGHT_FAQ: [string, string][] = [
  ['چند ساعت قبل از پرواز در فرودگاه باشم؟', 'برای پروازهای داخلی دست‌کم دو ساعت و برای پروازهای خارجی دست‌کم سه ساعت پیش از پرواز در فرودگاه باشید؛ پذیرش معمولاً نیم ساعت (داخلی) تا یک ساعت (خارجی) پیش از پرواز بسته می‌شود.'],
  ['بار مجاز من چقدر است؟', 'بار مجاز را ایرلاین و نوع نرخ تعیین می‌کند و پیش از پرداخت، کنار هر پرواز نمایش داده می‌شود.'],
  ['استرداد بلیت هواپیما چطور انجام می‌شود؟', 'درخواست استرداد را از «سفرهای من» ثبت کنید؛ مبلغ جریمه طبق قوانین همان نرخ و فاصله تا زمان پرواز محاسبه و پیش از تأیید به شما نمایش داده می‌شود.'],
  ['قیمت بلیت کودک و نوزاد چگونه است؟', 'نرخ کودک (۲ تا ۱۲ سال) و نوزاد (زیر ۲ سال) را ایرلاین تعیین می‌کند و هنگام انتخاب پرواز جدا از بزرگسال نمایش داده می‌شود.'],
  ['پرواز چارتری با سیستمی چه فرقی دارد؟', 'بلیت سیستمی مستقیم از ایرلاین صادر می‌شود و قوانین استرداد ایرلاین را دارد؛ بلیت چارتری را کارگزار با قوانین خودش می‌فروشد. نوع هر بلیت در نتایج جست‌وجو مشخص است.'],
  ['بلیت را بعد از خرید کجا ببینم؟', 'بلیت الکترونیکی در «سفرهای من» و پیامک ارسالی در دسترس است؛ برای پذیرش کارت شناسایی یا گذرنامهٔ معتبر همراه داشته باشید.'],
];
export function FlightLanding() {
  const places = useCatalog<{items: Place[]}>('/catalog/places?kind=city&with_image=true&limit=500');
  const airlines = useCatalog<{items: Airline[]}>('/catalog/airlines?country=IR');
  const LOCAL: Record<string, string> = {شیراز: '/images/figma/tile-shiraz.jpeg', اصفهان: '/images/approved-figma/imgTileIsfahan.jpg', یزد: '/images/figma/hero-yazd.jpeg'};
  const img = (city: string) => LOCAL[city] ?? places.data?.items.find(x => x.name === city || x.name_fa === city)?.image_url ?? null;
  const [depart, setDepart] = useState('');
  useEffect(() => { const d = new Date(Date.now() + 86400000); setDepart(d.toISOString().slice(0, 10)); }, []); // eslint-disable-line react-hooks/set-state-in-effect -- date exists only on the client (avoid hydration mismatch)
  const href = (o: string, d: string) => `/search/results?${new URLSearchParams({vertical: 'flight', origin: o, destination: d, adults: '1', trip_type: 'one_way', ...(depart ? {depart} : {})})}`;
  return <>
    <section className="tl-sec" aria-labelledby="fl-routes"><h2 id="fl-routes">مسیرهای پرطرفدار</h2><p className="fl-sub">روی هر مسیر بزن تا پروازهای فردای آن را ببینی؛ تاریخ را در صفحهٔ نتایج عوض کن.</p>
      <div className="tl-routes fl-routes">{(places.data ? FLIGHT_ROUTES.filter(([, d]) => img(d)) : FLIGHT_ROUTES).slice(0, 10).map(([o, d]) => <a key={o + d} href={href(o, d)} className="tl-route"><Thumb src={img(d)} credit={null} alt={d} label={d}/><span>{o} <i aria-hidden="true">←</i> {d}</span></a>)}</div></section>
    {airlines.data && airlines.data.items.length > 0 && <section className="tl-sec" aria-labelledby="fl-air"><h2 id="fl-air">ایرلاین‌های داخلی</h2>
      <ul className="fl-airlines">{airlines.data.items.map(a => <li key={a.id} title={a.name}><AirlineLogo a={a}/><span>{faName(a.name)}</span></li>)}</ul></section>}
    <section className="tl-sec tl-perks" aria-label="مزایای خرید">
      {[['مقایسهٔ پروازها کنار هم', 'ساعت، ایرلاین، بار مجاز و قوانین استرداد پروازها را در یک صفحه مقایسه کن.'], ['قوانین هر نرخ پیش از خرید', 'بار، کلاس و شرایط استرداد هر بلیت پیش از پرداخت نمایش داده می‌شود.'], ['پیگیری در سفرهای من', 'وضعیت پرداخت، صدور و استرداد بلیت را در حساب خودت ببین.'], ['پشتیبانی کارشناس', 'پیش و پس از خرید، کارشناس کارن تراول پاسخگوست.']]
        .map(([t, d]) => <article key={t}><b>{t}</b><p>{d}</p></article>)}
    </section>
    <section className="tl-sec" aria-labelledby="fl-faq"><h2 id="fl-faq">پرسش‌های پرتکرار خرید بلیت هواپیما</h2>
      <div className="tl-faq">{FLIGHT_FAQ.map(([q, a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}</div></section>
  </>;
}

/* Train landing after the common pattern of Iranian booking sites (Alibaba, MrBilit): quick routes with city photos,
   what the customer gets, rail companies, and short answers to common questions. No station dump, no prices. */
const TRAIN_CITIES = ['مشهد', 'اصفهان', 'تبریز', 'شیراز', 'یزد', 'اهواز', 'کرمان', 'رشت', 'بندرعباس', 'گرگان'];
const TRAIN_FAQ: [string, string][] = [
  ['برای سوار شدن به قطار چه مدرکی لازم است؟', 'کارت شناسایی معتبر (کارت ملی یا شناسنامه برای کودکان) مسافرانی که بلیت به نامشان صادر شده است. مأمور قطار ممکن است مدرک را با مشخصات بلیت تطبیق دهد.'],
  ['چه زمانی باید در ایستگاه باشم؟', 'بهتر است دست‌کم نیم ساعت پیش از ساعت حرکت در ایستگاه باشید تا سکو و واگن خود را پیدا کنید؛ قطار رأس ساعت اعلام‌شده حرکت می‌کند.'],
  ['استرداد بلیت قطار چطور انجام می‌شود؟', 'درخواست استرداد را از «سفرهای من» ثبت کنید. مبلغ جریمه را قوانین شرکت ریلی و فاصله تا زمان حرکت تعیین می‌کند و پیش از تأیید به شما نمایش داده می‌شود.'],
  ['قیمت بلیت کودک و نوزاد چطور حساب می‌شود؟', 'نرخ کودک و نوزاد را شرکت ریلی تعیین می‌کند و هنگام انتخاب قطار، جدا از بزرگسال نمایش داده می‌شود.'],
  ['کوپه‌ی دربست یا کوپه‌ی ویژه‌ی بانوان را چطور بگیرم؟', 'اگر قطار انتخابی این امکان را داشته باشد، در جزئیات همان قطار نمایش داده می‌شود؛ برای هماهنگی سفر گروهی با پشتیبانی تماس بگیرید.'],
  ['اگر بلیت را گم کنم چه کنم؟', 'بلیت الکترونیکی است و همیشه در «سفرهای من» در دسترس است؛ کافی است کارت شناسایی همراه داشته باشید.'],
];

export function TrainLanding() {
  const places = useCatalog<{items: Place[]}>('/catalog/places?kind=city&country=IR&with_image=true&limit=500');
  const ops = useCatalog<{items: {id: string; name_fa: string; website: string | null}[]}>('/catalog/rail/operators');
  const LOCAL: Record<string, string> = {شیراز: '/images/figma/tile-shiraz.jpeg', اصفهان: '/images/approved-figma/imgTileIsfahan.jpg', یزد: '/images/figma/hero-yazd.jpeg'};
  const img = (city: string) => LOCAL[city] ?? places.data?.items.find(x => x.name === city || x.name_fa === city)?.image_url ?? null;
  const href = (city: string) => `/trains?vertical=train&origin=${encodeURIComponent('تهران')}&destination=${encodeURIComponent(city)}`;
  return <>
    <section className="tl-sec" aria-labelledby="tl-routes"><h2 id="tl-routes">خرید بلیط قطار فوری</h2>
      <div className="tl-routes">{(places.data ? TRAIN_CITIES.filter(c => img(c)) : TRAIN_CITIES).map(c => <a key={c} href={href(c)} className="tl-route"><Thumb src={img(c)} credit={null} alt={c} label={c}/><span>بلیط قطار {c}</span></a>)}</div></section>
    <section className="tl-sec tl-perks" aria-label="مزایای خرید">
      {[['همه‌ی قطارها کنار هم', 'ساعت حرکت، نوع واگن و قیمت قطارهای شرکت‌های مختلف را در یک صفحه مقایسه کن.'], ['خرید ساده', 'انتخاب قطار، ثبت مسافران و پرداخت در چند قدم.'], ['استرداد از حساب کاربری', 'درخواست استرداد را از «سفرهای من» ثبت کن؛ جریمه پیش از تأیید نمایش داده می‌شود.'], ['پشتیبان سفر', 'از خرید تا پایان سفر، کارشناس پشتیبانی کنار توست.']]
        .map(([t, d]) => <article key={t}><b>{t}</b><p>{d}</p></article>)}
    </section>
    {ops.data && ops.data.items.length > 0 && <section className="tl-sec" aria-labelledby="tl-ops"><h2 id="tl-ops">شرکت‌های ریلی</h2>
      <ul className="tl-ops">{ops.data.items.map(o => <li key={o.id}>{o.name_fa}</li>)}</ul></section>}
    <section className="tl-sec" aria-labelledby="tl-faq"><h2 id="tl-faq">پرسش‌های شما</h2>
      <div className="tl-faq">{TRAIN_FAQ.map(([q, a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}</div></section>
  </>;
}
