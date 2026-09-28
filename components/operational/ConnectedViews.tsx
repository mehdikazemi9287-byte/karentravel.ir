'use client';

import Link from 'next/link';
import {OpsSupportReply} from './OpsSupportReply';
import { usePathname } from 'next/navigation';
import {AccommodationRequestAction} from './AccommodationRequestAction';
import {AdmissionTickets} from './AdmissionTickets';
import { ContactOptions } from '../customer/CustomerHelp';
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useAuth } from '../../lib/api/auth-context';
import { ApiError, newId } from '../../lib/api/karenseir-client';

function MockNotice({children='نسخه نمایشی — اطلاعات این بخش نمونه است.'}:{children?:ReactNode}){return <div className="journey-mock" role="note">● {children}</div>}

type LoadState<T> = { kind: 'loading' } | { kind: 'ready'; data: T } | { kind: 'error'; status: number; message: string };
type Reservation = { id: string; booking_reference?: string | null; service_type: string; status: string; price_snapshot?: { total_amount?: number; currency?: string }; policy_at_booking?: Record<string, unknown>; created_at?: string; manage_link?: string };
type Trip = { id: string; title: string; origin?: string | null; destination: string; starts_at?: string | null; status: string; timeline_link: string };
type Notice = { id: string; title: string; message: string; deep_link?: string | null; status: string };
type Offer = { id: string; title: string; amount: number; currency: string; service_type: string; provider_status: string };

export function ErrorState({ status, message, redirect }: { status: number; message: string; redirect?: string }) {
  const pathname=usePathname();
  const title = status === 401 ? 'برای مشاهده این بخش وارد شوید.' : status === 403 ? 'نقش شما به این بخش دسترسی ندارد.' : status === 503 ? 'سرویس موردنیاز فعلاً در دسترس نیست.' : 'دریافت اطلاعات انجام نشد.';
  return <section role="alert" className="mx-auto my-8 max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 text-center"><h2 className="text-xl font-black">{title}</h2><p className="mt-2 text-sm text-slate-600">{status===401 ? "سفرها و اطلاعات شخصی شما پس از ورود نمایش داده می‌شوند." : "می‌توانید دوباره تلاش کنید یا از پشتیبانی راهنمایی بگیرید."}</p>{status===401&&<Link className="button primary mt-4" href={`/login?redirect=${encodeURIComponent(redirect||pathname)}`}>ورود به حساب</Link>}<ContactOptions/></section>;
}

function LoadingState() { return <div role="status" className="mx-auto my-8 max-w-3xl animate-pulse rounded-2xl bg-white p-8 text-center text-slate-600">در حال دریافت اطلاعات معتبر…</div>; }
function EmptyState({ children }: { children: React.ReactNode }) { return <div role="status" className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">{children}</div>; }
function errorOf(error: unknown) { return error instanceof ApiError ? { status: error.status, message: error.message } : { status: 0, message: 'خطای پیش‌بینی‌نشده رخ داد.' }; }
const money = (amount?: number, currency='IRR') => amount == null ? '—' : `${amount.toLocaleString('fa-IR')} ${currency==='IRR'?'ریال':currency}`;

export function ConnectedTrips() {
  const { api, session } = useAuth();
  const [state, setState] = useState<LoadState<{trips: Trip[]; reservations: Reservation[]; notices: Notice[]}>>({kind:'loading'});
  useEffect(() => {
    if (!session) return;
    let active=true;
    Promise.all([api.get<Trip[]>('/me/trips'),api.get<Reservation[]>('/me/reservations'),api.get<Notice[]>('/me/notifications')])
      .then(([trips,reservations,notices])=>active&&setState({kind:'ready',data:{trips,reservations,notices}}))
      .catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item});});
    return()=>{active=false};
  },[api,session]);
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;
  if(state.kind==='loading')return <LoadingState/>;
  if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;
  const {trips,reservations,notices}=state.data;
  return <div className="grid gap-6"><section><h2 className="mb-3 text-xl font-black">سفرهای معتبر</h2>{trips.length===0?<EmptyState>هنوز سفری در حساب شما ساخته نشده است.</EmptyState>:<div className="grid gap-3 sm:grid-cols-2">{trips.map(t=><Link href={t.timeline_link} key={t.id} className="rounded-2xl border border-slate-200 bg-white p-5"><span className="tag">{t.status}</span><h3 className="mt-3 font-black">{t.title}</h3><p className="text-sm text-slate-600">{t.origin?`${t.origin} ← `:''}{t.destination}</p></Link>)}</div>}</section><section><h2 className="mb-3 text-xl font-black">رزروهای من</h2>{reservations.length===0?<EmptyState>رزرو عملیاتی برای این حساب وجود ندارد.</EmptyState>:<div className="grid gap-3 sm:grid-cols-2">{reservations.map(r=><article key={r.id} className="rounded-2xl border border-slate-200 bg-white p-5"><span className="tag">{r.status}</span><h3 className="mt-3 font-black">{r.booking_reference||'در انتظار مرجع رزرو'}</h3><p>{r.service_type} · {money(r.price_snapshot?.total_amount,r.price_snapshot?.currency)}</p><Link className="text-link" href={r.manage_link||`/manage-booking/${r.id}`}>مدیریت رزرو ←</Link></article>)}</div>}</section><aside><h2 className="mb-3 text-xl font-black">اعلان‌ها</h2>{notices.length===0?<EmptyState>اعلان تازه‌ای ندارید.</EmptyState>:notices.map(n=><article className="mb-2 rounded-xl bg-cyan-50 p-4" key={n.id}><b>{n.title}</b><p className="text-sm">{n.message}</p>{n.deep_link&&<Link href={n.deep_link}>مشاهده جزئیات</Link>}</article>)}</aside></div>;
}

