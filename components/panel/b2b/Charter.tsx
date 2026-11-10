'use client';
/* Charterer panel (Figma P2: CH-01 flights list, CH-02 seat-block form, CH-03/04 block detail with allocations to partner agencies).
   Seats, prices, the CAO cap and the domestic-charter flag all come from the API; publishing is done by operations staff. */
import Link from 'next/link';
import {useParams, useRouter} from 'next/navigation';
import {useMemo, useState} from 'react';
import {AgencyScope} from '../AgencyPanel';
import {Card, Stats, Table, useLoad} from '../PanelKit';
import {EmptyState, Loaded, Ref, Skeleton, Unavail, rial} from '../aftersales/kit';
import {BlockChip, DateField, tehranIso, Feedback, Field, MoneyBreakdown, apiCode, apiMessage, jalali, parseRial, pct, useAction, type SellerBreakdown} from './B2BKit';

type Agency = {id: string; name: string};
type Seats = {seats_total: number; sold: number; allocated_held: number; public_available: number; remaining: number};
export type Block = {id: string; source: string; external_ref: string | null; airline_code: string; airline_name: string | null; flight_number: string; origin: string; destination: string;
  origin_city: string | null; destination_city: string | null; route_scope: string; cabin: string; seats_total: number; net_adult_irr: number; net_child_irr: number; net_infant_irr: number;
  departure_at: string; arrival_at: string; release_at: string; status: string; review_note: string | null; price_cap_unit_irr: number | null; price_cap_reference: string | null; price_cap_status: string;
  domestic_sale_disabled: boolean; tax_role: string; accountant_confirmed: boolean; platform_fee_bps: number | null; seats: Seats; money: SellerBreakdown; owner_agency_name?: string;
  refund_policy: {non_refundable?: boolean; tiers?: {hours_before: number; penalty_bps: number}[]}; name_change_hours: number};
const SOURCE_FA: Record<string, string> = {manual: 'دستی', parto: 'پرتو', charter724: 'چارتر۷۲۴', sepehr: 'سپهر', other: 'سایر'};
export const route = (b: Pick<Block, 'origin' | 'destination' | 'origin_city' | 'destination_city'>) => `${b.origin_city ?? ''} (${b.origin}) ← ${b.destination_city ?? ''} (${b.destination})`;

