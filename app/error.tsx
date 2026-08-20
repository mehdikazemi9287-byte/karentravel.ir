'use client';

export default function GlobalError({reset}:{error:Error & {digest?:string};reset:()=>void}) {
  return <main className="journey-main" dir="rtl"><section className="confirmation-card"><span>خطای غیرمنتظره</span><h1>نمایش این بخش با مشکل روبه‌رو شد.</h1><p>اطلاعات رزرو یا پرداختی تغییر نکرده است. دوباره تلاش کنید یا از مسیر پشتیبانی ادامه دهید.</p><button type="button" className="plum-button" onClick={reset}>تلاش دوباره</button></section></main>;
}