type TimelineEvent = { id:string; type:string; severity:string; source:string; title:string; message:string; requires_action:boolean; deep_link?:string|null };
export function SupportLanding() {
 return <><div className="journey-title"><div><span>پشتیبانی کارن تراول</span><h1>چطور می‌توانیم کمک کنیم؟</h1><p>برای راهنمایی سفر، استعلام خدمات یا پیگیری رزرو با ما تماس بگیرید.</p></div></div><ContactOptions/><section className="support-paths"><article className="support-path"><h2>پیگیری رزرو</h2><p>برای مشاهده رزرو ثبت‌شده وارد حساب خود شوید. هنگام تماس، شماره پیگیری را همراه داشته باشید.</p><Link href="/trips">سفرها و رزروهای من ←</Link></article><article className="support-path"><h2>تغییر یا لغو سفر</h2><p>شرایط و هزینهٔ تغییر به رزرو شما بستگی دارد. تماس یا ارسال درخواست به‌تنهایی تأیید لغو و بازپرداخت نیست.</p><Link href="/contact">تماس برای بررسی درخواست ←</Link></article><article className="support-path"><h2>راهنمایی پیش از سفر</h2><p>مقصد، تاریخ و تعداد مسافران را مشخص کنید تا دربارهٔ خدمت موردنیازتان پرس‌وجو کنید.</p><Link href="/services">مشاهده خدمات ←</Link></article></section><section className="panel"><h2>کد ورود به دستتان نرسیده؟</h2><p>شماره همراه را بررسی کنید. اگر دریافت کد ممکن نشد، برای راهنمایی از شماره تماس بالا استفاده کنید. کد ورودتان را در اختیار دیگران نگذارید.</p><Link href="/login">بازگشت به ورود</Link></section></>;
}

export function ConnectedTripTimeline({tripId}:{tripId:string}) {
  const {api,session}=useAuth();
  const [state,setState]=useState<LoadState<{trip:{id:string;destination:string;status:string};events:Array<TimelineEvent&{created_at?:string}>}>>({kind:'loading'});
  const [support,setSupport]=useState<Array<{id:string;kind:'support';sender_type:string;body:string;created_at:string;subject:string}>>([]);
  useEffect(()=>{if(!session)return;let active=true;
    api.get<Extract<typeof state,{kind:'ready'}>['data']>(`/trips/${tripId}/timeline`).then(data=>active&&setState({kind:'ready',data})).catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item});});
    api.get<Array<{id:string;trip_id?:string|null;subject:string;messages:Array<{id:string;sender_type:string;body:string;created_at:string}>}>>('/support/cases').then(cases=>{if(!active)return;const msgs=cases.filter(c=>c.trip_id===tripId).flatMap(c=>c.messages.map(mm=>({id:mm.id,kind:'support' as const,sender_type:mm.sender_type,body:mm.body,created_at:mm.created_at,subject:c.subject})));setSupport(msgs);}).catch(()=>{});
    return()=>{active=false};},[api,session,tripId]);
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;
  if(state.kind==='loading')return <LoadingState/>;
  if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;
  const {trip,events}=state.data;
  const iconFor=(t:string)=>t.startsWith('booking')?'📋':/cancel/.test(t)?'✕':/refund/.test(t)?'↩':/payment/.test(t)?'💳':/flight/.test(t)?'✈':/hotel/.test(t)?'🏨':/change/.test(t)?'⟳':/voucher|document/.test(t)?'🎫':'•';
  type Row={id:string;created_at:string;node:ReactNode;action:boolean;fresh:boolean};
  const eventRows:Row[]=events.map(ev=>({id:ev.id,created_at:ev.created_at||'',action:ev.requires_action,fresh:ev.severity==='warning'||ev.severity==='error'||ev.requires_action,node:(
    <article className={`rounded-xl p-4 ${ev.requires_action?'bg-amber-50 border border-amber-300':ev.severity==='error'?'bg-rose-50':ev.severity==='warning'?'bg-amber-50':'bg-slate-50'}`}>
      <div className="flex items-center gap-2 text-xs"><span aria-hidden="true">{iconFor(ev.type)}</span><span className="rounded bg-slate-200 px-2 py-0.5">سیستم · {ev.type}</span>{ev.requires_action&&<span className="rounded bg-amber-600 px-2 py-0.5 text-white">نیاز به اقدام</span>}</div>
      <h3 className="mt-2 font-bold">{ev.title}</h3><p className="text-sm text-slate-600">{ev.message}</p>
      {ev.deep_link&&<Link className="text-link mt-1 inline-block text-sm" href={ev.deep_link}>مشاهده اقدام ←</Link>}
    </article>)}));
  const supportRows:Row[]=support.map(m=>{const human=m.sender_type==='human_agent';const ai=m.sender_type==='ai';const you=m.sender_type==='customer';
    return {id:m.id,created_at:m.created_at,action:false,fresh:human,node:(
    <article className={`rounded-xl p-4 border ${human?'bg-sky-50 border-sky-400':ai?'bg-violet-50 border-violet-300':'bg-white border-slate-200'}`}>
      <div className="flex items-center gap-2 text-xs"><span aria-hidden="true">{human?'🧑‍💼':ai?'🤖':you?'🙋':'💬'}</span>
        <span className={`rounded px-2 py-0.5 ${human?'bg-sky-600 text-white':ai?'bg-violet-600 text-white':'bg-slate-200'}`}>{human?'کارشناس انسانی':ai?'پاسخ خودکار':you?'شما':'پشتیبانی'}</span>
        <span className="text-slate-500">{m.subject}</span></div>
      <p className="mt-2 text-sm">{m.body}</p>
    </article>)};});
  const rows=[...eventRows,...supportRows].sort((a,b)=>(b.created_at||'').localeCompare(a.created_at||''));
  const actionCount=rows.filter(r=>r.action).length;
  return <div className="grid gap-6"><header className="trip-hero"><div><span>سفر عملیاتی</span><h1>{trip.destination}</h1><p>وضعیت: {trip.status}</p></div></header>
    <section className="trip-timeline"><header><span>Trip Operations Center</span><h2>چه چیزی در سفر من تغییر کرده؟</h2>
      <p className="text-sm text-slate-600">{rows.length===0?'تغییری ثبت نشده است.':actionCount>0?`${actionCount.toLocaleString('fa-IR')} مورد نیاز به اقدام شما دارد.`:`${rows.length.toLocaleString('fa-IR')} رویداد در این سفر.`}</p></header>
      {rows.length===0?<EmptyState>تغییر جدیدی برای این سفر ثبت نشده است.</EmptyState>:<div className="grid gap-3">{rows.map(r=><div key={r.id}>{r.node}</div>)}</div>}
    </section>
    <p className="text-xs text-slate-500">پیام کارشناس انسانی با رنگ و برچسب مجزا از رویداد سیستمی و پاسخ خودکار نمایش داده می‌شود.</p>
  </div>;
}