/* ---------------------------------------------------------------- CH-01 */
export function CharterFlightsPage() {return <AgencyScope>{a => <ListBody a={a}/>}</AgencyScope>;}
function ListBody({a}: {a: Agency}) {
  const r = useLoad<{items: Block[]; band_alef_valid: boolean; domestic_charter_sale: boolean; member_role: string; summary: {seats_total: number; sold: number; allocated_held: number; next_release_at: string | null}}>(`/agency/${a.id}/charter/blocks`);
  const src = useLoad<{items: {key: string; label: string; status: string}[]}>('/charter/sources');
  const [tab, setTab] = useState('all');
  return <Loaded state={r.state} reload={r.reload} skeleton={<Skeleton kind="table" rows={4}/>}>{d => {
    const rows = d.items.filter(b => tab === 'all' || (tab === 'draft' ? b.status === 'draft' : b.route_scope === tab));
    return <>
      <div className="b2b-toolbar"><div className="b2b-flags">
        {d.band_alef_valid ? <span className="as-chip ok">مجوز بند الف: معتبر</span> : <span className="as-chip bad">مجوز معتبر بند الف ندارید</span>}
        <span className={`as-chip ${d.domestic_charter_sale ? 'ok' : ''}`}>چارتر داخلی: {d.domestic_charter_sale ? 'فروش آنلاین فعال' : 'فروش آنلاین خاموش (charter_domestic_sale)'}</span></div>
        {d.member_role === 'owner' && d.band_alef_valid && <Link className="as-btn" href="/agency/inventory/flights/new">ثبت بلوک صندلی</Link>}</div>
      <Stats items={[{label: `صندلی قراردادی (${d.items.length.toLocaleString('fa-IR')} پرواز)`, value: d.summary.seats_total.toLocaleString('fa-IR')}, {label: 'فروخته‌شده', value: d.summary.sold.toLocaleString('fa-IR')},
        {label: 'سهمیهٔ همکاران (hold)', value: d.summary.allocated_held.toLocaleString('fa-IR')}, {label: 'release نزدیک', value: d.summary.next_release_at ? jalali(d.summary.next_release_at, true) : '—'}]}/>
      <Card><div className="pn-chips" role="group" aria-label="فیلتر">{[['all', 'همه'], ['international', 'بین‌المللی'], ['domestic', 'داخلی'], ['draft', 'پیش‌نویس']].map(([k, l]) => <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}>{l} ({(k === 'all' ? d.items.length : d.items.filter(b => k === 'draft' ? b.status === 'draft' : b.route_scope === k).length).toLocaleString('fa-IR')})</button>)}</div>
        {rows.length === 0 ? <EmptyState title="بلوکی ثبت نشده است">{d.band_alef_valid ? 'با «ثبت بلوک صندلی» اولین پرواز چارتر خود را ثبت کنید.' : 'برای ثبت پرواز، مجوز بند الف را در «پروفایل و مجوزها» ثبت و احراز کنید.'}</EmptyState>
          : <div className="as-scroll"><table className="as-table"><caption className="sr-only" style={{position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)'}}>بلوک‌های صندلی</caption>
            <thead><tr>{['مسیر', 'ایرلاین', 'شمارهٔ پرواز', 'تاریخ و ساعت', 'ظرفیت', 'فروخته', 'hold', 'مانده', 'release', 'منبع', 'وضعیت'].map(h => <th key={h} scope="col">{h}</th>)}</tr></thead>
            <tbody>{rows.map(b => <tr key={b.id} className={b.domestic_sale_disabled ? 'b2b-row-warn' : ''} aria-disabled={b.domestic_sale_disabled || undefined}>
              <td data-label="مسیر"><Link className="pn-link" href={`/agency/inventory/flights/${b.id}`}>{route(b)}</Link></td><td data-label="ایرلاین">{b.airline_name ?? b.airline_code}</td>
              <td data-label="شمارهٔ پرواز"><Ref>{b.airline_code}{b.flight_number}</Ref></td><td data-label="تاریخ و ساعت">{jalali(b.departure_at, true)}</td>
              <td data-label="ظرفیت">{b.seats.seats_total.toLocaleString('fa-IR')}</td><td data-label="فروخته">{b.seats.sold.toLocaleString('fa-IR')}</td><td data-label="hold">{b.seats.allocated_held.toLocaleString('fa-IR')}</td>
              <td data-label="مانده">{b.seats.remaining.toLocaleString('fa-IR')}</td><td data-label="release">{jalali(b.release_at, true)}</td><td data-label="منبع">{SOURCE_FA[b.source] ?? b.source}</td>
              <td data-label="وضعیت">{b.domestic_sale_disabled ? <span className="as-chip">فروش آنلاین خاموش</span> : <BlockChip status={b.status}/>}</td></tr>)}</tbody></table></div>}</Card>
      <Card title="منابع موجودی پرواز"><Loaded state={src.state}>{s => <ul className="pn-list">{s.items.map(x => <li key={x.key} className="as-row" style={{display: 'flex', justifyContent: 'space-between'}}><span>{x.label}</span>
        {x.status === 'active' ? <span className="as-chip ok">فعال</span> : <span className="as-chip">پس از قرارداد</span>}</li>)}</ul>}</Loaded>
        <p className="as-muted">اتصال به سامانه‌های اشتراکی (پرتو و مشابه) پس از قرارداد و دریافت دسترسی فعال می‌شود؛ تا آن زمان شناسهٔ مرجع آن سامانه را در فرم ثبت کنید.</p></Card>
    </>;}}</Loaded>;
}

