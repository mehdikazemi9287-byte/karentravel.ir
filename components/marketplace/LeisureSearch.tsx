'use client';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
function party(value:string|null,fallback:number,min:number){const n=value===null?NaN:Number(value);return Number.isInteger(n)&&n>=min&&n<=50?n:fallback;}
const entries={event_hall:{route:'/events-venues',name:'رویداد',action:'جست‌وجوی رویدادها',hint:'بلیت رویداد و درخواست اختصاصی تالار متفاوت‌اند؛ ظرفیت یا رزرو فقط پس از بررسی همان خدمت مشخص می‌شود.'},pool_sport:{route:'/pools-sports',name:'استخر',action:'جست‌وجوی سانس‌ها',hint:'محدودیت سنی، شرایط ورود و نوع بلیت هر سانس را پیش از رزرو بررسی کن؛ تعرفهٔ کودک فقط در صورت ارائهٔ مجموعه قابل انتخاب است.'},attraction:{route:'/attractions',name:'جاذبه',action:'جست‌وجوی زمان بازدید',hint:'شرایط سنی، زمان ورود و نوع بلیت را در جزئیات بررسی کن؛ انتخاب تعداد به معنی تأیید ظرفیت نیست.'}};
export function LeisureSearch({service}:{service:keyof typeof entries}){
  const entry=entries[service];
  const params=useSearchParams();
  return <form action={entry.route} className="panel stay-search-form dining-search">
    <input type="hidden" name="vertical" value={service}/>
    <label>شهر<input aria-label={"شهر "+entry.name} required name="destination" defaultValue={params.get('destination')||'شیراز'} placeholder="شهر مقصد"/></label>
    <label>تاریخ حضور<input aria-label={"تاریخ حضور "+entry.name} type="date" name="depart" defaultValue={params.get('depart')||''}/></label>
    <label>بزرگسال<input aria-label={"بزرگسال "+entry.name} name="adults" type="number" min={1} max={50} defaultValue={party(params.get('adults'),2,1)}/></label>
    <label>کودک<input aria-label={"کودک "+entry.name} name="children" type="number" min={0} max={50} defaultValue={party(params.get('children'),0,0)}/></label>
    <button className="button primary">{entry.action}</button>
    <p>{entry.hint}</p>{service==='event_hall'&&<Link className="button secondary" href={"/support?"+new URLSearchParams({inquiry:"event_hall",destination:params.get("destination")||"",date:params.get("depart")||"",guests:params.get("adults")||""})}>ثبت درخواست بررسی تالار</Link>}
  </form>;
}