const bookingStatus=(s:string)=>({booking_pending:'در انتظار پاسخ میزبان',reserved:'نگه‌داشت موقت',draft:'پیش‌نویس',held:'نگه‌داشت موقت',awaiting_payment:'در حال تکمیل رزرو',confirmed:'تأیید شده',issued:'مدارک صادر شده',changed:'تغییر ثبت شده',cancelled:'لغو شده',expired:'مهلت پایان یافته',failed:'تکمیل نشده'} as Record<string,string>)[s]||'در حال پیگیری';
export function ConnectedManageBooking({ reservationId }: { reservationId: string }) {
  const {api,session}=useAuth();
  const [state,setState]=useState<LoadState<{reservation:Reservation;history:{history:Array<{from?:string;to:string;at:string;reason?:string}>};quote?:Record<string,unknown>}>>({kind:'loading'});
  const [result,setResult]=useState('');
  useEffect(()=>{if(!session)return;let active=true;Promise.all([api.get<Reservation>(`/reservations/${reservationId}`),api.get<{history:Array<{from?:string;to:string;at:string;reason?:string}>}>(`/reservations/${reservationId}/history`),api.get<Record<string,unknown>>(`/reservations/${reservationId}/cancellation-quote`).catch(error=>{if(error instanceof ApiError&&error.status===409)return undefined;throw error;})]).then(([reservation,history,quote])=>active&&setState({kind:'ready',data:{reservation,history,quote}})).catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item});});return()=>{active=false};},[api,session,reservationId]);
  async function downloadVoucher(){try{const html=await api.getText(`/reservations/${reservationId}/voucher`);const url=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=`karen-travel-voucher-${reservationId}.html`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setResult('واچر دریافت شد؛ فایل را برای مشاهده و چاپ باز کنید.')}catch{setResult('دریافت واچر انجام نشد؛ وضعیت صدور را بررسی کنید یا دوباره تلاش کنید.')}}
  async function submit(request_type:'cancel'|'change'|'refund'){setResult('در حال ثبت درخواست…');try{const data=await api.post<{id:string;status:string}>(`/reservations/${reservationId}/service-requests`,{request_type,reason:'درخواست ثبت‌شده توسط مسافر'},newId());setResult(`درخواست شما برای بررسی ثبت شد. کد پیگیری: ${data.id}`);}catch(error){setResult(errorOf(error).message)}}
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;if(state.kind==='loading')return <LoadingState/>;if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;
  const {reservation,history,quote}=state.data;
  return <div className="grid gap-5"><article className="rounded-2xl border border-slate-200 bg-white p-6"><span className="tag">{bookingStatus(reservation.status)}</span><h1 className="mt-3 text-2xl font-black">مدیریت {reservation.booking_reference||reservation.id}</h1><p>{reservation.service_type==='handicraft'?'سفارش با تحویل حضوری':'خدمت رزروشده'} · {money(reservation.price_snapshot?.total_amount,reservation.price_snapshot?.currency)}</p>{reservation.status==='issued'?<button className="button primary" onClick={()=>void downloadVoucher()}>دریافت واچر صادرشده</button>:<p>مدارک نهایی پس از تأیید خدمت و صدور در همین صفحه قرار می‌گیرند.</p>}<>{reservation.service_type==='vacation_rental'&&<AccommodationRequestAction id={reservation.id} status={reservation.status}/>}</><Link className="text-link mt-3 inline-block" href={`/support?booking=${reservation.id}`}>گفت‌وگو با پشتیبانی انسانی ←</Link></article>{reservation.status==='issued'&&<AdmissionTickets reservationId={reservation.id}/>}<section className="rounded-2xl border border-slate-200 bg-white p-6"><h2 className="text-xl font-black">قوانین و برآورد استرداد</h2>{quote?<div><p>مبلغ سفارش: {money(typeof quote.total_amount==='number'?quote.total_amount:undefined)}</p><p>جریمه طبق شرایط: {money(typeof quote.penalty_amount==='number'?quote.penalty_amount:undefined)}</p><p>برآورد قابل استرداد: {money(typeof quote.refundable_amount==='number'?quote.refundable_amount:undefined)}</p><p>این برآورد به معنی انجام بازپرداخت نیست؛ درخواست باید بررسی شود.</p></div>:<p role="status" className="mt-3 text-slate-600">برآورد معتبر در دسترس نیست؛ مبلغ یا جریمه حدس زده نمی‌شود.</p>}<div className="mt-5 flex flex-wrap gap-2"><button className="button secondary" onClick={()=>submit('change')}>درخواست تغییر</button><button className="button secondary" onClick={()=>submit('cancel')}>درخواست کنسلی</button><button className="button primary" onClick={()=>submit('refund')}>درخواست استرداد</button></div>{result&&<p role="status" className="mt-4 rounded-xl bg-cyan-50 p-3">{result}</p>}</section><section className="rounded-2xl border border-slate-200 bg-white p-6"><h2 className="text-xl font-black">تاریخچه وضعیت</h2>{history.history.length===0?<EmptyState>تاریخچه‌ای ثبت نشده است.</EmptyState>:history.history.map((h,index)=><div className="mt-3 border-r-2 border-cyan-700 pr-4" key={`${h.at}-${index}`}><b>{h.from?bookingStatus(h.from):'شروع'} ← {bookingStatus(h.to)}</b><small className="block text-slate-500">{new Date(h.at).toLocaleString('fa-IR')}</small></div>)}</section></div>;
}

