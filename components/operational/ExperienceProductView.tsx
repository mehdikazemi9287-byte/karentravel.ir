'use client';
import Link from 'next/link';
import { useRouter,useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError, newId } from '../../lib/api/karenseir-client';
import {ContactOptions} from '../customer/CustomerHelp';
import {JourneyShell as Shell} from '../journey/JourneyShell';

const money=(value:number,currency='IRR')=>`${value.toLocaleString('fa-IR')} ${currency==='IRR'?'ریال':currency}`;
function failure(error: unknown) { return error instanceof ApiError&&error.status===409?'قیمت، ظرفیت یا وضعیت این خدمت تغییر کرده است؛ دوباره بررسی کنید.':'دریافت یا ثبت درخواست انجام نشد؛ دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.'; }
const verticalLabels: Record<string, string> = { restaurant: 'رستوران و کافه', event_hall: 'رویداد و تالار', pool_sport: 'استخر و ورزش', attraction: 'اماکن گردشگری و تفریحی' };

type TicketType = { id: string; code: string; label: string; price: number; currency: string; quota: number | null; active: boolean;min_age?:number|null;max_age?:number|null;restrictions?:{entry_rules?:string[]} };
type SessionRow = { id: string; starts_at: string; ends_at: string; capacity_available: number; status: string;restrictions?:{entry_rules?:string[]} };
type Place = { id: string; name: string; city: string; address: string | null;amenities?:string[] };
type Product = { id: string; title: string; description: string; service_type: string; booking_mode: string;cancellation_policy?:{description?:string;cancellation?:{description?:string}};restrictions?:{entry_rules?:string[]} };
type Detail = { place: Place | null; product: Product; sessions: SessionRow[]; ticket_types: TicketType[] };
type PriceCheckResult = { id: string; amount: number; currency: string; expires_at: string; ticket_breakdown: Array<{ code: string; label: string; unit_price: number; quantity: number; subtotal: number }> };

