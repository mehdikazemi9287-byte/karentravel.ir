'use client';
/* Commercial rules (admin) + treasury (finance) + customer deposit / bank account.
   Every figure comes from /commerce/* or /me/*; nothing is computed or invented on the client. */
import {useState, type FormEvent, type ReactNode} from 'react';
import {Async, Badge, Card, Empty, Stats, Table, dateFa, errorOf, fa, money, useLoad} from './PanelKit';

export type Opt = [string, string][];
export type Field = {key: string; label: string; type?: 'text' | 'number' | 'select' | 'bool' | 'textarea' | 'date' | 'percent' | 'money'; options?: Opt; hint?: string; required?: boolean; wide?: boolean};
export type Row = Record<string, any>;

const SERVICES: Opt = [['flight', 'پرواز'], ['hotel', 'هتل'], ['tour', 'تور'], ['train', 'قطار'], ['bus', 'اتوبوس'], ['insurance', 'بیمه'], ['visa', 'ویزا'], ['package', 'پرواز + هتل'], ['cip', 'CIP'], ['transfer', 'ترانسفر'], ['any', 'همه خدمات']];
const STATUS: Opt = [['active', 'فعال'], ['disabled', 'غیرفعال']];
const SCOPE: Opt = [['any', 'داخلی و خارجی'], ['domestic', 'داخلی'], ['international', 'خارجی']];
const FTYPE: Opt = [['any', 'همه'], ['system', 'سیستمی'], ['charter', 'چارتری']];
const label = (opts: Opt, v: string) => opts.find(o => o[0] === v)?.[1] ?? v ?? '—';
const ACCOUNT: Opt = [['wallet', 'کیف پول'], ['credit', 'اعتبار'], ['receivable', 'دریافتنی'], ['payable', 'پرداختنی'], ['bank', 'بانک'], ['cash', 'نقد'], ['gateway', 'درگاه']];
const OPERATION: Opt = [['deposit', 'واریز'], ['withdrawal', 'برداشت'], ['purchase', 'خرید'], ['refund', 'استرداد'], ['settlement', 'تسویه'], ['adjustment', 'اصلاحی'], ['fee', 'کارمزد']];
const PARTY: Opt = [['user', 'کاربر'], ['organization', 'سازمان'], ['agency', 'آژانس همکار'], ['supplier', 'تأمین‌کننده'], ['company', 'شرکت']];

export function Tabs({tabs}: {tabs: [string, ReactNode][]}) {
  const [i, setI] = useState(0);
  return <div><div className="pn-chips" role="tablist" style={{marginBottom: 14}}>{tabs.map(([t], k) => <button key={t} role="tab" aria-selected={i === k} className={i === k ? 'active' : ''} style={i === k ? {background: 'var(--pn-plum, #4b2a4f)', color: '#fff'} : undefined} onClick={() => setI(k)}>{t}</button>)}</div>{tabs[i][1]}</div>;
}

export function Note({msg}: {msg: {ok: boolean; text: string} | null}) {
  return msg ? <p className={`pn-note ${msg.ok ? '' : 'error'}`} role={msg.ok ? 'status' : 'alert'}>{msg.text}</p> : null;
}

