import Link from 'next/link';
import '../../components/solutions/solutions.css';
import {DemoRequest} from '../../components/solutions/DemoRequest';
import {FAQ, MODULES, PLANS, STEPS} from '../../components/solutions/content';

export const metadata = {
  title: 'راهکارهای کارن تراول برای آژانس‌ها و سازمان‌ها',
  description: 'سایت و اپ با برند خودتان، اتصال به تأمین‌کنندگان، قرارداد و صندوق، میز فروش، باشگاه مشتریان، پیامک و خروجی فرانگر — روی یک پرونده.',
};
const fa = (n: number) => n.toLocaleString('fa-IR');

export default function SolutionsPage() {
  return <div className="so" dir="rtl">
    <header className="so-top"><Link href="/" className="so-brand">کارن تراول</Link><span className="so-tag">برای کسب‌وکارها</span>
      <nav aria-label="راهکارها"><a href="#modules">راهکارها</a><a href="#steps">روش کار</a><a href="#pricing">تعرفه</a><a href="#faq">پرسش‌ها</a></nav>
      <span className="so-top-actions"><a className="so-btn" href="#demo">درخواست قیمت</a><Link className="so-btn ghost" href="/login?redirect=/admin/ops">ورود به پنل</Link></span></header>

    <section className="so-hero">
      <div className="so-hero-text"><span className="so-pill">سامانه‌ی یکپارچه‌ی آژانس مسافرتی</span>
        <h1>از سایت تا سند حسابداری؛ همه روی یک پرونده</h1>
        <p>سایت و اپ با برند خودتان، اتصال به ایرلاین‌ها و هتل‌ها، قرارداد و صندوق، میز فروش، باشگاه مشتریان، پیامک و خروجی فرانگر و مؤدیان — بدون هماهنگ‌سازی و کار دوباره.</p>
        <div className="so-actions"><a className="so-btn" href="#demo">مشاوره‌ی رایگان</a><a className="so-btn light" href="#demo">درخواست دموی آنلاین</a></div>
        <ul className="so-facts"><li><b>{fa(MODULES.length)} ماژول</b><span>روی یک پایگاه داده</span></li><li><b>جداسازی کامل</b><span>داده‌ی هر مجموعه</span></li><li><b>برند شما</b><span>دامنه، لوگو و رنگ</span></li></ul>
      </div>
      <div className="so-preview" aria-label="نمای پیشخوان پنل عملیات">
        <div className="so-preview-kpis">{['فروش امروز', 'طلب از مشتریان', 'حاشیه‌ی سود'].map(k => <div key={k}><small>{k}</small><i aria-hidden="true"/></div>)}</div>
        <div className="so-preview-tasks"><b>کارهای منتظر</b><span>ارسال لیست پرواز</span><span>واریز منتظر تأیید</span><span>تور منتظر انتشار</span></div>
        <small className="so-muted">نمای پیشخوان پنل عملیات</small>
      </div>
    </section>

    <section id="modules" className="so-sec"><h2>راهکارها</h2><p className="so-muted">هر ماژول جدا قابل خرید است و همه روی یک پایگاه داده کار می‌کنند.</p>
      <div className="so-cards">{MODULES.map(mo => <article key={mo.title} className="so-card"><h3>{mo.title}</h3><p>{mo.copy}</p><a href="#demo">بیشتر بدانید ←</a></article>)}</div></section>

    <section id="steps" className="so-band"><h2>چطور شروع می‌کنیم</h2><p>از مشاوره تا فروش اول، با یک کارشناس ثابت</p>
      <ol className="so-steps">{STEPS.map(([t, s], i) => <li key={t}><span className="so-num">{fa(i + 1)}</span><b>{t}</b><small>{s}</small></li>)}</ol></section>

    <section id="pricing" className="so-sec"><h2>تعرفه</h2><p className="so-muted">قیمت هر بسته بر اساس ماژول‌ها و اتصال‌ها پس از جلسه‌ی دمو به‌صورت مکتوب اعلام می‌شود.</p>
      <div className="so-plans">{PLANS.map(p => <article key={p.name} className={`so-plan ${p.badge ? 'featured' : ''}`}><div className="so-plan-head"><h3>{p.name}</h3>{p.badge && <span className="so-pill coral">{p.badge}</span>}</div>
        <p className="so-price">پیشنهاد قیمت پس از دمو</p><ul>{p.features.map(f => <li key={f}>{f}</li>)}</ul><a className={`so-btn ${p.badge ? '' : 'ghost'}`} href="#demo">{p.cta}</a></article>)}</div></section>

    <section className="so-sec so-two" id="demo">
      <div id="faq" className="so-faq"><h2>پرسش‌های پرتکرار</h2>{FAQ.map(([q, a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}</div>
      <DemoRequest/>
    </section>
    <footer className="so-foot"><span>کارن تراول — بخشی از گروه کارن تراول</span><Link href="/">صفحه‌ی اصلی</Link></footer>
  </div>;
}
