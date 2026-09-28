'use client';
import Link from 'next/link';
import {useRef,useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {newId} from '../../lib/api/karenseir-client';
export function AccommodationRequestAction({id,status}:{id:string;status:string}){
 const{api}=useAuth();const key=useRef(newId());const[busy,setBusy]=useState(false),[note,setNote]=useState('');
 async function withdraw(){if(busy)return;setBusy(true);try{await api.post(`/reservations/${id}/accommodation-decision`,{action:'withdraw',reason:'انصراف مشتری پیش از پذیرش میزبان',command_id:key.current});window.location.reload()}catch{setNote('انصراف تأیید نشد؛ وضعیت را تازه کنید یا همین درخواست را دوباره بفرستید.');setBusy(false)}}
 if(status==='reserved')return <Link className="button primary" href={`/checkout/${id}`}>ادامهٔ تکمیل رزرو اقامت</Link>;
 if(status!=='booking_pending')return null;
 return <section className="panel"><h2>در انتظار پاسخ میزبان</h2><p>این درخواست هنوز رزرو قطعی یا پرداخت‌شده نیست. میزبان پیش از پذیرش، مبلغ و ظرفیت را دوباره بررسی می‌کند.</p><button className="button secondary" onClick={()=>window.location.reload()}>تازه‌سازی وضعیت درخواست</button><button className="button secondary" disabled={busy} onClick={()=>void withdraw()}>انصراف از درخواست اقامت</button>{note&&<p role="status">{note}</p>}</section>
}
