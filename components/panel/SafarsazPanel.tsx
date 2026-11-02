'use client';
/* Safarsaz (سفرساز): build a tour as a draft, pass the publish checklist, publish into the bookable tour catalogue.
   Everything shown comes from /safarsaz/*; nothing is pre-filled with sample data. */
import {useState, type FormEvent} from 'react';
import {Async, Card, Empty, Table, dateFa, errorOf, fa, money, useLoad} from './PanelKit';
import {FormFields, Note, type Opt, type Row} from './CommercePanel';

const SOURCES: Opt = [['manual', 'ورود دستی'], ['supplier_contract', 'قرارداد تأمین‌کننده'], ['charter_block', 'بلوک چارتر'], ['catalog', 'تور مرجع'], ['copy', 'کپی تور قبلی']];
const ROOMS: Opt = [['double', 'دوتخته (پایه)'], ['single', 'یک‌تخته'], ['triple', 'سه‌تخته'], ['extra_bed', 'تخت اضافه']];
const BOARDS: Opt = [['RO', 'بدون صبحانه'], ['BB', 'با صبحانه'], ['HB', 'نیم‌پانسیون'], ['FB', 'فول‌برد'], ['AI', 'همه‌چیز آزاد']];
const STATUS_FA: Record<string, [string, string]> = {draft: ['پیش‌نویس', 'warn'], published: ['منتشرشده', 'ok'], archived: ['بایگانی', '']};
const lines = (s: string) => s.split('\n').map(x => x.trim()).filter(Boolean);
type Msg = {ok: boolean; text: string} | null;

function useSuppliers(): Opt {
  const {state} = useLoad<{items: Row[]}>('/inventory/suppliers');
  return state.kind === 'ready' ? [['', '—'], ...state.data.items.filter(s => s.status === 'active').map(s => [s.id, s.name] as [string, string])] : [['', '—']];
}

function toForm(t?: Row): Row {
  return {title: t?.title ?? '', origin: t?.origin ?? '', destination: t?.destination ?? '', tour_type: t?.tour_type ?? 'leisure', supplier_id: t?.supplier_id ?? '',
    source: t?.source ?? 'manual', source_ref: t?.source_ref ?? '', description: t?.description ?? '', deposit_bps: t?.deposit_bps ?? 0, visa_status: t?.visa_status ?? 'VISA_NOT_REQUIRED',
    itinerary: (t?.itinerary ?? []).map((d: Row) => `${d.title}${d.body ? ` | ${d.body}` : ''}`).join('\n'),
    hotels: (t?.hotels ?? []).map((h: Row) => [h.name, h.city, h.nights, h.board, h.stars ?? ''].join(' | ')).join('\n'),
    inclusions: (t?.inclusions ?? []).join('\n'), exclusions: (t?.exclusions ?? []).join('\n'), documents: (t?.documents ?? []).join('\n'),
    cancellation: (t?.cancellation ?? []).map((c: Row) => `${c.days_before} | ${c.penalty_bps / 100}`).join('\n')};
}

function toPayload(v: Row): Row {
  return {title: v.title, origin: v.origin, destination: v.destination, tour_type: v.tour_type || 'leisure', supplier_id: v.supplier_id || null, source: v.source, source_ref: v.source_ref || null,
    description: v.description ?? '', deposit_bps: v.deposit_bps || 0, visa_status: v.visa_status,
    itinerary: lines(v.itinerary ?? '').map(l => {const [title, ...rest] = l.split('|'); return {title: title.trim(), body: rest.join('|').trim()};}),
    hotels: lines(v.hotels ?? '').map(l => {const [name, city, nights, board, stars] = l.split('|').map(x => x.trim()); return {name, city, nights: Number(nights) || 1, board: board || 'BB', stars: stars ? Number(stars) : null};}),
    inclusions: lines(v.inclusions ?? ''), exclusions: lines(v.exclusions ?? ''), documents: lines(v.documents ?? ''),
    cancellation: lines(v.cancellation ?? '').map(l => {const [days, pct] = l.split('|').map(x => Number(x.trim())); return {days_before: days || 0, penalty_bps: Math.round((pct || 0) * 100)};})};
}

