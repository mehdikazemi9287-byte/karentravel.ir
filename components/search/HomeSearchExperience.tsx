'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../../lib/api/auth-context';
import { parseTravelIntent, type NLIntent } from '../../lib/domain/nl-intent';

type Suggestion={id:string;title:string;subtitle:string;entity_type:string;city?:string;country?:string;code?:string;source:string};
type AutocompleteResponse={suggestions:Suggestion[]};
type TripType='round_trip'|'one_way'|'multi_city';
type Popover='origin'|'destination'|'dates'|'passengers'|null;
type SpeechRecognitionResultLike={0:{transcript:string}};
type SpeechRecognitionEventLike={results:SpeechRecognitionResultLike[]};
type SpeechRecognitionLike={lang:string;interimResults:boolean;start():void;onresult:((event:SpeechRecognitionEventLike)=>void)|null;onerror:(()=>void)|null};

// Single consistent line-icon set (24px grid, currentColor). Replaces the
// emoji/glyph icons the search widget used before. `|` separates sub-paths.
const ICONS:Record<string,string>={
  origin:'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18|M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4',
  destination:'M12 21s-6.5-5.4-6.5-11a6.5 6.5 0 0 1 13 0C18.5 15.6 12 21 12 21z|M12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5',
  takeoff:'M2 22h20|M6.36 17.4 4 17l-2-4 1.1-.55a2 2 0 0 1 1.8 0l.17.1a2 2 0 0 0 1.8 0L8 12 5 6l.9-.45a2 2 0 0 1 2.09.2l4.02 3a2 2 0 0 0 2.1.2l4.19-2.06a2.41 2.41 0 0 1 1.73-.17L21 6a1.4 1.4 0 0 1 .87 1.99l-.38.76c-.23.46-.6.84-1.07 1.08L7.58 17.2a2 2 0 0 1-1.22.18z',
  landing:'M2 22h20|M3.77 10.77 2 9l2-4.5 1.1.55a2 2 0 0 1 1.8 0l.17.1a2 2 0 0 0 1.8 0L11 4 8 10l3 2 4.75-1.6a2 2 0 0 1 1.55.15l5.7 3.4a1.4 1.4 0 0 1-.36 2.53l-.8.2a2.4 2.4 0 0 1-1.7-.2L14 15l-6.35 2.65a2 2 0 0 1-1.53-.06z',
  swap:'M7 4 3 8l4 4|M3 8h13|M17 20l4-4-4-4|M21 16H8',
  calendar:'M8 3v4|M16 3v4|M4 9h16|M6 5h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z',
  users:'M16 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20|M9 10.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8z|M22 20v-1.5a4 4 0 0 0-3-3.9|M16 2.6a4 4 0 0 1 0 7.8',
  search:'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z|M20 20l-4-4',
  mic:'M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3z|M19 12a7 7 0 0 1-14 0|M12 19v3',
  chat:'M21 11.5a8.5 8.5 0 0 1-12.6 7.5L3 21l1.5-5.4A8.5 8.5 0 1 1 21 11.5z',
  dot:'M12 13a2 2 0 1 0 0-4 2 2 0 0 0 0 4',
  flight:'M22 2 11 13|M22 2l-7 20-4-9-9-4 20-7z',
  hotel:'M3 8v11|M3 12h15a3 3 0 0 1 3 3v4|M3 19h18|M7 12V9h4v3',
  home:'M3 10.5 12 4l9 6.5|M5 9.5V20h14V9.5|M10 20v-6h4v6',
  compass:'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z|M15.5 8.5l-2 5.5-5.5 2 2-5.5z',
  train:'M8 4h8a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z|M5 11h14|M7 21l2-3|M17 21l-2-3',
  car:'M5 13l1.6-4.6A2 2 0 0 1 8.5 7h7a2 2 0 0 1 1.9 1.4L19 13|M5 13h14v4a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1v-1H8v1a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z',
  anchor:'M12 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z|M12 8v13|M5 12H3a9 9 0 0 0 18 0h-2',
  passport:'M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z|M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6z|M9 16.5h6',
};
function Icon({name}:{name:string}){
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{(ICONS[name]??ICONS.dot).split('|').map((seg,index)=><path key={index} d={seg}/>)}</svg>;
}