export function ConnectedCompare() {
  const {api,session}=useAuth();const search=useSyncExternalStore(()=>()=>{},()=>window.location.search,()=>'');const params=useMemo(()=>new URLSearchParams(search),[search]);const requestedType=params.get('type');const [manualType,setManualType]=useState<string|null>(null);const type=manualType||(requestedType&&['flight','hotel','train','tour','package'].includes(requestedType)?requestedType:'hotel');const selectedOfferIds=useMemo(()=>manualType?[]:(params.get('offers')||'').split(',').filter(Boolean).slice(0,4),[manualType,params]);const [state,setState]=useState<LoadState<{offers:Offer[];comparison?:{results:Array<{offer_id:string;title:string;score:number;amount:number;currency:string;breakdown:Record<string,number>;explanation:string[]}>}}>>({kind:'loading'});
  useEffect(()=>{if(!session)return;let active=true;api.post<Offer[]>('/search/offers',{service_type:type}).then(async offers=>{const chosen=selectedOfferIds.length?offers.filter(offer=>selectedOfferIds.includes(offer.id)):offers.slice(0,4);const comparison=chosen.length>=2?await api.post<{results:Array<{offer_id:string;title:string;score:number;amount:number;currency:string;breakdown:Record<string,number>;explanation:string[]}>}>('/compare/offers',{offer_ids:chosen.map(x=>x.id)}):undefined;if(active)setState({kind:'ready',data:{offers:chosen,comparison}})}).catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item});});return()=>{active=false};},[api,session,type,selectedOfferIds]);
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;
  return <div className="container compare-wrap"><label className="mb-5 block font-bold">نوع خدمت<select value={type} onChange={e=>{setManualType(e.target.value);setState({kind:'loading'})}} className="mr-3 rounded-xl border border-slate-300 p-3"><option value="flight">پرواز</option><option value="train">قطار</option><option value="hotel">هتل</option><option value="tour">تور</option><option value="package">پرواز + هتل</option></select></label>{state.kind==='loading'?<LoadingState/>:!state.data.comparison?<EmptyState>حداقل دو گزینه معتبر و هم‌نوع برای مقایسه لازم است.</EmptyState>:<div className="grid gap-4 sm:grid-cols-2">{state.data.comparison.results.map(row=><article className="rounded-2xl border border-slate-200 bg-white p-5" key={row.offer_id}><span className="tag">امتیاز {row.score.toLocaleString('fa-IR')}</span><h3 className="mt-3 text-lg font-black">{row.title}</h3><p>{money(row.amount,row.currency)}</p><ul className="mt-3 text-sm">{Object.entries(row.breakdown).map(([key,value])=><li key={key}>{key}: {value.toLocaleString('fa-IR')}</li>)}</ul></article>)}</div>}</div>;
}

export function ConnectedOrganization() {
  const {api,session}=useAuth();const [state,setState]=useState<LoadState<{organizations:Array<{id:string;name:string;status:string}>;departments:Array<{id:string;name:string;code:string}>;cost_centers:Array<{id:string;name:string;budget_amount:number}>;workflows:Array<{id:string;status:string;current_step:number;escalation_count:number}>}>>({kind:'loading'});
  useEffect(()=>{if(!session)return;let active=true;api.get<Extract<typeof state,{kind:'ready'}>['data']>('/organization/overview').then(data=>active&&setState({kind:'ready',data})).catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item});});return()=>{active=false};},[api,session]);
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;if(state.kind==='loading')return <LoadingState/>;if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;const d=state.data;
  return <div className="dashboard container"><Link className="button primary" href="/organization/structure">مدیریت واحدها و مراکز هزینه</Link><section className="metrics"><div><small>سازمان‌ها</small><strong>{d.organizations.length.toLocaleString('fa-IR')}</strong><span>داده معتبر tenant</span></div><div><small>گردش‌های تأیید</small><strong>{d.workflows.length.toLocaleString('fa-IR')}</strong><span>{d.workflows.filter(x=>x.status==='pending').length.toLocaleString('fa-IR')} در انتظار</span></div><div><small>مراکز هزینه</small><strong>{d.cost_centers.length.toLocaleString('fa-IR')}</strong><span>Backend authoritative</span></div></section><section className="dashboard-grid"><article className="panel"><div className="panel-head"><h3>گردش تأیید</h3></div>{d.workflows.length===0?<EmptyState>گردش تأییدی وجود ندارد.</EmptyState>:d.workflows.map(w=><div className="activity" key={w.id}><div><strong>{w.status}</strong><small>مرحله {w.current_step.toLocaleString('fa-IR')} · escalation {w.escalation_count.toLocaleString('fa-IR')}</small></div></div>)}</article><article className="panel"><div className="panel-head"><h3>ساختار سازمانی</h3></div>{d.organizations.map(o=><p key={o.id}><b>{o.name}</b> · {o.status}</p>)}<p>{d.departments.length.toLocaleString('fa-IR')} واحد سازمانی</p></article></section></div>;
}


