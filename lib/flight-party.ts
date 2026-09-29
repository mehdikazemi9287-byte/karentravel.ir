/** Existing manual flight offers quote one adult seat per unit, never inferred child fares. */
export function flightPartyIssue(adults:number,children:number,infants:number,tripType:string){
 if(!Number.isInteger(adults)||adults<1||adults>20||!Number.isInteger(children)||children<0||!Number.isInteger(infants)||infants<0)return 'تعداد مسافران را در جست‌وجو اصلاح کنید.';
 if(children||infants)return 'نرخ کودک و نوزاد برای این گزینه جداگانه تأیید نشده است؛ پیش از رزرو از پشتیبانی استعلام بگیرید.';
 if(tripType!=='one_way')return 'این گزینه فقط یک مسیر پرواز را پوشش می‌دهد؛ قیمت برگشت یا مسیرهای دیگر در آن نیست. برای رزرو همین مسیر، جست‌وجوی یک‌طرفه را انتخاب کنید.';
 return '';
}
