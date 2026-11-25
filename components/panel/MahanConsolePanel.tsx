'use client';
/* Staff-only Mahan (W5) test console: status → search → price check (FareQuote) → seat hold (PNR). Ticket issuance stays
   disabled until the owner approves it. Every figure comes from /flights/suppliers/mahan/*; nothing is invented here,
   and an unavailable provider is shown with the reason the API gives. The public search page is not touched. */
import {useState, type FormEvent} from 'react';
import {ApiError} from '../../lib/api/karenseir-client';
import {persianDigits} from '../../lib/domain/jalali';
import {afterHold, apiProblem, emptyPassengers, isPhone, MODE_FA, newHoldKey, normalizePhone, PAX_FA, REASON_FA, searchBody, validatePassenger,
  type PassengerBody, type PassengerForm, type SearchForm} from '../../lib/mahan-console';
import {Async, Badge, Card, Empty, Stats, Table, Unavailable, dateFa, fa, money, useLoad} from './PanelKit';
import {Note} from './CommercePanel';

type Status = {provider: string; mode: string; enabled: boolean; reason: string; missing_settings: string[]; test_inventory: boolean; ticket_issuance: string};
type Segment = {carrier: string; flight_number: string; origin: string; destination: string; departs_at: string; arrives_at: string};
type Offer = {offer_ref: string; indicative_adult_fare: number; currency: string; booking_class: string; expires_at: string; refundable: boolean | null; segments: Segment[]};
type SearchResult = {status: 'ok' | 'unavailable'; reason?: string; message?: string; retryable?: boolean; test_inventory?: boolean; price_note?: string; offers: Offer[]};
type PerPax = {type: string; count: number; unit_amount: number};
type Priced = {status: 'ok' | 'price_changed'; total_amount: number; currency: string; per_passenger: PerPax[]; previous_amount?: number; delta?: number; test_inventory?: boolean};
type HoldResult = {hold_id: string; status: string; record_locator?: string; total_amount?: number; currency?: string; test_booking?: boolean; message?: string; previous_amount?: number};
type HoldRow = {hold_id: string; created_at: string | null; status: string; record_locator: string | null; total_amount: number | null; currency: string | null; test_booking: boolean | null; error_code: string | null};
type Msg = {ok: boolean; text: string} | null;

const PAX_KEY_FA: Record<string, string> = {adult: 'بزرگسال', child: 'کودک', infant: 'نوزاد'};
const HOLD_STATUS_FA: Record<string, string> = {held: 'نگه‌داشته (PNR)', unknown: 'نامعلوم — بررسی دستی', not_held: 'ثبت نشد', price_changed: 'قیمت تغییر کرد', in_progress: 'در حال انجام'};
const today = () => {const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;};
/** Airport-local wall time as Mahan gives it (the ISO string carries the airport offset), shown without re-zoning. */
const localTime = (iso: string) => {const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/); return m ? `${dateFa(m[1])} — ${persianDigits(m[2])}` : '—';};
const problemOf = (e: unknown, fallback: string) => e instanceof ApiError ? {status: e.status, ...apiProblem(e.detail, e.message || fallback)} : {status: 0, code: undefined, message: 'ارتباط با سرور برقرار نشد.'};

