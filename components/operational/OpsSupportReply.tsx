'use client';
import Link from 'next/link';
import {FormEvent,useEffect,useMemo,useRef,useState} from 'react';
import {useAuth} from '../../lib/api/auth-context';
import {ApiError,newId} from '../../lib/api/karenseir-client';
type Case={id:string;subject:string;status:string};
type Pending={caseId:string;body:string;key:string};
export function OpsSupportReply({cases}:{cases:Case[]}){
 const{session}=useAuth();
 const owner=useMemo(()=>{try{const c=JSON.parse(atob(session!.access_token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));return c.sub?JSON.stringify([c.iss,c.sub,session?.user?.tenant]):null}catch{return null}},[session]);
 if(!owner)return null;
 return <ReplyForm key={owner} owner={owner} cases={cases}/>;
}
function ReplyForm({owner,cases}:{owner:string;cases:Case[]}){
 const{api}=useAuth(),[caseId,setCaseId]=useState(''),[body,setBody]=useState(''),[pending,setPending]=useState<Pending|null>(null),[ready,setReady]=useState(false),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const sending=useRef(false),storage='karen-ops-reply:'+owner;
 useEffect(()=>{try{const value=JSON.parse(sessionStorage.getItem(storage)||'null');if(value&&typeof value.caseId==='string'&&typeof value.body==='string'&&typeof value.key==='string'){setPending(value);setCaseId(value.caseId);setBody(value.body)}}catch{}setReady(true)},[storage]);
 async function send(command:Pending){
  if(sending.current)return;
  sending.current=true;setBusy(true);setNotice('');
  try{sessionStorage.setItem(storage,JSON.stringify(command))}catch{setNotice('امکان نگهداری پیام در این مرورگر فراهم نیست؛ هیچ پیامی ارسال نشد.');setBusy(false);sending.current=false;return}
  setPending(command);
  try{
   await api.post('/support/cases/'+command.caseId+'/human-replies',{body:command.body},command.key);
   // Keep the command if storage cleanup fails; replaying it remains safe.
   try{sessionStorage.removeItem(storage);setPending(null);setBody('');setNotice('پاسخ کارشناس انسانی ثبت شد.')}catch{setNotice('پاسخ ثبت شد؛ برای پاک‌شدن درخواست ذخیره‌شده دوباره پیگیری کنید.')}
  }catch(error){
   if(error instanceof ApiError&&[403,404,409,422].includes(error.status)){
    try{sessionStorage.removeItem(storage);setPending(null)}catch{}
    setNotice('ارسال تأیید نشد؛ دسترسی، وضعیت پرونده و متن را بررسی کنید.');
   }else setNotice('پاسخ قطعی دریافت نشد؛ همان پیام را پیگیری کنید تا دوباره ثبت نشود.');
  }finally{sending.current=false;setBusy(false)}
 }
 function submit(e:FormEvent){e.preventDefault();if(ready&&!pending&&caseId&&body.trim().length>=3)void send({caseId,body:body.trim(),key:newId()})}
 const open=cases.filter(c=>c.status!=='closed');
 return <section className="panel mb-5" aria-label="پاسخ پشتیبانی انسانی"><h2 className="font-black">پاسخ پشتیبانی انسانی</h2>
 {pending?<div><p>پیام در انتظار پاسخ قطعی</p><p style={{whiteSpace:'pre-wrap'}}>{pending.body}</p><button className="button primary" disabled={!ready||busy} onClick={()=>void send(pending)}>پیگیری همان پاسخ کارشناس</button></div>:open.length===0?<p>پرونده‌ای برای پاسخ وجود ندارد.</p>:<form onSubmit={submit}>
 <label className="mt-3 block font-bold">پرونده<select aria-label="پرونده پشتیبانی" className="mt-2 block w-full rounded-xl border p-3" value={caseId} onChange={e=>setCaseId(e.target.value)} disabled={!ready||busy} required><option value="">انتخاب پرونده</option>{open.map(c=><option key={c.id} value={c.id}>{c.subject} · {({open:'باز',in_progress:'در حال رسیدگی',resolved:'رسیدگی‌شده'} as Record<string,string>)[c.status]||'در حال پیگیری'}</option>)}</select></label>
 <label className="mt-3 block font-bold">پیام کارشناس<textarea aria-label="پیام کارشناس انسانی" className="mt-2 block min-h-24 w-full rounded-xl border p-3" value={body} onChange={e=>setBody(e.target.value)} disabled={!ready||busy} required minLength={3} maxLength={4000}/></label>
 <button className="button primary mt-3" disabled={!ready||busy}>ارسال با برچسب کارشناس انسانی</button></form>}
 {(pending?.caseId||caseId)&&<Link className="button secondary mt-3" href={'/support?case='+encodeURIComponent(pending?.caseId||caseId)}>مشاهدهٔ گفت‌وگوی پرونده</Link>}
 {notice&&<p role="status" className="mt-3">{notice}</p>}
 </section>;
}
