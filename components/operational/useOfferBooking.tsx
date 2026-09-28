'use client';
import Link from 'next/link';
import {useEffect,useMemo,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError,newId} from '../../lib/api/karenseir-client';
type Pending={offerId:string;priceCheckId:string;commandId:string};
export function useOfferBooking(){
 const{api,session}=useAuth(),router=useRouter();
 const storage=useMemo(()=>{try{const c=JSON.parse(atob(session!.access_token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));return c.sub?'karen-offer-pending:'+JSON.stringify([c.iss,c.sub,session?.user?.tenant]):null}catch{return null}},[session]);
 const[loaded,setLoaded]=useState<{key:string|null|undefined;value:Pending|null}>({key:undefined,value:null}),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');const inFlight=useRef<string|null>(null),activeKey=useRef(storage);activeKey.current=storage;
 useEffect(()=>{let value:Pending|null=null;try{const p=storage?JSON.parse(sessionStorage.getItem(storage)||'null'):null;if(p&&typeof p.offerId==='string'&&typeof p.priceCheckId==='string'&&typeof p.commandId==='string')value=p}catch{}setLoaded({key:storage,value});setNotice('');setBusy(false)},[storage]);
 const ready=loaded.key===storage,pending=ready?loaded.value:null;
 async function send(command:Pending){if(!storage||!ready||inFlight.current===storage)return;inFlight.current=storage;setBusy(true);setNotice('');setLoaded({key:storage,value:command});try{sessionStorage.setItem(storage,JSON.stringify(command))}catch{setNotice('امکان نگهداری درخواست در این مرورگر فراهم نیست؛ از مرورگر دیگری یا پشتیبانی کمک بگیر.');inFlight.current=null;setBusy(false);return}try{const result=await api.post<{id:string}>('/orchestration/bookings',{price_check_id:command.priceCheckId,command_id:command.commandId});try{sessionStorage.removeItem(storage)}catch{}if(activeKey.current!==storage)return;setLoaded({key:storage,value:null});router.push('/checkout/'+result.id)}catch(e){if(activeKey.current!==storage)return;if(e instanceof ApiError&&[404,409,422].includes(e.status)){try{sessionStorage.removeItem(storage)}catch{}setLoaded({key:storage,value:null});setNotice('استعلام قبلی قابل استفاده نیست؛ پیش از ادامه، قیمت و ظرفیت را دوباره بررسی کن.')}else setNotice('پاسخ قطعی رزرو دریافت نشد؛ همان درخواست را پیگیری کن تا رزرو تازه‌ای ساخته نشود.')}finally{if(inFlight.current===storage)inFlight.current=null;if(activeKey.current===storage)setBusy(false)}}
 return {ready,pending,busy,notice,begin:(offerId:string,priceCheckId:string)=>{if(!pending)return send({offerId,priceCheckId,commandId:newId()})},resume:()=>pending?send(pending):undefined};
}
export function OfferBookingRecovery({booking}:{booking:ReturnType<typeof useOfferBooking>}){return <>{booking.pending&&<section className="panel leisure-pending"><h2>درخواست رزرو در انتظار پاسخ قطعی</h2><p>برای جلوگیری از درخواست تکراری، ابتدا نتیجهٔ همان انتخاب را پیگیری کن.</p><button className="button primary" disabled={!booking.ready||booking.busy} onClick={()=>void booking.resume()}>پیگیری همان رزرو</button> <Link href="/trips">بررسی سفرهای من</Link></section>}{booking.notice&&<p role="status">{booking.notice}</p>}</>}
