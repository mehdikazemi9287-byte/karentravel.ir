'use client';
import {useState} from 'react';
function photoUrl(value:unknown){if(typeof value!=='string')return null;try{const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password||!u.hostname.includes('.')||/^(localhost|127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(u.hostname)||u.hostname.endsWith('.local'))return null;return u.href}catch{return null}}
export function StayPresentation({details,title}:{details:Record<string,unknown>;title:string}){
 const[failed,setFailed]=useState<string[]>([]);const photos=Array.isArray(details.photos)?details.photos.flatMap((p:unknown)=>{if(!p||typeof p!=='object'||!('url'in p))return[];const url=photoUrl(p.url);return url?[{url,alt:'alt'in p&&typeof p.alt==='string'?p.alt:title}]:[]}).filter(p=>!failed.includes(p.url)):[];
 return <>{photos.length>0?<section className="panel" aria-label="تصاویر اقامتگاه"><h2>تصاویر ارائه‌شدهٔ اقامتگاه</h2><div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,240px),1fr))',gap:12}}>{photos.map((p,i)=><img key={p.url+String(i)} src={p.url} alt={p.alt} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(v=>[...v,p.url])} style={{width:'100%',height:220,objectFit:'cover',borderRadius:16}}/>)}</div></section>:<p>تصویر قابل نمایش برای این اقامتگاه ثبت نشده است؛ پیش از رزرو از پشتیبانی راهنمایی بگیرید.</p>}
 {typeof details.description==='string'&&details.description.trim()&&<p>{details.description}</p>}
 {typeof details.host_name==='string'&&details.host_name.trim()&&<section className="panel"><h2>میزبان / بهره‌بردار اعلام‌شده</h2><p>{details.host_name}</p></section>}
 {typeof details.location_description==='string'&&details.location_description.trim()&&<section className="panel"><h2>موقعیت اقامتگاه</h2><p>{details.location_description}</p></section>}
 {Array.isArray(details.amenities)&&details.amenities.length>0&&<section className="panel"><h2>امکانات اعلام‌شده</h2><ul>{details.amenities.filter(v=>typeof v==='string').map((v,i)=><li key={i}>{v}</li>)}</ul></section>}
 {(details.house_rules||details.check_in||details.check_out)?<section className="panel"><h2>قوانین و زمان تحویل</h2>{typeof details.house_rules==='string'&&<p>{details.house_rules}</p>}{typeof details.check_in==='string'&&<p>تحویل: {details.check_in}</p>}{typeof details.check_out==='string'&&<p>تخلیه: {details.check_out}</p>}</section>:null}
 </>
}