const services=[
  {name:'پرواز',icon:'flight',vertical:'flight',origin:true,description:'پروازهای داخلی و خارجی'},
  {name:'هتل',icon:'hotel',vertical:'hotel',origin:false,description:'اقامت و رزرو هتل'},
  {name:'ویلا',icon:'home',vertical:'vacation_rental',origin:false,description:'ویلا، سوئیت و اقامتگاه'},
  {name:'تور',icon:'compass',vertical:'tour',origin:true,description:'تورهای داخلی و خارجی'},
  {name:'قطار',icon:'train',vertical:'train',origin:true,description:'سفر ریلی و ایستگاه‌ها'},
  {name:'خودرو',icon:'car',vertical:'car_rental',origin:true,description:'اجاره خودرو در مقصد'},
  {name:'کروز',icon:'anchor',vertical:'cruise',origin:false,description:'سفر دریایی و کشتی'},
  {name:'ویزا',icon:'passport',vertical:'visa',origin:true,description:'بررسی و درخواست ویزا'},
] as const;
const entityLabels:Record<string,string>={city:'شهر',airport:'فرودگاه',railway_station:'ایستگاه',hotel:'هتل',accommodation:'اقامتگاه',attraction:'جاذبه',poi:'مکان دیدنی'};

function EntityInput({kind,label,value,onChange,onSelect,open,setOpen,vertical}:{kind:'origin'|'destination';label:string;value:string;onChange:(value:string)=>void;onSelect:(item:Suggestion)=>void;open:boolean;setOpen:()=>void;vertical:string}){
  const {api}=useAuth();
  const [items,setItems]=useState<Suggestion[]>([]); const [loading,setLoading]=useState(false); const request=useRef(0);
  useEffect(()=>{if(!open||value.trim().length<2)return;const current=++request.current;const timer=window.setTimeout(async()=>{setLoading(true);try{const response=await api.publicGet<AutocompleteResponse>(`/search/autocomplete/public?q=${encodeURIComponent(value)}`);if(current===request.current)setItems(response.suggestions)}catch{if(current===request.current)setItems([])}finally{if(current===request.current)setLoading(false)}},180);return()=>window.clearTimeout(timer)},[api,open,value,vertical]);
  return <div className="fs-field fs-field--entity">
    <span className="fs-field-ic"><Icon name={kind==='origin'?(vertical==='flight'?'takeoff':'origin'):(vertical==='flight'?'landing':'destination')}/></span>
    <label className="fs-field-body">
      <span className="fs-field-label">{label}</span>
      <input className="fs-field-input" aria-label={label} role="combobox" aria-expanded={open} aria-controls={`${kind}-suggestions`} autoComplete="off" value={value} onFocus={setOpen} onClick={setOpen} onChange={event=>{onChange(event.target.value);setOpen()}}/>
    </label>
    {open&&<div className="fs-pop fs-pop--auto" id={`${kind}-suggestions`} role="listbox" aria-label={`پیشنهادهای ${label}`}>{loading?<div className="fs-sug-msg">در حال یافتن مقصد…</div>:items.length?<>{items.map(item=><button type="button" role="option" aria-selected="false" key={item.id} onClick={()=>onSelect(item)}><i aria-hidden="true"><Icon name={item.entity_type==='airport'?'flight':item.entity_type==='city'?'destination':'dot'}/></i><span><b>{item.title}</b><small>{[entityLabels[item.entity_type]??item.entity_type,item.code,item.city||item.country].filter(Boolean).join(' · ')}</small></span></button>)}</>:<div className="fs-sug-msg">حداقل دو حرف بنویس؛ شهر، فرودگاه یا کد IATA را جست‌وجو می‌کنیم.</div>}</div>}
  </div>;
}

