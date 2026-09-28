'use client';
import {useSearchParams} from 'next/navigation';
function party(value:string|null,fallback:number,min:number){const n=value===null?NaN:Number(value);return Number.isInteger(n)&&n>=min&&n<=50?n:fallback;}
export function PoolSearch(){
  const params=useSearchParams();
  return <form action="/pools-sports" className="panel stay-search-form dining-search">
    <input type="hidden" name="vertical" value="pool_sport"/>
    <label>شهر<input aria-label="شهر استخر" required name="destination" defaultValue={params.get('destination')||'شیراز'} placeholder="شهر مقصد"/></label>
    <label>تاریخ حضور<input aria-label="تاریخ حضور استخر" type="date" name="depart" defaultValue={params.get('depart')||''}/></label>
    <label>بزرگسال<input aria-label="بزرگسال استخر" name="adults" type="number" min={1} max={50} defaultValue={party(params.get('adults'),2,1)}/></label>
    <label>کودک<input aria-label="کودک استخر" name="children" type="number" min={0} max={50} defaultValue={party(params.get('children'),0,0)}/></label>
    <button className="button primary">جست‌وجوی سانس‌ها</button>
    <p>محدودیت سنی، شرایط ورود و نوع بلیت هر سانس را پیش از رزرو بررسی کن؛ تعرفهٔ کودک فقط در صورت ارائهٔ مجموعه قابل انتخاب است.</p>
  </form>;
}