export function MahanConsole() {
  const status = useLoad<Status>('/flights/suppliers/mahan/status');
  const holds = useLoad<{items: HoldRow[]}>('/flights/suppliers/mahan/holds?limit=30');
  const api = status.api;

  const [form, setForm] = useState<SearchForm>({origin: 'IKA', destination: 'BKK', depart_on: '', return_on: '', trip: 'one_way', adults: '1', children: '0', infants: '0'});
  const [searching, setSearching] = useState(false); const [searchMsg, setSearchMsg] = useState<Msg>(null);
  const [result, setResult] = useState<SearchResult | null>(null); const [party, setParty] = useState({adults: 1, children: 0, infants: 0, depart_on: ''});

  const [offer, setOffer] = useState<Offer | null>(null); const [priced, setPriced] = useState<Priced | null>(null);
  const [pricing, setPricing] = useState(false); const [priceMsg, setPriceMsg] = useState<Msg>(null);

  const [pax, setPax] = useState<PassengerForm[]>([]); const [phone, setPhone] = useState(''); const [touched, setTouched] = useState(false);
  const [holdKey, setHoldKey] = useState<string | null>(null); const [holding, setHolding] = useState(false);
  const [hold, setHold] = useState<HoldResult | null>(null); const [holdMsg, setHoldMsg] = useState<Msg>(null); const [locked, setLocked] = useState<'done' | 'stop' | null>(null);

  const set = (k: keyof SearchForm) => (v: string) => setForm(f => ({...f, [k]: v}));
  const searchErrors = searchBody(form, today()).errors;

  async function search(e: FormEvent) {
    e.preventDefault(); setSearchMsg(null);
    const {body, errors} = searchBody(form, today());
    if (!body) {setSearchMsg({ok: false, text: errors.join(' ')}); return;}
    setSearching(true); setResult(null); setOffer(null); setPriced(null); setHold(null); setLocked(null); setHoldKey(null);
    try {
      const r = await api.post<SearchResult>('/flights/suppliers/mahan/search', body);
      setResult(r); setParty({adults: body.adults, children: body.children, infants: body.infants, depart_on: body.depart_on});
      if (r.status !== 'ok') setSearchMsg({ok: false, text: `${r.message ?? 'جست‌وجو انجام نشد.'}${r.reason ? ` (${REASON_FA[r.reason] ?? r.reason})` : ''}${r.retryable ? ' — می‌توانید دوباره تلاش کنید.' : ''}`});
    } catch (x) {const p = problemOf(x, 'جست‌وجو انجام نشد.'); setSearchMsg({ok: false, text: p.message});}
    finally {setSearching(false);}
  }

  async function revalidate(o: Offer) {
    setOffer(o); setPriced(null); setPriceMsg(null); setHold(null); setHoldMsg(null); setLocked(null); setHoldKey(null); setTouched(false);
    setPax(prev => prev.length === party.adults + party.children + party.infants ? prev : emptyPassengers(party));
    setPricing(true);
    try {
      const r = await api.post<Priced>('/flights/suppliers/mahan/revalidate', {offer_ref: o.offer_ref, ...(priced && offer?.offer_ref === o.offer_ref ? {expected_total: priced.total_amount} : {})});
      setPriced(r);
      setPriceMsg(r.status === 'price_changed' ? {ok: false, text: `قیمت نسبت به استعلام قبلی تغییر کرد: ${money(r.previous_amount, r.currency)} ← ${money(r.total_amount, r.currency)}.`} : {ok: true, text: 'قیمت قطعی از ماهان دریافت شد.'});
    } catch (x) {const p = problemOf(x, 'بررسی قیمت انجام نشد.'); setPriceMsg({ok: false, text: p.message});}
    finally {setPricing(false);}
  }

  const checks = pax.map(p => validatePassenger(p, today(), party.depart_on || today()));
  const phoneOk = isPhone(phone);
  const formOk = pax.length > 0 && checks.every(c => c.body) && phoneOk;

  async function submitHold(e: FormEvent) {
    e.preventDefault(); setTouched(true); setHoldMsg(null);
    if (!offer || !priced || locked) return;
    if (!formOk) {setHoldMsg({ok: false, text: 'اطلاعات مسافران یا شمارهٔ تماس کامل نیست؛ خطاهای زیر فیلدها را ببینید.'}); return;}
    const key = holdKey ?? newHoldKey(); setHoldKey(key);            // a fresh key per attempt; reused only when the outcome is unknown
    const body = {offer_ref: offer.offer_ref, expected_total: priced.total_amount, contact_phone: normalizePhone(phone), passengers: checks.map(c => c.body as PassengerBody)};
    setHolding(true);
    try {
      const r = await api.post<HoldResult>('/flights/suppliers/mahan/hold', body, key);
      setHold(r);
      const next = afterHold({status: r.status});
      if (next === 'done' || next === 'stop') setLocked(next);
      if (next === 'new') setHoldKey(null);
      setHoldMsg(r.status === 'held' ? {ok: true, text: r.message ?? 'صندلی نگه داشته شد.'} : r.status === 'unknown' ? {ok: false, text: r.message ?? 'نتیجهٔ رزرو نامعلوم است؛ دوباره رزرو نکنید.'} : {ok: false, text: `نتیجه: ${HOLD_STATUS_FA[r.status] ?? r.status}`});
      holds.reload();
    } catch (x) {
      const p = problemOf(x, 'رزرو موقت انجام نشد.');
      const next = afterHold({httpStatus: p.status, code: p.code});
      if (next === 'new') setHoldKey(null);
      const d = x instanceof ApiError ? x.detail as {total_amount?: number; per_passenger?: PerPax[]; currency?: string} | undefined : undefined;
      if (p.code === 'PRICE_CHANGED' && d && typeof d.total_amount === 'number') {
        setPriced({status: 'price_changed', total_amount: d.total_amount, currency: d.currency ?? 'IRR', per_passenger: d.per_passenger ?? [], previous_amount: priced.total_amount});
        setHoldMsg({ok: false, text: `قیمت هنگام رزرو تغییر کرد و رزروی انجام نشد. مبلغ تازه: ${money(d.total_amount, d.currency)}. اگر قبول دارید، دوباره «رزرو موقت» را بزنید.`});
      } else if (next === 'reuse') {
        setHoldMsg({ok: false, text: `${p.message} وضعیت این تلاش روشن نیست؛ «تلاش دوباره» همان درخواست را با همان کلید می‌فرستد تا رزرو تکراری ساخته نشود. پیش از آن فهرست رزروهای اخیر را ببینید.`});
      } else setHoldMsg({ok: false, text: p.message});
      holds.reload();
    } finally {setHolding(false);}
  }

  const setP = (i: number, k: keyof PassengerForm, v: string) => setPax(list => list.map((p, j) => j === i ? {...p, [k]: v} : p));
  const err = (i: number, k: keyof PassengerForm) => touched ? checks[i]?.errors[k] : undefined;

  return <>
    <Async state={status.state}>{st => <>
      {st.mode === 'qaa' && <div className="pn-note" role="note" data-state="qaa" style={{background: '#fff4d6', color: '#7a4b00', fontWeight: 700}}>
        محیط آزمایشی ماهان (QAA): همهٔ جست‌وجوها و رزروهای این صفحه آزمایشی‌اند و بلیت واقعی نیستند. روی QAA فقط مسیر IKA ↔ BKK قیمت دارد.</div>}
      {st.mode === 'live' && <div className="pn-note error" role="note" data-state="live" style={{fontWeight: 700}}>
        محیط عملیاتی ماهان (Live): رزرو موقت در این حالت یک PNR واقعی می‌سازد. فقط برای کار واقعی استفاده کنید.</div>}
      {!st.enabled && <Unavailable title="اتصال ماهان فعال نیست">{REASON_FA[st.reason] ?? st.reason}{st.missing_settings.length > 0 && <> تنظیمات جاافتاده: <span dir="ltr">{st.missing_settings.join('، ')}</span></>}</Unavailable>}
      <Card title="وضعیت اتصال ماهان">
        <Stats items={[{label: 'حالت', value: MODE_FA[st.mode] ?? st.mode}, {label: 'وضعیت', value: st.enabled ? 'فعال' : 'غیرفعال', hint: REASON_FA[st.reason] ?? st.reason},
          {label: 'موجودی', value: st.test_inventory ? 'آزمایشی' : st.mode === 'live' ? 'واقعی' : '—'}, {label: 'صدور بلیت', value: 'غیرفعال', hint: 'تا تأیید مالک'}]}/>
        <p className="pn-muted">تنظیمات جاافتاده (فقط نام، بدون مقدار): {st.missing_settings.length ? <span dir="ltr">{st.missing_settings.join('، ')}</span> : 'هیچ'}</p>
      </Card>
    </>}</Async>

    <Card title="جست‌وجوی پرواز ماهان"><form className="pn-form" onSubmit={search} noValidate>
      <label htmlFor="mh-origin">مبدأ (کد فرودگاه)<input id="mh-origin" dir="ltr" maxLength={3} value={form.origin} onChange={e => set('origin')(e.target.value.toUpperCase())} required/></label>
      <label htmlFor="mh-dest">مقصد (کد فرودگاه)<input id="mh-dest" dir="ltr" maxLength={3} value={form.destination} onChange={e => set('destination')(e.target.value.toUpperCase())} required/></label>
      <label htmlFor="mh-trip">نوع سفر<select id="mh-trip" value={form.trip} onChange={e => set('trip')(e.target.value)}><option value="one_way">یک‌طرفه</option><option value="round_trip">رفت و برگشت</option></select></label>
      <label htmlFor="mh-dep">تاریخ رفت (میلادی)<input id="mh-dep" dir="ltr" inputMode="numeric" placeholder="2026-12-01" value={form.depart_on} onChange={e => set('depart_on')(e.target.value)} required/></label>
      {form.trip === 'round_trip' && <label htmlFor="mh-ret">تاریخ برگشت (میلادی)<input id="mh-ret" dir="ltr" inputMode="numeric" placeholder="2026-12-05" value={form.return_on} onChange={e => set('return_on')(e.target.value)} required/></label>}
      <label htmlFor="mh-ad">بزرگسال<input id="mh-ad" inputMode="numeric" value={form.adults} onChange={e => set('adults')(e.target.value)}/></label>
      <label htmlFor="mh-ch">کودک (۲ تا ۱۱ سال)<input id="mh-ch" inputMode="numeric" value={form.children} onChange={e => set('children')(e.target.value)}/></label>
      <label htmlFor="mh-in">نوزاد (زیر ۲ سال)<input id="mh-in" inputMode="numeric" value={form.infants} onChange={e => set('infants')(e.target.value)}/></label>
      <button className="pn-btn" disabled={searching}>{searching ? 'در حال جست‌وجو…' : 'جست‌وجو'}</button>
    </form>
      <p className="pn-muted">تاریخ‌ها میلادی‌اند؛ ارقام فارسی هم پذیرفته می‌شوند.{form.depart_on && searchErrors.length > 0 && <> {searchErrors[0]}</>}</p>
      <Note msg={searchMsg}/>
      {result?.status === 'ok' && <>
        {result.price_note && <p className="pn-muted">{result.price_note}</p>}
        <Table rows={result.offers} rowKey={r => r.offer_ref} empty="ماهان برای این مسیر و تاریخ پرواز قابل‌فروشی برنگرداند." cols={[
          {label: 'پرواز', cell: r => r.segments.map(s => <div key={s.flight_number + s.departs_at} dir="ltr" style={{textAlign: 'right'}}>{s.carrier}{s.flight_number} {s.origin}→{s.destination}</div>)},
          {label: 'حرکت', cell: r => r.segments.map(s => <div key={s.departs_at}>{localTime(s.departs_at)}</div>)},
          {label: 'رسیدن', cell: r => r.segments.map(s => <div key={s.arrives_at}>{localTime(s.arrives_at)}</div>)},
          {label: 'کلاس', cell: r => <span dir="ltr">{r.booking_class}</span>},
          {label: 'قیمت تقریبی هر بزرگسال', cell: r => money(r.indicative_adult_fare, r.currency)},
          {label: '', cell: r => <button type="button" className="pn-btn ghost" disabled={pricing} onClick={() => revalidate(r)}>بررسی قیمت</button>}]}/>
      </>}
    </Card>

    {offer && <Card title="پرواز انتخاب‌شده">
      <p dir="ltr" style={{textAlign: 'right'}}>{offer.segments.map(s => `${s.carrier}${s.flight_number} ${s.origin}→${s.destination}`).join(' / ')} — {offer.booking_class}</p>
      {pricing && <p className="pn-muted" role="status">در حال استعلام قیمت قطعی از ماهان…</p>}
      <Note msg={priceMsg}/>
      {priced && <>
        <Stats items={[{label: 'مبلغ قابل رزرو', value: money(priced.total_amount, priced.currency), hint: priced.status === 'price_changed' ? 'قیمت تغییر کرده' : 'قیمت قطعی'},
          ...priced.per_passenger.map(p => ({label: `${PAX_KEY_FA[p.type] ?? p.type} × ${fa(p.count)}`, value: money(p.unit_amount, priced.currency), hint: 'هر نفر'}))]}/>
        <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8}}>
          <button type="button" className="pn-btn ghost" disabled={pricing} onClick={() => revalidate(offer)}>بررسی دوبارهٔ قیمت</button>
        </div>
      </>}
    </Card>}

    {offer && priced && <Card title="رزرو موقت (نگه‌داشتن صندلی)"><form className="pn-form" onSubmit={submitHold} noValidate>
      {pax.map((p, i) => <fieldset key={i} style={{flexBasis: '100%', border: '1px solid #e6dccf', borderRadius: 14, padding: 12, display: 'flex', flexWrap: 'wrap', gap: 10}}>
        <legend style={{fontWeight: 700}}>مسافر {fa(i + 1)} — {PAX_FA[p.type]}</legend>
        {([['first_name', 'نام (لاتین)'], ['last_name', 'نام خانوادگی (لاتین)']] as [keyof PassengerForm, string][]).map(([k, l]) =>
          <label key={k} htmlFor={`mh-${k}-${i}`}>{l}<input id={`mh-${k}-${i}`} dir="ltr" autoComplete="off" value={p[k]} onChange={e => setP(i, k, e.target.value)} aria-invalid={!!err(i, k)} aria-describedby={err(i, k) ? `mh-${k}-${i}-e` : undefined}/>{err(i, k) && <small id={`mh-${k}-${i}-e`} className="pn-field-error" style={{color: '#9b2414'}}>{err(i, k)}</small>}</label>)}
        <label htmlFor={`mh-gender-${i}`}>جنسیت<select id={`mh-gender-${i}`} value={p.gender} onChange={e => setP(i, 'gender', e.target.value)} aria-invalid={!!err(i, 'gender')}><option value="">—</option><option value="M">مرد</option><option value="F">زن</option></select>{err(i, 'gender') && <small style={{color: '#9b2414'}}>{err(i, 'gender')}</small>}</label>
        <label htmlFor={`mh-birth-${i}`}>تاریخ تولد (میلادی)<input id={`mh-birth-${i}`} dir="ltr" inputMode="numeric" placeholder="1990-05-21" value={p.birth_date} onChange={e => setP(i, 'birth_date', e.target.value)} aria-invalid={!!err(i, 'birth_date')}/>{err(i, 'birth_date') && <small style={{color: '#9b2414'}}>{err(i, 'birth_date')}</small>}</label>
        <label htmlFor={`mh-doctype-${i}`}>نوع مدرک<select id={`mh-doctype-${i}`} value={p.document_type} onChange={e => setP(i, 'document_type', e.target.value)}><option value="P">گذرنامه</option><option value="I">کارت ملی</option></select></label>
        <label htmlFor={`mh-doc-${i}`}>شمارهٔ مدرک<input id={`mh-doc-${i}`} dir="ltr" autoComplete="off" value={p.document_number} onChange={e => setP(i, 'document_number', e.target.value)} aria-invalid={!!err(i, 'document_number')}/>{err(i, 'document_number') && <small style={{color: '#9b2414'}}>{err(i, 'document_number')}</small>}</label>
        <label htmlFor={`mh-exp-${i}`}>اعتبار مدرک تا (میلادی)<input id={`mh-exp-${i}`} dir="ltr" inputMode="numeric" placeholder="2030-01-31" value={p.document_expiry} onChange={e => setP(i, 'document_expiry', e.target.value)} aria-invalid={!!err(i, 'document_expiry')}/>{err(i, 'document_expiry') && <small style={{color: '#9b2414'}}>{err(i, 'document_expiry')}</small>}</label>
        <label htmlFor={`mh-nat-${i}`}>ملیت (کد سه‌حرفی)<input id={`mh-nat-${i}`} dir="ltr" maxLength={3} value={p.nationality} onChange={e => setP(i, 'nationality', e.target.value.toUpperCase())} aria-invalid={!!err(i, 'nationality')}/>{err(i, 'nationality') && <small style={{color: '#9b2414'}}>{err(i, 'nationality')}</small>}</label>
      </fieldset>)}
      <label htmlFor="mh-phone">شمارهٔ تماس رزرو<input id="mh-phone" dir="ltr" inputMode="tel" placeholder="09121234567" value={phone} onChange={e => setPhone(e.target.value)} aria-invalid={touched && !phoneOk}/>{touched && !phoneOk && <small style={{color: '#9b2414'}}>شمارهٔ تماس ۱۰ تا ۱۵ رقم است (ارقام فارسی هم پذیرفته می‌شود).</small>}</label>
      <button className="pn-btn" disabled={holding || !!locked}>{holding ? 'در حال رزرو…' : holdKey ? 'تلاش دوباره' : 'رزرو موقت'}</button>
    </form>
      <p className="pn-muted">مبلغ رزرو: {money(priced.total_amount, priced.currency)}. اگر ماهان قیمت را عوض کرده باشد، رزروی انجام نمی‌شود و مبلغ تازه نمایش داده می‌شود.</p>
      <Note msg={holdMsg}/>
      {hold && <div style={{marginTop: 10}}>
        <Stats items={[{label: 'وضعیت', value: HOLD_STATUS_FA[hold.status] ?? hold.status}, {label: 'کد رزرو ماهان (PNR)', value: hold.record_locator ?? '—'},
          {label: 'مبلغ', value: hold.total_amount !== undefined ? money(hold.total_amount, hold.currency) : '—'}, {label: 'نوع', value: hold.test_booking ? 'رزرو آزمایشی (QAA)' : hold.test_booking === false ? 'رزرو واقعی' : '—'}]}/>
        <p className="pn-muted">شناسهٔ پیگیری: <span dir="ltr">{hold.hold_id}</span></p>
        {hold.status === 'unknown' && <p className="pn-note error" role="alert">پاسخ ماهان گم شد و ممکن است PNR ساخته شده باشد. دوباره رزرو نکنید؛ وضعیت را با NRSRT در سامانهٔ ماهان بررسی کنید.</p>}
      </div>}
      <div style={{display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 10}}>
        <button type="button" className="pn-btn" disabled aria-disabled="true" aria-describedby="mh-issue-why">صدور بلیت</button>
        <span id="mh-issue-why" className="pn-muted">صدور بلیت ماهان مالی و برگشت‌ناپذیر است و تا تأیید کتبی مالک و اتصال پرداخت غیرفعال است. رزرو موقت فقط صندلی را نگه می‌دارد.</span>
      </div>
    </Card>}

    <Card title="رزروهای موقت اخیر ماهان" action={<button type="button" className="pn-btn ghost" onClick={holds.reload}>به‌روزرسانی</button>}>
      <Async state={holds.state}>{d => d.items.length === 0 ? <Empty>هنوز رزرو موقتی ثبت نشده است.</Empty> : <Table rows={d.items} rowKey={r => r.hold_id} empty="—" cols={[
        {label: 'زمان', cell: r => r.created_at ? new Date(r.created_at).toLocaleString('fa-IR', {dateStyle: 'medium', timeStyle: 'short'}) : '—'},
        {label: 'وضعیت', cell: r => r.status === 'held' ? <Badge status="held"/> : <span className="pn-badge">{HOLD_STATUS_FA[r.status] ?? r.status}</span>},
        {label: 'PNR', cell: r => <span dir="ltr">{r.record_locator ?? '—'}</span>},
        {label: 'مبلغ', cell: r => r.total_amount !== null ? money(r.total_amount, r.currency) : '—'},
        {label: 'نوع', cell: r => r.test_booking ? 'آزمایشی' : r.test_booking === false ? 'واقعی' : '—'},
        {label: 'خطا', cell: r => r.error_code ?? '—'},
        {label: 'شناسه', cell: r => <span dir="ltr" style={{fontSize: 11}}>{r.hold_id.slice(0, 8)}</span>}]}/>}</Async>
    </Card>
  </>;
}
