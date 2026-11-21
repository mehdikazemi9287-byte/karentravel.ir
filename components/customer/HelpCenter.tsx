import Link from 'next/link';
import type { ReactNode } from 'react';
import { supportPhone } from '../../lib/site-contact';
import '../marketplace/stitch-pages-2026-11.css';

// Help-center family for /support, /contact and /services: same hero family as /flights, /hotels,
// /trains (fl-hero) with the support phone as the primary action. Copy is factual only — no hours,
// addresses or response-time promises that the business has not confirmed.

export function HelpHero({kicker,title,lead,children}:{kicker:string;title:string;lead:string;children?:ReactNode}){
  return <section className="fl-hero fl-hero-help" aria-labelledby="help-title">
    <span className="fl-kicker">{kicker}</span>
    <h1 id="help-title">{title}</h1>
    <p>{lead}</p>
    <div className="hc-cta">
      <a className="hc-call" href={supportPhone.href}><span aria-hidden="true">☎</span> تماس با پشتیبانی <b dir="ltr">{supportPhone.display}</b></a>
      <Link className="hc-ghost" href="/assistant">✦ دستیار هوشمند سفر</Link>
      <Link className="hc-ghost" href="/trips">پیگیری رزروهای من</Link>
    </div>
    {children}
  </section>;
}

const PATHS = [
  {icon:'⌕', title:'پیگیری رزرو', copy:'برای مشاهدهٔ رزرو ثبت‌شده وارد حساب خود شوید. هنگام تماس، شمارهٔ پیگیری را همراه داشته باشید.', href:'/trips', cta:'سفرها و رزروهای من'},
  {icon:'↺', title:'تغییر یا لغو سفر', copy:'شرایط و هزینهٔ تغییر به رزرو شما بستگی دارد. تماس یا ارسال درخواست به‌تنهایی تأیید لغو و بازپرداخت نیست.', href:'/contact', cta:'تماس برای بررسی درخواست'},
  {icon:'✈', title:'راهنمایی پیش از سفر', copy:'مقصد، تاریخ و تعداد مسافران را مشخص کنید تا دربارهٔ خدمت موردنیازتان پرس‌وجو کنید.', href:'/services', cta:'مشاهدهٔ خدمات'},
  {icon:'✦', title:'دستیار هوشمند سفر', copy:'سؤال سفرت را بپرس تا مسیر مناسب جست‌وجو یا درخواست را پیدا کنی.', href:'/assistant', cta:'گفت‌وگو با دستیار'},
] as const;

export function HelpPaths(){
  return <section className="hc-paths" aria-label="مسیرهای پشتیبانی">{PATHS.map(p=>
    <article className="hc-card" key={p.title}>
      <span className="hc-ic" aria-hidden="true">{p.icon}</span>
      <h2>{p.title}</h2>
      <p>{p.copy}</p>
      <Link href={p.href}>{p.cta} ←</Link>
    </article>)}
  </section>;
}

export function HelpFaq(){
  return <section className="hc-faq" aria-labelledby="hc-faq-title">
    <h2 id="hc-faq-title">پرسش‌های رایج</h2>
    <details><summary>کد ورود به دستم نرسیده؛ چه کنم؟</summary><p>شمارهٔ همراه را بررسی کنید. اگر دریافت کد ممکن نشد، برای راهنمایی با شمارهٔ پشتیبانی تماس بگیرید. کد ورودتان را در اختیار دیگران نگذارید.</p><Link href="/login">بازگشت به ورود</Link></details>
    <details><summary>برای پیگیری رزرو چه اطلاعاتی لازم است؟</summary><p>شمارهٔ پیگیری رزرو و شماره‌ای که با آن ثبت‌نام کرده‌اید. رزروهای ثبت‌شده پس از ورود در «سفرهای من» دیده می‌شوند.</p></details>
    <details><summary>با تماس یا ثبت درخواست، لغو من انجام شده است؟</summary><p>نه. شرایط و هزینهٔ تغییر یا لغو به قوانین همان رزرو بستگی دارد و پس از بررسی اعلام می‌شود.</p></details>
    <details><summary>هنگام تماس چه چیزی آماده داشته باشم؟</summary><p>مقصد، تاریخ سفر و تعداد مسافران. برای پیگیری خرید قبلی، شناسهٔ رزرو را هم اعلام کنید.</p></details>
  </section>;
}
