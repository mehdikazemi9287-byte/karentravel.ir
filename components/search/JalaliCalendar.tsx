import { useState } from 'react';
import { gregorianToJalali, jalaliMonths, jalaliMonthLength, jalaliToIso, persianDigits, todayJalali, type JalaliDate } from '../../lib/domain/jalali';

const next = (v: JalaliDate): JalaliDate => (v.jm === 12 ? {jy: v.jy + 1, jm: 1, jd: 1} : {...v, jm: v.jm + 1, jd: 1});
const prev = (v: JalaliDate): JalaliDate => (v.jm === 1 ? {jy: v.jy - 1, jm: 12, jd: 1} : {...v, jm: v.jm - 1, jd: 1});

/* Two months side by side on wide screens (one on phones), Fridays in red, the trip range highlighted,
   and «رفت» / «برگشت» tabs so the traveller always knows which date the next tap sets. */
export function JalaliCalendar({depart,returnDate,showReturn,onDepart,onReturn,minIso}:{depart:string;returnDate:string;showReturn:boolean;onDepart:(iso:string)=>void;onReturn:(iso:string)=>void;minIso:string}){
  const today=todayJalali();
  const initial=depart?gregorianToJalali(...depart.split('-').map(Number) as [number,number,number]):today;
  const [view,setView]=useState<JalaliDate>({...initial,jd:1});
  const [target,setTarget]=useState<'depart'|'return'>(showReturn&&depart&&!returnDate?'return':'depart');
  const atStart=view.jy<today.jy||(view.jy===today.jy&&view.jm<=today.jm);
  function pick(iso:string){if(iso<minIso)return;if(target==='return'&&showReturn){if(depart&&iso<depart){onDepart(iso);return}onReturn(iso);return}onDepart(iso);if(showReturn)setTarget('return')}
  function month(m:JalaliDate,extra:string){
    const firstDay=(new Date(jalaliToIso({jy:m.jy,jm:m.jm,jd:1})+'T00:00:00').getDay()+1)%7;
    const cells=Array.from({length:firstDay+jalaliMonthLength(m.jy,m.jm)},(_,i)=>i<firstDay?null:i-firstDay+1);
    return <div className={`jalali-month ${extra}`} key={`${m.jy}-${m.jm}`}>
      <b className="jalali-month-title">{jalaliMonths[m.jm-1]} {persianDigits(m.jy)}</b>
      <div className="jalali-weekdays">{['ش','ی','د','س','چ','پ','ج'].map(x=><span key={x}>{x}</span>)}</div>
      <div className="jalali-grid">{cells.map((day,i)=>{if(day===null)return <span key={i}/>;const iso=jalaliToIso({jy:m.jy,jm:m.jm,jd:day});
        const cls=[i%7===6?'is-friday':'',iso===depart||iso===returnDate?'is-selected':'',showReturn&&depart&&returnDate&&iso>depart&&iso<returnDate?'is-range':'',iso===jalaliToIso({...today}) ?'is-today':''].filter(Boolean).join(' ');
        return <button type="button" key={i} disabled={iso<minIso} aria-pressed={iso===depart||iso===returnDate} aria-label={'انتخاب '+persianDigits(day)+' '+jalaliMonths[m.jm-1]+' '+persianDigits(m.jy)} className={cls} onClick={()=>pick(iso)}>{persianDigits(day)}</button>})}</div>
    </div>;
  }
  return <div className="jalali-calendar" dir="rtl" aria-label="تقویم شمسی">
    {showReturn&&<div className="jalali-targets" role="group" aria-label="انتخاب تاریخ">
      <button type="button" aria-pressed={target==='depart'} className={target==='depart'?'on':''} onClick={()=>setTarget('depart')}>رفت</button>
      <button type="button" aria-pressed={target==='return'} className={target==='return'?'on':''} onClick={()=>setTarget('return')}>برگشت</button></div>}
    <div className="jalali-calendar-head">
      <button type="button" aria-label="ماه قبل" disabled={atStart} onClick={()=>setView(prev)}>›</button>
      <button type="button" className="jalali-today" onClick={()=>setView({...today,jd:1})}>برو به امروز</button>
      <button type="button" aria-label="ماه بعد" onClick={()=>setView(next)}>‹</button>
    </div>
    <div className="jalali-months">{month(view,'')}{month(next(view),'jalali-month--second')}</div>
  </div>;
}