const defaultDestinationFor=(vertical:string)=>vertical==='hotel'||vertical==='vacation_rental'?'یزد':vertical==='cruise'?'دبی':vertical==='visa'?'فرانسه':vertical==='car_rental'?'شیراز':vertical==='tour'?'استانبول':'شیراز';
export function HomeSearchExperience(){
  const router=useRouter(); const params=useSearchParams();
  // Previously this form always mounted with hardcoded defaults (flight/تهران/شیراز)
  // regardless of the URL - confirmed live: loading /?vertical=cruise&destination=دبی
  // showed correct "کروز به دبی" results below (UnifiedSearchView reads the URL) while
  // this form still showed the پرواز tab with تهران/شیراز. Reading the same URL params
  // this form itself writes on submit() fixes that mismatch on direct load/refresh/back-
  // forward, without changing the submit contract or the tab-switch defaults below.
  const initial=useMemo(()=>{
    const vertical=params.get('vertical');
    const active=Math.max(0,services.findIndex(item=>item.vertical===vertical));
    const svc=services[active];
    return {
      active,
      origin:params.get('origin')??(svc.vertical==='visa'?'':svc.origin?'تهران':''),
      destination:params.get('destination')||defaultDestinationFor(svc.vertical),
      depart:params.get('depart')||'2026-09-15',
      returnDate:params.get('return')||'2026-09-18',
      flexibility:params.get('flexibility')||'exact',
      tripType:(params.get('trip_type') as TripType|null)||'round_trip',
      adults:Number(params.get('adults')||2),
      children:Number(params.get('children')||0),
      infants:Number(params.get('infants')||0),
      rooms:Number(params.get('rooms')||1),
      cabin:params.get('cabin')||'economy',
    };
  },[params]);
  const [active,setActive]=useState(initial.active); const service=services[active];
  const [origin,setOrigin]=useState(initial.origin); const [destination,setDestination]=useState(initial.destination);
  const [depart,setDepart]=useState(initial.depart); const [returnDate,setReturnDate]=useState(initial.returnDate); const [flexibility,setFlexibility]=useState(initial.flexibility); const [tripType,setTripType]=useState<TripType>(initial.tripType);
  const [adults,setAdults]=useState(initial.adults); const [children,setChildren]=useState(initial.children); const [infants,setInfants]=useState(initial.infants); const [rooms,setRooms]=useState(initial.rooms); const [cabin,setCabin]=useState(initial.cabin); const [popover,setPopover]=useState<Popover>(null);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- resyncing the search form from a changed URL (direct link/refresh with existing params, or browser back/forward), the same justified pattern as UnifiedSearchView's URL resync effect
  useEffect(()=>{setActive(initial.active);setOrigin(initial.origin);setDestination(initial.destination);setDepart(initial.depart);setReturnDate(initial.returnDate);setFlexibility(initial.flexibility);setTripType(initial.tripType);setAdults(initial.adults);setChildren(initial.children);setInfants(initial.infants);setRooms(initial.rooms);setCabin(initial.cabin)},[initial]);
  const {api,session}=useAuth();
  const [nlOpen,setNlOpen]=useState(false); const [nlText,setNlText]=useState(''); const [nlIntent,setNlIntent]=useState<NLIntent|null>(null); const [nlRecording,setNlRecording]=useState(false); const [nlBusy,setNlBusy]=useState(false); const [nlError,setNlError]=useState('');
  const nlRecorder=useRef<MediaRecorder|null>(null); const nlChunks=useRef<Blob[]>([]); const nlStopTimer=useRef<number|undefined>(undefined);
  function nlSpeak(text:string){setNlText(text);setNlIntent(parseTravelIntent(text))}
  async function nlUseTranscript(transcript:string){nlSpeak(transcript)}
  function nlStopRecording(){nlRecorder.current?.state==='recording'&&nlRecorder.current.stop();if(nlStopTimer.current)window.clearTimeout(nlStopTimer.current)}
  async function nlStartRecording(){
    setNlError('');
    if(!session){setNlError('برای دستیار صوتی ابتدا وارد شوید؛ فعلاً تایپ کن.');return}
    if(typeof navigator==='undefined'||!navigator.mediaDevices?.getUserMedia){setNlError('مرورگر شما از ضبط صدا پشتیبانی نمی‌کند؛ لطفاً تایپ کن.');return}
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      const recorder=new MediaRecorder(stream); nlRecorder.current=recorder; nlChunks.current=[];
      recorder.ondataavailable=event=>{if(event.data.size>0)nlChunks.current.push(event.data)};
      recorder.onstop=async()=>{
        stream.getTracks().forEach(track=>track.stop()); setNlRecording(false);
        const blob=new Blob(nlChunks.current,{type:'audio/webm'}); nlChunks.current=[];
        setNlBusy(true);
        try{
          const result=await api.postAudio<{transcript:string}>('/search/voice/transcribe',blob,'voice.webm');
          await nlUseTranscript(result.transcript);
        }catch{
          const win=window as unknown as {SpeechRecognition?:new()=>SpeechRecognitionLike;webkitSpeechRecognition?:new()=>SpeechRecognitionLike};
          const SpeechRecognitionCtor=win.SpeechRecognition??win.webkitSpeechRecognition;
          if(SpeechRecognitionCtor){
            setNlError('سرویس گفتار کارن‌سیر در دسترس نیست؛ در حال استفاده از تشخیص گفتار مرورگر…');
            try{
              const recognition=new SpeechRecognitionCtor(); recognition.lang='fa-IR'; recognition.interimResults=false;
              recognition.onresult=(event)=>{void nlUseTranscript(event.results[0][0].transcript)};
              recognition.onerror=()=>setNlError('تشخیص گفتار ناموفق بود؛ لطفاً تایپ کن.');
              recognition.start();
            }catch{setNlError('دستیار صوتی هنوز در دسترس نیست؛ لطفاً جمله سفر را تایپ کن.')}
          } else setNlError('دستیار صوتی هنوز در دسترس نیست؛ لطفاً جمله سفر را تایپ کن.');
        } finally{setNlBusy(false)}
      };
      recorder.start(); setNlRecording(true);
      nlStopTimer.current=window.setTimeout(nlStopRecording,12000);
    }catch{setNlError('اجازه دسترسی به میکروفون داده نشد؛ لطفاً تایپ کن.')}
  }
  function nlConfirm(){
    if(!nlIntent)return;
    const nlVertical=nlIntent.vertical??'hotel'; const nlIndex=services.findIndex(item=>item.vertical===nlVertical); if(nlIndex>=0)setActive(nlIndex);
    const params=new URLSearchParams({vertical:nlVertical,origin:nlIntent.origin??'',destination:nlIntent.destination??'',depart:nlIntent.depart??depart,trip_type:'round_trip',flexibility:nlIntent.flexibility??'exact',adults:String(nlIntent.adults??adults),children:String(nlIntent.children??0),infants:'0',rooms:'1',cabin:'economy',sort:'recommended'});
    if(nlIntent.budgetMax)params.set('filters_max_price',String(nlIntent.budgetMax));
    router.push(`/?${params.toString()}`);
  }
  function changeService(index:number){const previousVertical=service.vertical;setActive(index);setPopover(null);const next=services[index];if(next.vertical==='visa')setOrigin('');else if(previousVertical==='visa')setOrigin('تهران');setDestination(next.vertical==='hotel'||next.vertical==='vacation_rental'?'یزد':next.vertical==='cruise'?'دبی':next.vertical==='visa'?'فرانسه':next.vertical==='car_rental'?'شیراز':next.vertical==='tour'?'استانبول':'شیراز')}
  // trip_type ("یک‌طرفه"/"چندمسیره") is a flight-only concept - changeService()
  // above never resets it when switching tabs, so it used to leak into every
  // other vertical's URL and, since it wasn't 'round_trip', silently dropped
  // `return` (the hotel/villa/etc. checkout date) from the URL too. Only
  // writing trip_type for flight, and gating `return` on the same showReturn
  // flag the date field itself already uses, fixes both at the source.
  function submit(){const params=new URLSearchParams({vertical:service.vertical,origin:service.origin?origin:'',destination,depart,flexibility,adults:String(adults),children:String(children),infants:String(infants),rooms:String(rooms),cabin,sort:'recommended'});if(service.vertical==='flight')params.set('trip_type',tripType);if(showReturn)params.set('return',returnDate);router.push(`/?${params.toString()}`)}
  const travellerTotal=adults+children+infants;
  const isStay=service.vertical==='hotel'||service.vertical==='vacation_rental';
  const showReturn=service.vertical!=='flight'||tripType==='round_trip';
  const originLabel=service.vertical==='visa'?'ملیت / کشور گذرنامه':service.vertical==='cruise'?'بندر حرکت':service.vertical==='car_rental'?'شهر تحویل':'مبدأ';
  const destinationLabel=isStay?'مقصد، هتل یا منطقه':service.vertical==='visa'?'کشور مقصد':service.vertical==='car_rental'?'محل بازگشت':service.vertical==='cruise'?'مسیر / مقصد':'مقصد';
  const dateLabel=service.vertical==='visa'?'تاریخ سفر':service.vertical==='cruise'?'تاریخ حرکت':isStay?'ورود و خروج':'تاریخ سفر';
  const departLabel=isStay?'تاریخ ورود':service.vertical==='car_rental'?'تاریخ تحویل':'تاریخ رفت';
  const returnLabel=isStay?'تاریخ خروج':service.vertical==='car_rental'?'تاریخ بازگشت':'تاریخ برگشت';
  return <section className="fs" id="search" aria-label="جست‌وجوی یکپارچه سفر" onKeyDown={event=>{if(event.key==='Escape')setPopover(null)}}>
    {popover&&<div className="fs-scrim" aria-hidden="true" onClick={()=>setPopover(null)}/>}
    <div className="fs-tabs" role="tablist" aria-label="نوع خدمت">{services.map((tab,index)=><button type="button" role="tab" aria-selected={active===index} aria-controls="service-search-panel" onClick={()=>changeService(index)} className={active===index?'is-active':''} key={tab.name}><Icon name={tab.icon}/>{tab.name}</button>)}</div>
    <div className="fs-box" id="service-search-panel" role="tabpanel" aria-label={`فرم جست‌وجوی ${service.name}`}>
      {service.vertical==='flight'&&<div className="fs-seg" role="group" aria-label="نوع سفر">{([['round_trip','رفت‌وبرگشت'],['one_way','یک‌طرفه'],['multi_city','چندمسیره']] as const).map(([value,label])=><button type="button" aria-pressed={tripType===value} className={tripType===value?'is-active':''} onClick={()=>{if(value==='multi_city'){setTripType(value);router.push('/?vertical=flight&trip_type=multi_city&edit=1')}else setTripType(value)}} key={value}>{label}</button>)}</div>}
      <div className="fs-row">
        <div className={service.origin?'fs-places fs-places--swap':'fs-places'}>
          {service.origin&&<><EntityInput kind="origin" label={originLabel} value={origin} onChange={setOrigin} onSelect={item=>{setOrigin(item.title);setPopover(null)}} open={popover==='origin'} setOpen={()=>setPopover('origin')} vertical={service.vertical}/><button type="button" className="fs-swap" aria-label="جابجایی مبدا و مقصد" onClick={()=>{setOrigin(destination);setDestination(origin)}}><Icon name="swap"/></button></>}
          <EntityInput kind="destination" label={destinationLabel} value={destination} onChange={setDestination} onSelect={item=>{setDestination(item.title);setPopover(null)}} open={popover==='destination'} setOpen={()=>setPopover('destination')} vertical={service.vertical}/>
        </div>
        <div className="fs-field fs-field--dates">
          <span className="fs-field-ic"><Icon name="calendar"/></span>
          <button type="button" className="fs-field-body fs-field-body--split" aria-label={dateLabel} aria-expanded={popover==='dates'} onClick={()=>setPopover(popover==='dates'?null:'dates')}>
            <span className="fs-datecol"><span className="fs-field-label">{departLabel}</span><span className="fs-field-value">{depart.replaceAll('-','/')}</span></span>
            <span className={showReturn?'fs-datecol':'fs-datecol is-disabled'}><span className="fs-field-label">{returnLabel}</span><span className="fs-field-value">{showReturn?returnDate.replaceAll('-','/'):'—'}</span></span>
          </button>
          {popover==='dates'&&<div className="fs-pop fs-pop--date" aria-label="انتخاب تاریخ">
            <header><b>{dateLabel}</b><small>قیمت فقط پس از اتصال داده معتبر نمایش داده می‌شود.</small></header>
            <div className="fs-pop-dates"><label><span>رفت</span><input aria-label="تاریخ رفت" type="date" value={depart} onChange={event=>setDepart(event.target.value)}/></label>{showReturn&&<label><span>برگشت</span><input aria-label="تاریخ برگشت" type="date" min={depart} value={returnDate} onChange={event=>setReturnDate(event.target.value)}/></label>}</div>
            <fieldset className="fs-flex"><legend>تاریخ منعطف</legend>{[['exact','دقیق'],['plus_minus_1','±۱ روز'],['plus_minus_3','±۳ روز']].map(([value,label])=><button type="button" aria-pressed={flexibility===value} className={flexibility===value?'is-active':''} onClick={()=>setFlexibility(value)} key={value}>{label}</button>)}</fieldset>
            <button type="button" className="fs-pop-done" onClick={()=>setPopover(null)}>تأیید تاریخ</button>
          </div>}
        </div>
        <div className="fs-field fs-field--pax">
          <span className="fs-field-ic"><Icon name="users"/></span>
          <button type="button" className="fs-field-body" aria-expanded={popover==='passengers'} onClick={()=>setPopover(popover==='passengers'?null:'passengers')}>
            <span className="fs-field-label">{isStay?'اتاق و مهمان':'مسافران'}</span>
            <span className="fs-field-value">{travellerTotal.toLocaleString('fa-IR')} مسافر{isStay?`، ${rooms.toLocaleString('fa-IR')} اتاق`:''}{service.vertical==='flight'?` · ${cabin==='economy'?'اکونومی':'بیزینس'}`:''}</span>
          </button>
          {popover==='passengers'&&<div className="fs-pop fs-pop--pax" aria-label="انتخاب مسافران">
            {([['بزرگسال','۱۲ سال به بالا',adults,setAdults,1],['کودک','۲ تا ۱۱ سال',children,setChildren,0],['نوزاد','کمتر از ۲ سال',infants,setInfants,0]] as const).map(([label,help,value,setter,min])=><div className="fs-counter" key={label}><span><b>{label}</b><small>{help}</small></span><div><button type="button" aria-label={`کاهش ${label}`} disabled={value<=min} onClick={()=>setter(value-1)}>−</button><b>{value.toLocaleString('fa-IR')}</b><button type="button" aria-label={`افزایش ${label}`} onClick={()=>setter(value+1)}>+</button></div></div>)}
            {isStay&&<div className="fs-counter"><span><b>اتاق</b><small>تعداد اتاق موردنیاز</small></span><div><button type="button" aria-label="کاهش اتاق" disabled={rooms<=1} onClick={()=>setRooms(rooms-1)}>−</button><b>{rooms.toLocaleString('fa-IR')}</b><button type="button" aria-label="افزایش اتاق" onClick={()=>setRooms(rooms+1)}>+</button></div></div>}
            {service.vertical==='flight'&&<label className="fs-cabin"><span>کلاس پروازی</span><select aria-label="کلاس پروازی" value={cabin} onChange={event=>setCabin(event.target.value)}><option value="economy">اکونومی</option><option value="business">بیزینس</option></select></label>}
            <button type="button" className="fs-pop-done" onClick={()=>setPopover(null)}>تأیید مسافران</button>
          </div>}
        </div>
        <button type="button" className="fs-go" onClick={submit}><Icon name="search"/>جست‌وجو</button>
      </div>
    </div>
    <div className="fs-tools"><span>قیمت و موجودی فقط از Provider معتبر</span><span>استعلام مجدد پیش از خرید</span><button type="button" className="nl-toggle" onClick={()=>setNlOpen(value=>!value)} aria-expanded={nlOpen}><Icon name="chat"/> با زبان خودت بگو</button></div>
    {nlOpen&&<div className="nl-panel" aria-label="جست‌وجوی زبان طبیعی">
      <div className="nl-input-row">
        <textarea aria-label="سفرت را با جمله فارسی توصیف کن" placeholder="مثلاً: آخر شهریور برای دو نفر از تهران یه سفر چهار روزه به شیراز می‌خوام" value={nlText} onChange={event=>{setNlText(event.target.value);setNlIntent(null)}} rows={2}/>
        <button type="button" className={`nl-mic ${nlRecording?'recording':''}`} onClick={nlRecording?nlStopRecording:nlStartRecording} aria-pressed={nlRecording} aria-label={nlRecording?'پایان ضبط صدا':'شروع ضبط صدا با میکروفون'} disabled={nlBusy}><Icon name="mic"/></button>
      </div>
      {nlBusy&&<small className="nl-status">در حال پردازش صدا…</small>}
      {nlError&&<small className="nl-status nl-error" role="alert">{nlError}</small>}
      {!nlIntent&&<button type="button" className="button secondary nl-parse" onClick={()=>nlSpeak(nlText)} disabled={!nlText.trim()}>تحلیل جمله</button>}
      {nlIntent&&<div className="nl-confirm" role="status">
        <p>من این‌طور متوجه شدم:</p>
        <div className="nl-chips">
          {nlIntent.origin&&<span>مبدأ: {nlIntent.origin}</span>}
          {nlIntent.destination?<span>مقصد: {nlIntent.destination}</span>:<span className="nl-missing">مقصد نامشخص</span>}
          {(nlIntent.adults??0)>0&&<span>{nlIntent.adults} نفر{nlIntent.children?` و ${nlIntent.children} کودک`:''}</span>}
          {nlIntent.nights&&<span>{nlIntent.nights} شب</span>}
          {nlIntent.dateHint&&<span>{nlIntent.dateHint}</span>}
          {nlIntent.budgetMax&&<span>بودجه تا {(nlIntent.budgetMax/1_000_000).toLocaleString('fa-IR')} میلیون</span>}
          {nlIntent.vertical&&<span>{services.find(item=>item.vertical===nlIntent.vertical)?.name??nlIntent.vertical}</span>}
        </div>
        {nlIntent.missing.includes('destination')&&<small className="nl-status">مقصد را متوجه نشدم؛ لطفاً نام شهر را اضافه کن.</small>}
        <div className="nl-actions">
          <button type="button" className="button primary" onClick={nlConfirm} disabled={!nlIntent.destination}>جست‌وجو</button>
          <button type="button" className="button secondary" onClick={()=>setNlIntent(null)}>ویرایش</button>
          <button type="button" className="button secondary" onClick={()=>{setNlText('');setNlIntent(null)}}>دوباره بگو</button>
        </div>
      </div>}
    </div>}
  </section>;
}
