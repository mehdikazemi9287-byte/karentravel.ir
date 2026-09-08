import { useState } from 'react';
import { gregorianToJalali, jalaliMonths, jalaliMonthLength, jalaliToIso, persianDigits, todayJalali, type JalaliDate } from '../../lib/domain/jalali';

export function JalaliCalendar({depart,returnDate,showReturn,onDepart,onReturn,minIso}:{depart:string;returnDate:string;showReturn:boolean;onDepart:(iso:string)=>void;onReturn:(iso:string)=>void;minIso:string}){
  const initial=depart?gregorianToJalali(...depart.split('-').map(Number) as [number,number,number]):todayJalali();
  const [view,setView]=useState<JalaliDate>(initial);
  const [target,setTarget]=useState<'depart'|'return'>(returnDate?'return':'depart');
  const first=jalaliToIso({jy:view.jy,jm:view.jm,jd:1});
  const firstDay=(new Date(first+'T00:00:00').getDay()+1)%7;
  const cells=Array.from({length:firstDay+jalaliMonthLength(view.jy,view.jm)},(_,i)=>i<firstDay?null:i-firstDay+1);
  function pick(day:number){const iso=jalaliToIso({jy:view.jy,jm:view.jm,jd:day});if(iso<minIso)return;if(target==='return'&&showReturn&&depart&&iso<depart)return;if(target==='depart'){onDepart(iso);if(showReturn)setTarget('return')}else onReturn(iso)}
  return <div className="jalali-calendar" dir="rtl" aria-label="تقویم شمسی">
    <div className="jalali-calendar-head"><button type="button" aria-label="ماه بعد" onClick={()=>setView(v=>v.jm===12?{jy:v.jy+1,jm:1,jd:1}:{...v,jm:v.jm+1})}>‹</button><b>{jalaliMonths[view.jm-1]} {persianDigits(view.jy)}</b><button type="button" aria-label="ماه قبل" onClick={()=>setView(v=>v.jm===1?{jy:v.jy-1,jm:12,jd:1}:{...v,jm:v.jm-1})}>›</button></div>
    <div className="jalali-weekdays">{['ش','ی','د','س','چ','پ','ج'].map(x=><span key={x}>{x}</span>)}</div>
    <div className="jalali-grid">{cells.map((day,i)=>day===null?<span key={i}/>:<button type="button" key={i} disabled={jalaliToIso({jy:view.jy,jm:view.jm,jd:day})<minIso||(target==='return'&&!!depart&&jalaliToIso({jy:view.jy,jm:view.jm,jd:day})<depart)} aria-label={'انتخاب '+persianDigits(day)+' '+jalaliMonths[view.jm-1]+' '+persianDigits(view.jy)} className={jalaliToIso({jy:view.jy,jm:view.jm,jd:day})===depart||jalaliToIso({jy:view.jy,jm:view.jm,jd:day})===returnDate?'is-selected':''} onClick={()=>pick(day)}>{persianDigits(day)}</button>)}</div>
    {showReturn&&<small className="jalali-target">{target==='depart'?'تاریخ رفت را انتخاب کنید':'تاریخ برگشت را انتخاب کنید'}</small>}
  </div>;
}
