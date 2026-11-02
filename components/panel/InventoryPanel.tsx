'use client';
/* Own inventory: flight routes, flight series (declaration), dated flights with capacity/manifest,
   suppliers, contract templates, and the sales report. Data only from /inventory/* and /commerce/reports/*. */
import {useState, type FormEvent} from 'react';
import {Async, Badge, Card, Stats, Table, dateFa, errorOf, fa, money, serviceFa, useLoad} from './PanelKit';
import {Crud, FormFields, Note, Tabs, type Field, type Opt, type Row} from './CommercePanel';

const DAYS: [string, string][] = [['5', 'شنبه'], ['6', 'یکشنبه'], ['0', 'دوشنبه'], ['1', 'سه‌شنبه'], ['2', 'چهارشنبه'], ['3', 'پنج‌شنبه'], ['4', 'جمعه']];
const timeFa = (iso: string) => new Date(iso).toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tehran'});

function useOptions(path: string, map: (r: Row) => [string, string]): Opt {
  const {state} = useLoad<{items: Row[]}>(path);
  return state.kind === 'ready' ? state.data.items.map(map) : [];
}

function Routes() {
  return <Crud path="/inventory/routes" title="مسیرهای پرواز" blank={{origin: '', destination: '', origin_city: '', destination_city: '', scope: 'domestic', status: 'active'}}
    fields={[{key: 'origin', label: 'مبدأ (IATA)', required: true}, {key: 'origin_city', label: 'شهر مبدأ'}, {key: 'destination', label: 'مقصد (IATA)', required: true}, {key: 'destination_city', label: 'شهر مقصد'},
      {key: 'scope', label: 'نوع', type: 'select', options: [['domestic', 'داخلی'], ['international', 'خارجی']]}, {key: 'status', label: 'وضعیت', type: 'select', options: [['active', 'فعال'], ['disabled', 'غیرفعال']]}]}
    cols={[{label: 'مسیر', cell: r => <span dir="ltr">{r.origin} → {r.destination}</span>}, {label: 'شهرها', cell: r => `${r.origin_city || '—'} به ${r.destination_city || '—'}`}, {label: 'نوع', cell: r => r.scope === 'domestic' ? 'داخلی' : 'خارجی'}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}/>;
}

function Suppliers() {
  const {state, reload, api} = useLoad<{items: Row[]}>('/inventory/suppliers');
  const [v, setV] = useState<Row>({supplier_type: 'charterer'}); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function add(e: FormEvent) {e.preventDefault(); try {await api.post('/inventory/suppliers', v); setV({supplier_type: v.supplier_type}); setMsg({ok: true, text: 'تأمین‌کننده ثبت شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="تأمین‌کنندگان">
    <form className="pn-form" onSubmit={add}><FormFields value={v} set={setV} fields={[{key: 'name', label: 'نام', required: true}, {key: 'supplier_type', label: 'نوع', type: 'select', options: [['charterer', 'چارترکننده'], ['airline', 'ایرلاین'], ['hotel', 'هتل'], ['tour_operator', 'تورگردان'], ['transport', 'حمل‌ونقل'], ['other', 'سایر']]}]}/><button className="pn-btn">افزودن</button></form>
    <Note msg={msg}/>
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="تأمین‌کننده‌ای ثبت نشده است." cols={[{label: 'نام', cell: r => r.name}, {label: 'نوع', cell: r => r.type}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}/>}</Async>
  </Card>;
}

function ScheduleEditor({value, set}: {value: Row; set: (v: Row) => void}) {
  const sched: Row = value.schedule || {};
  const put = (k: string, slot: Row | null) => {const n = {...sched}; if (slot) n[k] = slot; else delete n[k]; set({...value, schedule: n});};
  return <fieldset style={{flexBasis: '100%', border: '1px solid #e6dccf', borderRadius: 12, padding: 10}}><legend>برنامه‌ی هفتگی (ساعت حرکت به وقت تهران و مدت پرواز به دقیقه)</legend>
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(170px,1fr))', gap: 8}}>{DAYS.map(([k, l]) => {const s = sched[k]; return <div key={k} style={{display: 'grid', gap: 4}}>
      <label style={{display: 'flex', gap: 6, alignItems: 'center'}}><input type="checkbox" checked={!!s} onChange={e => put(k, e.target.checked ? {time: '08:00', duration: 60} : null)}/>{l}</label>
      {s && <span style={{display: 'flex', gap: 4}}><input aria-label={`ساعت ${l}`} type="time" value={s.time} onChange={e => put(k, {...s, time: e.target.value})} dir="ltr"/><input aria-label={`مدت ${l}`} inputMode="numeric" value={s.duration} onChange={e => put(k, {...s, duration: Number(e.target.value.replace(/\D/g, '')) || 0})} style={{width: 64}}/></span>}
    </div>;})}</div></fieldset>;
}

function Series() {
  const routes = useOptions('/inventory/routes', r => [r.id, `${r.origin} → ${r.destination}`]);
  const suppliers = useOptions('/inventory/suppliers', r => [r.id, r.name]);
  const {state, reload, api} = useLoad<{items: Row[]}>('/inventory/flight-series');
  const [edit, setEdit] = useState<Row | null>(null); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  const fields: Field[] = [{key: 'route_id', label: 'مسیر', type: 'select', options: [['', '—'], ...routes]}, {key: 'supplier_id', label: 'تأمین‌کننده', type: 'select', options: [['', '—'], ...suppliers]},
    {key: 'airline_code', label: 'کد ایرلاین', required: true}, {key: 'airline_name', label: 'نام ایرلاین'}, {key: 'flight_number', label: 'شماره پرواز', required: true}, {key: 'aircraft', label: 'هواپیما'},
    {key: 'flight_type', label: 'نوع', type: 'select', options: [['charter', 'چارتری'], ['system', 'سیستمی']]}, {key: 'cabin', label: 'کابین', type: 'select', options: [['economy', 'اکونومی'], ['business', 'بیزینس'], ['premium', 'پریمیوم'], ['first', 'فرست']]}, {key: 'fare_class', label: 'کلاس نرخی'},
    {key: 'date_from', label: 'از تاریخ', type: 'date', required: true}, {key: 'date_to', label: 'تا تاریخ', type: 'date', required: true}, {key: 'capacity', label: 'ظرفیت هر پرواز', type: 'number', required: true},
    {key: 'adult_fare', label: 'نرخ خالص بزرگسال (ریال)', type: 'money', required: true}, {key: 'child_fare', label: 'نرخ کودک', type: 'money'}, {key: 'infant_fare', label: 'نرخ نوزاد', type: 'money'}, {key: 'baggage_kg', label: 'بار (کیلو)', type: 'number'},
    {key: 'stop_sale_minutes', label: 'توقف فروش (دقیقه قبل از پرواز)', type: 'number'}, {key: 'send_list_minutes', label: 'ارسال لیست به ایرلاین (دقیقه قبل)', type: 'number'}, {key: 'stop_quota_minutes', label: 'توقف سهمیه (دقیقه قبل)', type: 'number'},
    {key: 'penalty_code', label: 'کد جریمه کنسلی'}, {key: 'refundable', label: 'قابل استرداد', type: 'bool'}, {key: 'status', label: 'وضعیت', type: 'select', options: [['active', 'فعال'], ['disabled', 'غیرفعال']]}, {key: 'description', label: 'توضیحات', type: 'textarea', wide: true}];
  async function save(e: FormEvent) {
    e.preventDefault(); if (!edit) return; const {id, ...b} = edit;
    try {const body = {...b, child_fare: b.child_fare || 0, infant_fare: b.infant_fare || 0, penalty_code: b.penalty_code || null}; id ? await api.put(`/inventory/flight-series/${id}`, body) : await api.post('/inventory/flight-series', body); setEdit(null); setMsg({ok: true, text: 'ذخیره شد. برای انتشار پروازها «ساخت پروازها» را بزنید.'}); reload();}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  async function generate(r: Row) {try {const g = await api.post<Row>(`/inventory/flight-series/${r.id}/generate`, {}); setMsg({ok: true, text: `${fa(g.created)} پرواز جدید ساخته و ${fa(g.updated)} پرواز به‌روز شد.`});} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <Card title="تعریف پرواز" action={<button className="pn-btn" onClick={() => setEdit({flight_type: 'charter', cabin: 'economy', capacity: 0, baggage_kg: 20, stop_sale_minutes: 120, send_list_minutes: 360, stop_quota_minutes: 1440, refundable: true, status: 'active', schedule: {}})}>تعریف پرواز جدید</button>}>
    <Note msg={msg}/>
    {edit && <form className="pn-form" onSubmit={save} style={{marginBottom: 16, padding: 12, border: '1px dashed #d9cdc0', borderRadius: 14}}>
      <FormFields fields={fields} value={edit} set={setEdit}/><ScheduleEditor value={edit} set={setEdit}/>
      <span style={{display: 'flex', gap: 8}}><button className="pn-btn">ثبت</button><button type="button" className="pn-btn ghost" onClick={() => setEdit(null)}>انصراف</button></span></form>}
    <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="پروازی تعریف نشده است." cols={[{label: 'پرواز', cell: r => <span dir="ltr">{r.airline_code}{r.flight_number}</span>}, {label: 'مسیر', cell: r => routes.find(x => x[0] === r.route_id)?.[1] ?? '—'},
      {label: 'بازه', cell: r => `${dateFa(r.date_from)} تا ${dateFa(r.date_to)}`}, {label: 'روزها', cell: r => DAYS.filter(([k]) => r.schedule[k]).map(([k, l]) => `${l} ${r.schedule[k].time}`).join('، ')},
      {label: 'ظرفیت', cell: r => fa(r.capacity)}, {label: 'نرخ بزرگسال', cell: r => money(r.adult_fare, r.currency)}, {label: 'نوع', cell: r => r.flight_type === 'charter' ? 'چارتری' : 'سیستمی'}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>},
      {label: '', cell: r => <span style={{display: 'flex', gap: 6}}><button className="pn-btn ghost" onClick={() => setEdit({...r})}>ویرایش</button><button className="pn-btn" onClick={() => generate(r)}>ساخت پروازها</button></span>}]}/>}</Async>
  </Card>;
}

function Manifest({id, onClose}: {id: string; onClose: () => void}) {
  const {state} = useLoad<Row>(`/inventory/flights/${id}/manifest`);
  return <Card title="لیست مسافران (مانیفست)" action={<span style={{display: 'flex', gap: 6}}><button className="pn-btn ghost" onClick={() => window.print()}>چاپ</button><button className="pn-btn ghost" onClick={onClose}>بستن</button></span>}>
    <Async state={state}>{d => <><p className="pn-muted">پرواز <b dir="ltr">{d.flight.flight}</b> — {d.flight.route_name} — {dateFa(d.flight.departure_at)} ساعت {timeFa(d.flight.departure_at)} — صندلی رزروشده: {fa(d.seats_booked)}</p>
      <Table rows={d.passengers} rowKey={(r: Row) => r.reservation_id} empty="هنوز مسافری ثبت نشده است." cols={[{label: 'کد رزرو', cell: (r: Row) => <span dir="ltr">{r.booking_reference}</span>}, {label: 'خریدار', cell: (r: Row) => r.buyer},
        {label: 'مسافران', cell: (r: Row) => r.travellers.join('، ') || '—'}, {label: 'صندلی', cell: (r: Row) => fa(r.seats)}, {label: 'وضعیت', cell: (r: Row) => <Badge status={r.status}/>}]}/></>}</Async>
  </Card>;
}

function Flights() {
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState<Row>({date_from: today}); const [q, setQ] = useState(`?date_from=${today}`);
  const routes = useOptions('/inventory/routes', r => [r.id, `${r.origin} → ${r.destination}`]);
  const {state, reload, api} = useLoad<{items: Row[]; totals: Row}>(`/inventory/flights${q}`);
  const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null); const [man, setMan] = useState<string | null>(null);
  async function upd(r: Row, body: Row) {try {await api.put(`/inventory/flights/${r.id}`, body); setMsg({ok: true, text: 'به‌روز شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <>
    <Card title="پروازهای تاریخ‌دار">
      <form className="pn-form" onSubmit={e => {e.preventDefault(); setQ('?' + Object.entries(f).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&'));}}>
        <FormFields value={f} set={setF} fields={[{key: 'date_from', label: 'از تاریخ', type: 'date'}, {key: 'date_to', label: 'تا تاریخ', type: 'date'}, {key: 'route_id', label: 'مسیر', type: 'select', options: [['', 'همه'], ...routes]}]}/><button className="pn-btn">نمایش</button></form>
      <Note msg={msg}/>
      <Async state={state}>{d => <><Stats items={[{label: 'تعداد پرواز', value: fa(d.items.length)}, {label: 'کل ظرفیت', value: fa(d.totals.capacity)}, {label: 'فروخته‌شده', value: fa(d.totals.sold)}, {label: 'ضریب اشغال', value: d.totals.capacity ? `${fa(Math.round(100 * d.totals.sold / d.totals.capacity))}٪` : '—'}]}/>
        <Table rows={d.items} rowKey={r => r.id} empty="پروازی در این بازه نیست." cols={[{label: 'تاریخ و ساعت', cell: r => `${dateFa(r.departure_at)} ${timeFa(r.departure_at)}`}, {label: 'پرواز', cell: r => <span dir="ltr">{r.flight}</span>}, {label: 'مسیر', cell: r => r.route_name},
          {label: 'ظرفیت / فروش / مانده', cell: r => `${fa(r.capacity)} / ${fa(r.sold)} / ${fa(r.remaining)}`}, {label: 'نرخ', cell: r => money(r.adult_fare, r.currency)},
          {label: 'وضعیت', cell: r => <span>{r.status === 'open' ? (r.sale_open ? 'در حال فروش' : 'توقف فروش') : r.status === 'closed' ? 'بسته' : 'لغو'}{r.list_due && <b style={{color: '#b3261e'}}> — ارسال لیست!</b>}{r.list_sent_at && <small> — لیست ارسال شد</small>}</span>},
          {label: '', cell: r => <span style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}>
            <button className="pn-btn ghost" onClick={() => {const c = window.prompt('ظرفیت جدید', String(r.capacity)); if (c) upd(r, {capacity: Number(c)});}}>ظرفیت</button>
            {r.status === 'open' ? <button className="pn-btn ghost" onClick={() => upd(r, {status: 'closed'})}>بستن فروش</button> : r.status === 'closed' ? <button className="pn-btn ghost" onClick={() => upd(r, {status: 'open'})}>باز کردن</button> : null}
            <button className="pn-btn ghost" onClick={() => setMan(r.id)}>مانیفست</button>
            {!r.list_sent_at && <button className="pn-btn ghost" onClick={() => upd(r, {mark_list_sent: true})}>لیست ارسال شد</button>}</span>}]}/></>}</Async>
    </Card>
    {man && <Manifest id={man} onClose={() => setMan(null)}/>}
  </>;
}

function Templates() {
  const {state} = useLoad<{placeholders: string[]}>('/inventory/contract-templates');
  return <>
    <Crud path="/inventory/contract-templates" title="مفاد قراردادها" blank={{service_type: 'any', title: '', body: 'اینجانب {{customer_name}} خرید خدمت {{service}} ({{title}}) با کد رزرو {{booking_reference}} به مبلغ {{amount}} {{currency}} را در تاریخ {{booking_date}} برای {{travellers}} می‌پذیرم.\nقوانین استرداد: {{policy}}', status: 'active'}}
      fields={[{key: 'service_type', label: 'خدمت', type: 'select', options: [['any', 'همه خدمات'], ['flight', 'پرواز'], ['hotel', 'هتل'], ['tour', 'تور'], ['train', 'قطار'], ['visa', 'ویزا'], ['insurance', 'بیمه'], ['package', 'پرواز + هتل']]}, {key: 'title', label: 'عنوان', required: true},
        {key: 'status', label: 'وضعیت', type: 'select', options: [['active', 'فعال'], ['disabled', 'غیرفعال']]}, {key: 'body', label: 'متن قرارداد', type: 'textarea', wide: true}]}
      cols={[{label: 'عنوان', cell: r => r.title}, {label: 'خدمت', cell: r => r.service_type === 'any' ? 'همه' : serviceFa(r.service_type)}, {label: 'نسخه', cell: r => fa(r.version)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}/>
    <Async state={state}>{d => <p className="pn-muted">جای‌نگهدارهای قابل استفاده: {d.placeholders.map(p => <code key={p} dir="ltr" style={{marginInline: 4}}>{`{{${p}}}`}</code>)}</p>}</Async>
  </>;
}


const BOARD: Opt = [['RO', 'بدون صبحانه'], ['BB', 'با صبحانه'], ['HB', 'نیم‌پانسیون'], ['FB', 'تمام‌پانسیون'], ['AI', 'همه‌چیز رایگان']];

function HotelPicker({onPick}: {onPick: (h: Row) => void}) {
  const [q, setQ] = useState(''); const [s, setS] = useState('');
  const {state} = useLoad<{items: Row[]}>(s ? `/stays/hotels/search?q=${encodeURIComponent(s)}` : null);
  return <div style={{flexBasis: '100%'}}><form className="pn-form" onSubmit={e => {e.preventDefault(); setS(q.trim());}}><label>جستجوی هتل<input value={q} onChange={e => setQ(e.target.value)}/></label><button className="pn-btn ghost">جستجو</button></form>
    {s && <Async state={state}>{d => <div className="pn-chips" style={{marginTop: 6}}>{d.items.map(h => <button type="button" key={h.id} onClick={() => onPick(h)}>{h.name}{h.stars ? ` ${fa(h.stars)}★` : ''}</button>)}</div>}</Async>}</div>;
}

function RoomCalendar({room}: {room: Row}) {
  const today = new Date(); const later = new Date(); later.setDate(today.getDate() + 30);
  const [range, setRange] = useState<Row>({date_from: today.toISOString().slice(0, 10), date_to: later.toISOString().slice(0, 10)});
  const {state, reload, api} = useLoad<{nights: Row[]}>(`/stays/rooms/${room.id}/calendar?date_from=${range.date_from}&date_to=${range.date_to}`);
  const [v, setV] = useState<Row>({weekdays: [0, 1, 2, 3, 4, 5, 6]}); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function apply(e: FormEvent) {
    e.preventDefault(); const body: Row = {date_from: v.date_from || range.date_from, date_to: v.date_to || range.date_to, weekdays: v.weekdays};
    for (const k of ['allotment', 'price', 'single_price', 'extra_bed_price', 'child_price', 'min_stay']) if (v[k] !== undefined && v[k] !== null && v[k] !== '') body[k] = v[k];
    for (const k of ['stop_sell', 'closed_to_arrival']) if (v[k] === 'yes' || v[k] === 'no') body[k] = v[k] === 'yes';
    try {const r = await api.put<Row>(`/stays/rooms/${room.id}/calendar`, body); setMsg({ok: true, text: `${fa(r.nights_updated)} شب به‌روز شد.`}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  const wd = [[5, 'ش'], [6, 'ی'], [0, 'د'], [1, 'س'], [2, 'چ'], [3, 'پ'], [4, 'ج']] as const;
  return <Card title={`تقویم نرخ و ظرفیت — ${room.name}`}>
    <form className="pn-form" onSubmit={apply} style={{padding: 10, border: '1px dashed #d9cdc0', borderRadius: 14}}>
      <FormFields value={v} set={setV} fields={[{key: 'date_from', label: 'از تاریخ', type: 'date'}, {key: 'date_to', label: 'تا تاریخ', type: 'date'}, {key: 'allotment', label: 'ظرفیت (اتاق)', type: 'number'}, {key: 'price', label: 'نرخ هر شب (ریال)', type: 'money', hint: 'ظرفیت پایه'},
        {key: 'single_price', label: 'نرخ یک‌نفره', type: 'money'}, {key: 'extra_bed_price', label: 'تخت اضافه', type: 'money'}, {key: 'child_price', label: 'کودک', type: 'money'}, {key: 'min_stay', label: 'حداقل اقامت', type: 'number'},
        {key: 'stop_sell', label: 'توقف فروش', type: 'select', options: [['', 'بدون تغییر'], ['yes', 'بله'], ['no', 'خیر']]}, {key: 'closed_to_arrival', label: 'بسته برای ورود', type: 'select', options: [['', 'بدون تغییر'], ['yes', 'بله'], ['no', 'خیر']]}]}/>
      <span className="pn-chips" aria-label="روزهای هفته">{wd.map(([k, l]) => <button type="button" key={k} style={v.weekdays.includes(k) ? {background: 'var(--pn-plum, #4b2a4f)', color: '#fff'} : undefined} onClick={() => setV({...v, weekdays: v.weekdays.includes(k) ? v.weekdays.filter((x: number) => x !== k) : [...v.weekdays, k]})}>{l}</button>)}</span>
      <button className="pn-btn">اعمال روی بازه</button></form>
    <Note msg={msg}/>
    <form className="pn-form" style={{marginTop: 10}} onSubmit={e => e.preventDefault()}><FormFields value={range} set={setRange} fields={[{key: 'date_from', label: 'نمایش از', type: 'date'}, {key: 'date_to', label: 'تا', type: 'date'}]}/></form>
    <Async state={state}>{d => <Table rows={d.nights} rowKey={r => r.night} empty="—" cols={[{label: 'شب', cell: r => dateFa(r.night)}, {label: 'ظرفیت', cell: r => fa(r.allotment)}, {label: 'فروش', cell: r => fa(r.sold)}, {label: 'آزاد', cell: r => <b style={{color: r.free <= 0 ? '#b3261e' : undefined}}>{fa(r.free)}</b>},
      {label: 'نرخ', cell: r => r.price ? money(r.price, 'IRR') : '—'}, {label: 'یک‌نفره', cell: r => r.single_price ? money(r.single_price, 'IRR') : '—'}, {label: 'وضعیت', cell: r => [r.stop_sell && 'توقف فروش', r.closed_to_arrival && 'بسته برای ورود', r.min_stay && `حداقل ${fa(r.min_stay)} شب`].filter(Boolean).join('، ') || 'باز'}]}/>}</Async>
  </Card>;
}

function ContractRooms({contract}: {contract: Row}) {
  const [cal, setCal] = useState<Row | null>(null);
  return <>
    <Crud path={`/stays/contracts/${contract.id}/rooms`} title={`اتاق‌های قرارداد «${contract.title}»`} blank={{name: '', board: 'BB', max_adults: 2, max_children: 1, extra_beds: 0, status: 'active'}}
      fields={[{key: 'name', label: 'نام اتاق', required: true}, {key: 'board', label: 'وعده', type: 'select', options: BOARD}, {key: 'max_adults', label: 'ظرفیت پایه (بزرگسال)', type: 'number'}, {key: 'max_children', label: 'حداکثر کودک', type: 'number'}, {key: 'extra_beds', label: 'تخت اضافه', type: 'number'}, {key: 'status', label: 'وضعیت', type: 'select', options: [['active', 'فعال'], ['disabled', 'غیرفعال']]}]}
      cols={[{label: 'اتاق', cell: r => r.name}, {label: 'وعده', cell: r => BOARD.find(b => b[0] === r.board)?.[1]}, {label: 'ظرفیت', cell: r => `${fa(r.max_adults)} بزرگسال + ${fa(r.max_children)} کودک${r.extra_beds ? ` + ${fa(r.extra_beds)} تخت اضافه` : ''}`}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}]}
      extra={r => <button className="pn-btn" onClick={() => setCal(r)}>تقویم نرخ</button>}/>
    {cal && <RoomCalendar key={cal.id} room={cal}/>}
  </>;
}

function HotelContracts() {
  const suppliers = useOptions('/inventory/suppliers', r => [r.id, r.name]);
  const {state, reload, api} = useLoad<{items: Row[]}>('/stays/contracts');
  const [edit, setEdit] = useState<Row | null>(null); const [open, setOpen] = useState<Row | null>(null); const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  async function save(e: FormEvent) {e.preventDefault(); if (!edit) return; const {id, hotel_name, ...b} = edit; void hotel_name;
    try {const body = {...b, penalty_code: b.penalty_code || null}; id ? await api.put(`/stays/contracts/${id}`, body) : await api.post('/stays/contracts', body); setEdit(null); setMsg({ok: true, text: 'قرارداد ذخیره شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}
  return <>
    <Card title="قراردادهای هتل" action={<button className="pn-btn" onClick={() => setEdit({currency: 'IRR', release_days: 0, min_stay: 1, max_stay: 30, refundable: true, child_free_age: 2, child_max_age: 12, status: 'active'})}>قرارداد جدید</button>}>
      <Note msg={msg}/>
      {edit && <form className="pn-form" onSubmit={save} style={{marginBottom: 16, padding: 12, border: '1px dashed #d9cdc0', borderRadius: 14}}>
        {!edit.id && <HotelPicker onPick={h => setEdit({...edit, hotel_id: h.id, hotel_name: h.name})}/>}
        <p className="pn-muted" style={{flexBasis: '100%'}}>هتل: <b>{edit.hotel_name || 'انتخاب نشده'}</b></p>
        <FormFields value={edit} set={setEdit} fields={[{key: 'title', label: 'عنوان قرارداد', required: true}, {key: 'supplier_id', label: 'تأمین‌کننده', type: 'select', options: [['', '—'], ...suppliers]}, {key: 'valid_from', label: 'از تاریخ', type: 'date', required: true}, {key: 'valid_to', label: 'تا تاریخ', type: 'date', required: true},
          {key: 'release_days', label: 'توقف فروش (روز قبل از ورود)', type: 'number'}, {key: 'min_stay', label: 'حداقل شب', type: 'number'}, {key: 'max_stay', label: 'حداکثر شب', type: 'number'}, {key: 'child_free_age', label: 'کودک رایگان تا سن', type: 'number'}, {key: 'child_max_age', label: 'نرخ کودک تا سن', type: 'number'},
          {key: 'refundable', label: 'قابل استرداد', type: 'bool'}, {key: 'penalty_code', label: 'کد جریمه کنسلی'}, {key: 'status', label: 'وضعیت', type: 'select', options: [['active', 'فعال'], ['disabled', 'غیرفعال']]}, {key: 'terms', label: 'شرایط و قوانین هتل', type: 'textarea', wide: true}]}/>
        <span style={{display: 'flex', gap: 8}}><button className="pn-btn">ثبت</button><button type="button" className="pn-btn ghost" onClick={() => setEdit(null)}>انصراف</button></span></form>}
      <Async state={state}>{d => <Table rows={d.items} rowKey={r => r.id} empty="قرارداد هتلی ثبت نشده است." cols={[{label: 'هتل', cell: r => r.hotel_name}, {label: 'عنوان', cell: r => r.title}, {label: 'اعتبار', cell: r => `${dateFa(r.valid_from)} تا ${dateFa(r.valid_to)}`},
        {label: 'شرایط', cell: r => `حداقل ${fa(r.min_stay)} شب · توقف ${fa(r.release_days)} روز قبل`}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>},
        {label: '', cell: r => <span style={{display: 'flex', gap: 6}}><button className="pn-btn ghost" onClick={() => setEdit({...r})}>ویرایش</button><button className="pn-btn" onClick={() => setOpen(r)}>اتاق‌ها و نرخ</button></span>}]}/>}</Async>
    </Card>
    {open && <ContractRooms key={open.id} contract={open}/>}
  </>;
}

export function AdminInventory() {
  return <Tabs tabs={[['پروازها', <Flights key="f"/>], ['قرارداد هتل', <HotelContracts key="h"/>], ['تعریف پرواز', <Series key="s"/>], ['مسیرها', <Routes key="r"/>], ['تأمین‌کنندگان', <Suppliers key="p"/>], ['مفاد قرارداد', <Templates key="t"/>]]}/>;
}

export function SalesReport() {
  const [f, setF] = useState<Row>({}); const [q, setQ] = useState('');
  const {state} = useLoad<{items: Row[]; by_service: Record<string, Row>; total_amount: number}>(`/commerce/reports/sales${q}`);
  return <Card title="گزارش فروش">
    <form className="pn-form" onSubmit={e => {e.preventDefault(); setQ('?' + Object.entries(f).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&'));}}>
      <FormFields value={f} set={setF} fields={[{key: 'date_from', label: 'از تاریخ', type: 'date'}, {key: 'date_to', label: 'تا تاریخ', type: 'date'}, {key: 'service_type', label: 'خدمت', type: 'select', options: [['', 'همه'], ['flight', 'پرواز'], ['hotel', 'هتل'], ['tour', 'تور'], ['train', 'قطار'], ['visa', 'ویزا'], ['flight_hotel', 'پرواز + هتل']]},
        {key: 'status', label: 'وضعیت', type: 'select', options: [['', 'همه'], ['reserved', 'رزرو شده'], ['confirmed', 'قطعی'], ['cancelled', 'لغو شده']]}]}/><button className="pn-btn">گزارش</button></form>
    <Async state={state}>{d => <><Stats items={[{label: 'جمع فروش معتبر', value: money(d.total_amount, 'IRR')}, ...Object.entries(d.by_service).map(([k, v]) => ({label: serviceFa(k), value: money(v.amount, 'IRR'), hint: `${fa(v.count)} رزرو`}))]}/>
      <Table rows={d.items} rowKey={r => r.id} empty="رزروی در این بازه نیست." cols={[{label: 'تاریخ', cell: r => dateFa(r.created_at)}, {label: 'کد رزرو', cell: r => <span dir="ltr">{r.booking_reference || '—'}</span>}, {label: 'خدمت', cell: r => serviceFa(r.service_type)},
        {label: 'خریدار', cell: r => r.buyer}, {label: 'مبلغ', cell: r => money(r.amount, r.currency)}, {label: 'وضعیت', cell: r => <Badge status={r.status}/>}, {label: '', cell: r => <a className="pn-link" href={`/contract/${r.id}`} target="_blank" rel="noopener">قرارداد</a>}]}/></>}</Async>
  </Card>;
}

export function ContractView({reservationId}: {reservationId: string}) {
  const {state} = useLoad<{title: string; html: string; version: number}>(`/reservations/${encodeURIComponent(reservationId)}/contract`);
  return <Async state={state}>{d => <Card title={d.title} action={<button className="pn-btn ghost" onClick={() => window.print()}>چاپ</button>}>
    <div style={{lineHeight: 2.1, fontSize: 15}} dangerouslySetInnerHTML={{__html: d.html}}/>
    <p className="pn-muted" style={{marginTop: 24}}>نسخه‌ی متن قرارداد: {fa(d.version)}</p>
  </Card>}</Async>;
}