export function FormFields({fields, value, set}: {fields: Field[]; value: Row; set: (v: Row) => void}) {
  return <>{fields.map(f => {
    const v = value[f.key];
    const on = (x: any) => set({...value, [f.key]: x});
    const common = {id: `f-${f.key}`, required: f.required};
    let input: ReactNode;
    if (f.type === 'select') input = <select {...common} value={v ?? ''} onChange={e => on(e.target.value)}>{f.options!.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>;
    else if (f.type === 'bool') input = <select {...common} value={v ? '1' : '0'} onChange={e => on(e.target.value === '1')}><option value="1">بله</option><option value="0">خیر</option></select>;
    else if (f.type === 'textarea') input = <textarea {...common} rows={3} value={v ?? ''} onChange={e => on(e.target.value)} style={{border: '1px solid #d9cdc0', borderRadius: 12, padding: 9, font: 'inherit'}}/>;
    else if (f.type === 'percent') input = <input {...common} inputMode="decimal" value={v === undefined || v === null ? '' : String(v / 100)} onChange={e => on(e.target.value === '' ? 0 : Math.round(Number(e.target.value) * 100))}/>;
    else if (f.type === 'number' || f.type === 'money') input = <input {...common} inputMode="numeric" value={v ?? ''} onChange={e => {const t = e.target.value.replace(/[^\d]/g, ''); on(t === '' ? null : Number(t));}}/>;
    else input = <input {...common} type={f.type === 'date' ? 'date' : 'text'} value={v ?? ''} onChange={e => on(e.target.value)} dir={f.type === 'date' ? 'ltr' : undefined}/>;
    return <label key={f.key} htmlFor={`f-${f.key}`} style={f.wide ? {flexBasis: '100%'} : undefined}>{f.label}{f.hint && <small style={{fontWeight: 400}}> — {f.hint}</small>}{input}</label>;
  })}</>;
}

/* Generic list + create/edit for one rule collection. */
export function Crud({path, title, fields, cols, blank, toPayload, fromRow, extra}: {path: string; title: string; fields: Field[]; cols: {label: string; cell: (r: Row) => ReactNode}[];
  blank: Row; toPayload?: (v: Row) => Row; fromRow?: (r: Row) => Row; extra?: (r: Row) => ReactNode}) {
  const {state, reload, api} = useLoad<{items: Row[]}>(path);
  const [edit, setEdit] = useState<Row | null>(null);
  const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  const [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault(); if (!edit) return; setBusy(true); setMsg(null);
    const {id, ...rest} = edit; const body = toPayload ? toPayload(rest) : rest;
    try {id ? await api.put(`${path}/${id}`, body) : await api.post(path, body); setMsg({ok: true, text: 'ذخیره شد.'}); setEdit(null); reload();}
    catch (err) {setMsg({ok: false, text: errorOf(err).message});} finally {setBusy(false);}
  }
  return <Card title={title} action={<button className="pn-btn" onClick={() => {setEdit({...blank}); setMsg(null);}}>افزودن</button>}>
    <Note msg={msg}/>
    {edit && <form className="pn-form" onSubmit={save} style={{marginBottom: 16, padding: 12, border: '1px dashed #d9cdc0', borderRadius: 14}}>
      <FormFields fields={fields} value={edit} set={setEdit}/>
      <span style={{display: 'flex', gap: 8}}><button className="pn-btn" disabled={busy}>{edit.id ? 'ذخیره‌ی تغییرات' : 'ثبت'}</button><button type="button" className="pn-btn ghost" onClick={() => setEdit(null)}>انصراف</button></span>
    </form>}
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="هنوز موردی ثبت نشده است."
      cols={[...cols, {label: '', cell: r => <span style={{display: 'flex', gap: 6}}><button className="pn-btn ghost" onClick={() => {setEdit(fromRow ? fromRow(r) : {...r}); setMsg(null);}}>ویرایش</button>{extra?.(r)}</span>}]}/>}</Async>
  </Card>;
}

/* ------------------------------------------------------------------ admin: commercial rules */
function GroupMembers({group}: {group: Row}) {
  const {state, reload, api} = useLoad<{items: Row[]}>(`/commerce/groups/${group.id}/members`);
  const [ids, setIds] = useState(''); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function add(e: FormEvent) {
    e.preventDefault(); const list = ids.split(/[\s,،]+/).map(Number).filter(Boolean); if (!list.length) return;
    try {await api.put(`/commerce/groups/${group.id}/members`, {user_ids: list}); setIds(''); setMsg({ok: true, text: 'کاربران به گروه منتقل شدند.'}); reload();} catch (err) {setMsg({ok: false, text: errorOf(err).message});}
  }
  return <div style={{marginTop: 8}}>
    <form className="pn-form" onSubmit={add}><label>شناسه‌ی کاربران (با ویرگول جدا کنید)<input value={ids} onChange={e => setIds(e.target.value)} dir="ltr"/></label><button className="pn-btn">افزودن به گروه</button></form>
    <Note msg={msg}/>
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => String(r.user_id)} empty="عضوی ندارد." cols={[{label: 'شناسه', cell: r => fa(r.user_id)}, {label: 'نام', cell: r => r.name}, {label: 'ایمیل', cell: r => <span dir="ltr">{r.email}</span>}]}/>}</Async>
  </div>;
}

