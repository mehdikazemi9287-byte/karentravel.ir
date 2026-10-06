'use client';
/* Admin view of reference records (places, airlines, airports, attractions, visa guidance): search, filter, edit, and a
   completeness figure per record so missing content can be filled later. No price or availability field exists here. */
import {useCallback, useEffect, useState} from 'react';
import Link from 'next/link';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError} from '../../lib/api/karenseir-client';

type Completeness = {percent: number; missing: string[]};
type Row = {id: string; name: string; name_en: string | null; type: string | null; country_code: string | null; parent: string | null; source: string; admin_owned: boolean; status: string | null; completeness: Completeness};
type Field = {key: string; label: string; type: string; required: boolean; options: string[] | null; max: number | null; counts: boolean};
type Detail = Row & {kind: string; values: Record<string, string | number | null>; fields: Field[]; provenance: {source: string; source_ref: string | null; license: string | null; retrieved_on: string | null};
  updated_at: string | null; relations?: Record<string, number>};
type Summary = Record<string, {label: string; total: number; complete: number}>;
const KINDS: Record<string, string> = {places: 'کشور، استان و شهر', attractions: 'جاذبه‌ها', airports: 'فرودگاه‌ها', airlines: 'ایرلاین‌ها', visa: 'راهنمای ویزا'};
const PLACE_TYPES: Record<string, string> = {country: 'کشور', region: 'استان / منطقه', city: 'شهر'};
const RELATIONS: Record<string, string> = {children: 'زیرمجموعه', hotels: 'هتل', tours: 'تور', attractions: 'جاذبه', airports: 'فرودگاه'};
const OPTION_FA: Record<string, string> = {published: 'منتشرشده', draft: 'پیش‌نویس', international: 'بین‌المللی'};
const fa = (n: number) => n.toLocaleString('fa-IR');
const message = (e: unknown) => {
  if (e instanceof ApiError) {
    const d = e.detail as {detail?: unknown} | undefined; const inner = d && typeof d === 'object' && 'detail' in d ? d.detail : d;
    return e.status === 403 ? 'این نقش اجازهٔ ویرایش فهرست مرجع را ندارد.' : e.status === 401 ? 'ابتدا وارد شوید.' : typeof inner === 'string' ? inner : e.message;
  }
  return 'ارتباط با سرور برقرار نشد.';
};