function TourForm({tour, saved}: {tour?: Row; saved: (t: Row) => void}) {
  const {api} = useLoad<unknown>(null);
  const suppliers = useSuppliers();
  const [v, setV] = useState<Row>(toForm(tour)); const [msg, setMsg] = useState<Msg>(null);
  async function submit(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    try {const t = tour ? await api.put<Row>(`/safarsaz/tours/${tour.id}`, toPayload(v)) : await api.post<Row>('/safarsaz/tours', toPayload(v)); setMsg({ok: true, text: 'ذخیره شد.'}); saved(t);}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  return <form className="pn-form" onSubmit={submit}>
    <FormFields value={v} set={setV} fields={[{key: 'title', label: 'عنوان تور', required: true}, {key: 'origin', label: 'مبدأ', required: true}, {key: 'destination', label: 'مقصد', required: true},
      {key: 'supplier_id', label: 'برگزارکننده', type: 'select', options: suppliers}, {key: 'source', label: 'روش ورود', type: 'select', options: SOURCES},
      {key: 'source_ref', label: 'شناسه‌ی منبع', hint: 'برای قرارداد، چارتر و تور مرجع لازم است'}, {key: 'deposit_bps', label: 'بیعانه (درصد)', type: 'percent'},
      {key: 'visa_status', label: 'روادید', type: 'select', options: [['VISA_NOT_REQUIRED', 'لازم نیست'], ['VISA_REQUIRED', 'لازم است'], ['VISA_ON_ARRIVAL', 'فرودگاهی'], ['VISA_STATUS_UNKNOWN', 'نامشخص']]},
      {key: 'description', label: 'معرفی تور', type: 'textarea', wide: true},
      {key: 'itinerary', label: 'برنامه‌ی روزانه', type: 'textarea', wide: true, hint: 'هر روز یک خط: عنوان | شرح'},
      {key: 'hotels', label: 'هتل‌ها', type: 'textarea', wide: true, hint: `هر خط: نام | شهر | شب | سرویس (${BOARDS.map(b => b[0]).join('/')}) | ستاره`},
      {key: 'inclusions', label: 'خدمات شامل', type: 'textarea', hint: 'هر خط یک مورد'}, {key: 'exclusions', label: 'خدمات غیرشامل', type: 'textarea'},
      {key: 'documents', label: 'مدارک لازم', type: 'textarea'}, {key: 'cancellation', label: 'قوانین کنسلی', type: 'textarea', hint: 'هر خط: روز مانده | درصد جریمه'}]}/>
    <button className="pn-btn">{tour ? 'ذخیره‌ی تغییرات' : 'ساخت پیش‌نویس'}</button><Note msg={msg}/>
  </form>;
}

function DepartureForm({tourId, saved}: {tourId: string; saved: (t: Row) => void}) {
  const {api} = useLoad<unknown>(null);
  const [v, setV] = useState<Row>({starts_at: '', ends_at: '', booking_deadline: '', capacity: 20, double_adult: null, double_child: null, double_infant: null});
  const [msg, setMsg] = useState<Msg>(null);
  async function submit(e: FormEvent) {
    e.preventDefault(); setMsg(null);
    const prices = ROOMS.map(([room]) => ({room, adult: v[`${room}_adult`], child: v[`${room}_child`] ?? null, infant: v[`${room}_infant`] ?? null})).filter(p => p.adult);
    const iso = (s: string) => new Date(s).toISOString();
    try {saved(await api.post<Row>(`/safarsaz/tours/${tourId}/departures`, {starts_at: iso(v.starts_at), ends_at: iso(v.ends_at), booking_deadline: iso(v.booking_deadline), capacity: v.capacity, prices})); setMsg({ok: true, text: 'حرکت اضافه شد.'});}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});}
  }
  const dt = (key: string, label: string) => <label key={key} htmlFor={`f-${key}`}>{label}<input id={`f-${key}`} type="datetime-local" dir="ltr" required value={v[key]} onChange={e => setV({...v, [key]: e.target.value})}/></label>;
  return <form className="pn-form" onSubmit={submit}>
    {dt('starts_at', 'رفت')}{dt('ends_at', 'برگشت')}{dt('booking_deadline', 'مهلت رزرو')}
    <FormFields value={v} set={setV} fields={[{key: 'capacity', label: 'ظرفیت', type: 'number', required: true},
      ...ROOMS.flatMap(([room, l]) => [{key: `${room}_adult`, label: `${l} — بزرگسال (ریال)`, type: 'money' as const, required: room === 'double'}, {key: `${room}_child`, label: `${l} — کودک`, type: 'money' as const}, {key: `${room}_infant`, label: `${l} — نوزاد`, type: 'money' as const}])]}/>
    <p className="pn-muted">نرخ کودک و نوزاد هر نوع اتاق در استعلام و رزرو تور اعمال می‌شود؛ اگر برای اتاقی خالی بماند، رزرو کودک یا نوزاد در آن اتاق ممکن نیست.</p>
    <button className="pn-btn">افزودن حرکت</button><Note msg={msg}/>
  </form>;
}

