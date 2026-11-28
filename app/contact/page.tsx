import { JourneyShell } from '../../components/journey/JourneyShell';
import { TripRequestForm } from '../../components/customer/TripRequestForm';
import { HelpHero, HelpPaths, HelpFaq } from '../../components/customer/HelpCenter';
import Link from 'next/link';
import {seoFor} from '../../lib/seo-pages';
import {supportPhone} from '../../lib/site-contact';
import '../../components/customer/info-pages.css';
export const metadata = seoFor('/contact');

export default function ContactPage(){
  return <JourneyShell><main className="journey-main hc-page">
    <HelpHero kicker="همراه شما در مسیر سفر" title="تماس با کارن تراول" lead="برای راهنمایی انتخاب خدمت، بررسی امکان رزرو یا پیگیری درخواست، با شمارهٔ پشتیبانی تماس بگیرید یا درخواستت را ثبت کن."/>
    <section className="hc-section" aria-label="ثبت درخواست سفر"><TripRequestForm/></section>
    <section className="hc-section" aria-labelledby="contact-facts">
      <h2 id="contact-facts">پیش از تماس بدانید</h2>
      <ul className="contact-facts">
        <li>شمارهٔ پشتیبانی کارن تراول: <a href={supportPhone.href} dir="ltr">{supportPhone.display}</a></li>
        <li>رزرو پرواز داخلی فعلاً به‌صورت «درخواست رزرو» است؛ درخواست را ثبت کنید تا کارشناس برای تأیید و صدور بلیت تماس بگیرد.</li>
        <li>برای پیگیری رزرو، شمارهٔ رزرو و نام مسافر را آماده داشته باشید. کارشناسان ما هرگز کد ورود پیامکی یا رمز کارت بانکی شما را نمی‌پرسند.</li>
        <li>کارن تراول سامانهٔ خدمات سفر تاژبان گشت پارس است؛ <Link href="/about">دربارهٔ ما</Link> بیشتر بخوانید.</li>
        <li>شرایط استرداد را در <Link href="/refund-policy">قوانین استرداد و کنسلی</Link> و پاسخ پرسش‌های رایج را در <Link href="/faq">پرسش‌های متداول</Link> ببینید.</li>
      </ul>
    </section>
    <HelpPaths/>
    <HelpFaq/>
  </main></JourneyShell>;
}