type AssetRow = { id: string; entity_type: string; kind: string; visibility: string; original_filename: string; content_type: string; byte_size: number; download_url: string; created_at: string };
function SupplierAssets({ suppliers }: { suppliers: Array<{ id: string; name: string }> }) {
  const { api } = useAuth();
  const [sid, setSid] = useState(suppliers[0]?.id || '');
  const [rows, setRows] = useState<AssetRow[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState<'image' | 'document'>('image');
  const [entityType, setEntityType] = useState('supplier_profile');
  const [makePublic, setMakePublic] = useState(false);
  useEffect(() => { setSid(suppliers[0]?.id || ''); }, [suppliers]);
  const load = useCallback(async (id: string) => {
    if (!id) { setRows([]); return; }
    try { const d = await api.get<{ assets: AssetRow[] }>(`/supplier/${id}/assets`); setRows(d.assets); }
    catch (e) { setNote(e instanceof ApiError ? e.message : 'خطا در دریافت فایل‌ها'); }
  }, [api]);
  useEffect(() => { load(sid); }, [sid, load]);
  useEffect(() => {
    const revoke: string[] = [];
    (async () => {
      const next: Record<string, string> = {};
      for (const r of rows) {
        if (!r.content_type.startsWith('image/')) continue;
        try {
          const res = await fetch(`${api.apiBase}${r.download_url}`, { headers: { Authorization: `Bearer ${api.getSession()?.access_token}` } });
          if (res.ok) { const u = URL.createObjectURL(await res.blob()); next[r.id] = u; revoke.push(u); }
        } catch { /* preview is best-effort */ }
      }
      setPreviews(next);
    })();
    return () => { revoke.forEach(URL.revokeObjectURL); };
  }, [rows, api]);
  async function upload(event: FormEvent) {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem('file') as HTMLInputElement;
    const f = input.files?.[0];
    if (!f || !sid) return;
    setBusy(true); setNote('در حال بارگذاری…');
    try {
      const body = new FormData();
      body.append('file', f); body.append('entity_type', entityType); body.append('kind', kind); body.append('visibility', kind === 'image' && makePublic ? 'public' : 'private');
      await api.postForm(`/supplier/${sid}/assets`, body);
      setNote('فایل بارگذاری شد.'); input.value = ''; await load(sid);
    } catch (err) { setNote(err instanceof ApiError ? err.message : 'بارگذاری ناموفق بود.'); }
    finally { setBusy(false); }
  }
  async function replace(id: string, file: File) {
    setBusy(true); setNote('در حال جایگزینی…');
    try { const body = new FormData(); body.append('file', file); await api.putForm(`/supplier/assets/${id}/content`, body); setNote('فایل جایگزین شد.'); await load(sid); }
    catch (err) { setNote(err instanceof ApiError ? err.message : 'جایگزینی ناموفق بود.'); }
    finally { setBusy(false); }
  }
  async function remove(id: string) {
    setBusy(true); setNote('در حال حذف…');
    try { await api.delete(`/supplier/assets/${id}`, {}); setNote('فایل حذف شد.'); await load(sid); }
    catch (err) { setNote(err instanceof ApiError ? err.message : 'حذف ناموفق بود.'); }
    finally { setBusy(false); }
  }
  if (suppliers.length === 0) return null;
  const cats = kind === 'image' ? ['supplier_profile', 'product_image'] : ['license', 'contract', 'supplier_document'];
  return <section className="panel mb-5"><h2 className="font-black">تصاویر و مدارک</h2>
    {suppliers.length > 1 && <label className="mt-3 block font-bold">تأمین‌کننده<select aria-label="تأمین‌کننده" className="mt-2 block w-full rounded-xl border p-3" value={sid} onChange={e => setSid(e.target.value)}>{suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
    <form onSubmit={upload} className="mt-3 flex flex-wrap items-end gap-3">
      <label className="font-bold">نوع<select aria-label="نوع فایل" className="mt-2 block rounded-xl border p-2" value={kind} onChange={e => { const k = e.target.value as 'image' | 'document'; setKind(k); setEntityType(k === 'image' ? 'supplier_profile' : 'license'); }}><option value="image">تصویر</option><option value="document">سند</option></select></label>
      <label className="font-bold">دسته<select aria-label="دسته فایل" className="mt-2 block rounded-xl border p-2" value={entityType} onChange={e => setEntityType(e.target.value)}>{cats.map(v => <option key={v} value={v}>{v}</option>)}</select></label>
      <label className="min-w-48 flex-1 font-bold">فایل<input name="file" type="file" required accept={kind === 'image' ? 'image/png,image/jpeg,image/webp,image/gif' : 'application/pdf,image/png,image/jpeg'} className="mt-2 block w-full text-sm" /></label>
      {kind === 'image' && <label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={makePublic} onChange={e => setMakePublic(e.target.checked)} />نمایش عمومی</label>}
      <button disabled={busy || !sid} className="button primary">بارگذاری</button>
    </form>
    {note && <p role="status" className="mt-3 rounded-xl bg-cyan-50 p-3 text-sm">{note}</p>}
    {rows.length === 0 ? <p className="mt-3 text-sm text-slate-600">فایلی بارگذاری نشده است.</p> : <ul className="mt-4 space-y-3">{rows.map(r => <li key={r.id} className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-50 p-3">
      {previews[r.id] ? <img src={previews[r.id]} alt={r.original_filename} className="h-14 w-14 rounded object-cover" /> : <span className="grid h-14 w-14 place-items-center rounded bg-slate-200 text-xs">{r.kind === 'document' ? 'PDF' : 'IMG'}</span>}
      <span className="flex-1"><b className="block">{r.original_filename}</b><small className="text-slate-600">{r.entity_type} · {r.visibility === 'public' ? 'عمومی' : 'خصوصی'} · {(r.byte_size / 1024).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} KB</small>{r.visibility === 'public' && <a className="text-link block text-xs" href={`${api.apiBase}/media/public/${r.id}`} target="_blank" rel="noreferrer">لینک عمومی ↗</a>}</span>
      <label className="button secondary cursor-pointer">جایگزینی<input type="file" hidden accept={r.content_type} onChange={e => { const f = e.target.files?.[0]; if (f) replace(r.id, f); }} /></label>
      <button disabled={busy} className="button ghost" onClick={() => remove(r.id)}>حذف</button>
    </li>)}</ul>}
  </section>;
}

const panelLabels:Record<string,string>={counts:'آمار',users:'مشتریان',suppliers:'تأمین‌کنندگان',agencies:'آژانس‌ها',reservations:'رزروها',payments:'پرداخت‌ها',refunds:'استردادها',wallets:'کیف پول‌ها',notifications:'اعلان‌ها',security_events:'رویدادهای امنیتی',invoices:'صورتحساب‌ها',support_cases:'پرونده‌های پشتیبانی',providers:'اتصال خدمات',offers:'عرضه‌ها',active_offers:'عرضه‌های فعال',available_units:'ظرفیت',tenant_id:'شناسه سازمان',status:'وضعیت',mode:'حالت',detail:'توضیح',payment:'پرداخت',hotel:'هتل',flight:'پرواز',train:'قطار',otp:'ورود پیامکی',sms:'پیامک',push:'اعلان دستگاه',email:'ایمیل',supplier_inventory:'موجودی تأمین‌کننده',voucher_issuance:'صدور مدارک',tour_hotel:'هتل تور',active:'فعال',paused:'متوقف',suspended:'تعلیق',not_connected:'متصل نیست',disabled:'غیرفعال',configuration_error:'نیازمند تنظیم اتصال',configured_not_verified:'تنظیم شده؛ اتصال واقعی تأیید نشده',kavenegar:'کاوه‌نگار',mock:'غیرفعال / آزمایشی'};
function PanelValue({value}:{value:unknown}){if(value==null)return <span>—</span>;if(typeof value==='number')return <span>{value.toLocaleString('fa-IR')}</span>;if(typeof value==='boolean')return <span>{value?'بله':'خیر'}</span>;if(typeof value==='string')return <span>{panelLabels[value]||value}</span>;if(Array.isArray(value))return <ul>{value.map((v,i)=><li key={i}><PanelValue value={v}/></li>)}</ul>;return <dl>{Object.entries(value as Record<string,unknown>).map(([k,v])=><div key={k} style={{marginBlock:8,overflowWrap:'anywhere'}}><dt>{panelLabels[k]||k}</dt><dd>{k==='detail'?'وضعیت اتصال از سامانه دریافت شده؛ اتصال غیرفعال به معنی ارائهٔ خدمت نیست.':<PanelValue value={v}/>}</dd></div>)}</dl>}
type PanelKind='supplier'|'agency'|'backoffice';
const PANEL_PATHS={supplier:'/supplier/dashboard',agency:'/agency/dashboard',backoffice:'/backoffice/overview'} as const;
export function ConnectedRolePanel({kind}:{kind:PanelKind}) {
  const {api,session}=useAuth();const [state,setState]=useState<LoadState<Record<string,unknown>>>({kind:'loading'});const [result,setResult]=useState('');const [name,setName]=useState('');
  async function reload(){setState({kind:'loading'});try{setState({kind:'ready',data:await api.get<Record<string,unknown>>(PANEL_PATHS[kind])})}catch(error){const item=errorOf(error);setState({kind:'error',...item})}}
  useEffect(()=>{if(!session)return;let active=true;api.get<Record<string,unknown>>(PANEL_PATHS[kind]).then(data=>active&&setState({kind:'ready',data})).catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item});});return()=>{active=false};},[api,session,kind]);
  async function mutate(action:()=>Promise<unknown>,success:string){setResult('در حال ثبت امن…');try{await action();setResult(success);await reload()}catch(error){setResult(errorOf(error).message)}}
  async function create(event:FormEvent){event.preventDefault();if(kind==='supplier')await mutate(()=>api.post('/supplier/onboarding',{supplier_type:'multi_service',display_name:name},newId()),'تأمین‌کننده ثبت شد.');if(kind==='agency')await mutate(()=>api.post('/agency/sub-agencies',{display_name:name,markup_bps:0,commission_bps:0}),'زیرآژانس ثبت شد.');setName('')}
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;if(state.kind==='loading')return <LoadingState/>;if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;
  const entries=Object.entries(state.data);const offers=(state.data.offer_records as Array<{id:string;title:string;available_units:number;status:string}>|undefined)||[];const agencies=(state.data.agencies as Array<{id:string;name:string;markup_bps:number;commission_bps:number}>|undefined)||[];const suppliers=(state.data.suppliers as Array<{id:string;name:string;status:string}>|undefined)||[];const reservations=(state.data.reservations as Array<{id:string;booking_reference?:string;status:string;can_issue_invoice:boolean}>|undefined)||[];const cases=(state.data.support_cases as Array<{id:string;subject:string;status:string}>|undefined)||[];const supplierRecords=(state.data.supplier_records as Array<{id:string;name:string}>|undefined)||[];

  return <div className="dashboard container" style={{overflowWrap:'anywhere'}}><div className="dashboard-title"><div><span className="eyebrow">پنل متصل و نقش‌محور</span><h1>{kind==='supplier'?'پنل تأمین‌کننده':kind==='agency'?'پنل آژانس':'BackOffice / Admin'}</h1><p>اطلاعات و اقدامات این صفحه به حساب و سطح دسترسی شما محدود است.</p></div></div>{result&&<p role="status" className="mb-4 rounded-xl bg-cyan-50 p-4">{result}</p>}{kind!=='backoffice'&&<form onSubmit={create} className="panel mb-5 flex flex-wrap gap-3"><label className="min-w-64 flex-1 font-bold">{kind==='supplier'?'نام تأمین‌کننده':'نام زیرآژانس'}<input className="mt-2 block w-full rounded-xl border p-3" value={name} onChange={e=>setName(e.target.value)} required minLength={2}/></label><button className="button primary self-end">ثبت</button></form>}{kind==='supplier'&&<SupplierAssets suppliers={supplierRecords}/>}{kind==='supplier'&&offers.length>0&&<section className="panel mb-5"><h2 className="font-black">مدیریت موجودی</h2>{offers.map(o=><div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3" key={o.id}><span><b>{o.title}</b><small className="block">{o.available_units.toLocaleString('fa-IR')} واحد · {o.status}</small></span><button className="button secondary" onClick={()=>mutate(()=>api.put(`/supplier/offers/${o.id}`,{available_units:o.available_units,status:o.status==='active'?'paused':'active'}),'Offer به‌روز شد.')}>{o.status==='active'?'توقف فروش':'فعال‌سازی'}</button></div>)}</section>}{kind==='agency'&&agencies.length>0&&<section className="panel mb-5"><h2 className="font-black">تنظیم markup</h2>{agencies.map(a=><div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3" key={a.id}><span><b>{a.name}</b><small className="block">markup: {a.markup_bps.toLocaleString('fa-IR')}</small></span><button className="button secondary" onClick={()=>mutate(()=>api.put(`/agency/agencies/${a.id}`,{markup_bps:a.markup_bps+25}),'Markup ذخیره شد.')}>افزایش ۲۵ bps</button></div>)}</section>}{kind==='backoffice'&&<><section className="panel mb-5"><div className="flex items-center justify-between"><h2 className="font-black">عملیات صورتحساب</h2><Link className="text-link" href="/admin">مدیریت کاربران ←</Link></div>{reservations.length===0?<EmptyState>رزروی برای صدور صورتحساب وجود ندارد.</EmptyState>:reservations.map(r=><div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3" key={r.id}><span><b>{r.booking_reference||r.id}</b><small className="block">{r.status}</small></span><button disabled={!r.can_issue_invoice} className="button secondary" onClick={()=>mutate(()=>api.post(`/reservations/${r.id}/invoice`,{},newId()),'صورتحساب معتبر صادر شد.')}>صدور صورتحساب</button></div>)}</section><OpsSupportReply cases={cases}/></>}{kind==='backoffice'&&suppliers.length>0&&<section className="panel mb-5"><h2 className="font-black">وضعیت تأمین‌کنندگان</h2>{suppliers.map(s=><div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3" key={s.id}><span><b>{s.name}</b><small className="block">{s.status}</small></span><button className="button secondary" onClick={()=>mutate(()=>api.put(`/backoffice/suppliers/${s.id}/status`,{status:s.status==='active'?'suspended':'active',reason:'اقدام ثبت‌شده در BackOffice'}),'وضعیت تأمین‌کننده ثبت شد.')}>{s.status==='active'?'تعلیق':'فعال‌سازی'}</button></div>)}</section>}{entries.length===0?<EmptyState>داده‌ای برای نمایش وجود ندارد.</EmptyState>:<section className="grid gap-4 sm:grid-cols-2">{entries.filter(([key])=>!['offer_records','supplier_records','agencies','suppliers','reservation_records','support_cases'].includes(key)).map(([key,value])=><article className="panel" key={key}><h2 className="font-black">{panelLabels[key]||key}</h2><PanelValue value={value}/></article>)}</section>}</div>;
}