function Groups() {
  const [open, setOpen] = useState<Row | null>(null);
  return <>
    <Crud path="/commerce/groups" title="گروه‌های کاربری (سطح قیمت)" blank={{code: '', name: '', description: '', is_default: false, status: 'active'}}
      fields={[{key: 'code', label: 'کد', required: true, hint: 'لاتین'}, {key: 'name', label: 'نام گروه', required: true}, {key: 'is_default', label: 'گروه پیش‌فرض', type: 'bool'}, {key: 'status', label: 'وضعیت', type: 'select', options: STATUS}, {key: 'description', label: 'توضیح', type: 'textarea', wide: true}]}
      cols={[{label: 'کد', cell: r => <span dir="ltr">{r.code}</span>}, {label: 'نام', cell: r => r.name}, {label: 'پیش‌فرض', cell: r => r.is_default ? 'بله' : '—'}, {label: 'اعضا', cell: r => fa(r.members ?? 0)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}
      extra={r => <button className="pn-btn ghost" onClick={() => setOpen(open?.id === r.id ? null : r)}>اعضا</button>}/>
    {open && <Card title={`اعضای گروه «${open.name}»`}><GroupMembers group={open}/></Card>}
  </>;
}

function GroupSelect(): Opt {
  const {state} = useLoad<{items: Row[]}>('/commerce/groups');
  return [['', 'همه‌ی کاربران'], ...(state.kind === 'ready' ? state.data.items.map(g => [g.id, g.name] as [string, string]) : [])];
}

function Markups() {
  const groups = GroupSelect();
  const pct = (r: Row, k: string) => r.calc === 'percent' ? `${fa(r[k] / 100)}٪` : money(r[k], 'IRR');
  return <Crud path="/commerce/markup-rules" title="مارک‌آپ و تخفیف"
    blank={{title: '', service_type: 'flight', group_id: '', scope: 'any', flight_type: 'any', effect: 'markup', calc: 'percent', basis: 'total', adult: 0, child: 0, infant: 0, round_to: 0, priority: 100, status: 'active'}}
    toPayload={v => ({...v, group_id: v.group_id || null, cap_amount: v.cap_amount || null, min_stars: v.min_stars || null, valid_from: v.valid_from || null, valid_to: v.valid_to || null})}
    fromRow={r => ({...r, group_id: r.group_id ?? ''})}
    fields={[{key: 'title', label: 'عنوان', required: true}, {key: 'service_type', label: 'خدمت', type: 'select', options: SERVICES}, {key: 'group_id', label: 'گروه کاربری', type: 'select', options: groups},
      {key: 'effect', label: 'نوع', type: 'select', options: [['markup', 'افزایش (مارک‌آپ)'], ['discount', 'تخفیف']]}, {key: 'calc', label: 'محاسبه', type: 'select', options: [['percent', 'درصدی'], ['fixed', 'مبلغ ثابت (ریال)']]},
      {key: 'basis', label: 'مبنا', type: 'select', options: [['total', 'قیمت کل'], ['base', 'نرخ پایه']]},
      {key: 'adult', label: 'بزرگسال', type: 'number', hint: 'درصد: ۱۰۰ = ۱٪'}, {key: 'child', label: 'کودک', type: 'number'}, {key: 'infant', label: 'نوزاد', type: 'number'},
      {key: 'scope', label: 'محدوده', type: 'select', options: SCOPE}, {key: 'flight_type', label: 'نوع پرواز', type: 'select', options: FTYPE},
      {key: 'airline_code', label: 'کد ایرلاین', hint: 'مثلاً IR'}, {key: 'origin', label: 'مبدأ (IATA)'}, {key: 'destination', label: 'مقصد (IATA)'},
      {key: 'city_id', label: 'شهر هتل (شناسه)'}, {key: 'min_stars', label: 'حداقل ستاره', type: 'number'}, {key: 'supplier_id', label: 'تأمین‌کننده (شناسه)'},
      {key: 'round_to', label: 'گرد کردن به بالا (ریال)', type: 'money'}, {key: 'cap_amount', label: 'سقف مبلغ (ریال)', type: 'money'}, {key: 'priority', label: 'اولویت', type: 'number', hint: 'عدد کمتر = مقدم'},
      {key: 'valid_from', label: 'از تاریخ', type: 'date'}, {key: 'valid_to', label: 'تا تاریخ', type: 'date'}, {key: 'status', label: 'وضعیت', type: 'select', options: STATUS}, {key: 'note', label: 'یادداشت', type: 'textarea', wide: true}]}
    cols={[{label: 'عنوان', cell: r => r.title}, {label: 'خدمت', cell: r => label(SERVICES, r.service_type)}, {label: 'گروه', cell: r => label(groups, r.group_id ?? '')},
      {label: 'شرط', cell: r => [r.airline_code, r.origin && r.destination ? `${r.origin}→${r.destination}` : r.origin || r.destination, r.scope !== 'any' && label(SCOPE, r.scope), r.flight_type !== 'any' && label(FTYPE, r.flight_type), r.min_stars && `${fa(r.min_stars)}★+`].filter(Boolean).join('، ') || 'عمومی'},
      {label: 'بزرگسال/کودک/نوزاد', cell: r => <span>{r.effect === 'discount' ? '−' : '+'}{pct(r, 'adult')} / {pct(r, 'child')} / {pct(r, 'infant')}</span>}, {label: 'اولویت', cell: r => fa(r.priority)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}/>;
}

function Preview() {
  const {api} = useLoad<unknown>(null);
  const [v, setV] = useState<Row>({service_type: 'flight', adult_count: 1, adult_total: 10000000, child_count: 0, child_total: 0, infant_count: 0, infant_total: 0});
  const [res, setRes] = useState<Row | null>(null); const [err, setErr] = useState('');
  async function run(e: FormEvent) {
    e.preventDefault(); setErr('');
    const fares = Object.fromEntries(['adult', 'child', 'infant'].map(p => [p, {count: v[`${p}_count`] || 0, total: v[`${p}_total`] || 0}]));
    try {setRes(await api.post('/commerce/markup-rules/preview', {service_type: v.service_type, user_id: v.user_id || null, airline_code: v.airline_code || null, origin: v.origin || null, destination: v.destination || null, scope: v.scope || null, flight_type: v.flight_type || null, city_id: v.city_id || null, stars: v.stars || null, fares}));}
    catch (x) {setErr(errorOf(x).message);}
  }
  return <Card title="آزمایش قیمت فروش">
    <form className="pn-form" onSubmit={run}><FormFields value={v} set={setV} fields={[{key: 'service_type', label: 'خدمت', type: 'select', options: SERVICES}, {key: 'user_id', label: 'شناسه کاربر', type: 'number'},
      {key: 'airline_code', label: 'ایرلاین'}, {key: 'origin', label: 'مبدأ'}, {key: 'destination', label: 'مقصد'}, {key: 'scope', label: 'محدوده', type: 'select', options: [['', '—'], ...SCOPE.slice(1)]}, {key: 'flight_type', label: 'نوع پرواز', type: 'select', options: [['', '—'], ...FTYPE.slice(1)]},
      {key: 'city_id', label: 'شهر هتل'}, {key: 'stars', label: 'ستاره', type: 'number'},
      {key: 'adult_count', label: 'تعداد بزرگسال', type: 'number'}, {key: 'adult_total', label: 'نرخ بزرگسال (ریال)', type: 'money'}, {key: 'child_count', label: 'تعداد کودک', type: 'number'}, {key: 'child_total', label: 'نرخ کودک', type: 'money'}, {key: 'infant_count', label: 'تعداد نوزاد', type: 'number'}, {key: 'infant_total', label: 'نرخ نوزاد', type: 'money'}]}/>
      <button className="pn-btn">محاسبه</button></form>
    {err && <p className="pn-note error">{err}</p>}
    {res && <><p className="pn-muted">قانون اعمال‌شده: {res.rule ? res.rule.title : 'هیچ قانونی منطبق نشد (قیمت خالص)'}</p>
      <Table rows={res.lines} rowKey={(r: Row) => r.pax} empty="—" cols={[{label: 'مسافر', cell: (r: Row) => ({adult: 'بزرگسال', child: 'کودک', infant: 'نوزاد'} as Row)[r.pax]}, {label: 'تعداد', cell: (r: Row) => fa(r.count)}, {label: 'خالص', cell: (r: Row) => money(r.net, 'IRR')}, {label: 'تعدیل', cell: (r: Row) => money(r.adjustment, 'IRR')}, {label: 'فروش', cell: (r: Row) => money(r.sell, 'IRR')}, {label: 'جمع', cell: (r: Row) => money(r.line_total, 'IRR')}]}/>
      <Stats items={[{label: 'جمع خالص', value: money(res.net_total, 'IRR')}, {label: 'جمع فروش', value: money(res.sell_total, 'IRR')}, {label: 'سود/تخفیف', value: money(res.margin, 'IRR')}]}/></>}
  </Card>;
}

function Penalties() {
  const tiersText = (t: Row[]) => (t || []).map(x => `${x.until_minutes}:${x.type === 'fixed' ? 'f' : 'p'}:${x.adult}:${x.child}:${x.infant}`).join('\n');
  const parse = (s: string) => s.split(/\n+/).map(l => l.trim()).filter(Boolean).map(l => {const [m, t, a, c, i] = l.split(':'); return {until_minutes: Number(m), type: t === 'f' ? 'fixed' : 'percent', adult: Number(a || 0), child: Number(c || 0), infant: Number(i || 0)};});
  return <Crud path="/commerce/penalty-rules" title="جریمه‌ی کنسلی"
    blank={{code: '', title: '', service_type: 'flight', flight_type: 'any', status: 'active', tiers_text: '4320:p:3000:3000:1000\n180:p:5000:5000:1000\n0:p:8000:8000:1000'}}
    fromRow={r => ({...r, tiers_text: tiersText(r.tiers)})}
    toPayload={v => {const {tiers_text, tiers, ...rest} = v; return {...rest, airline_code: rest.airline_code || null, tiers: parse(tiers_text || '')};}}
    fields={[{key: 'code', label: 'کد', required: true}, {key: 'title', label: 'عنوان', required: true}, {key: 'service_type', label: 'خدمت', type: 'select', options: SERVICES}, {key: 'airline_code', label: 'ایرلاین'}, {key: 'flight_type', label: 'نوع پرواز', type: 'select', options: FTYPE}, {key: 'status', label: 'وضعیت', type: 'select', options: STATUS},
      {key: 'tiers_text', label: 'پله‌های جریمه', type: 'textarea', wide: true, hint: 'هر خط: دقیقه‌مانده‌به‌شروع:p(درصد) یا f(ریال):بزرگسال:کودک:نوزاد — درصد با پایه‌ی ۱۰۰ (۳۰۰۰ = ۳۰٪)'},
      {key: 'text_rules', label: 'قوانین متنی برای مسافر', type: 'textarea', wide: true}]}
    cols={[{label: 'کد', cell: r => <span dir="ltr">{r.code}</span>}, {label: 'عنوان', cell: r => r.title}, {label: 'خدمت', cell: r => label(SERVICES, r.service_type)}, {label: 'ایرلاین', cell: r => r.airline_code || 'همه'},
      {label: 'پله‌ها', cell: r => (r.tiers || []).map((t: Row) => `${t.until_minutes >= 60 ? fa(Math.round(t.until_minutes / 60)) + ' ساعت' : fa(t.until_minutes) + ' دقیقه'}: ${t.type === 'fixed' ? money(t.adult, 'IRR') : fa(t.adult / 100) + '٪'}`).join(' | ')}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}/>;
}

function Baggage() {
  return <Crud path="/commerce/baggage-rules" title="بار مجاز" blank={{airline_code: '', cabin: 'economy', scope: 'any', adult_kg: 20, child_kg: 20, infant_kg: 10, pieces: 1, hand_kg: 5, status: 'active'}}
    toPayload={v => ({...v, fare_class: v.fare_class || null})}
    fields={[{key: 'airline_code', label: 'کد ایرلاین', required: true}, {key: 'cabin', label: 'کابین', type: 'select', options: [['economy', 'اکونومی'], ['premium', 'پریمیوم'], ['business', 'بیزینس'], ['first', 'فرست']]}, {key: 'fare_class', label: 'کلاس نرخی'}, {key: 'scope', label: 'محدوده', type: 'select', options: SCOPE},
      {key: 'adult_kg', label: 'بزرگسال (کیلو)', type: 'number'}, {key: 'child_kg', label: 'کودک', type: 'number'}, {key: 'infant_kg', label: 'نوزاد', type: 'number'}, {key: 'pieces', label: 'تعداد چمدان', type: 'number'}, {key: 'hand_kg', label: 'بار دستی', type: 'number'}, {key: 'status', label: 'وضعیت', type: 'select', options: STATUS}, {key: 'note', label: 'توضیح', type: 'textarea', wide: true}]}
    cols={[{label: 'ایرلاین', cell: r => <span dir="ltr">{r.airline_code}</span>}, {label: 'کابین', cell: r => r.cabin}, {label: 'کلاس', cell: r => r.fare_class || 'همه'}, {label: 'بزرگسال/کودک/نوزاد', cell: r => `${fa(r.adult_kg)} / ${fa(r.child_kg)} / ${fa(r.infant_kg)} کیلو`}, {label: 'چمدان', cell: r => fa(r.pieces)}, {label: 'دستی', cell: r => `${fa(r.hand_kg)} کیلو`}]}/>;
}

function Rates() {
  const {state, reload, api} = useLoad<{current: Row[]; history: Row[]}>('/commerce/currency-rates');
  const [v, setV] = useState<Row>({from_currency: 'USD', to_currency: 'IRR', rate: '', display_on_sale: true}); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function save(e: FormEvent) {e.preventDefault(); try {await api.post('/commerce/currency-rates', v); setMsg({ok: true, text: 'نرخ ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="نرخ ارز">
    <form className="pn-form" onSubmit={save}><FormFields value={v} set={setV} fields={[{key: 'from_currency', label: 'ارز', type: 'select', options: [['USD', 'دلار'], ['EUR', 'یورو'], ['AED', 'درهم'], ['TRY', 'لیر'], ['IQD', 'دینار عراق'], ['GBP', 'پوند'], ['CNY', 'یوان'], ['RUB', 'روبل'], ['GEL', 'لاری'], ['AMD', 'درام'], ['THB', 'بات']]}, {key: 'rate', label: 'نرخ به ریال', required: true}, {key: 'display_on_sale', label: 'نمایش در فروش', type: 'bool'}]}/><button className="pn-btn">ثبت نرخ</button></form>
    <Note msg={msg}/>
    <Async state={state}>{d => <Table rows={d.current} rowKey={r => r.id} empty="نرخی ثبت نشده است." cols={[{label: 'ارز', cell: r => r.from_currency}, {label: 'نرخ (ریال)', cell: r => fa(Number(r.rate))}, {label: 'نمایش در فروش', cell: r => r.display_on_sale ? 'بله' : 'خیر'}, {label: 'زمان ثبت', cell: r => dateFa(r.created_at)}]}/>}</Async>
  </Card>;
}

export function AdminCommerce() {
  return <Tabs tabs={[['مارک‌آپ و تخفیف', <Markups key="m"/>], ['آزمایش قیمت', <Preview key="p"/>], ['گروه‌های کاربری', <Groups key="g"/>], ['جریمه‌ی کنسلی', <Penalties key="pe"/>], ['بار مجاز', <Baggage key="b"/>], ['نرخ ارز', <Rates key="r"/>]]}/>;
}

/* ------------------------------------------------------------------ finance: treasury */
function Book() {
  const [f, setF] = useState<Row>({}); const [applied, setApplied] = useState('');
  const {state, reload, api} = useLoad<{items: Row[]; total: number; totals: Row}>(`/commerce/treasury?limit=200${applied}`);
  const [add, setAdd] = useState<Row | null>(null); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  const filter = (e: FormEvent) => {e.preventDefault(); setApplied(Object.entries(f).filter(([, v]) => v).map(([k, v]) => `&${k}=${encodeURIComponent(String(v))}`).join(''));};
  async function post(e: FormEvent) {e.preventDefault(); try {await api.post('/commerce/treasury', {...add, debit: add!.debit || 0, credit: add!.credit || 0}); setAdd(null); setMsg({ok: true, text: 'سند ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  async function reverse(r: Row) {const note = window.prompt('علت برگشت سند؟'); if (note === null) return; try {await api.post(`/commerce/treasury/${r.id}/reverse`, {approve: true, note}); setMsg({ok: true, text: 'سند برگشتی ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="دفتر صندوق" action={<button className="pn-btn" onClick={() => setAdd({counterparty_type: 'user', account_type: 'bank', operation: 'deposit', currency: 'IRR'})}>ثبت سند</button>}>
    <form className="pn-form" onSubmit={filter}><FormFields value={f} set={setF} fields={[{key: 'date_from', label: 'از تاریخ', type: 'date'}, {key: 'date_to', label: 'تا تاریخ', type: 'date'}, {key: 'counterparty_type', label: 'طرف حساب', type: 'select', options: [['', 'همه'], ...PARTY]}, {key: 'counterparty_ref', label: 'شناسه طرف حساب'},
      {key: 'account_type', label: 'نوع حساب', type: 'select', options: [['', 'همه'], ...ACCOUNT]}, {key: 'operation', label: 'نحوه عملیات', type: 'select', options: [['', 'همه'], ...OPERATION]}, {key: 'q', label: 'جستجو', hint: 'پیگیری، قرارداد، شرح'}]}/><button className="pn-btn">جستجو</button></form>
    <Note msg={msg}/>
    {add && <form className="pn-form" onSubmit={post} style={{margin: '12px 0', padding: 12, border: '1px dashed #d9cdc0', borderRadius: 14}}>
      <FormFields value={add} set={setAdd} fields={[{key: 'counterparty_type', label: 'نوع طرف حساب', type: 'select', options: PARTY}, {key: 'counterparty_ref', label: 'شناسه طرف حساب', required: true}, {key: 'counterparty_name', label: 'نام طرف حساب'},
        {key: 'account_type', label: 'نوع حساب', type: 'select', options: ACCOUNT}, {key: 'operation', label: 'نحوه عملیات', type: 'select', options: OPERATION}, {key: 'debit', label: 'بدهکار (ریال)', type: 'money'}, {key: 'credit', label: 'بستانکار (ریال)', type: 'money'},
        {key: 'bank_name', label: 'بانک'}, {key: 'tracking_no', label: 'شماره پیگیری'}, {key: 'contract_ref', label: 'شماره قرارداد/رزرو'}, {key: 'purchase_ref', label: 'شماره خرید'}, {key: 'operation_date', label: 'تاریخ عملیات', type: 'date'}, {key: 'description', label: 'شرح', type: 'textarea', wide: true}]}/>
      <span style={{display: 'flex', gap: 8}}><button className="pn-btn">ثبت سند</button><button type="button" className="pn-btn ghost" onClick={() => setAdd(null)}>انصراف</button></span></form>}
    <Async state={state}>{d => <>
      <Stats items={[{label: 'جمع بدهکار', value: money(d.totals.debit, 'IRR')}, {label: 'جمع بستانکار', value: money(d.totals.credit, 'IRR')}, {label: 'مانده', value: money(d.totals.balance, 'IRR')}, {label: 'تعداد سند', value: fa(d.total)}]}/>
      <Table rows={d.items} rowKey={r => r.id} empty="سندی یافت نشد." cols={[{label: 'تاریخ', cell: r => dateFa(r.operation_date)}, {label: 'طرف حساب', cell: r => `${label(PARTY, r.counterparty_type)} ${r.counterparty_name || r.counterparty_ref}`},
        {label: 'حساب', cell: r => label(ACCOUNT, r.account_type)}, {label: 'عملیات', cell: r => label(OPERATION, r.operation)}, {label: 'بدهکار', cell: r => r.debit ? money(r.debit, r.currency) : '—'}, {label: 'بستانکار', cell: r => r.credit ? money(r.credit, r.currency) : '—'},
        {label: 'مانده در خط', cell: r => money(r.balance, 'IRR')}, {label: 'پیگیری/قرارداد', cell: r => [r.tracking_no, r.contract_ref].filter(Boolean).join(' / ') || '—'}, {label: 'شرح', cell: r => r.description || '—'},
        {label: '', cell: r => r.reversal_of_id ? <small>برگشتی</small> : <button className="pn-btn ghost" onClick={() => reverse(r)}>برگشت</button>}]}/></>}</Async>
  </Card>;
}

function Subsidiary() {
  const [t, setT] = useState('');
  const {state} = useLoad<{items: Row[]; totals: Row}>(`/commerce/subsidiary${t ? `?counterparty_type=${t}` : ''}`);
  return <Card title="بدهکاران و بستانکاران" action={<select value={t} onChange={e => setT(e.target.value)} aria-label="نوع طرف حساب"><option value="">همه</option>{PARTY.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>}>
    <Async state={state}>{d => <><Stats items={[{label: 'جمع بدهکار', value: money(d.totals.debtor, 'IRR')}, {label: 'جمع بستانکار', value: money(d.totals.creditor, 'IRR')}]}/>
      <Table rows={d.items} rowKey={r => `${r.counterparty_type}:${r.counterparty_ref}`} empty="حسابی ثبت نشده است." cols={[{label: 'نوع', cell: r => label(PARTY, r.counterparty_type)}, {label: 'طرف حساب', cell: r => r.name || r.counterparty_ref},
        {label: 'بدهکار', cell: r => money(r.debtor, 'IRR')}, {label: 'بستانکار', cell: r => money(r.creditor, 'IRR')}, {label: 'مانده', cell: r => <b style={{color: r.remaining < 0 ? '#b3261e' : undefined}}>{money(r.remaining, 'IRR')}{r.remaining < 0 ? ' (بدهکار)' : r.remaining > 0 ? ' (بستانکار)' : ''}</b>}]}/></>}</Async>
  </Card>;
}

function Requests() {
  const [status, setStatus] = useState('submitted');
  const {state, reload, api} = useLoad<{items: Row[]}>(`/commerce/treasury-requests?status=${status}`); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function decide(r: Row, approve: boolean) {const note = window.prompt(approve ? 'توضیح تأیید (اختیاری)' : 'علت رد درخواست'); if (note === null) return; try {await api.post(`/commerce/treasury-requests/${r.id}/decide`, {approve, note}); setMsg({ok: true, text: approve ? 'تأیید و در کیف پول ثبت شد.' : 'درخواست رد شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="درخواست‌های واریز و برداشت" action={<select value={status} onChange={e => setStatus(e.target.value)} aria-label="وضعیت"><option value="submitted">در انتظار بررسی</option><option value="approved">تأییدشده</option><option value="rejected">ردشده</option></select>}>
    <Note msg={msg}/>
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="درخواستی نیست." cols={[{label: 'کاربر', cell: r => `${r.user_name} (${fa(r.user_id)})`}, {label: 'نوع', cell: r => r.request_type === 'deposit' ? 'واریز' : 'برداشت'}, {label: 'مبلغ', cell: r => money(r.amount, r.currency)},
      {label: 'بانک / پیگیری', cell: r => [r.bank_name, r.tracking_no].filter(Boolean).join(' / ') || '—'}, {label: 'تاریخ پرداخت', cell: r => dateFa(r.paid_on)}, {label: 'یادداشت', cell: r => r.note || '—'}, {label: 'ثبت', cell: r => dateFa(r.created_at)},
      {label: '', cell: r => r.status === 'submitted' ? <span style={{display: 'flex', gap: 6}}><button className="pn-btn" onClick={() => decide(r, true)}>تأیید</button><button className="pn-btn ghost" onClick={() => decide(r, false)}>رد</button></span> : <Badge status={r.status}/>}]}/>}</Async>
  </Card>;
}

function UserAccount() {
  const [q, setQ] = useState(''); const [search, setSearch] = useState(''); const [uid, setUid] = useState<number | null>(null);
  const found = useLoad<{items: Row[]}>(search ? `/commerce/users?q=${encodeURIComponent(search)}` : null);
  const acct = useLoad<Row>(uid ? `/commerce/users/${uid}/account` : null);
  const [adj, setAdj] = useState<Row>({target: 'wallet', direction: 'increase'}); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function apply(e: FormEvent) {e.preventDefault(); try {await acct.api.post(`/commerce/users/${uid}/adjust`, adj); setMsg({ok: true, text: 'ثبت شد.'}); setAdj({target: adj.target, direction: adj.direction}); acct.reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="حساب کاربر (کیف پول و اعتبار)">
    <form className="pn-form" onSubmit={e => {e.preventDefault(); setSearch(q.trim());}}><label>نام، ایمیل، موبایل یا شناسه<input value={q} onChange={e => setQ(e.target.value)}/></label><button className="pn-btn">جستجو</button></form>
    {search && <Async state={found.state}>{d => d.items.length ? <div className="pn-chips" style={{margin: '10px 0'}}>{d.items.map(u => <button key={u.id} onClick={() => setUid(u.id)}>{u.name} — {fa(u.id)}</button>)}</div> : <Empty>کاربری پیدا نشد.</Empty>}</Async>}
    {uid && <Async state={acct.state}>{d => <>
      <p className="pn-muted">لطفاً از درستی کاربر انتخاب‌شده مطمئن شوید و سپس تغییر را ثبت کنید. کاربر: <b>{d.user.name}</b> ({d.user.email}) {d.group && <>— گروه: {d.group.name}</>}</p>
      <Stats items={[{label: 'کیف پول — آزاد', value: money(d.wallet.available, 'IRR')}, {label: 'کیف پول — رزروشده', value: money(d.wallet.reserved, 'IRR')}, {label: 'سقف اعتبار', value: money(d.credit.limit_amount, 'IRR')}, {label: 'اعتبار آزاد', value: money(d.credit.available, 'IRR')}]}/>
      {d.bank_account && <p className="pn-muted">حساب بانکی: {d.bank_account.holder_name} — کارت ****{d.bank_account.card_last4 ?? '—'} {d.bank_account.card_bank ?? ''} — شبا <span dir="ltr">{d.bank_account.sheba ?? '—'}</span></p>}
      <form className="pn-form" onSubmit={apply} style={{margin: '12px 0'}}><FormFields value={adj} set={setAdj} fields={[{key: 'target', label: 'حساب', type: 'select', options: [['wallet', 'کیف پول'], ['credit', 'سقف اعتبار']]}, {key: 'direction', label: 'عملیات', type: 'select', options: [['increase', 'افزایش'], ['decrease', 'کاهش']]},
        {key: 'amount', label: 'مبلغ (ریال)', type: 'money', required: true}, {key: 'bank_name', label: 'بانک'}, {key: 'tracking_no', label: 'شماره پیگیری'}, {key: 'description', label: 'شرح', required: true, wide: true}]}/><button className="pn-btn">ثبت</button></form>
      <Note msg={msg}/>
      <Table rows={d.statement} rowKey={(r: Row) => r.id} empty="تراکنشی ثبت نشده است." cols={[{label: 'تاریخ', cell: (r: Row) => dateFa(r.operation_date)}, {label: 'حساب', cell: (r: Row) => label(ACCOUNT, r.account_type)}, {label: 'عملیات', cell: (r: Row) => label(OPERATION, r.operation)},
        {label: 'بدهکار', cell: (r: Row) => r.debit ? money(r.debit, 'IRR') : '—'}, {label: 'بستانکار', cell: (r: Row) => r.credit ? money(r.credit, 'IRR') : '—'}, {label: 'مانده', cell: (r: Row) => money(r.balance, 'IRR')}, {label: 'شرح', cell: (r: Row) => r.description || '—'}]}/>
    </>}</Async>}
  </Card>;
}

export function FinanceTreasury() {
  return <Tabs tabs={[['دفتر صندوق', <Book key="b"/>], ['بدهکار / بستانکار', <Subsidiary key="s"/>], ['درخواست‌های صندوق', <Requests key="r"/>], ['حساب کاربر', <UserAccount key="u"/>]]}/>;
}

/* ------------------------------------------------------------------ customer */
export function CustomerTreasuryRequests() {
  const {state, reload, api} = useLoad<{items: Row[]}>('/me/treasury-requests');
  const [v, setV] = useState<Row>({request_type: 'deposit'}); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function send(e: FormEvent) {e.preventDefault(); try {await api.post('/me/treasury-requests', {...v, paid_on: v.paid_on || null}); setMsg({ok: true, text: 'درخواست ثبت شد و پس از بررسی واحد مالی در کیف پول اعمال می‌شود.'}); setV({request_type: v.request_type}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="شارژ یا برداشت از کیف پول (واریز بانکی)">
    <p className="pn-muted">اگر مبلغی را کارت‌به‌کارت یا با واریز بانکی پرداخت کرده‌اید، مشخصات آن را ثبت کنید. برداشت به شماره شبای ثبت‌شده در پروفایل انجام می‌شود.</p>
    <form className="pn-form" onSubmit={send}><FormFields value={v} set={setV} fields={[{key: 'request_type', label: 'نوع', type: 'select', options: [['deposit', 'واریز به کیف پول'], ['withdrawal', 'برداشت از کیف پول']]}, {key: 'amount', label: 'مبلغ (ریال)', type: 'money', required: true},
      {key: 'bank_name', label: 'بانک'}, {key: 'tracking_no', label: 'شماره پیگیری'}, {key: 'paid_on', label: 'تاریخ پرداخت', type: 'date'}, {key: 'note', label: 'توضیح', wide: true}]}/><button className="pn-btn">ثبت درخواست</button></form>
    <Note msg={msg}/>
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="درخواستی ثبت نکرده‌اید." cols={[{label: 'نوع', cell: r => r.request_type === 'deposit' ? 'واریز' : 'برداشت'}, {label: 'مبلغ', cell: r => money(r.amount, r.currency)}, {label: 'پیگیری', cell: r => r.tracking_no || '—'}, {label: 'ثبت', cell: r => dateFa(r.created_at)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}, {label: 'پاسخ', cell: r => r.decision_note || '—'}]}/>}</Async>
  </Card>;
}

export function CustomerBankAccount() {
  const {state, reload, api} = useLoad<{bank_account: Row | null}>('/me/bank-account');
  const [v, setV] = useState<Row>({}); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function save(e: FormEvent) {e.preventDefault(); try {await api.put('/me/bank-account', {holder_name: v.holder_name, card_number: v.card_number || null, sheba: v.sheba || null}); setMsg({ok: true, text: 'حساب بانکی ذخیره شد.'}); setV({}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="حساب بانکی برای استرداد وجه">
    <Async state={state}>{d => d.bank_account ? <p className="pn-muted">ثبت‌شده: {d.bank_account.holder_name} — کارت ****{d.bank_account.card_last4 ?? '—'} {d.bank_account.card_bank ?? ''} — شبا <span dir="ltr">{d.bank_account.sheba ?? '—'}</span> {d.bank_account.sheba_bank ? `(${d.bank_account.sheba_bank})` : ''}</p> : <p className="pn-muted">هنوز حساب بانکی ثبت نکرده‌اید.</p>}</Async>
    <form className="pn-form" onSubmit={save}><FormFields value={v} set={setV} fields={[{key: 'holder_name', label: 'نام صاحب حساب', required: true}, {key: 'card_number', label: 'شماره کارت', hint: '۱۶ رقم'}, {key: 'sheba', label: 'شماره شبا', hint: 'IR و ۲۴ رقم'}]}/><button className="pn-btn">ذخیره</button></form>
    <Note msg={msg}/>
  </Card>;
}