/* ---------------------------------------------------------------- CH-02 */
export function CharterBlockFormPage() {return <AgencyScope>{a => <FormBody a={a}/>}</AgencyScope>;}
function plusDays(days: number, hhmm: string) {const d = new Date(Date.now() + days * 86400000); return `${d.toISOString().slice(0, 10)}T${hhmm}`;}  // a Tehran wall-clock value for datetime-local
function FormBody({a}: {a: Agency}) {
  const router = useRouter(); const flags = useLoad<{domestic_charter_sale: boolean}>('/charter/sources'); const act = useAction();
  const [f, setF] = useState({origin: 'IKA', destination: 'IST', origin_city: 'تهران', destination_city: 'استانبول', airline_code: '', airline_name: '', flight_number: '', aircraft: '', cabin: 'economy', fare_class: '',
    route_scope: 'international', departure: plusDays(14, '07:30'), arrival: plusDays(14, '11:00'), seats: '', baggage: '20', adult: '', child: '', infant: '', release: plusDays(12, '12:00'), name_change: '72',
    tier1h: '72', tier1p: '20', tier2h: '3', tier2p: '50', non_refundable: false, source: 'manual', external_ref: ''});
  const [capError, setCapError] = useState('');
  const day = f.departure.slice(0, 10);
  const cap = useLoad<{cap_unit_irr: number | null; legal_reference: string | null; status: string}>(/^[A-Za-z]{3}$/.test(f.origin) && /^[A-Za-z]{3}$/.test(f.destination) && day ? `/charter/price-cap?origin=${f.origin}&destination=${f.destination}&day=${day}` : null);
  const capUnit = cap.state.kind === 'ready' ? cap.state.data.cap_unit_irr : null;
  const domesticOn = flags.state.kind === 'ready' && flags.state.data.domestic_charter_sale;
  const set = (k: keyof typeof f) => (e: {target: {value: string}}) => setF({...f, [k]: e.target.value});
  const fares = useMemo(() => [['بزرگسال (ADT)', parseRial(f.adult)], ['کودک (CHD)', parseRial(f.child)], ['نوزاد (INF)', parseRial(f.infant)]] as [string, number][], [f.adult, f.child, f.infant]);
  const save = (submit: boolean) => act.run(async api => {
    setCapError('');
    const tiers = f.non_refundable ? [] : [[f.tier1h, f.tier1p], [f.tier2h, f.tier2p]].filter(([h, p]) => h && p).map(([h, p]) => ({hours_before: Number(parseRial(h)), penalty_bps: Math.round(Number(parseRial(p)) * 100)}));
    try {
      const b = await api.post<Block>(`/agency/${a.id}/charter/blocks`, {origin: f.origin.toUpperCase(), destination: f.destination.toUpperCase(), origin_city: f.origin_city || null, destination_city: f.destination_city || null,
        airline_code: f.airline_code, airline_name: f.airline_name || null, flight_number: f.flight_number, aircraft: f.aircraft || null, cabin: f.cabin, fare_class: f.fare_class || null, route_scope: f.route_scope,
        departure_at: tehranIso(f.departure), arrival_at: tehranIso(f.arrival), seats_total: Number(parseRial(f.seats)), baggage_kg: Number(parseRial(f.baggage)) || 0,
        net_adult_irr: parseRial(f.adult), net_child_irr: parseRial(f.child) || 0, net_infant_irr: parseRial(f.infant) || 0, release_at: tehranIso(f.release), name_change_hours: Number(parseRial(f.name_change)) || 0,
        refund_tiers: tiers, non_refundable: f.non_refundable, source: f.source, external_ref: f.external_ref || null, submit});
      router.push(`/agency/inventory/flights/${b.id}`); return b;
    } catch (e) {if (apiCode(e) === 'PRICE_CAP_EXCEEDED') setCapError(apiMessage(e)); throw e;}
  });
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void save(true);}}>
    <div className="b2b-toolbar"><p className="as-muted">پیش‌نویس فقط برای شما دیده می‌شود؛ پس از ارسال، عملیات بازبینی و منتشر می‌کند. تا آن زمان فروش ممکن نیست.</p>
      <div className="as-actions"><button className="as-btn ghost" type="button" disabled={act.busy} onClick={() => void save(false)}>ذخیرهٔ پیش‌نویس</button><button className="as-btn" type="submit" disabled={act.busy}>ارسال برای بازبینی</button></div></div>
    {capError && <div className="as-note bad" role="alert"><b>ارسال ممکن نیست: نرخ از سقف سازمان هواپیمایی بیشتر است.</b><br/>{capError} (کد خطا: PRICE_CAP_EXCEEDED)</div>}
    <Card title="۱. مسیر و پرواز"><div className="b2b-grid3">
      <Field label="مبدأ (کد IATA)"><input required value={f.origin} onChange={set('origin')} dir="ltr" maxLength={3}/></Field><Field label="شهر مبدأ"><input value={f.origin_city} onChange={set('origin_city')}/></Field>
      <Field label="مقصد (کد IATA)"><input required value={f.destination} onChange={set('destination')} dir="ltr" maxLength={3}/></Field><Field label="شهر مقصد"><input value={f.destination_city} onChange={set('destination_city')}/></Field>
      <Field label="ایرلاین چارتردهنده (کد)"><input required value={f.airline_code} onChange={set('airline_code')} dir="ltr" maxLength={3}/></Field><Field label="نام ایرلاین"><input value={f.airline_name} onChange={set('airline_name')}/></Field>
      <Field label="شمارهٔ پرواز"><input required value={f.flight_number} onChange={set('flight_number')} dir="ltr" maxLength={8}/></Field><Field label="نوع هواپیما"><input value={f.aircraft} onChange={set('aircraft')} dir="ltr"/></Field>
      <Field label="کابین و کلاس"><select value={f.cabin} onChange={set('cabin')}><option value="economy">اقتصادی</option><option value="premium">اقتصادی ممتاز</option><option value="business">بیزینس</option><option value="first">فرست</option></select></Field>
    </div>
      <div className="b2b-choice" role="radiogroup" aria-label="محدودهٔ مسیر (route_scope)">
        <label><input type="radio" name="scope" checked={f.route_scope === 'international'} onChange={() => setF({...f, route_scope: 'international'})}/> <span><b>بین‌المللی (INTERNATIONAL)</b><small>فروش آنلاین پس از بازبینی مجاز است</small></span></label>
        <label aria-disabled={!domesticOn}><input type="radio" name="scope" disabled={!domesticOn} checked={f.route_scope === 'domestic'} onChange={() => setF({...f, route_scope: 'domestic'})}/> <span><b>داخلی (DOMESTIC)</b><small>{domesticOn ? 'فروش آنلاین چارتر داخلی فعال است' : 'غیرفعال: فروش چارتر داخلی تا تأیید قانونی فعال نشده است'}</small></span></label>
      </div></Card>
    <Card title="۲. زمان و ظرفیت"><div className="b2b-grid">
      <DateField type="datetime-local" label="زمان حرکت (به وقت تهران)" value={f.departure} onChange={v => setF({...f, departure: v})} required/>
      <DateField type="datetime-local" label="زمان رسیدن" value={f.arrival} onChange={v => setF({...f, arrival: v})} required/>
      <Field label="ظرفیت قراردادی (صندلی)"><input required inputMode="numeric" value={f.seats} onChange={set('seats')} dir="ltr"/></Field><Field label="بار مجاز (کیلوگرم)"><input inputMode="numeric" value={f.baggage} onChange={set('baggage')} dir="ltr"/></Field>
    </div></Card>
    <Card title="۳. نرخ‌ها (ریال، به ازای هر مسافر)">
      <div className="b2b-grid3"><Field label="نرخ خالص بزرگسال (ADT)"><input required inputMode="numeric" value={f.adult} onChange={set('adult')} dir="ltr"/></Field>
        <Field label="کودک (CHD)"><input inputMode="numeric" value={f.child} onChange={set('child')} dir="ltr"/></Field><Field label="نوزاد (INF)"><input inputMode="numeric" value={f.infant} onChange={set('infant')} dir="ltr"/></Field></div>
      <Table rows={fares.filter(([, v]) => v > 0)} rowKey={([l]) => l} empty="نرخ‌ها را وارد کنید." cols={[{label: 'نوع مسافر', cell: ([l]) => l}, {label: 'نرخ', cell: ([, v]) => rial(v)},
        {label: 'سقف سازمان هواپیمایی', cell: ([l]) => l.startsWith('بزرگسال') && capUnit !== null ? rial(capUnit) : '—'},
        {label: 'بررسی سقف', cell: ([l, v]) => !l.startsWith('بزرگسال') ? '—' : capUnit === null ? <span className="as-chip">سقف ثبت نشده</span> : v > capUnit ? <span className="as-chip bad">بیش از سقف</span> : <span className="as-chip ok">در سقف</span>}]}/>
      <p className="as-muted">{cap.state.kind === 'ready' && cap.state.data.legal_reference ? `مرجع سقف: ${cap.state.data.legal_reference}` : 'سقف از جدول price_cap خوانده و سمت سرور کنترل می‌شود؛ برای این مسیر و تاریخ سقفی ثبت نشده است.'}</p></Card>
    <div className="b2b-split">
      <Card title="۴. سیاست‌ها"><div className="b2b-grid">
        <DateField type="datetime-local" label="زمان release (برگشت صندلی‌های نفروخته)" value={f.release} onChange={v => setF({...f, release: v})} required/>
        <Field label="مهلت تغییر نام (ساعت پیش از پرواز)"><input inputMode="numeric" value={f.name_change} onChange={set('name_change')} dir="ltr"/></Field></div>
        <label className="as-check"><input type="checkbox" checked={f.non_refundable} onChange={e => setF({...f, non_refundable: e.target.checked})}/> غیرقابل استرداد</label>
        {!f.non_refundable && <div className="b2b-grid"><Field label="پلهٔ ۱: ساعت پیش از پرواز"><input inputMode="numeric" value={f.tier1h} onChange={set('tier1h')} dir="ltr"/></Field><Field label="جریمه (٪)"><input inputMode="numeric" value={f.tier1p} onChange={set('tier1p')} dir="ltr"/></Field>
          <Field label="پلهٔ ۲: ساعت پیش از پرواز"><input inputMode="numeric" value={f.tier2h} onChange={set('tier2h')} dir="ltr"/></Field><Field label="جریمه (٪)"><input inputMode="numeric" value={f.tier2p} onChange={set('tier2p')} dir="ltr"/></Field></div>}
        <div className="as-note info"><b>قاعدهٔ اجباری (غیرقابل ویرایش)</b><br/>لغو یا تأخیر بیش از ۲ ساعت از طرف ایرلاین = استرداد کامل به مسافر.</div></Card>
      <Card title="۵. مالیات، منبع و قرارداد"><span className="as-chip warn">نقش مالیاتی: PRINCIPAL · نیازمند تأیید حسابدار</span>
        <Field label="منبع موجودی"><select value={f.source} onChange={set('source')}>{Object.entries(SOURCE_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        {f.source !== 'manual' && <Field label="شناسهٔ مرجع در آن سامانه" hint="اتصال خودکار پس از قرارداد؛ فعلاً فقط شناسه ثبت می‌شود"><input required value={f.external_ref} onChange={set('external_ref')} dir="ltr"/></Field>}
        <Unavail title="قرارداد چارتر با ایرلاین">بارگذاری فایل قرارداد در این نسخه فعال نیست؛ نسخهٔ امضاشده را به عملیات تحویل دهید.</Unavail></Card>
    </div>
    <Feedback error={capError ? undefined : act.error}/>
  </form>;
}

/* ---------------------------------------------------------------- CH-03/04 */
type Allocation = {id: string; agency_id: string; agency: string | null; seats: number; seats_initial: number; status: string; release_at: string; released_reason: string | null; note: string | null};
export function CharterBlockDetailPage() {const p = useParams<{id: string}>(); return <AgencyScope>{a => <DetailBody a={a} id={String(p?.id ?? '')}/>}</AgencyScope>;}
function DetailBody({a, id}: {a: Agency; id: string}) {
  const r = useLoad<Block & {member_role: string; allocations: Allocation[]}>(`/agency/${a.id}/charter/blocks/${id}`); const act = useAction();
  const submit = () => act.run(api => api.post(`/agency/${a.id}/charter/blocks/${id}/submit`, {}), 'برای بازبینی ارسال شد.').then(x => {if (x) r.reload();});
  return <Loaded state={r.state} reload={r.reload}>{b => <>
    <Card title={`${route(b)} · ${b.airline_code}${b.flight_number}`} action={<BlockChip status={b.status}/>}>
      <dl className="b2b-kv"><dt>حرکت</dt><dd>{jalali(b.departure_at, true)}</dd><dt>release</dt><dd>{jalali(b.release_at, true)}</dd><dt>منبع</dt><dd>{SOURCE_FA[b.source] ?? b.source}{b.external_ref && <> · <Ref>{b.external_ref}</Ref></>}</dd>
        <dt>نرخ خالص ADT / CHD / INF</dt><dd>{rial(b.net_adult_irr)} / {rial(b.net_child_irr)} / {rial(b.net_infant_irr)}</dd>
        <dt>سقف سازمان هواپیمایی</dt><dd>{b.price_cap_unit_irr !== null ? `${rial(b.price_cap_unit_irr)} — ${b.price_cap_reference ?? ''}` : 'برای این مسیر و تاریخ ثبت نشده است'}</dd>
        <dt>سیاست استرداد</dt><dd>{b.refund_policy.non_refundable ? 'غیرقابل استرداد' : (b.refund_policy.tiers ?? []).map(t => `${t.hours_before.toLocaleString('fa-IR')} ساعت پیش: ${pct(t.penalty_bps)}`).join('، ') || '—'} · لغو یا تأخیر بیش از ۲ ساعت ایرلاین: استرداد کامل</dd>
        <dt>نقش مالیاتی</dt><dd>{b.tax_role}{b.accountant_confirmed ? '' : ' (نیازمند تأیید حسابدار)'}</dd></dl>
      {b.domestic_sale_disabled && <p className="as-note warn">چارتر داخلی: ثبت شده ولی فروش آنلاین تا تأیید قانونی خاموش است.</p>}
      {b.review_note && <p className={`as-note ${b.status === 'rejected' ? 'bad' : 'info'}`}>یادداشت عملیات: {b.review_note}</p>}
      {b.member_role === 'owner' && (b.status === 'draft' || b.status === 'rejected') && <div className="as-actions"><button className="as-btn" type="button" disabled={act.busy} onClick={() => void submit()}>ارسال برای بازبینی</button></div>}
      <Feedback error={act.error} done={act.done}/></Card>
    <Stats items={[{label: 'ظرفیت', value: b.seats.seats_total.toLocaleString('fa-IR')}, {label: 'فروخته', value: b.seats.sold.toLocaleString('fa-IR')}, {label: 'سهمیهٔ همکاران', value: b.seats.allocated_held.toLocaleString('fa-IR')}, {label: 'آزاد برای فروش عمومی', value: b.seats.public_available.toLocaleString('fa-IR')}]}/>
    <div className="b2b-split"><Card title="سهمیه برای آژانس‌های همکار">{b.status !== 'published' ? <p className="as-muted">سهمیه پس از انتشار بلوک تعریف می‌شود.</p> : <>
      <Table rows={b.allocations} rowKey={x => x.id} empty="سهمیه‌ای تعریف نشده است." cols={[{label: 'آژانس', cell: x => x.agency ?? '—'}, {label: 'صندلی', cell: x => `${x.seats.toLocaleString('fa-IR')} از ${x.seats_initial.toLocaleString('fa-IR')}`},
        {label: 'release', cell: x => jalali(x.release_at, true)}, {label: 'وضعیت', cell: x => <span className={`as-chip ${x.status === 'held' ? 'warn' : ''}`}>{x.status === 'held' ? 'نگه‌داشته' : x.released_reason === 'agency_booking' ? 'فروخته به همکار' : 'آزادشده'}</span>},
        {label: 'اقدام', cell: x => b.member_role === 'owner' && x.status === 'held' ? <ReleaseButton agencyId={a.id} blockId={b.id} q={x} onDone={r.reload}/> : '—'}]}/>
      {b.member_role === 'owner' && <AllocationForm agencyId={a.id} blockId={b.id} disabled={b.domestic_sale_disabled} onDone={r.reload}/>}</>}</Card>
      <Card title="مبالغ (نمای آژانس فروشنده)"><MoneyBreakdown view="agency_seller" data={b.money}/></Card></div>
    <Link className="pn-link" href="/agency/inventory/flights">بازگشت به فهرست پروازها</Link>
  </>}</Loaded>;
}
function ReleaseButton({agencyId, blockId, q, onDone}: {agencyId: string; blockId: string; q: Allocation; onDone: () => void}) {
  const act = useAction();
  return <><button className="as-btn ghost" type="button" disabled={act.busy} onClick={() => void act.run(api => api.post(`/agency/${agencyId}/charter/blocks/${blockId}/allocations/${q.id}/release`, {})).then(x => {if (x) onDone();})}>آزادسازی</button><Feedback error={act.error}/></>;
}
function AllocationForm({agencyId, blockId, disabled, onDone}: {agencyId: string; blockId: string; disabled: boolean; onDone: () => void}) {
  const partners = useLoad<{items: {id: string; name: string}[]}>(`/agency/${agencyId}/charter/partners`); const [f, setF] = useState({agency_id: '', seats: '', note: ''}); const act = useAction();
  const send = () => act.run(api => api.post(`/agency/${agencyId}/charter/blocks/${blockId}/allocations`, {agency_id: f.agency_id, seats: Number(parseRial(f.seats)), note: f.note || null}), 'سهمیه ثبت شد.').then(x => {if (x) {setF({agency_id: '', seats: '', note: ''}); onDone();}});
  if (disabled) return <Unavail title="سهمیهٔ چارتر داخلی">تا فعال شدن فروش چارتر داخلی، سهمیه‌دهی به همکاران هم غیرفعال است.</Unavail>;
  return <form className="b2b-section" onSubmit={e => {e.preventDefault(); void send();}}><b>سهمیهٔ تازه</b><div className="b2b-grid3">
    <Field label="آژانس گیرنده"><select required value={f.agency_id} onChange={e => setF({...f, agency_id: e.target.value})}><option value="">انتخاب کنید</option>{partners.state.kind === 'ready' && partners.state.data.items.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
    <Field label="تعداد صندلی"><input required inputMode="numeric" value={f.seats} onChange={e => setF({...f, seats: e.target.value})} dir="ltr"/></Field>
    <Field label="یادداشت"><input value={f.note} onChange={e => setF({...f, note: e.target.value})}/></Field></div>
    <p className="as-muted">صندلی‌های سهمیه از فروش عمومی خارج می‌شوند و در زمان release بلوک خودکار برمی‌گردند. آژانس گیرنده با نرخ همین بلوک از حساب خودش می‌خرد.</p>
    <Feedback error={act.error} done={act.done}/><div className="as-actions"><button className="as-btn" type="submit" disabled={act.busy}>ثبت سهمیه</button></div></form>;
}
