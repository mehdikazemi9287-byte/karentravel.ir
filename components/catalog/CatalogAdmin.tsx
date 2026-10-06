'use client';
/* Admin editing of global hotel master content. Structured fields + standard options only;
   price and availability are not part of this form or its API. */
import {useCallback, useEffect, useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';

type Dict = Record<string, string>;
type Options = {hotel_types: Dict; amenities: Dict; policy_fields: Dict; policy_values: Dict; bed_types: Dict; views: Dict; stars_status: Dict; status: Dict; countries: {code: string; name: string}[]};
type Row = {id: string; slug: string; name: string; name_en: string | null; country_code: string; city: string | null; stars: number | null; status: string; source: string; admin_owned: boolean};
type Image = {url: string; caption: string; author: string; license: string; license_url: string; source_url: string};
type Room = {name_fa: string; name_en: string; bed_type: string; max_adults: string; max_children: string; size_m2: string; view: string; amenities: string[]; description: string};
type Form = {name_fa: string; name_en: string; name_local: string; country_code: string; city_id: string; hotel_type: string; stars: string; stars_status: string; address: string; latitude: string; longitude: string;
  amenities: string[]; description: string; rules_text: string; checkin_time: string; checkout_time: string; children_policy: string; pets_policy: string; smoking_policy: string; phone: string; website: string; email: string;
  status: string; source_ref: string; retrieved_on: string; images: Image[]; room_types: Room[]};

const EMPTY: Form = {name_fa: '', name_en: '', name_local: '', country_code: 'IR', city_id: '', hotel_type: 'hotel', stars: '', stars_status: '', address: '', latitude: '', longitude: '', amenities: [], description: '', rules_text: '',
  checkin_time: '', checkout_time: '', children_policy: '', pets_policy: '', smoking_policy: '', phone: '', website: '', email: '', status: 'draft', source_ref: '', retrieved_on: '', images: [], room_types: []};
const NEW_IMAGE: Image = {url: '', caption: '', author: '', license: '', license_url: '', source_url: ''};
const NEW_ROOM: Room = {name_fa: '', name_en: '', bed_type: '', max_adults: '', max_children: '', size_m2: '', view: '', amenities: [], description: ''};
const s = (v: unknown) => (v === null || v === undefined ? '' : String(v));
const nul = (v: string) => (v.trim() === '' ? null : v.trim());
const num = (v: string) => (v.trim() === '' ? null : Number(v));
const message = (e: unknown) => {
  if (e instanceof ApiError) {
    const d = e.detail as {detail?: unknown} | undefined; const inner = d && typeof d === 'object' && 'detail' in d ? d.detail : d;
    if (Array.isArray(inner)) return inner.map((i: {loc?: unknown[]; msg?: string}) => `${(i.loc ?? []).slice(1).join('.')}: ${i.msg}`).join(' | ');
    return e.status === 403 ? 'این نقش اجازهٔ ویرایش فهرست مرجع را ندارد.' : e.status === 401 ? 'ابتدا وارد شوید.' : typeof inner === 'string' ? inner : e.message;
  }
  return 'ارتباط با سرور برقرار نشد.';
};

/* eslint-disable @typescript-eslint/no-explicit-any */
function toForm(h: any): Form {
  return {name_fa: s(h.name_fa), name_en: s(h.name_en), name_local: s(h.name_local), country_code: h.country_code, city_id: s(h.city?.id), hotel_type: h.hotel_type, stars: s(h.stars), stars_status: s(h.stars_status), address: s(h.address),
    latitude: s(h.latitude), longitude: s(h.longitude), amenities: h.amenity_keys ?? [], description: s(h.description), rules_text: s(h.rules_text), checkin_time: s(h.checkin_time), checkout_time: s(h.checkout_time),
    children_policy: s(h.children_policy), pets_policy: s(h.pets_policy), smoking_policy: s(h.smoking_policy), phone: s(h.phone), website: s(h.website), email: s(h.email), status: h.status, source_ref: s(h.provenance?.source_ref),
    retrieved_on: s(h.provenance?.retrieved_on), images: (h.images ?? []).map((i: any) => ({url: i.url, caption: s(i.caption), author: s(i.author), license: i.license, license_url: s(i.license_url), source_url: i.source_url})),
    room_types: (h.room_types ?? []).map((r: any) => ({name_fa: r.name_fa, name_en: s(r.name_en), bed_type: s(r.bed_type), max_adults: s(r.max_adults), max_children: s(r.max_children), size_m2: s(r.size_m2), view: s(r.view),
      amenities: (r.amenities ?? []).map((a: any) => a.key), description: s(r.description)}))};
}
/* eslint-enable @typescript-eslint/no-explicit-any */
function toBody(f: Form) {
  return {name_fa: nul(f.name_fa), name_en: nul(f.name_en), name_local: nul(f.name_local), country_code: f.country_code, city_id: nul(f.city_id), hotel_type: f.hotel_type, stars: num(f.stars), stars_status: nul(f.stars_status),
    address: nul(f.address), latitude: num(f.latitude), longitude: num(f.longitude), amenities: f.amenities, description: nul(f.description), rules_text: nul(f.rules_text), checkin_time: nul(f.checkin_time),
    checkout_time: nul(f.checkout_time), children_policy: nul(f.children_policy), pets_policy: nul(f.pets_policy), smoking_policy: nul(f.smoking_policy), phone: nul(f.phone), website: nul(f.website), email: nul(f.email),
    status: f.status, source_ref: nul(f.source_ref), retrieved_on: nul(f.retrieved_on),
    images: f.images.map(i => ({url: i.url.trim(), caption: nul(i.caption), author: nul(i.author), license: i.license.trim(), license_url: nul(i.license_url), source_url: i.source_url.trim()})),
    room_types: f.room_types.map(r => ({name_fa: r.name_fa.trim(), name_en: nul(r.name_en), bed_type: nul(r.bed_type), max_adults: num(r.max_adults), max_children: num(r.max_children), size_m2: num(r.size_m2), view: nul(r.view),
      amenities: r.amenities, description: nul(r.description)}))};
}

function Select({label, value, onChange, options, empty}: {label: string; value: string; onChange: (v: string) => void; options: Dict; empty?: string}) {
  return <label>{label}<select value={value} onChange={e => onChange(e.target.value)}>{empty !== undefined && <option value="">{empty}</option>}{Object.entries(options).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>;
}
function Text({label, value, onChange, ltr, type = 'text', wide}: {label: string; value: string; onChange: (v: string) => void; ltr?: boolean; type?: string; wide?: boolean}) {
  return <label className={wide ? 'wide' : ''}>{label}<input type={type} value={value} dir={ltr ? 'ltr' : undefined} onChange={e => onChange(e.target.value)}/></label>;
}
function Checks({legend, value, onChange, options}: {legend: string; value: string[]; onChange: (v: string[]) => void; options: Dict}) {
  return <fieldset className="cadm-checks"><legend>{legend}</legend>{Object.entries(options).map(([k, v]) => <label key={k} className={value.includes(k) ? 'on' : ''}>
    <input type="checkbox" checked={value.includes(k)} onChange={() => onChange(value.includes(k) ? value.filter(x => x !== k) : [...value, k])}/>{v}</label>)}</fieldset>;
}

export function CatalogAdmin() {
  const {api, session} = useAuth();
  const [opts, setOpts] = useState<Options | null>(null);
  const [rows, setRows] = useState<{total: number; items: Row[]}>({total: 0, items: []});
  const [filter, setFilter] = useState({q: '', status: '', source: ''});
  const [editing, setEditing] = useState<string | null>(null);  // hotel id, 'new' or null
  const [form, setForm] = useState<Form>(EMPTY);
  const [cities, setCities] = useState<{id: string; name: string}[]>([]);
  const [notice, setNotice] = useState<{kind: 'ok' | 'error'; text: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm(f => ({...f, [key]: value}));

  const load = useCallback(async (f = filter) => {
    const query = new URLSearchParams(); if (f.q) query.set('q', f.q); if (f.status) query.set('status', f.status); if (f.source) query.set('source', f.source);
    try {setRows(await api.get(`/admin/catalog/hotels?${query}`));} catch (e) {setNotice({kind: 'error', text: message(e)});}
  }, [api, filter]);
  useEffect(() => {
    if (!session) return;
    let active = true;
    Promise.all([api.get<Options>('/admin/catalog/options'), api.get<{total: number; items: Row[]}>('/admin/catalog/hotels')])
      .then(([o, r]) => {if (active) {setOpts(o); setRows(r);}}).catch(e => {if (active) setNotice({kind: 'error', text: message(e)});});
    return () => {active = false;};
  }, [api, session]);
  useEffect(() => {
    if (!session || !editing) return;
    let active = true;
    api.get<{id: string; name: string}[]>(`/admin/catalog/cities?country=${form.country_code}`).then(c => {if (active) setCities(c);}).catch(() => {if (active) setCities([]);});
    return () => {active = false;};
  }, [api, session, editing, form.country_code]);

  async function open(id: string) {
    setNotice(null);
    try {setForm(toForm(await api.get(`/admin/catalog/hotels/${encodeURIComponent(id)}`))); setEditing(id);} catch (e) {setNotice({kind: 'error', text: message(e)});}
  }
  async function save() {
    if (!editing) return;
    setBusy(true); setNotice(null);
    try {
      const saved = editing === 'new' ? await api.post<{id: string}>('/admin/catalog/hotels', toBody(form)) : await api.put<{id: string}>(`/admin/catalog/hotels/${encodeURIComponent(editing)}`, toBody(form));
      setForm(toForm(saved)); setEditing(saved.id); setNotice({kind: 'ok', text: 'ذخیره شد و در سابقهٔ ممیزی ثبت گردید.'}); await load();
    } catch (e) {setNotice({kind: 'error', text: message(e)});} finally {setBusy(false);}
  }

  if (!session) return <div className="cadm"><p role="alert" className="cadm-note error">برای مدیریت فهرست هتل‌ها وارد شوید.</p></div>;
  const cityOptions = Object.fromEntries((form.city_id && !cities.some(c => c.id === form.city_id) ? [{id: form.city_id, name: form.city_id}, ...cities] : cities).map(c => [c.id, c.name]));
  return <div className="cadm">
    <header><h1>مدیریت هتل‌های فهرست مرجع</h1><p>هر مشخصه در فیلد مستقل و با گزینه‌های استاندارد ثبت می‌شود تا در جست‌وجو قابل فیلتر باشد. قیمت و موجودی در این فرم وجود ندارد و فقط از نرخ واقعی تأمین‌کننده می‌آید.</p></header>
    {notice && <p role={notice.kind === 'error' ? 'alert' : 'status'} className={`cadm-note ${notice.kind}`}>{notice.text}</p>}
    {!editing && opts && <>
      <form className="cadm-bar" onSubmit={e => {e.preventDefault(); void load();}}>
        <Text label="جست‌وجو" value={filter.q} onChange={v => setFilter({...filter, q: v})}/>
        <Select label="وضعیت" value={filter.status} onChange={v => setFilter({...filter, status: v})} options={opts.status} empty="همه"/>
        <Select label="منبع" value={filter.source} onChange={v => setFilter({...filter, source: v})} options={{checkline: 'CheckLine', openstreetmap: 'OpenStreetMap', karenseir: 'کارن‌سیر'}} empty="همه"/>
        <button className="button primary" type="submit">اعمال</button>
        <button className="button secondary" type="button" onClick={() => {setForm(EMPTY); setEditing('new'); setNotice(null);}}>هتل جدید</button>
      </form>
      <p className="cadm-count">{rows.total.toLocaleString('fa-IR')} هتل</p>
      <ul className="cadm-list">{rows.items.map(r => <li key={r.id}><button onClick={() => void open(r.id)}>
        <strong>{r.name}</strong><span>{[r.city, r.country_code, r.stars ? `${r.stars}★` : null].filter(Boolean).join(' · ')}</span>
        <em className={`st-${r.status}`}>{opts.status[r.status] ?? r.status}</em><small>{r.source}{r.admin_owned ? ' · ویرایش‌شده' : ''}</small></button></li>)}</ul>
    </>}
    {editing && opts && <form className="cadm-form" onSubmit={e => {e.preventDefault(); void save();}}>
      <div className="cadm-actions"><button type="button" className="button secondary" onClick={() => {setEditing(null); setNotice(null);}}>بازگشت به فهرست</button><button className="button primary" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیره'}</button></div>
      <section><h2>شناسه و طبقه‌بندی</h2><div className="cadm-grid">
        <Text label="نام فارسی" value={form.name_fa} onChange={v => set('name_fa', v)}/><Text label="نام انگلیسی" value={form.name_en} onChange={v => set('name_en', v)} ltr/><Text label="نام محلی" value={form.name_local} onChange={v => set('name_local', v)}/>
        <Select label="نوع اقامتگاه" value={form.hotel_type} onChange={v => set('hotel_type', v)} options={opts.hotel_types}/>
        <Select label="درجه (ستاره)" value={form.stars} onChange={v => set('stars', v)} options={{1: '۱', 2: '۲', 3: '۳', 4: '۴', 5: '۵'}} empty="نامشخص"/>
        <Select label="اعتبار درجه" value={form.stars_status} onChange={v => set('stars_status', v)} options={opts.stars_status} empty="—"/>
        <Select label="وضعیت انتشار" value={form.status} onChange={v => set('status', v)} options={opts.status}/></div></section>
      <section><h2>موقعیت</h2><div className="cadm-grid">
        <Select label="کشور" value={form.country_code} onChange={v => setForm(f => ({...f, country_code: v, city_id: ''}))} options={Object.fromEntries(opts.countries.map(c => [c.code, c.name]))}/>
        <Select label="شهر" value={form.city_id} onChange={v => set('city_id', v)} options={cityOptions} empty="نامشخص"/>
        <Text label="نشانی" value={form.address} onChange={v => set('address', v)} wide/>
        <Text label="عرض جغرافیایی" value={form.latitude} onChange={v => set('latitude', v)} ltr/><Text label="طول جغرافیایی" value={form.longitude} onChange={v => set('longitude', v)} ltr/></div></section>
      <section><h2>امکانات</h2><Checks legend="امکانات هتل" value={form.amenities} onChange={v => set('amenities', v)} options={opts.amenities}/></section>
      <section><h2>قوانین و ساعت‌ها</h2><div className="cadm-grid">
        <Text label="ساعت ورود" type="time" value={form.checkin_time} onChange={v => set('checkin_time', v)} ltr/><Text label="ساعت خروج" type="time" value={form.checkout_time} onChange={v => set('checkout_time', v)} ltr/>
        {(Object.keys(opts.policy_fields) as (keyof Form)[]).map(k => <Select key={k} label={opts.policy_fields[k]} value={form[k] as string} onChange={v => set(k, v as never)} options={opts.policy_values} empty="نامشخص"/>)}
        <label className="wide">سایر قوانین<textarea rows={3} value={form.rules_text} onChange={e => set('rules_text', e.target.value)}/></label></div></section>
      <section><h2>متن معرفی</h2><label className="wide">مکمل فیلدهای بالا؛ مشخصات ساختاری را اینجا تکرار نکنید<textarea rows={5} value={form.description} onChange={e => set('description', e.target.value)}/></label></section>
      <section><h2>انواع اتاق <small>(توصیفی؛ بدون قیمت و موجودی)</small></h2>
        {form.room_types.map((r, i) => {const up = (patch: Partial<Room>) => set('room_types', form.room_types.map((x, j) => j === i ? {...x, ...patch} : x)); return <div className="cadm-item" key={i}><div className="cadm-grid">
          <Text label="نام اتاق" value={r.name_fa} onChange={v => up({name_fa: v})}/><Text label="نام انگلیسی" value={r.name_en} onChange={v => up({name_en: v})} ltr/>
          <Select label="نوع تخت" value={r.bed_type} onChange={v => up({bed_type: v})} options={opts.bed_types} empty="نامشخص"/><Select label="منظره" value={r.view} onChange={v => up({view: v})} options={opts.views} empty="نامشخص"/>
          <Text label="حداکثر بزرگسال" type="number" value={r.max_adults} onChange={v => up({max_adults: v})} ltr/><Text label="حداکثر کودک" type="number" value={r.max_children} onChange={v => up({max_children: v})} ltr/>
          <Text label="متراژ (m²)" type="number" value={r.size_m2} onChange={v => up({size_m2: v})} ltr/><Text label="توضیح" value={r.description} onChange={v => up({description: v})} wide/></div>
          <Checks legend="امکانات اتاق" value={r.amenities} onChange={v => up({amenities: v})} options={opts.amenities}/>
          <button type="button" className="cadm-remove" onClick={() => set('room_types', form.room_types.filter((_, j) => j !== i))}>حذف این اتاق</button></div>;})}
        <button type="button" className="button secondary" onClick={() => set('room_types', [...form.room_types, NEW_ROOM])}>افزودن نوع اتاق</button></section>
      <section><h2>تصاویر <small>(فقط تصویر واقعی همین هتل با مجوز مشخص؛ اولین تصویر، تصویر اصلی است)</small></h2>
        {form.images.map((im, i) => {const up = (patch: Partial<Image>) => set('images', form.images.map((x, j) => j === i ? {...x, ...patch} : x)); return <div className="cadm-item" key={i}><div className="cadm-grid">
          {/^https:\/\//.test(im.url) && /* eslint-disable-next-line @next/next/no-img-element */ <img src={im.url} alt={im.caption || form.name_fa} loading="lazy"/>}
          <Text label="نشانی تصویر (https)" value={im.url} onChange={v => up({url: v})} ltr wide/><Text label="صفحهٔ منبع" value={im.source_url} onChange={v => up({source_url: v})} ltr wide/>
          <Text label="مجوز" value={im.license} onChange={v => up({license: v})} ltr/><Text label="نشانی مجوز" value={im.license_url} onChange={v => up({license_url: v})} ltr/>
          <Text label="پدیدآور" value={im.author} onChange={v => up({author: v})}/><Text label="شرح" value={im.caption} onChange={v => up({caption: v})}/></div>
          <button type="button" className="cadm-remove" onClick={() => set('images', form.images.filter((_, j) => j !== i))}>حذف این تصویر</button></div>;})}
        <button type="button" className="button secondary" onClick={() => set('images', [...form.images, NEW_IMAGE])}>افزودن تصویر</button></section>
      <section><h2>تماس و منبع</h2><div className="cadm-grid">
        <Text label="تلفن" value={form.phone} onChange={v => set('phone', v)} ltr/><Text label="وب‌سایت (https)" value={form.website} onChange={v => set('website', v)} ltr/><Text label="ایمیل" value={form.email} onChange={v => set('email', v)} ltr/>
        <Text label="ارجاع منبع" value={form.source_ref} onChange={v => set('source_ref', v)} ltr/><Text label="تاریخ دریافت (YYYY-MM-DD)" value={form.retrieved_on} onChange={v => set('retrieved_on', v)} ltr/></div></section>
      <div className="cadm-actions"><button className="button primary" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیره'}</button></div>
    </form>}
  </div>;
}
