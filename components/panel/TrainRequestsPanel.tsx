'use client';
/* Train ticket requests: the customer's request form and list (offers → accept → checkout), and the agents' desk
   (claim, send offers checked in the rail supplier's panel, issue after payment, hand over to the tour desk). */
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
import {useState} from 'react';
import {Async, Card, Empty, Stats, Table, errorOf, fa, money, useLoad} from './PanelKit';
import {Note, type Row} from './CommercePanel';
import {formatJalali, todayIso} from '../../lib/domain/jalali';
import {useAuth} from '../../lib/api/auth-context';

type Msg = {ok: boolean; text: string} | null;
const timeFa = (iso?: string | null) => (iso ? new Date(iso).toLocaleString('fa-IR', {timeZone: 'Asia/Tehran', weekday: 'short', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'}) : '—');
const pax = (r: Row) => [r.adults && `${fa(r.adults)} بزرگسال`, r.children && `${fa(r.children)} کودک`, r.infants && `${fa(r.infants)} نوزاد`].filter(Boolean).join('، ');
const BADGE: Record<string, string> = {submitted: 'warn', offered: 'warn', accepted: 'warn', issued: 'ok', unavailable: 'bad', cancelled: '', referred: ''};

function DeskHours({desk}: {desk: Row}) {
  return desk.open ? <p className="tr-hours open">کارشناسان قطار الان پاسخ می‌دهند؛ معمولاً در کمتر از یک ساعت پیشنهاد می‌گیرید.</p>
    : <p className="tr-hours">الان خارج از ساعت کاری است؛ درخواست شما {desk.next_open_fa ? `از ${desk.next_open_fa}` : 'در اولین ساعت کاری'} بررسی می‌شود.</p>;
}

/* ---- customer: request form (prefilled from the train search) ---- */
export function TrainRequestForm() {
  const {session, api} = useAuth();
  const params = useSearchParams();
  const desk = useLoad<Row>('/train-requests/desk');
  const [v, setV] = useState<Row>({origin: params.get('origin') ?? '', destination: params.get('destination') ?? '', depart_on: params.get('depart') || todayIso(), return_on: params.get('return') ?? '',
    adults: Number(params.get('adults')) || 1, children: Number(params.get('children')) || 0, infants: Number(params.get('infants')) || 0,
    wagon: 'any', passenger_kind: 'normal', exclusive_coupe: false, car_transport: false, note: ''});
  const [msg, setMsg] = useState<Msg>(null); const [done, setDone] = useState<Row | null>(null); const [busy, setBusy] = useState(false);
  const here = typeof window === 'undefined' ? '/trains/request' : window.location.pathname + window.location.search;
  if (!session) return <Card title="درخواست بلیت قطار"><p>برای ثبت درخواست و دریافت پیشنهاد، وارد حساب کاربری شوید. پیشنهادها و بلیت در «سفرهای من» شما قرار می‌گیرد.</p><Link className="pn-btn" href={`/login?redirect=${encodeURIComponent(here)}`}>ورود یا ثبت‌نام</Link></Card>;
  if (done) return <Card title="درخواست شما ثبت شد"><p>کد پیگیری: <b dir="ltr">{done.code}</b></p>{done.desk && <DeskHours desk={done.desk}/>}<p>وقتی کارشناس قطارهای موجود را فرستاد، در «درخواست‌های قطار» ببینید، یکی را انتخاب و پرداخت کنید.</p><Link className="pn-btn" href="/account/train-requests">درخواست‌های قطار من</Link></Card>;
  const set = (k: string, x: unknown) => setV({...v, [k]: x});
  async function submit() {
    setMsg(null); setBusy(true);
    try {setDone(await api.post<Row>('/train-requests', {...v, return_on: v.return_on || null, note: v.note || null}));}
    catch (x) {setMsg({ok: false, text: errorOf(x).message});} finally {setBusy(false);}
  }
  const meta = desk.state.kind === 'ready' ? desk.state.data : null;
  return <Card title="درخواست بلیت قطار">
    {meta && <DeskHours desk={meta}/>}
    <div className="tr-form">
      <label>مبدأ<input value={v.origin} onChange={e => set('origin', e.target.value)} placeholder="مثلاً تهران"/></label>
      <label>مقصد<input value={v.destination} onChange={e => set('destination', e.target.value)} placeholder="مثلاً مشهد"/></label>
      <label>تاریخ رفت<input type="date" dir="ltr" min={todayIso()} value={v.depart_on} onChange={e => set('depart_on', e.target.value)}/><small>{v.depart_on && formatJalali(v.depart_on)}</small></label>
      <label>تاریخ برگشت (اختیاری)<input type="date" dir="ltr" min={v.depart_on} value={v.return_on} onChange={e => set('return_on', e.target.value)}/><small>{v.return_on ? formatJalali(v.return_on) : 'یک‌طرفه'}</small></label>
      <label>بزرگسال<input type="number" min={1} max={9} value={v.adults} onChange={e => set('adults', Number(e.target.value))}/></label>
      <label>کودک (۲ تا ۱۲ سال)<input type="number" min={0} max={9} value={v.children} onChange={e => set('children', Number(e.target.value))}/></label>
      <label>نوزاد<input type="number" min={0} max={9} value={v.infants} onChange={e => set('infants', Number(e.target.value))}/></label>
      <label>نوع واگن<select value={v.wagon} onChange={e => set('wagon', e.target.value)}>{Object.entries(meta?.wagons ?? {any: 'فرقی ندارد'}).map(([k, l]) => <option key={k} value={k}>{String(l)}</option>)}</select></label>
      <label>مسافران<select value={v.passenger_kind} onChange={e => set('passenger_kind', e.target.value)}>{Object.entries(meta?.kinds ?? {normal: 'مسافران عادی'}).map(([k, l]) => <option key={k} value={k}>{String(l)}</option>)}</select></label>
      <label className="tr-check"><input type="checkbox" checked={v.exclusive_coupe} onChange={e => set('exclusive_coupe', e.target.checked)}/>کوپه‌ی دربست می‌خواهم</label>
      <label className="tr-check"><input type="checkbox" checked={v.car_transport} onChange={e => set('car_transport', e.target.checked)}/>حمل خودرو می‌خواهم</label>
      <label className="tr-wide">توضیح برای کارشناس (اختیاری)<textarea rows={2} maxLength={500} value={v.note} onChange={e => set('note', e.target.value)} placeholder="مثلاً ساعت حرکت شب، یا صندلی‌ها کنار هم"/></label>
    </div>
    <p className="pn-muted">قیمت و ظرفیت را کارشناس از سامانه‌ی فروش ریلی بررسی می‌کند و برایتان می‌فرستد. بلیت پس از انتخاب قطار و پرداخت صادر می‌شود.</p>
    <button className="pn-btn" type="button" disabled={busy || !v.origin || !v.destination} onClick={() => void submit()}>{busy ? 'در حال ثبت…' : 'ثبت درخواست'}</button>
    <Note msg={msg}/>
  </Card>;
}

/* ---- customer: my requests ---- */
function Offers({r, reload}: {r: Row; reload: () => void}) {
  const {api} = useAuth();
  const [pick, setPick] = useState<Record<string, string>>({}); const [msg, setMsg] = useState<Msg>(null);
  const legs: string[] = Array.from(new Set(r.offers.map((o: Row) => o.leg)));
  const ready = legs.every(l => pick[l]);
  async function accept() {
    try {const x = await api.post<Row>(`/me/train-requests/${r.id}/accept`, {offer_ids: Object.values(pick)}); window.location.href = x.checkout_url;}
    catch (e) {setMsg({ok: false, text: errorOf(e).message}); reload();}
  }
  return <div className="tr-offers">
    {legs.map(leg => <fieldset key={leg}><legend>{leg === 'return' ? 'قطار برگشت' : 'قطار رفت'}</legend>
      {r.offers.filter((o: Row) => o.leg === leg).map((o: Row) => <label key={o.id} className={`tr-offer${pick[leg] === o.id ? ' on' : ''}`}>
        <input type="radio" name={`${r.id}-${leg}`} checked={pick[leg] === o.id} onChange={() => setPick({...pick, [leg]: o.id})}/>
        <span><b>{o.train_name}</b>{o.train_number ? ` · شماره ${o.train_number}` : ''}{o.company ? ` · ${o.company}` : ''}<br/>
          <small>حرکت {timeFa(o.departs_at)}{o.arrives_at ? ` — رسیدن ${timeFa(o.arrives_at)}` : ''} · {o.wagon}</small></span>
        <strong>{money(o.total, 'ریال')}</strong></label>)}
    </fieldset>)}
    <p className="pn-muted">این قیمت‌ها تا {timeFa(r.offer_expires_at)} معتبر است.</p>
    <button className="pn-btn" type="button" disabled={!ready} onClick={() => void accept()}>انتخاب و پرداخت</button>
    <Note msg={msg}/>
  </div>;
}

export function MyTrainRequests() {
  const {state, reload, api} = useLoad<{items: Row[]}>('/me/train-requests');
  const [msg, setMsg] = useState<Msg>(null);
  const cancel = async (id: string) => {try {await api.post(`/me/train-requests/${id}/cancel`, {}); setMsg({ok: true, text: 'درخواست لغو شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}};
  return <>
    <Card action={<Link className="pn-btn" href="/trains">درخواست تازه</Link>} title="درخواست‌های قطار"><Note msg={msg}/>
      <Async state={state}>{d => d.items.length === 0 ? <Empty>هنوز درخواست قطاری ثبت نکرده‌اید.</Empty> : <div className="tr-list">{d.items.map(r => <article key={r.id} className="tr-item">
        <header><b>{r.origin} ← {r.destination}</b><span className={`pn-badge ${BADGE[r.status] ?? ''}`}>{r.offer_expired ? 'مهلت پیشنهاد گذشت' : r.status_fa}</span></header>
        <p className="pn-muted">{formatJalali(r.depart_on)}{r.return_on ? ` تا ${formatJalali(r.return_on)}` : ''} · {pax(r)} · {r.wagon_fa}{r.exclusive_coupe ? ' · دربست' : ''} · کد <span dir="ltr">{r.code}</span></p>
        {r.status === 'offered' && !r.offer_expired && <Offers r={r} reload={reload}/>}
        {r.status === 'accepted' && r.checkout_url && <Link className="pn-btn" href={r.checkout_url}>پرداخت</Link>}
        {r.status === 'issued' && <p>بلیت صادر شد. شماره‌ی بلیت: <b>{r.ticket_numbers}</b> — <Link href={`/manage-booking/${r.reservation_id}`}>جزئیات سفر</Link></p>}
        {r.status === 'unavailable' && <p>{r.staff_note}</p>}
        {r.status === 'referred' && <p>کارشناس تور برای برنامه‌ی کامل سفر با شما تماس می‌گیرد.</p>}
        {(r.status === 'submitted' || r.status === 'offered') && <button className="pn-btn ghost" type="button" onClick={() => void cancel(r.id)}>لغو درخواست</button>}
      </article>)}</div>}</Async>
    </Card>
  </>;
}

/* ---- agents: desk ---- */
const EMPTY_OFFER = {leg: 'depart', train_name: '', train_number: '', company: '', departs_at: '', arrives_at: '', wagon: '', price_adult: '', price_child: '', price_infant: ''};

function OfferForm({r, done}: {r: Row; done: (m: Msg) => void}) {
  const {api} = useAuth();
  const [rows, setRows] = useState<Row[]>([{...EMPTY_OFFER}]);
  const set = (i: number, k: string, x: string) => setRows(rows.map((o, j) => (j === i ? {...o, [k]: x} : o)));
  async function send() {
    try {
      const offers = rows.map(o => ({...o, train_number: o.train_number || null, company: o.company || null, departs_at: new Date(o.departs_at).toISOString(),
        arrives_at: o.arrives_at ? new Date(o.arrives_at).toISOString() : null, price_adult: Number(o.price_adult), price_child: Number(o.price_child) || 0, price_infant: Number(o.price_infant) || 0}));
      await api.post(`/train-desk/requests/${r.id}/offers`, {offers}); done({ok: true, text: 'پیشنهاد برای مشتری فرستاده شد.'});
    } catch (x) {done({ok: false, text: errorOf(x).message});}
  }
  return <div className="tr-offer-form">
    {rows.map((o, i) => <div className="tr-offer-row" key={i}>
      {r.return_on && <label>مسیر<select value={o.leg} onChange={e => set(i, 'leg', e.target.value)}><option value="depart">رفت</option><option value="return">برگشت</option></select></label>}
      <label>نام قطار<input value={o.train_name} onChange={e => set(i, 'train_name', e.target.value)} placeholder="مثلاً غزال"/></label>
      <label>شماره<input dir="ltr" value={o.train_number} onChange={e => set(i, 'train_number', e.target.value)}/></label>
      <label>شرکت<input value={o.company} onChange={e => set(i, 'company', e.target.value)}/></label>
      <label>حرکت<input type="datetime-local" dir="ltr" value={o.departs_at} onChange={e => set(i, 'departs_at', e.target.value)}/></label>
      <label>رسیدن<input type="datetime-local" dir="ltr" value={o.arrives_at} onChange={e => set(i, 'arrives_at', e.target.value)}/></label>
      <label>واگن<input value={o.wagon} onChange={e => set(i, 'wagon', e.target.value)} placeholder="کوپه‌ی ۴ تخته"/></label>
      <label>نرخ بزرگسال (ریال)<input dir="ltr" inputMode="numeric" value={o.price_adult} onChange={e => set(i, 'price_adult', e.target.value.replace(/\D/g, ''))}/></label>
      {r.children > 0 && <label>نرخ کودک<input dir="ltr" inputMode="numeric" value={o.price_child} onChange={e => set(i, 'price_child', e.target.value.replace(/\D/g, ''))}/></label>}
      {r.infants > 0 && <label>نرخ نوزاد<input dir="ltr" inputMode="numeric" value={o.price_infant} onChange={e => set(i, 'price_infant', e.target.value.replace(/\D/g, ''))}/></label>}
      {rows.length > 1 && <button type="button" className="pn-btn ghost" onClick={() => setRows(rows.filter((_, j) => j !== i))}>حذف</button>}
    </div>)}
    <div className="tr-actions">{rows.length < 8 && <button type="button" className="pn-btn ghost" onClick={() => setRows([...rows, {...EMPTY_OFFER}])}>قطار دیگر</button>}
      <button type="button" className="pn-btn" onClick={() => void send()}>ارسال پیشنهاد به مشتری</button></div>
  </div>;
}

function DeskItem({r, done}: {r: Row; done: (m: Msg) => void}) {
  const {api} = useAuth();
  const [tickets, setTickets] = useState('');
  const act = async (path: string, body: Row, ok: string) => {try {const x = await api.post<Row>(`/train-desk/requests/${r.id}/${path}`, body); done({ok: true, text: x.sales_case_code ? `${ok} (پرونده‌ی ${x.sales_case_code})` : ok});} catch (e) {done({ok: false, text: errorOf(e).message});}};
  const paid = r.reservation_status === 'confirmed';
  return <div className="tr-desk-item">
    <p>{r.customer?.name ?? 'مشتری'} · <span dir="ltr">{r.customer?.mobile ?? '—'}</span> · {pax(r)} · {r.wagon_fa} · {r.passenger_kind_fa}{r.exclusive_coupe ? ' · دربست' : ''}{r.car_transport ? ' · حمل خودرو' : ''}</p>
    {r.note && <p className="pn-muted">توضیح مشتری: {r.note}</p>}
    {!r.assigned_user_id && <button className="pn-btn ghost" type="button" onClick={() => void act('claim', {}, 'درخواست را برداشتید.')}>برداشتن</button>}
    {(r.status === 'submitted' || r.status === 'offered') && <>
      {r.status === 'offered' && <p className="pn-muted">{fa(r.offers.length)} پیشنهاد فرستاده شده، معتبر تا {timeFa(r.offer_expires_at)}{r.offer_expired ? ' (گذشته)' : ''}. ارسال دوباره، پیشنهادهای قبلی را جایگزین می‌کند.</p>}
      <OfferForm r={r} done={done}/>
      <div className="tr-actions"><button className="pn-btn ghost" type="button" onClick={() => void act('unavailable', {}, 'به مشتری گفته شد ظرفیت نیست.')}>ظرفیت نیست</button>
        <button className="pn-btn ghost" type="button" onClick={() => void act('refer', {note: 'مشتری تور کامل می‌خواهد'}, 'به میز فروش تور ارجاع شد')}>ارجاع به کارشناس تور</button></div>
    </>}
    {r.status === 'accepted' && (paid ? <div className="tr-actions"><input aria-label="شماره‌ی بلیت" placeholder="شماره‌ی بلیت‌ها" value={tickets} onChange={e => setTickets(e.target.value)}/>
      <button className="pn-btn" type="button" disabled={tickets.trim().length < 3} onClick={() => void act('issue', {ticket_numbers: tickets}, 'بلیت ثبت شد و برای مشتری نمایش داده می‌شود.')}>ثبت بلیت صادرشده</button></div>
      : <p className="pn-muted">مشتری قطار را انتخاب کرده و در انتظار پرداخت است. پیش از پرداخت بلیت صادر نکنید.</p>)}
    {r.status === 'issued' && <p>بلیت: {r.ticket_numbers}</p>}
  </div>;
}

function HoursCard() {
  const {state, reload, api} = useLoad<Row>('/train-desk/settings');
  const [msg, setMsg] = useState<Msg>(null);
  return <Async state={state}>{s => {
    const h = s.hours; const days: string[] = s.days_fa;
    const save = async (patch: Row) => {try {await api.put('/train-desk/settings', {...h, offer_valid_minutes: s.offer_valid_minutes, ...patch}); setMsg({ok: true, text: 'ساعت کاری ذخیره شد.'}); reload();} catch (x) {setMsg({ok: false, text: errorOf(x).message});}};
    return <Card title="ساعت کاری میز قطار">
      <div className="tr-days">{days.map((d, i) => <label key={d} className="tr-check"><input type="checkbox" checked={h.days.includes(i)} onChange={e => void save({days: e.target.checked ? [...h.days, i] : h.days.filter((x: number) => x !== i)})}/>{d}</label>)}</div>
      <div className="tr-actions"><label>شروع<input type="time" dir="ltr" defaultValue={h.start} onBlur={e => e.target.value !== h.start && void save({start: e.target.value})}/></label>
        <label>پایان<input type="time" dir="ltr" defaultValue={h.end} onBlur={e => e.target.value !== h.end && void save({end: e.target.value})}/></label>
        <label>پایان پنجشنبه<input type="time" dir="ltr" defaultValue={h.thursday_end ?? ''} onBlur={e => void save({thursday_end: e.target.value || null})}/></label>
        <label>اعتبار پیشنهاد (دقیقه)<input type="number" min={10} max={1440} defaultValue={s.offer_valid_minutes} onBlur={e => Number(e.target.value) !== s.offer_valid_minutes && void save({offer_valid_minutes: Number(e.target.value)})}/></label></div>
      <Note msg={msg}/><p className="pn-muted">تغییر ساعت کاری فقط با مدیر مجموعه است.</p>
    </Card>;
  }}</Async>;
}

export function TrainDesk() {
  const [status, setStatus] = useState('open'); const [mine, setMine] = useState(false);
  const {state, reload} = useLoad<{items: Row[]; counts: Record<string, number>; desk: Row}>(`/train-desk/requests?status=${status}${mine ? '&mine_only=true' : ''}`);
  const [open, setOpen] = useState<string | null>(null); const [msg, setMsg] = useState<Msg>(null);
  const done = (m: Msg) => {setMsg(m); reload();};
  return <>
    <Async state={state}>{d => <>
      <Stats items={[{label: 'در انتظار بررسی', value: fa(d.counts.submitted ?? 0)}, {label: 'منتظر انتخاب مشتری', value: fa(d.counts.offered ?? 0)}, {label: 'منتظر پرداخت یا صدور', value: fa(d.counts.accepted ?? 0)}, {label: 'صادرشده', value: fa(d.counts.issued ?? 0)}]}/>
      <Card title="درخواست‌های بلیت قطار" action={<span className="tr-actions"><select aria-label="وضعیت" value={status} onChange={e => setStatus(e.target.value)}>
        {[['open', 'باز'], ['submitted', 'در انتظار بررسی'], ['offered', 'پیشنهاد ارسال شد'], ['accepted', 'در انتظار پرداخت'], ['issued', 'صادرشده'], ['unavailable', 'ظرفیت نبود'], ['referred', 'ارجاع به تور'], ['cancelled', 'لغوشده'], ['all', 'همه']].map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <label className="tr-check"><input type="checkbox" checked={mine} onChange={e => setMine(e.target.checked)}/>فقط من</label></span>}>
        {!d.desk.open && <p className="pn-note">الان خارج از ساعت کاری است؛ به مشتری‌ها گفته شده {d.desk.next_open_fa ?? 'در اولین ساعت کاری'} پاسخ می‌گیرند.</p>}
        <Note msg={msg}/>
        <Table rows={d.items} rowKey={r => r.id} empty={<Empty>درخواستی در این وضعیت نیست.</Empty>} cols={[
          {label: 'کد', cell: r => <span dir="ltr">{r.code}</span>}, {label: 'مسیر', cell: r => `${r.origin} ← ${r.destination}`},
          {label: 'تاریخ', cell: r => formatJalali(r.depart_on) + (r.return_on ? ` / ${formatJalali(r.return_on)}` : '')}, {label: 'مسافر', cell: r => fa(r.adults + r.children + r.infants)},
          {label: 'کارشناس', cell: r => r.assigned_to ?? '—'}, {label: 'وضعیت', cell: r => <span className={`pn-badge ${BADGE[r.status] ?? ''}`}>{r.status === 'accepted' && r.reservation_status === 'confirmed' ? 'پرداخت شد؛ صدور بلیت' : r.status_fa}</span>},
          {label: '', cell: r => <button className="pn-btn ghost" type="button" onClick={() => setOpen(open === r.id ? null : r.id)}>{open === r.id ? 'بستن' : 'باز کردن'}</button>}]}/>
        {d.items.filter(r => r.id === open).map(r => <DeskItem key={r.id} r={r} done={done}/>)}
      </Card></>}</Async>
    <HoursCard/>
  </>;
}