export function ExperienceProductView({ productId }: { productId: string }) {
  const { api, session } = useAuth();
  const router=useRouter(),params=useSearchParams();const day=params.get('date')||params.get('depart')||'',requestedSession=params.get('session')||'';const self='/experience-products/'+productId+'?'+params.toString();
  const [detail, setDetail] = useState<Detail | null | undefined>();
  const [notice, setNotice] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [priceCheck, setPriceCheck] = useState<PriceCheckResult | null>(null);
  const [busy, setBusy] = useState(false);
  const bookingKey=useRef(newId()),generation=useRef(0);
  const[pending,setPending]=useState<{priceCheckId:string;commandId:string}|null>(null);
  const pendingStorage=useMemo(()=>{if(!session)return null;try{const claims=JSON.parse(atob(session.access_token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));return claims.sub?'karen-leisure-pending:'+JSON.stringify([claims.iss,claims.sub,session.user?.tenant,productId]):null}catch{return null}},[session,productId]);
  useEffect(()=>{setPending(null);if(!pendingStorage)return;try{const p=JSON.parse(sessionStorage.getItem(pendingStorage)||'null');if(p&&typeof p.priceCheckId==='string'&&typeof p.commandId==='string')setPending(p)}catch{}},[pendingStorage]);
  function clearPending(){setPending(null);if(pendingStorage)try{sessionStorage.removeItem(pendingStorage)}catch{}}


  useEffect(()=>{if(!session)return;let active=true;const seq=++generation.current;setPriceCheck(null);setBusy(true);api.get<Detail>(`/experience-products/${productId}`+(day?'?date='+encodeURIComponent(day):'')).then(data=>{if(!active||seq!==generation.current)return;setDetail(data);const chosen=requestedSession?data.sessions.find(x=>x.id===requestedSession):data.sessions[0];setSessionId(chosen?.id||'');if(requestedSession&&!chosen)setNotice('زمان انتخاب‌شده دیگر در دسترس نیست؛ زمان دیگری را خودت انتخاب کن.');const query=new URLSearchParams(window.location.search);let saved:Record<string,unknown>={};try{saved=JSON.parse(query.get('selection')||'{}')}catch{};const initial:Record<string,number>={};for(const ticket of data.ticket_types){const value=saved?.[ticket.id]??(ticket.code==='adult'?Number(query.get('adults')||0):ticket.code==='child'?Number(query.get('children')||0):0);initial[ticket.id]=typeof value==='number'&&Number.isInteger(value)&&value>=0&&value<=50?value:0}setQuantities(initial)}).catch(error=>{if(active){setDetail(null);setNotice(failure(error))}}).finally(()=>{if(active&&seq===generation.current)setBusy(false)});return()=>{active=false}},[api,productId,session,day,requestedSession]);
  function setQuantity(ticketTypeId:string,value:number){if(busy||pending)return;const next={...quantities,[ticketTypeId]:Math.max(0,Math.min(50,value))};setQuantities(next);setPriceCheck(null);const p=new URLSearchParams(window.location.search);p.set('selection',JSON.stringify(next));window.history.replaceState(null,'','?'+p)}

  async function runPriceCheck() {
    if(busy||pending)return;const seq=generation.current;
    const selections = Object.entries(quantities).filter(([, quantity]) => quantity > 0).map(([ticket_type_id, quantity]) => ({ ticket_type_id, quantity }));
    if (!sessionId || selections.length === 0) { setNotice('حداقل یک بلیت را انتخاب کنید.'); return; }
    setBusy(true); setNotice('');
    try {
      const result = await api.post<PriceCheckResult>(`/leisure-sessions/${sessionId}/price-check`, { selections, command_id: newId() });
      if(seq===generation.current){setPriceCheck(result);bookingKey.current=newId();}
    } catch (error) { setNotice(failure(error)); } finally { setBusy(false); }
  }

  async function confirmReservation(){if((!priceCheck&&!pending)||busy)return;const command=pending||{priceCheckId:priceCheck!.id,commandId:bookingKey.current};setBusy(true);setNotice('');setPending(command);if(pendingStorage)try{sessionStorage.setItem(pendingStorage,JSON.stringify(command))}catch{}try{const reservation=await api.post<{id:string}>('/orchestration/bookings',{price_check_id:command.priceCheckId,command_id:command.commandId});clearPending();router.push(`/checkout/${reservation.id}`)}catch(error){if(error instanceof ApiError&&[409,422].includes(error.status)){clearPending();setPriceCheck(null);setNotice('استعلام قبلی قابل استفاده نیست؛ قیمت و ظرفیت را دوباره بررسی کن.')}else setNotice('پاسخ رزرو دریافت نشد. برای جلوگیری از درخواست تکراری، همین درخواست قبلی را پیگیری کن.')}finally{setBusy(false)}}
  const pendingNotice=pending&&<section className="panel leisure-pending"><h2>پیگیری درخواست رزرو قبلی</h2><p>نتیجهٔ درخواست قبلی هنوز روشن نیست. پیگیری با همان شناسه انجام می‌شود.</p><button className="button primary" disabled={busy} onClick={()=>void confirmReservation()}>پیگیری همان درخواست</button> <Link href="/trips">بررسی سفرهای من</Link></section>;

  if (!session) return <Shell><div className="journey-main leisure-product" style={{ paddingTop: 24 }}>{pendingNotice}<p className="panel">برای مشاهده جزئیات و رزرو <Link href={"/login?redirect="+encodeURIComponent(self)}>وارد شوید</Link>.</p></div></Shell>;
  if (detail === undefined) return <Shell><div className="journey-main leisure-product" style={{ paddingTop: 24 }}>{pendingNotice}در حال دریافت اطلاعات…</div></Shell>;
  if (!detail) return <Shell><div className="journey-main leisure-product" style={{ paddingTop: 24 }}>{pendingNotice}<p className="panel">{notice || 'این خدمت پیدا نشد.'}</p></div></Shell>;

  const { place, product, sessions, ticket_types: ticketTypes } = detail;
  if(['DISCOVERY_ONLY','VENUE_INQUIRY'].includes(product.booking_mode))return <Shell><section className="container customer-page"><h1>{product.title}</h1><p>{product.description}</p><p>این خدمت با استعلام و هماهنگی مسئول رزرو ارائه می‌شود؛ قیمت و ظرفیت نهایی هنوز تأیید نشده است.</p><ContactOptions/></section></Shell>;
  const entryRules=[product.restrictions?.entry_rules,sessions.find(s=>s.id===sessionId)?.restrictions?.entry_rules].flatMap(v=>Array.isArray(v)?v.filter(x=>typeof x==='string'):[]);
  const wholeVenue=product.service_type==='event_hall'&&product.booking_mode==='FIXED_PACKAGE';

  return <Shell><div className="journey-main leisure-product" style={{ paddingTop: 24, paddingBottom: 40 }}>{pendingNotice}
    <span className="eyebrow">{verticalLabels[product.service_type] ?? product.service_type}</span>
    <h1>{product.title}</h1>
    {place && <p>{place.name} · {place.city}{place.address ? ` · ${place.address}` : ''}</p>}
    {product.description && <p>{product.description}</p>}
    {Array.isArray(place?.amenities)&&place.amenities.length>0&&<section className="panel"><h2>امکانات اعلام‌شده</h2><ul>{place.amenities.filter(v=>typeof v==='string').map((v,i)=><li key={i}>{v}</li>)}</ul></section>}
    {(product.cancellation_policy?.description||product.cancellation_policy?.cancellation?.description)&&<section className="panel"><h2>شرایط خدمت و لغو</h2>{typeof product.cancellation_policy.description==='string'&&<p>{product.cancellation_policy.description}</p>}{typeof product.cancellation_policy.cancellation?.description==='string'&&<p>{product.cancellation_policy.cancellation.description}</p>}</section>}
    {entryRules.length>0&&<section className="panel"><h2>شرایط پذیرش این انتخاب</h2>{entryRules.map((rule,i)=><p key={i}>{rule}</p>)}</section>}
    {notice && <p role="status" className="results-notice">{notice}</p>}

    <section className="panel" style={{ marginTop: 20 }}>
      <h2>تاریخ و سانس</h2><label>تاریخ حضور<input type="date" aria-label="تاریخ حضور خدمت" value={day} disabled={busy||!!pending} onChange={e=>{const p=new URLSearchParams(params.toString());p.set('date',e.target.value);p.delete('depart');p.delete('session');router.replace('/experience-products/'+productId+'?'+p)}}/></label>
      {sessions.length === 0 ? <p>در حال حاضر سانس فعالی برای این خدمت ثبت نشده است.</p> : <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
        {sessions.map(row => <button type="button" key={row.id} disabled={busy||!!pending} aria-pressed={sessionId===row.id} onClick={()=>{const p=new URLSearchParams(params.toString());p.set('session',row.id);router.replace('/experience-products/'+productId+'?'+p)}} className={sessionId === row.id ? 'active' : ''} style={{ padding: '8px 14px', borderRadius: 10, border: '1px solid var(--line)', background: sessionId === row.id ? 'var(--ink)' : '#fff', color: sessionId === row.id ? '#fff' : 'inherit' }}>
          {new Date(row.starts_at).toLocaleString('fa-IR', {dateStyle:'short',timeStyle:'short',timeZone:'Asia/Tehran'})} · {row.capacity_available.toLocaleString('fa-IR')} ظرفیت اعلام‌شده
        </button>)}
      </div>}
    </section>

    <section className="panel" style={{ marginTop: 16 }}>
      <h2>{wholeVenue?'رزرو کل تالار در بازهٔ انتخاب‌شده':product.service_type==='restaurant'?'نوع پذیرش و تعداد مهمان':'نوع بلیت'}</h2>
      {ticketTypes.length === 0 ? <p>بلیتی برای این خدمت تعریف نشده است.</p> : <div style={{ marginTop: 10 }}>
        {ticketTypes.map(ticketType => <div key={ticketType.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--line)' }}>
          <span><b>{ticketType.label}</b><small style={{ display: 'block', color: 'var(--muted)' }}>{money(ticketType.price,ticketType.currency)}</small>{(ticketType.min_age!=null||ticketType.max_age!=null)&&<small className="ticket-condition">شرط سنی: {ticketType.min_age!=null?`از ${ticketType.min_age.toLocaleString('fa-IR')} سال`:''}{ticketType.min_age!=null&&ticketType.max_age!=null?' — ':''}{ticketType.max_age!=null?`تا ${ticketType.max_age.toLocaleString('fa-IR')} سال`:''}</small>}{Array.isArray(ticketType.restrictions?.entry_rules)&&ticketType.restrictions.entry_rules.filter(rule=>typeof rule==='string').map((rule,i)=><small className="ticket-condition" key={i}>{rule}</small>)}</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button type="button" disabled={busy||!!pending||!(quantities[ticketType.id]>0)} onClick={() => setQuantity(ticketType.id, (quantities[ticketType.id] || 0) - 1)} aria-label={`کاهش ${ticketType.label}`}>−</button>
            <b>{quantities[ticketType.id] || 0}</b>
            <button type="button" disabled={busy||!!pending||(quantities[ticketType.id]||0)>=Math.min(50,ticketType.quota??50,sessions.find(s=>s.id===sessionId)?.capacity_available??0)} onClick={() => setQuantity(ticketType.id, (quantities[ticketType.id] || 0) + 1)} aria-label={`افزایش ${ticketType.label}`}>+</button>
          </span>
        </div>)}
      </div>}
      <button className="button primary" style={{ marginTop: 16 }} disabled={busy||!!pending||!sessionId||ticketTypes.length===0} onClick={() => void runPriceCheck()}>بررسی قیمت</button>
    </section>

    {priceCheck && !pending && <section className="panel" style={{ marginTop: 16 }}>
      <h2>{wholeVenue?'مبلغ کل رزرو تالار':'جمع‌بندی قیمت'}</h2>
      {priceCheck.ticket_breakdown.map(row => <p key={row.code}>{row.label} × {row.quantity.toLocaleString('fa-IR')} = {money(row.subtotal,priceCheck.currency)}</p>)}
      <p><b>مبلغ نهایی: {money(priceCheck.amount,priceCheck.currency)}</b></p>
      <button className="button primary" disabled={busy} onClick={() => void confirmReservation()}>تأیید و رزرو</button>
    </section>}
    <ContactOptions/>
  </div></Shell>;
}