export function ConnectedFinance(){
  type FinanceData={payments:Array<{payment_id:string;reservation_id:string;status:string;intent_amount:number;currency:string;issues:string[]}>;wallets:Array<{wallet_id:string;available:number;currency:string}>;settlements:{count:number;pending_amount:number;completed_amount:number;records:Array<{id:string;reservation_id:string;amount:number;currency:string;status:string}>};installments:Array<{id:string;reservation_id:string;total_payable:number;currency:string;status:string}>;summary:{discrepancy_count:number}};
  const {api,session}=useAuth();const [state,setState]=useState<LoadState<FinanceData>>({kind:'loading'});const [notice,setNotice]=useState('');
  async function load(){setState({kind:'loading'});try{setState({kind:'ready',data:await api.get<FinanceData>('/finance/reconciliation')})}catch(error){const item=errorOf(error);setState({kind:'error',...item})}}
  useEffect(()=>{if(!session)return;let active=true;api.get<FinanceData>('/finance/reconciliation').then(data=>active&&setState({kind:'ready',data})).catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item})});return()=>{active=false}},[api,session]);
  async function mutate(action:()=>Promise<unknown>,success:string){setNotice('در حال ثبت امن…');try{await action();setNotice(success);await load()}catch(error){setNotice(errorOf(error).message)}}
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;if(state.kind==='loading')return <LoadingState/>;if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;const d=state.data;
  return <div className="dashboard container"><div className="dashboard-title"><div><span className="eyebrow">تطبیق مالی عملیاتی</span><h1>پرداخت، کیف پول، اقساط و تسویه</h1><p>Ledger و رکوردهای backend منبع حقیقت‌اند؛ انتقال بیرونی تا اتصال معتبر در وضعیت pending می‌ماند.</p></div></div>{notice&&<p role="status" className="mb-4 rounded-xl bg-cyan-50 p-4">{notice}</p>}<section className="metrics"><div><small>پرداخت‌ها</small><strong>{d.payments.length.toLocaleString('fa-IR')}</strong></div><div><small>تسویه‌ها</small><strong>{d.settlements.count.toLocaleString('fa-IR')}</strong></div><div><small>مغایرت‌ها</small><strong>{d.summary.discrepancy_count.toLocaleString('fa-IR')}</strong></div></section><section className="panel mt-5"><h2 className="font-black">رکوردهای تطبیق</h2>{d.payments.length===0?<EmptyState>پرداختی برای تطبیق وجود ندارد.</EmptyState>:d.payments.map(p=><div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3" key={p.payment_id}><span><b>{money(p.intent_amount,p.currency)} · {p.status}</b><small className="block">{p.issues.length?p.issues.join('، '):'بدون مغایرت ثبت‌شده'}</small></span>{p.status==='captured'&&<button className="button secondary" onClick={()=>mutate(()=>api.post(`/finance/reservations/${p.reservation_id}/settlements`,{},newId()),'تسویه pending ثبت شد؛ انتقال بیرونی ادعا نمی‌شود.')}>ثبت تسویه pending</button>}</div>)}</section><section className="panel mt-5"><h2 className="font-black">درخواست‌های اقساط</h2>{d.installments.length===0?<EmptyState>درخواست اقساطی وجود ندارد.</EmptyState>:d.installments.map(item=><div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3" key={item.id}><span><b>{money(item.total_payable,item.currency)}</b><small className="block">{item.status} · رزرو {item.reservation_id}</small></span>{item.status==='requested'&&<button className="button primary" onClick={()=>mutate(()=>api.put(`/finance/installments/${item.id}/decision`,{decision:'activate'}),'قرارداد اقساط فعال شد.')}>فعال‌سازی اقساط</button>}</div>)}</section><section className="panel mt-5"><h2 className="font-black">تسویه‌های ثبت‌شده</h2>{d.settlements.records.length===0?<EmptyState>تسویه‌ای ثبت نشده است.</EmptyState>:d.settlements.records.map(item=><div className="mt-3 rounded-xl bg-slate-50 p-3" key={item.id}><b>{money(item.amount,item.currency)} · {item.status}</b><small className="block">رزرو {item.reservation_id}</small></div>)}</section></div>;
}