export function ReferenceAdmin() {
  const {api, session} = useAuth();
  const [kind, setKind] = useState('places');
  const [filter, setFilter] = useState({q: '', incomplete: false, country: '', type: ''});
  const [rows, setRows] = useState<{total: number; items: Row[]} | null>(null);
  const [offset, setOffset] = useState(0);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<{kind: 'ok' | 'error'; text: string} | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (k: string, f: typeof filter, o: number) => {
    const query = new URLSearchParams({offset: String(o), limit: '30'}); if (f.q) query.set('q', f.q); if (f.incomplete) query.set('incomplete', 'true');
    if (/^[A-Za-z]{2}$/.test(f.country)) query.set('country', f.country); if (f.type && k === 'places') query.set('type', f.type);
    try {setRows(await api.get(`/admin/catalog/reference/${k}?${query}`));} catch (e) {setRows({total: 0, items: []}); setNotice({kind: 'error', text: message(e)});}
  }, [api]);
  useEffect(() => {
    if (!session) return;
    let active = true;
    api.get<Summary>('/admin/catalog/completeness').then(s => {if (active) setSummary(s);}).catch(() => {});
    api.get<{total: number; items: Row[]}>('/admin/catalog/reference/places?limit=30').then(r => {if (active) setRows(r);}).catch(e => {if (active) setNotice({kind: 'error', text: message(e)});});
    return () => {active = false;};
  }, [api, session]);

  function show(d: Detail) {setDetail(d); setForm(Object.fromEntries(d.fields.map(f => [f.key, d.values[f.key] === null || d.values[f.key] === undefined ? '' : String(d.values[f.key])])));}
  async function open(id: string) {
    setNotice(null);
    try {show(await api.get<Detail>(`/admin/catalog/reference/${kind}/${encodeURIComponent(id)}`));} catch (e) {setNotice({kind: 'error', text: message(e)});}
  }
  async function save() {
    if (!detail || busy) return;
    setBusy(true); setNotice(null);
    const values = Object.fromEntries(detail.fields.map(f => [f.key, form[f.key].trim() === '' ? null : ['lat', 'lng', 'int'].includes(f.type) ? Number(form[f.key]) : form[f.key].trim()]));
    try {
      show(await api.put<Detail>(`/admin/catalog/reference/${detail.kind}/${encodeURIComponent(detail.id)}`, {values})); setNotice({kind: 'ok', text: 'ذخیره شد و در سابقهٔ ممیزی ثبت گردید.'});
      await load(kind, filter, offset); api.get<Summary>('/admin/catalog/completeness').then(setSummary).catch(() => {});
    } catch (e) {setNotice({kind: 'error', text: message(e)});} finally {setBusy(false);}
  }
  function choose(k: string) {const f = {q: '', incomplete: false, country: '', type: ''}; setKind(k); setFilter(f); setOffset(0); setDetail(null); setNotice(null); setRows(null); void load(k, f, 0);}
  function page(o: number) {setOffset(o); void load(kind, filter, o);}

  if (!session) return <div className="cadm"><p role="alert" className="cadm-note error">برای مدیریت فهرست مرجع وارد شوید.</p></div>;
  return <div className="cadm">
    <header><h1>داده‌های مرجع</h1><p>مقصدها، جاذبه‌ها، فرودگاه‌ها، ایرلاین‌ها و راهنمای ویزا. درصد کامل‌بودن هر رکورد نشان می‌دهد چه فیلدهایی هنوز خالی است. قیمت و موجودی در این بخش وجود ندارد. <Link href="/admin/catalog">هتل‌ها</Link> · <Link href="/admin/tours">تورها</Link></p></header>
    {summary && <dl className="cadm-state" aria-label="وضعیت کامل‌بودن">{Object.entries(summary).map(([k, s]) => <div key={k}><dt style={{direction: 'rtl'}}>{s.label}</dt><dd>{fa(s.complete)} از {fa(s.total)} کامل</dd></div>)}</dl>}
    <div className="cadm-checks" role="tablist" aria-label="نوع رکورد">{Object.entries(KINDS).map(([k, label]) => <label key={k} className={k === kind ? 'on' : ''}><input type="radio" name="ref-kind" checked={k === kind} onChange={() => choose(k)}/>{label}</label>)}</div>
    {notice && <p role={notice.kind === 'error' ? 'alert' : 'status'} className={`cadm-note ${notice.kind}`}>{notice.text}</p>}
    {!detail && <>
      <form className="cadm-bar" onSubmit={e => {e.preventDefault(); setOffset(0); void load(kind, filter, 0);}}>
        <label>جست‌وجو<input value={filter.q} onChange={e => setFilter({...filter, q: e.target.value})}/></label>
        {kind !== 'visa' && <label>کد کشور<input dir="ltr" maxLength={2} placeholder="IR" value={filter.country} onChange={e => setFilter({...filter, country: e.target.value.toUpperCase()})}/></label>}
        {kind === 'places' && <label>نوع<select value={filter.type} onChange={e => setFilter({...filter, type: e.target.value})}><option value="">همه</option>{Object.entries(PLACE_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>}
        <label className="cadm-inline"><input type="checkbox" checked={filter.incomplete} onChange={e => setFilter({...filter, incomplete: e.target.checked})}/>فقط رکوردهای ناقص</label>
        <button className="button primary" type="submit">اعمال</button>
      </form>
      {rows === null ? <p className="cadm-count">در حال دریافت…</p> : <>
        <p className="cadm-count">{fa(rows.total)} رکورد</p>
        {rows.items.length === 0 ? <p className="cadm-hint">رکوردی با این شرایط پیدا نشد.</p> : <ul className="cadm-list">{rows.items.map(r => <li key={r.id}><button onClick={() => void open(r.id)}>
          <strong>{r.name}</strong><span>{[r.type ? PLACE_TYPES[r.type] ?? r.type : null, r.parent, r.country_code, r.name_en && r.name_en !== r.name ? r.name_en : null].filter(Boolean).join(' · ')}</span>
          <em className={r.completeness.percent === 100 ? 'st-published' : 'st-draft'}>{fa(r.completeness.percent)}٪ کامل</em>
          <small>{r.source}{r.admin_owned ? ' · ویرایش‌شده' : ''}{r.completeness.missing.length ? ` · خالی: ${r.completeness.missing.join('، ')}` : ''}</small></button></li>)}</ul>}
        <div className="cadm-actions start"><button type="button" className="button secondary" disabled={offset === 0} onClick={() => page(Math.max(0, offset - 30))}>قبلی</button>
          <button type="button" className="button secondary" disabled={offset + 30 >= rows.total} onClick={() => page(offset + 30)}>بعدی</button><span className="cadm-hint">{fa(Math.min(offset + 1, rows.total))} تا {fa(Math.min(offset + 30, rows.total))}</span></div>
      </>}
    </>}
    {detail && <form className="cadm-form" onSubmit={e => {e.preventDefault(); void save();}}>
      <div className="cadm-actions"><button type="button" className="button secondary" onClick={() => {setDetail(null); setNotice(null);}}>بازگشت به فهرست</button><button className="button primary" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیره'}</button></div>
      <section><h2>{detail.name} <small>{detail.id}</small></h2>
        <dl className="cadm-state"><div><dt style={{direction: 'rtl'}}>کامل‌بودن</dt><dd>{fa(detail.completeness.percent)}٪</dd></div><div><dt style={{direction: 'rtl'}}>منبع</dt><dd>{detail.provenance.source}{detail.provenance.license ? ` · ${detail.provenance.license}` : ''}</dd></div>
          <div><dt style={{direction: 'rtl'}}>مالکیت</dt><dd>{detail.admin_owned ? 'ویرایش‌شده در پنل (واردکننده‌ها بازنویسی نمی‌کنند)' : 'تحت مدیریت واردکننده'}</dd></div>
          {detail.relations && Object.entries(detail.relations).map(([k, v]) => <div key={k}><dt style={{direction: 'rtl'}}>{RELATIONS[k] ?? k}</dt><dd>{fa(v)}</dd></div>)}</dl>
        {detail.completeness.missing.length > 0 && <p className="cadm-hint">برای کامل‌شدن: {detail.completeness.missing.join('، ')}</p>}
      </section>
      <section><h2>مشخصات</h2><div className="cadm-grid">{detail.fields.map(f => <label key={f.key} className={f.type === 'text' ? 'wide' : ''}>{f.label}{f.required ? ' *' : ''}
        {f.type === 'text' ? <textarea rows={8} maxLength={f.max ?? undefined} value={form[f.key] ?? ''} onChange={e => setForm({...form, [f.key]: e.target.value})}/>
          : f.type === 'enum' ? <select value={form[f.key] ?? ''} onChange={e => setForm({...form, [f.key]: e.target.value})}>{!f.required && <option value="">—</option>}{(f.options ?? []).map(o => <option key={o} value={o}>{OPTION_FA[o] ?? o}</option>)}</select>
          : <input dir={['url', 'lat', 'lng', 'int', 'city'].includes(f.type) ? 'ltr' : undefined} inputMode={['lat', 'lng'].includes(f.type) ? 'decimal' : f.type === 'int' ? 'numeric' : undefined} maxLength={f.max ?? undefined} value={form[f.key] ?? ''} onChange={e => setForm({...form, [f.key]: e.target.value})}/>}</label>)}</div></section>
    </form>}
  </div>;
}
