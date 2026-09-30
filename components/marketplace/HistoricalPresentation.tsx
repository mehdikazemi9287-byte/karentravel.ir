'use client';
import Link from 'next/link';
import Image from 'next/image';
import {useEffect,useState} from 'react';
import {supportPhone} from '../../lib/site-contact';

const compareOptions=[['هزینهٔ نهایی','◇','مبلغ کل','خدمات شامل'],['شرایط تغییر','↺','مهلت کنسلی','هزینهٔ جریمه'],['تناسب با سفر','⌖','موقعیت','امکانات موردنیاز']];
const trips=[
 {title:'سه روز در شیراز',image:'/images/figma/trip-shiraz.jpeg'},
 {title:'آرامش در جزیره قشم',image:'/images/figma/trip-qeshm.jpeg'},
 {title:'مسیر سبز شمال',image:'/images/figma/trip-north.jpeg'}
];
const destinations=[
  {name:'قشم',caption:'جزیره شگفتی‌ها',image:'/images/figma/trip-qeshm.jpeg',className:'qeshm'},
  {name:'شیراز',caption:'شهر شعر و عطر بهارنارنج',image:'/images/figma/trip-shiraz.jpeg',className:'shiraz'},
  {name:'یزد',caption:'شهر بادگیرها',image:'/images/home/hero-yazd.png',className:'isfahan'},
  {name:'ماسوله',caption:'خانه‌های رو به مه',image:'/images/figma/trip-north.jpeg',className:'masuleh'},
];
function Brand(){ return <Link className="brand" href="/" aria-label="کارن‌سیر، صفحه اصلی"><span className="brand-mark" aria-hidden="true">ک</span><span>کارن‌سیر<small>اکوسیستم هوشمند سفر و رفاه</small></span></Link> }
function DestinationMosaic(){return <section className="ref-section ref-container" id="destinations"><div className="ref-heading"><div><span>مقصد بعدی تو کجاست؟</span><h2>ایران، پر از جاهای دیدنی</h2></div><Link href="/destinations">همه مقصدها ←</Link></div><div className="destination-mosaic">{destinations.map((d,i)=><Link href={`/destinations/${["qeshm","shiraz","yazd","masuleh"][i]}`} className={`destination-tile ${d.className}`} key={d.name}><Image src={d.image} fill sizes="(max-width: 700px) 100vw, 50vw" alt={`نمایی از ${d.name}`}/><span><b>{d.name}</b><small>{d.caption}</small></span></Link>)}</div></section>}
function ReferenceTrips(){return <section className="ref-section selected-section" id="selected-trips"><div className="ref-container"><div className="ref-heading"><div><span>برای برنامه‌ریزی سفر</span><h2>ایده‌هایی برای مقصد بعدی تو</h2></div><Link href="/destinations">همه مقصدها ←</Link></div><div className="ref-trip-grid">{trips.map((t,i)=><article className="ref-trip" key={t.title}><Image src={t.image} width={1280} height={640} sizes="(max-width: 700px) 86vw, 33vw" alt={t.title}/><div><span className="ref-mock">راهنمای مقصد</span><h3>{t.title}</h3><p>{['باغ‌ها و معماری شیراز','سواحل و طبیعت جزیره','قدم‌زدن در ماسوله'][i]}</p><div className="trip-fit"><span>ایدهٔ سفر</span><span>نیازمند برنامه‌ریزی</span></div><small className="trip-supplier">این راهنما بستهٔ قابل رزرو نیست؛ برای خدمات و هزینه‌ها استعلام بگیرید.</small><footer><span>کشف مقصد</span><Link href={`/destinations/${['shiraz','qeshm','masuleh'][i]}`}>مشاهده راهنما ←</Link></footer></div></article>)}</div></div></section>}
function CompareBand(){return <section className="compare-band"><div className="ref-container"><div><span>قابلیت امضای کارن‌سیر</span><h2>قبل از انتخاب، کنار هم ببین.</h2><p>قیمت، کیفیت، امکانات، قوانین و ارزش واقعی را یک‌جا بفهم.</p></div><div className="compare-cards">{compareOptions.map(x=><article key={x[0]}><header><strong>{x[0]}</strong><b>{x[1]}</b></header><div><span>{x[2]}</span><span>{x[3]}</span></div></article>)}</div><Link href="/compare">شروع مقایسه ←</Link></div></section>}
function ReferenceFooter(){return <footer className="ref-footer"><div className="ref-footer-curve"/><div className="ref-container ref-footer-grid"><div><Brand/><p>کارن‌سیر؛ از انتخاب مقصد تا تجربه و رفاه سازمانی، همراه تمام مسیر.</p><Link href="/contact">راهنمایی و استعلام خدمات سفر</Link></div><div><b>سفر با کارن‌سیر</b><Link href="/hotels">هتل و اقامتگاه</Link><Link href="/compare">مقایسه</Link><Link href="/assistant">همراه هوشمند</Link></div><div><b>راهکارها</b><Link href="/organization">سازمانی و رفاهی</Link><Link href="/white-label">وایت‌لیبل</Link><Link href="/integrations">همکاری با تأمین‌کنندگان</Link></div><div><b>همراه شما</b><a href={supportPhone.href}>{supportPhone.display}</a><Link href="/support">پشتیبانی سفر</Link><Link href="/contact">تماس با ما</Link></div></div><div className="ref-container ref-footer-bottom"><span>© ۱۴۰۵ کارن‌سیر</span><span><Link href="/terms">قوانین استفاده</Link> · <Link href="/privacy">حریم خصوصی</Link></span></div></footer>}
function FloatingAssistant(){
  const [visible,setVisible]=useState(false);
  useEffect(()=>{
    function check(){const shell=document.querySelector('.ref-search-shell');const clearY=shell?shell.getBoundingClientRect().bottom+window.scrollY:600;setVisible(window.scrollY+window.innerHeight>clearY+40)}
    check();
    window.addEventListener('scroll',check,{passive:true});
    window.addEventListener('resize',check);
    return()=>{window.removeEventListener('scroll',check);window.removeEventListener('resize',check)};
  },[]);
  if(!visible)return null;
  return <Link className="mobile-ai-assistant" href="/assistant" aria-label="بازکردن دستیار هوشمند سفر"><span>AI</span> دستیار AI</Link>;
}
function ReferenceHero(){return <><section className="ref-hero"><Image src="/images/home/hero-yazd.png" fill priority sizes="100vw" alt="مسافری در میان بادگیرها و معماری خشتی یزد"/><div className="ref-hero-shade"/><div className="ref-hero-copy"><span>ایران را دوباره کشف کن</span><h1>تمام سفر،<br/><em>در یک مسیر</em></h1><p>هر مقصد، قصه‌ای تازه است؛ قصه‌ای که با کارن‌سیر از همین‌جا آغاز می‌شود.</p></div><div className="ref-hero-stamp"><b>یزد</b><span>شهر بادگیرها</span></div></section></>}
export {ReferenceHero, DestinationMosaic, ReferenceTrips, CompareBand, ReferenceFooter, FloatingAssistant};