type AdminUser={id:number;name:string;email:string;role:string;mutable:boolean};
export function ConnectedAdmin(){
  const {api,session}=useAuth();const [state,setState]=useState<LoadState<AdminUser[]>>({kind:'loading'});const [notice,setNotice]=useState('');
  async function load(){setState({kind:'loading'});try{setState({kind:'ready',data:await api.get<AdminUser[]>('/admin/users')})}catch(error){const item=errorOf(error);setState({kind:'error',...item})}}
  useEffect(()=>{if(!session)return;let active=true;api.get<AdminUser[]>('/admin/users').then(data=>active&&setState({kind:'ready',data})).catch(error=>{const item=errorOf(error);if(active)setState({kind:'error',...item})});return()=>{active=false}},[api,session]);
  async function changeRole(user:AdminUser,role:string){setNotice('در حال ثبت تغییر نقش…');try{await api.put(`/admin/users/${user.id}/role`,{role,reason:'تغییر نقش از پنل مدیریت کارن‌سیر'});setNotice('نقش کاربر با audit trail ذخیره شد.');await load()}catch(error){setNotice(errorOf(error).message)}}
  if(!session)return <ErrorState status={401} message="نشست مرورگر موجود نیست."/>;if(state.kind==='loading')return <LoadingState/>;if(state.kind==='error')return <ErrorState status={state.status} message={state.message}/>;
  return <div className="dashboard container"><div className="dashboard-title"><div><span className="eyebrow">مدیریت tenant و RBAC</span><h1>کاربران و نقش‌ها</h1><p>تغییر نقش فقط در tenant جاری، با کنترل ارتقای دسترسی و audit انجام می‌شود.</p></div></div>{notice&&<p role="status" className="mb-4 rounded-xl bg-cyan-50 p-4">{notice}</p>}<section className="panel">{state.data.length===0?<EmptyState>کاربری در این tenant وجود ندارد.</EmptyState>:state.data.map(user=><div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-4" key={user.id}><span><b>{user.name}</b><small className="block">{user.email} · {user.role}</small></span><label className="text-sm font-bold">نقش مجاز<select aria-label={`نقش ${user.email}`} className="mr-2 rounded-xl border p-2" disabled={!user.mutable} value={user.role} onChange={event=>changeRole(user,event.target.value)}><option value="customer">مشتری</option><option value="employee">کارمند</option><option value="manager">مدیر</option><option value="welfare_manager">کارشناس رفاه</option><option value="finance">مالی</option><option value="support_agent">پشتیبانی</option><option value="supplier">تأمین‌کننده</option><option value="agency">آژانس</option><option value="backoffice">عملیات</option><option value="organization_admin">مدیر سازمان</option><option value="tenant_admin">مدیر tenant</option></select></label></div>)}</section></div>;
}