function Editor({id, back}: {id: string; back: () => void}) {
  const {state, reload, api} = useLoad<Row>(`/safarsaz/tours/${id}`);
  const [msg, setMsg] = useState<Msg>(null);
  async function act(method: 'post' | 'delete', path: string, ok: string) {
    setMsg(null);
    try {if (method === 'post') await api.post(path, {}); else await api.delete(path, {}); setMsg({ok: true, text: ok}); reload();}
    catch (x) {const e = errorOf(x); setMsg({ok: false, text: e.message});}
  }
  return <Async state={state}>{t => <>
    <Card title={t.title} action={<button className="pn-btn ghost" onClick={back}>بازگشت به فهرست</button>}>
      <p><span className={`pn-badge ${STATUS_FA[t.status]?.[1] ?? ''}`}>{STATUS_FA[t.status]?.[0] ?? t.status}</span> {t.source_fa} {t.published_tour_id && <span className="pn-muted">— در فهرست تورها منتشر شده</span>}</p>
      <h3>چک‌لیست انتشار</h3>
      <ul className="pn-list">{t.checklist.map((c: Row) => <li key={c.key}><span>{c.label}</span><span className={`pn-badge ${c.ok ? 'ok' : 'bad'}`}>{c.ok ? 'کامل' : 'ناقص'}</span></li>)}</ul>
      <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12}}>
        <button className="pn-btn" disabled={!t.ready} onClick={() => act('post', `/safarsaz/tours/${id}/publish`, 'منتشر شد.')}>انتشار (مدیر)</button>
        {t.status === 'published' && <button className="pn-btn ghost" onClick={() => act('post', `/safarsaz/tours/${id}/unpublish`, 'به پیش‌نویس برگشت.')}>توقف انتشار</button>}
        <button className="pn-btn ghost" onClick={() => act('post', `/safarsaz/tours/${id}/copy`, 'کپی ساخته شد؛ در فهرست پیدایش کنید.')}>کپی تور</button>
      </div>
      <Note msg={msg}/>
    </Card>
    <Card title="حرکت‌ها و نرخ">
      <Table rows={t.departures} rowKey={(d: Row) => d.id} empty="هنوز حرکتی ثبت نشده است." cols={[
        {label: 'رفت', cell: (d: Row) => dateFa(d.starts_at)}, {label: 'برگشت', cell: (d: Row) => dateFa(d.ends_at)}, {label: 'مهلت رزرو', cell: (d: Row) => dateFa(d.booking_deadline)},
        {label: 'ظرفیت', cell: (d: Row) => fa(d.capacity)},
        {label: 'نرخ‌ها', cell: (d: Row) => d.prices.map((p: Row) => `${ROOMS.find(r => r[0] === p.room)?.[1] ?? p.room}: ${money(p.adult, d.currency)}`).join('، ')},
        {label: 'وضعیت', cell: (d: Row) => d.published ? <span className="pn-badge ok">منتشرشده</span> : d.open ? <span className="pn-badge warn">آماده‌ی انتشار</span> : <span className="pn-badge bad">مهلت گذشته</span>},
        {label: '', cell: (d: Row) => d.published ? null : <button className="pn-btn ghost" onClick={() => act('delete', `/safarsaz/tours/${id}/departures/${d.id}`, 'حذف شد.')}>حذف</button>}]}/>
      <DepartureForm tourId={id} saved={reload}/>
    </Card>
    <Card title="اطلاعات فروش و محتوا"><TourForm key={t.updated_at} tour={t} saved={reload}/></Card>
  </>}</Async>;
}

export function Safarsaz() {
  const [status, setStatus] = useState('');
  const {state, reload, api} = useLoad<{items: Row[]}>(`/safarsaz/tours${status ? `?status=${status}` : ''}`);
  const [open, setOpen] = useState<string | null>(null); const [creating, setCreating] = useState(false); const [msg, setMsg] = useState<Msg>(null);
  if (open) return <Editor id={open} back={() => {setOpen(null); reload();}}/>;
  return <>
    <Card title="تورها" action={<span style={{display: 'flex', gap: 8}}>
      <select aria-label="وضعیت" value={status} onChange={e => setStatus(e.target.value)}><option value="">همه</option><option value="draft">پیش‌نویس</option><option value="published">منتشرشده</option></select>
      <button className="pn-btn ghost" onClick={async () => {setMsg(null); try {const r = await api.post<Row>('/safarsaz/expire', {}); setMsg({ok: true, text: `${fa(r.returned_to_draft)} تور تاریخ‌گذشته به پیش‌نویس برگشت.`}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}}}>بررسی تورهای تاریخ‌گذشته</button>
      <button className="pn-btn" onClick={() => setCreating(c => !c)}>{creating ? 'بستن' : 'تور جدید'}</button></span>}>
      <Note msg={msg}/>
      {creating && <TourForm saved={t => {setCreating(false); setOpen(t.id);}}/>}
      <Async state={state}>{d => d.items.length === 0 ? <Empty>هنوز توری در سفرساز ساخته نشده است.</Empty> : <Table rows={d.items} rowKey={r => r.id} empty="—" cols={[
        {label: 'عنوان', cell: r => r.title}, {label: 'مقصد', cell: r => r.destination}, {label: 'منبع', cell: r => r.source_fa},
        {label: 'حرکت بعدی', cell: r => dateFa(r.next_departure)}, {label: 'ظرفیت پیش رو', cell: r => fa(r.capacity)},
        {label: 'چک‌لیست', cell: r => `${fa(r.checklist_done)} از ${fa(r.checklist_total)}`},
        {label: 'وضعیت', cell: r => <span className={`pn-badge ${STATUS_FA[r.status]?.[1] ?? ''}`}>{STATUS_FA[r.status]?.[0] ?? r.status}</span>},
        {label: '', cell: r => <button className="pn-btn ghost" onClick={() => setOpen(r.id)}>ویرایش</button>}]}/>}</Async>
    </Card>
  </>;
}
