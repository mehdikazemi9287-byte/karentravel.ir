'use client';
export type HotelRoomSelection={adults:number;children_ages:number[]};
export type HotelStaySelection={check_in:string;check_out:string;rooms:HotelRoomSelection[]};
export function initialHotelRooms(count:number,adults:number):HotelRoomSelection[]{
 return Array.from({length:Math.max(1,Math.min(20,count))},(_,i)=>({adults:Math.floor(adults/count)+(i<adults%count?1:0),children_ages:[]}));
}
export function hotelSelectionIssue(stay:HotelStaySelection,adults:number,children:number){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(stay.check_in)||!/^\d{4}-\d{2}-\d{2}$/.test(stay.check_out)||stay.check_out<=stay.check_in)return 'تاریخ ورود و خروج معتبر را در جست‌وجو انتخاب کنید.';
 if(stay.rooms.some(r=>!Number.isInteger(r.adults)||r.adults<1||r.children_ages.some(a=>!Number.isInteger(a)||a<0||a>17)))return 'هر اتاق به یک بزرگسال نیاز دارد؛ سن کودک باید عدد صحیح صفر تا ۱۷ باشد.';
 if(stay.rooms.reduce((n,r)=>n+r.adults,0)!==adults||stay.rooms.reduce((n,r)=>n+r.children_ages.length,0)!==children)return 'مجموع بزرگسالان و سن کودکان هر اتاق باید با مهمانان جست‌وجو برابر باشد؛ برای تغییر تعداد به جست‌وجو برگردید.';
 if(adults+children>20)return 'برای بیش از ۲۰ مهمان با پشتیبانی هماهنگ کنید.';
 return '';
}
export function HotelStaySummary({stay}:{stay:HotelStaySelection}){
 return <section aria-label="اطلاعات اقامت"><h3>اقامت انتخاب‌شده</h3><p>ورود: <bdi>{stay.check_in}</bdi> · خروج: <bdi>{stay.check_out}</bdi> · {stay.rooms.length.toLocaleString('fa-IR')} اتاق</p>{stay.rooms.map((room,i)=><p key={i}>اتاق {(i+1).toLocaleString('fa-IR')}: {room.adults.toLocaleString('fa-IR')} بزرگسال{room.children_ages.length>0&&`؛ سن کودکان: ${room.children_ages.map(a=>a.toLocaleString('fa-IR')).join('، ')}`}</p>)}</section>
}
export function HotelStayEditor({stay,onChange,disabled,rate}:{stay:HotelStaySelection;onChange:(rooms:HotelRoomSelection[])=>void;disabled:boolean;rate:unknown}){
 const terms=rate&&typeof rate==='object'?rate as Record<string,unknown>:null;
 const occupancy=terms?.occupancy&&typeof terms.occupancy==='object'?terms.occupancy as Record<string,unknown>:null;
 return <section><HotelStaySummary stay={stay}/>{terms?<p>نرخ اعلام‌شده برای {String(terms.room_type||'اتاق')} · {String(terms.rate_plan||'')}؛ ورود <bdi>{String(terms.check_in||'')}</bdi> تا خروج <bdi>{String(terms.check_out||'') }</bdi>. مبلغ هر اتاق برای تمام این بازه است؛ ترکیب مهمانان باید با نرخ عرضه‌شده تطابق داشته باشد.</p>:<p role="status">شرایط دقیق نرخ این اتاق ثبت نشده است. برای استعلام با پشتیبانی تماس بگیرید.</p>}{occupancy&&<p>ترکیب مشمول نرخ هر اتاق: {typeof occupancy.adults==='number'?occupancy.adults.toLocaleString('fa-IR'):'نامشخص'} بزرگسال؛ {Array.isArray(occupancy.children_ages)&&occupancy.children_ages.length?`سن کودکان: ${occupancy.children_ages.filter(age=>typeof age==='number').map(age=>age.toLocaleString('fa-IR')).join('، ')}`:'بدون کودک'}</p>}{stay.rooms.map((room,i)=><fieldset key={i} disabled={disabled}><legend>مهمانان اتاق {(i+1).toLocaleString('fa-IR')}</legend><label>بزرگسال<input aria-label={`بزرگسال اتاق ${i+1}`} type="number" min={1} max={20} value={room.adults} onChange={e=>onChange(stay.rooms.map((r,j)=>j===i?{...r,adults:Number(e.target.value)}:r))}/></label><label>سن کودکان و نوزادان (با کامای انگلیسی جدا کنید)<input aria-label={`سن کودکان اتاق ${i+1}`} placeholder="مثلاً 2,7؛ بدون کودک خالی بگذارید" onChange={e=>onChange(stay.rooms.map((r,j)=>j===i?{...r,children_ages:e.target.value.trim()?e.target.value.split(',').map(v=>/^\d+$/.test(v.trim())?Number(v.trim()):NaN):[]}:r))}/></label></fieldset>)}</section>
}