const homeServiceGroups=[['✓','قبل از سفر','بیمه، ویزا، CIP و آماده‌سازی'],['↔','جابه‌جایی','خودرو، ترانسفر و حمل‌ونقل'],['⌂','اقامت','هتل، اقامتگاه و بوم‌گردی'],['♨','رستوران و غذا','رستوران، کافه و غذای مقصد'],['◇','تفریح و تجربه','گشت، راهنما، ورزش و رویداد'],['✣','خرید سفر','صنایع‌دستی، سوغات و ملزومات']];

function HomeServicesHub(){return <section className="home-services-hub" id="home-services"><div className="ref-container"><header><div><span>خدماتی برای تمام مسیر سفر</span><h2>خدمات کارن‌سیر</h2><p>خدمت موردنیازتان را پیدا کنید؛ وضعیت دسترسی و راه تماس در هر بخش روشن است.</p></div><Link href="/services">مشاهده همه خدمات ←</Link></header><div>{homeServiceGroups.map((item,i)=><Link href={`/services?group=${i}`} key={item[1]}><i>{item[0]}</i><span><b>{item[1]}</b><small>{item[2]}</small></span><em>مشاهده ←</em></Link>)}</div><footer><span className="home-credit-symbol">ک</span><p><b>اعتبارپذیر</b> یعنی امکان بررسی اعتبار شخصی یا سازمانی؛ مانده و مجوز مصرف فقط از سامانه معتبر می‌آید.</p></footer></div></section>}

export {HomeServicesHub};
