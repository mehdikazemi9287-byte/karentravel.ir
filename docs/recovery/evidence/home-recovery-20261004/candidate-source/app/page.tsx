'use client';
import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  AssistantChatMessage, AssistantEntity, AssistantReplyData, AssistantTurnResponse,
  assistantErrorMessage, consumeResumePending, loadConversationId, loadStoredMessages,
  markResumePending, resetAssistantSession, saveConversationId, saveStoredMessages, selectResultPhrase, sendAssistantMessage,
} from '../lib/api/assistant-client';
import { ConnectedCompare, ConnectedOrganization, ConnectedRolePanel, ErrorState } from '../components/operational/ConnectedViews';
import { EmployeePortal } from '../components/operational/EmployeePortal';
import { AgencyPortal } from '../components/operational/AgencyPortal';
import { WhiteLabelConfig } from '../components/operational/WhiteLabelConfig';
import { NotificationCenter } from '../components/operational/NotificationCenter';
import { useAuth } from '../lib/api/auth-context';
import { HomeSearchExperience } from '../components/search/HomeSearchExperience';
import { ContactOptions, ServiceIntro } from '../components/customer/CustomerHelp';
import { supportPhone } from '../lib/site-contact';
import { MarketplaceHome } from '../components/marketplace/MarketplaceHome';
import { UnifiedSearchView } from '../components/operational/UnifiedSearchView';

const hotels = [
  { name: 'هتل پارسیان آزادی', city: 'تهران', score: '۴.۷', price: '۷٬۸۵۰٬۰۰۰', image: '/images/figma/trip-north.jpeg', tag: 'بهترین کیفیت' },
  { name: 'هتل زندیه', city: 'شیراز', score: '۴.۵', price: '۵٬۹۹۰٬۰۰۰', image: '/images/figma/trip-shiraz.jpeg', tag: 'بهترین ارزش خرید' },
  { name: 'هتل قصر طلایی', city: 'مشهد', score: '۴.۶', price: '۶٬۷۵۰٬۰۰۰', image: '/images/figma/trip-qeshm.jpeg', tag: 'انتخاب سازمانی' }
];
const nav = [['خانه','/'], ['خدمات سفر','/services'], ['پیشنهادها','/destinations'], ['تجربه مقصد','/experiences'], ['سازمانی','/organization'], ['دستیار سفر','/assistant'], ['مقایسه','/compare'], ['اعتبار من','/employee'], ['White Label','/white-label'], ['BackOffice','/integrations']];

function Brand(){ return <Link className="brand" href="/" aria-label="کارن‌سیر، صفحه اصلی"><span className="brand-mark" aria-hidden="true">ک</span><span>کارن‌سیر<small>اکوسیستم هوشمند سفر و رفاه</small></span></Link> }
function Header(){ return <header className="site-header"><div className="header"><Brand/><nav aria-label="ناوبری اصلی">{nav.slice(0,5).map(([n,p])=><Link href={p} key={p}>{n}</Link>)}</nav><div className="header-actions"><Link className="support-link" href="/support">پشتیبانی سفر</Link><Link className="ghost" href="/login">ورود / ثبت‌نام</Link></div></div></header> }
function MobileNav(){ return <nav className="mobile-nav">{nav.slice(0,5).map(([n,p])=><Link href={p} key={p}>{n}</Link>)}</nav> }
function Footer(){return <footer className="footer"><div className="footer-main"><div><Brand/><p>همه‌ی سفر، رفاه و تجربه‌های مقصد در یک مسیر شفاف و قابل اعتماد.</p><Link href="/contact">تماس با کارن تراول</Link></div><div><strong>خدمات سفر</strong><Link href="/hotels">هتل و اقامتگاه</Link><Link href="/compare">مقایسه گزینه‌ها</Link><Link href="/assistant">دستیار هوشمند</Link></div><div><strong>راهکارهای کسب‌وکار</strong><Link href="/organization">خدمات سازمانی</Link><Link href="/white-label">وایت‌لیبل</Link><Link href="/integrations">تأمین‌کنندگان</Link></div><div><strong>همراه شما</strong><Link href="/support">پشتیبانی سفر</Link><a href={supportPhone.href}>{supportPhone.display}</a><Link href="/contact">تماس با ما</Link></div></div><div className="footer-bottom"><span>© ۱۴۰۵ کارن‌سیر؛ همه حقوق محفوظ است.</span><span><Link href="/privacy">حریم خصوصی</Link> · <Link href="/terms">قوانین استفاده</Link></span></div></footer>}
export function Shell({children}:{children:React.ReactNode}){ return <><Header/><main>{children}</main><MobileNav/><Footer/></> }
function Hero(){ return <section className="hero"><div className="hero-copy"><span className="eyebrow light">سفر را همان‌طور که دوست داری تجربه کن</span><h1>از رؤیای سفر تا<br/><em>خاطره‌ای ماندگار</em></h1><p>پرواز، اقامت، تجربه‌های مقصد و مزایای سازمانی؛ همه در یک اکوسیستم هوشمند و همراه.</p><div className="hero-actions"><a className="button aqua" href="#search">سفرت را شروع کن</a><Link className="button glass" href="/assistant">✦ دستیار هوشمند سفر</Link></div><div className="hero-trust"><span>✓ مسیر پشتیبانی روشن</span><span>✓ مقایسه شفاف</span><span>✓ پرداخت پس از اتصال معتبر</span></div></div><div className="hero-image"><Image src="/images/home/hero-yazd.png" alt="معماری یزد و مسافر" fill priority sizes="(max-width: 900px) 100vw, 54vw"/><div className="floating-card"><span>پیشنهاد امروز · Mock</span><strong>قشم، از ۷٬۴۵۰٬۰۰۰ تومان</strong><small>۴ روز و ۳ شب · امتیاز ۴٫۹</small></div></div></section> }
function HotelCard({hotel, compact=false}:{hotel:typeof hotels[number]; compact?:boolean}){return <article className={'hotel-card '+(compact?'compact':'')}><Image src={hotel.image} width={1200} height={800} sizes={compact?'220px':'(max-width: 600px) 255px, 33vw'} alt={hotel.name}/><div className="hotel-info"><div className="card-top"><span className="tag">{hotel.tag}</span><span>★ {hotel.score}</span></div><h3>{hotel.name}</h3><p>{hotel.city} · اتاق دوتخته · صبحانه</p><div className="card-bottom"><span><b>{hotel.price}</b> ریال<small>هر شب · Mock</small></span><span className="hotel-actions"><Link href="/compare" className="text-link">مقایسه</Link><Link href="/booking/confirmation" className="text-link">رزرو Mock ←</Link></span></div></div></article>}
const trips=[
 {title:'سه روز در شیراز',meta:'۳ روز و ۲ شب',price:'۶٬۹۰۰٬۰۰۰',score:'۴٫۷',image:'/images/figma/trip-shiraz.jpeg'},
 {title:'آرامش در جزیره قشم',meta:'۴ روز و ۳ شب',price:'۷٬۴۵۰٬۰۰۰',score:'۴٫۹',image:'/images/figma/trip-qeshm.jpeg'},
 {title:'مسیر سبز شمال',meta:'۳ روز و ۲ شب',price:'۵٬۲۵۰٬۰۰۰',score:'۴٫۵',image:'/images/figma/trip-north.jpeg'}
];
const experiences:Array<[string,string,string,string]>=[['رستوران و کافه','طعم‌های منتخب هر شهر','♨','/restaurants'],['رویداد و تالار','لحظه‌های به‌یادماندنی','◇','/events-venues'],['استخر و ورزش','تندرستی در سفر','◌','/pools-sports'],['اماکن گردشگری و تفریحی','جاذبه‌های هر مقصد','⌖','/attractions']];
function SectionTitle({kicker,title,copy,link}:{kicker:string;title:string;copy?:string;link?:string}){return <div className="section-title"><div><span className="eyebrow">{kicker}</span><h2>{title}</h2>{copy&&<p>{copy}</p>}</div>{link&&<Link href={link}>مشاهده همه ←</Link>}</div>}
function Trips(){return <section className="section container" id="offers"><SectionTitle kicker="پیشنهادهای ویژه" title="سفرهای انتخاب‌شده برای تو" copy="ترکیبی از مقصد، اقامت و تجربه؛ با داده‌های نمایشی شفاف." link="/hotels"/><div className="trip-grid">{trips.map(t=><article className="trip-card" key={t.title}><Image src={t.image} width={1280} height={640} sizes="(max-width: 600px) 82vw, (max-width: 900px) 33vw, 380px" alt={`نمایی از ${t.title}`}/><div><span className="mock-label">پکیج Mock</span><h3>{t.title}</h3><p>{t.meta}</p><strong>شروع از {t.price} تومان</strong><footer><span>★ {t.score}</span><Link href="/compare" aria-label={`مقایسه ${t.title}`}>←</Link></footer></div></article>)}</div></section>}
function SmartFeatures(){return <section className="smart-section"><div className="container smart-grid"><div className="assistant-showcase"><span className="spark">✦</span><span className="eyebrow light">همراه هوشمند کارن‌سیر</span><h2>یک سفر خوب، از یک گفت‌وگوی خوب شروع می‌شود.</h2><p>بودجه، علایق و محدودیت‌هایت را بگو؛ دستیار سفر گزینه‌های Mock را کنار هم می‌چیند و دلیل هر پیشنهاد را شفاف نشان می‌دهد.</p><div className="mini-chat"><span>برای یک سفر آرام سه‌روزه کجا پیشنهاد می‌کنی؟</span><b>یزد و کاشان، با دو سبک متفاوت…</b></div><Link className="button aqua" href="/assistant">گفت‌وگو با دستیار</Link></div><div className="compare-showcase"><span className="eyebrow">مقایسه هوشمند</span><h2>بهترین گزینه، فقط ارزان‌ترین نیست.</h2><p>قیمت، کیفیت، امکانات، قوانین کنسلی و policy سازمانی را یک‌جا ببین.</p><div className="compare-mini"><div><span>هتل زندیه</span><b>۹۲</b><i style={{width:'92%'}}/></div><div><span>پارسیان آزادی</span><b>۸۶</b><i style={{width:'86%'}}/></div><div><span>قصر طلایی</span><b>۸۱</b><i style={{width:'81%'}}/></div></div><Link className="text-link" href="/compare">شروع مقایسه ←</Link></div></div></section>}
function Experiences(){return <section className="section container" id="experiences"><SectionTitle kicker="فراتر از رزرو" title="مقصد را زندگی کن" copy="از میز شام تا یک راهنمای محلی؛ تجربه سفر جایی بیرون از اتاق هتل کامل می‌شود."/><div className="experience-grid">{experiences.map(x=><article key={x[0]}><span>{x[2]}</span><h3>{x[0]}</h3><p>{x[1]}</p><Link href="/assistant">کشف تجربه‌ها ←</Link></article>)}</div></section>}
function OrganizationFeature(){return <section className="organization-feature"><div className="container org-grid"><div><span className="eyebrow light">کارن‌سیر برای سازمان‌ها</span><h2>رفاه کارکنان، ساده برای آن‌ها؛ شفاف برای شما.</h2><p>اعتبار سفر، کیف پول، اقساط، مزایای رفاهی و گردش تأیید را با سیاست‌های tenant-aware مدیریت کنید؛ بدون اتصال نمایشی به پرداخت یا provider واقعی.</p><div className="org-actions"><Link href="/organization" className="button warm">راهکار سازمانی</Link><Link href="/white-label" className="button glass">وایت‌لیبل اختصاصی</Link></div></div><div className="wallet-card"><div className="wallet-head"><span>کیف پول رفاهی · Mock</span><b>کارن‌سیر سازمانی</b></div><small>اعتبار قابل استفاده</small><strong>۴۸٬۰۰۰٬۰۰۰ <em>ریال</em></strong><div className="wallet-stats"><span>سفر <b>۶۰٪</b></span><span>ورزش <b>۲۵٪</b></span><span>رویداد <b>۱۵٪</b></span></div><p>✓ منطبق با سیاست فعال سازمان</p></div></div></section>}
function Ecosystem(){return <section className="section container ecosystem" id="services"><SectionTitle kicker="یک حساب، یک تجربه یکپارچه" title="اکوسیستم کارن‌سیر چطور همراهت می‌ماند؟"/><div className="ecosystem-flow"><div><b>۱</b><span>کشف و برنامه‌ریزی</span><small>جست‌وجو و دستیار هوشمند</small></div><i>←</i><div><b>۲</b><span>مقایسه و انتخاب</span><small>قیمت، کیفیت و policy</small></div><i>←</i><div><b>۳</b><span>سفر و تجربه مقصد</span><small>اقامت، رویداد و خدمات محلی</small></div><i>←</i><div><b>۴</b><span>پشتیبانی و بازگشت</span><small>همراهی و کیف پول</small></div></div><div className="trust-row"><span><b>روشن</b> مسیر پشتیبانی</span><span><b>شفاف</b> مقایسه قابل توضیح</span><span><b>امن</b> اتصال fail-closed</span><span><b>یکپارچه</b> سفر و رفاه</span></div></section>}
function Partners(){return <section className="partners"><div className="container"><p>همراه کسب‌وکارهای سفر و رفاه</p><div><span>هتل‌ها</span><span>آژانس‌ها</span><span>راهنمایان</span><span>مجموعه‌های ورزشی</span><span>سازمان‌ها</span></div><Link href="/integrations">پیوستن به شبکه تأمین‌کنندگان ←</Link></div></section>}
const destinations=[
  {name:'قشم',caption:'جزیره شگفتی‌ها',image:'/images/figma/trip-qeshm.jpeg',className:'qeshm'},
  {name:'شیراز',caption:'شهر شعر و عطر بهارنارنج',image:'/images/figma/trip-shiraz.jpeg',className:'shiraz'},
  {name:'یزد',caption:'شهر بادگیرها',image:'/images/home/hero-yazd.png',className:'isfahan'},
  {name:'ماسوله',caption:'خانه‌های رو به مه',image:'/images/figma/trip-north.jpeg',className:'masuleh'},
];
function HomeHeader(){return <header className="ref-header"><div className="ref-container"><Brand/><nav aria-label="ناوبری صفحه اصلی"><a href="#home-services">خدمات</a><Link href="/trips">سفرهای من</Link><Link href="/nearby">اطراف من</Link><Link href="/organization">سازمانی</Link></nav><div><Link href="/support" className="ref-help">پشتیبانی</Link><Link href="/login" className="ref-login">ورود / ثبت‌نام</Link></div></div></header>}
// Reuses the existing sitewide .mobile-nav bar/CSS (see MobileNav above) so the
// Homepage's own header links (HomeHeader, above - different targets than the
// generic Header's `nav` array) are reachable below ~800px too. HomeHeader's
// nav collapses to nothing at <=900px with no replacement, which was the
// reported mobile-navigation gap: خدمات/سفرهای من/اطراف من/سازمانی/پشتیبانی
// were unreachable on mobile with no menu button anywhere in the header.
function HomeMobileNav(){return <nav className="mobile-nav" aria-label="ناوبری صفحه اصلی (موبایل)"><a href="#home-services">خدمات</a><Link href="/trips">سفرهای من</Link><Link href="/nearby">اطراف من</Link><Link href="/organization">سازمانی</Link><Link href="/support">پشتیبانی</Link></nav>}
function SearchResultsSlot(){
  // Renders the same UnifiedSearchView used at /search/results, inline,
  // directly beneath the Homepage search form - only once a real search has
  // been submitted (presence of `destination` in the URL is the same signal
  // HomeSearchExperience always sets). No second engine, no duplicated
  // logic: this is the exact same component, just embedded in place instead
  // of navigating to a separate route.
  const searchParams=useSearchParams();
  if(searchParams.get('destination')===null)return null;
  return <UnifiedSearchView embedded/>;
}
function ReferenceHero(){return <><section className="ref-hero"><Image src="/images/home/hero-yazd.png" fill priority sizes="100vw" alt="مسافری در میان بادگیرها و معماری خشتی یزد"/><div className="ref-hero-shade"/><div className="ref-hero-copy"><span>ایران را دوباره کشف کن</span><h1>سفر را<br/><em>زندگی کن</em></h1><p>هر مقصد، قصه‌ای تازه است؛ قصه‌ای که با کارن‌سیر از همین‌جا آغاز می‌شود.</p></div><div className="ref-hero-stamp"><b>یزد</b><span>شهر بادگیرها</span></div></section><div className="ref-search-shell"><Suspense fallback={null}><HomeSearchExperience/></Suspense><Suspense fallback={null}><SearchResultsSlot/></Suspense><div className="search-human-help"><span><b>نیاز به راهنمایی داری؟</b><small>کارشناس انسانی، جدا از دستیار هوشمند</small></span><Link href="/support?channel=expert">صحبت با کارشناس</Link></div></div></>}
const homeServiceGroups=[['✓','قبل از سفر','بیمه، ویزا، CIP و آماده‌سازی'],['↔','جابه‌جایی','خودرو، ترانسفر و حمل‌ونقل'],['⌂','اقامت','هتل، اقامتگاه و بوم‌گردی'],['♨','رستوران و غذا','رستوران، کافه و غذای مقصد'],['◇','تفریح و تجربه','گشت، راهنما، ورزش و رویداد'],['✣','خرید سفر','صنایع‌دستی، سوغات و ملزومات']];
function HomeServicesHub(){return <section className="home-services-hub" id="home-services"><div className="ref-container"><header><div><span>خدماتی برای تمام مسیر سفر</span><h2>خدمات کارن‌سیر</h2><p>خدمت موردنیازتان را پیدا کنید؛ وضعیت دسترسی و راه تماس در هر بخش روشن است.</p></div><Link href="/services">مشاهده همه خدمات ←</Link></header><div>{homeServiceGroups.map((item,i)=><Link href={`/services?group=${i}`} key={item[1]}><i>{item[0]}</i><span><b>{item[1]}</b><small>{item[2]}</small></span><em>مشاهده ←</em></Link>)}</div><footer><span className="home-credit-symbol">ک</span><p><b>اعتبارپذیر</b> یعنی امکان بررسی اعتبار شخصی یا سازمانی؛ مانده و مجوز مصرف فقط از سامانه معتبر می‌آید.</p></footer></div></section>}
function DestinationMosaic(){return <section className="ref-section ref-container" id="destinations"><div className="ref-heading"><div><span>مقصد بعدی تو کجاست؟</span><h2>ایران، پر از جاهای دیدنی</h2></div><Link href="/destinations">همه مقصدها ←</Link></div><div className="destination-mosaic">{destinations.map((d,i)=><Link href={`/destinations/${["qeshm","shiraz","yazd","masuleh"][i]}`} className={`destination-tile ${d.className}`} key={d.name}><Image src={d.image} fill sizes="(max-width: 700px) 100vw, 50vw" alt={`نمایی از ${d.name}`}/><span><b>{d.name}</b><small>{d.caption}</small></span></Link>)}</div></section>}
function ReferenceTrips(){return <section className="ref-section selected-section" id="selected-trips"><div className="ref-container"><div className="ref-heading"><div><span>برای برنامه‌ریزی سفر</span><h2>ایده‌هایی برای مقصد بعدی تو</h2></div><Link href="/destinations">همه مقصدها ←</Link></div><div className="ref-trip-grid">{trips.map((t,i)=><article className="ref-trip" key={t.title}><Image src={t.image} width={1280} height={640} sizes="(max-width: 700px) 86vw, 33vw" alt={t.title}/><div><span className="ref-mock">راهنمای مقصد</span><h3>{t.title}</h3><p>{['باغ‌ها و معماری شیراز','سواحل و طبیعت جزیره','قدم‌زدن در ماسوله'][i]}</p><div className="trip-fit"><span>ایدهٔ سفر</span><span>نیازمند برنامه‌ریزی</span></div><small className="trip-supplier">این راهنما بستهٔ قابل رزرو نیست؛ برای خدمات و هزینه‌ها استعلام بگیرید.</small><footer><span>کشف مقصد</span><Link href={`/destinations/${['shiraz','qeshm','masuleh'][i]}`}>مشاهده راهنما ←</Link></footer></div></article>)}</div></div></section>}
function SmartCompanion(){const capabilities=['پیشنهاد مقصد متناسب با بودجه','برنامه‌ریزی سفر','مقایسه پرواز، هتل، پرواز + هتل و سایر خدمات','پیشنهاد گزینه‌های مناسب','راهنمایی قبل، حین و بعد از سفر'];return <section className="ref-section ref-container ai-travel-section" id="smart-companion" aria-labelledby="ai-travel-title"><div className="smart-banner"><div className="smart-portrait" aria-hidden="true"><span>AI</span><b>✦</b><small>هوش سفر کارن‌سیر</small></div><div className="ai-travel-copy"><span className="smart-kicker"><i>AI</i> همراه هوشمند سفر</span><h2 id="ai-travel-title">دستیار هوشمند سفر کارن‌سیر</h2><p>مقصد، بودجه و شرایطت را بگو؛ سفرت را هوشمندانه طراحی و مقایسه می‌کنم.</p><ul className="ai-capabilities">{capabilities.map(capability=><li key={capability}><span aria-hidden="true">✓</span>{capability}</li>)}</ul><Link href="/assistant" className="coral-button">شروع گفتگو با AI</Link></div></div></section>}
const compareOptions=[['هزینهٔ نهایی','◇','مبلغ کل','خدمات شامل'],['شرایط تغییر','↺','مهلت کنسلی','هزینهٔ جریمه'],['تناسب با سفر','⌖','موقعیت','امکانات موردنیاز']];
function CompareBand(){return <section className="compare-band"><div className="ref-container"><div><span>قابلیت امضای کارن‌سیر</span><h2>قبل از انتخاب، کنار هم ببین.</h2><p>قیمت، کیفیت، امکانات، قوانین و ارزش واقعی را یک‌جا بفهم.</p></div><div className="compare-cards">{compareOptions.map(x=><article key={x[0]}><header><strong>{x[0]}</strong><b>{x[1]}</b></header><div><span>{x[2]}</span><span>{x[3]}</span></div></article>)}</div><Link href="/compare">شروع مقایسه ←</Link></div></section>}
function LocalExperiences(){return <section className="ref-section ref-container"><div className="ref-heading"><div><span>سفر فقط رسیدن نیست</span><h2>تجربه‌های مقصد را کامل کن</h2></div><Link href="/experiences">مشاهده همه تفریح و تجربه ←</Link></div><div className="ref-experiences">{experiences.map(x=><Link href={x[3]} key={x[0]}><i>{x[2]}</i><span><b>{x[0]}</b><small>{x[1]}</small></span><em>←</em></Link>)}</div></section>}
function ReferenceOrganization(){return <section className="ref-org"><div className="ref-container"><div className="org-art"><div className="org-window"><span>خدمات رفاهی سازمان</span><b>سفر و رفاه کارکنان</b><i><em style={{width:'68%'}}/></i><small>فعال‌سازی خدمات وابسته به قرارداد سازمان است.</small></div><div className="org-person">ک</div></div><div><span>کارن‌سیر برای سازمان‌ها</span><h2>حال خوب کارکنان،<br/>مدیریت ساده برای شما</h2><p>سفر، کیف پول، اقساط و مزایای رفاهی را با سیاست‌های شفاف و وایت‌لیبل اختصاصی در یک مسیر مدیریت کنید.</p><div className="org-value"><span><b>اعتبار سازمانی</b><small>پس از احراز و استعلام</small></span><span><b>سهم شخصی</b><small>شفاف پیش از پرداخت</small></span><span><b>گردش تأیید</b><small>قابل پیگیری برای کارمند</small></span></div><div><Link className="plum-button" href="/organization">خدمات سازمانی</Link><Link className="text-plum" href="/white-label">وایت‌لیبل اختصاصی ←</Link></div></div></div></section>}
const trustItems=[['⌁','مجوزها و اطلاعات ثبتی','فقط پس از دریافت و راستی‌آزمایی منتشر می‌شود.'],['§','قوانین و حقوق مسافر','شرایط، موارد شامل و مسیر پیگیری شفاف.'],['✓','پرداخت و بازگشت وجه','وضعیت نهایی فقط از سرویس مالی مجاز دریافت می‌شود.'],['◇','تأمین‌کننده و پشتیبانی','هویت ارائه‌دهنده و مسئولیت خدمت پیش از خرید.']];
function TrustSection(){return <section className="trust-section"><div className="ref-container"><div className="ref-heading"><div><span>اعتماد، بخشی از مسیر است</span><h2>با خیال راحت سفر کن</h2><p>پیش از خرید، شرایط خدمت را بررسی کنید و پرسش‌هایتان را با ما در میان بگذارید.</p></div><Link href="/integrations">مرکز اطلاعات و همکاری ←</Link></div><div className="trust-grid">{trustItems.map(x=><article key={x[1]}><i aria-hidden="true">{x[0]}</i><div><h3>{x[1]}</h3><p>{x[2]}</p></div><Link href="/contact">پرسش از پشتیبانی ←</Link></article>)}</div></div></section>}
function ServiceRibbon(){return <section className="service-ribbon" aria-label="فضای خدمات آینده"><div className="ref-container" aria-hidden="true"/></section>}
function ReferenceFooter(){return <footer className="ref-footer"><div className="ref-footer-curve"/><div className="ref-container ref-footer-grid"><div><Brand/><p>کارن‌سیر؛ از انتخاب مقصد تا تجربه و رفاه سازمانی، همراه تمام مسیر.</p><Link href="/contact">راهنمایی و استعلام خدمات سفر</Link></div><div><b>سفر با کارن‌سیر</b><Link href="/hotels">هتل و اقامتگاه</Link><Link href="/compare">مقایسه</Link><Link href="/assistant">همراه هوشمند</Link></div><div><b>راهکارها</b><Link href="/organization">سازمانی و رفاهی</Link><Link href="/white-label">وایت‌لیبل</Link><Link href="/integrations">همکاری با تأمین‌کنندگان</Link></div><div><b>همراه شما</b><a href={supportPhone.href}>{supportPhone.display}</a><Link href="/support">پشتیبانی سفر</Link><Link href="/contact">تماس با ما</Link></div></div><div className="ref-container ref-footer-bottom"><span>© ۱۴۰۵ کارن‌سیر</span><span><Link href="/terms">قوانین استفاده</Link> · <Link href="/privacy">حریم خصوصی</Link></span></div></footer>}
// On mobile the Homepage's hero + search widget together span nearly the
// entire viewport width and well past its height (measured: search widget
// alone ~520px tall in a ~780px-tall 430px-wide viewport, leaving no static
// corner clear of either the hero destination badge or the search form's
// controls - moving the button between corners just traded one real overlap
// for another, confirmed by measuring getBoundingClientRect() on both).
// Showing the button only once the user has scrolled past the search widget
// avoids the collision entirely, at any viewport height, without shrinking,
// redesigning, or repositioning the search widget itself.
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
function Home(){return <div className="home-page"><HomeHeader/><main><ReferenceHero/><HomeServicesHub/><DestinationMosaic/><ReferenceTrips/><SmartCompanion/><CompareBand/><LocalExperiences/><ReferenceOrganization/><TrustSection/><ServiceRibbon/></main><HomeMobileNav/><ReferenceFooter/><FloatingAssistant/></div>}
function Hotels(){return <Shell><ServiceIntro title="هتل و اقامتگاه" description="مقصدتان را انتخاب کنید و گزینه‌های موجود را بررسی کنید. برای راهنمایی انتخاب محل اقامت با ما تماس بگیرید." vertical="hotel"/></Shell>}
function Compare(){return <Shell><div className="page-hero"><span className="eyebrow">مقایسه حرفه‌ای · داده معتبر</span><h1>تفاوت‌ها را یک‌جا ببینید.</h1><p>برای مقایسه، ابتدا از نتایج جست‌وجو دست‌کم دو گزینه انتخاب کنید. اگر گزینه‌ای موجود نیست، برای راهنمایی با پشتیبانی تماس بگیرید.</p><p className="mt-2 text-sm"><a className="text-link" href="/compare/package">مقایسه و رزرو بسته پرواز + هتل ←</a></p></div><div className="container"><Link className="button primary" href="/hotels">جست‌وجوی اقامت</Link><ContactOptions/></div><ConnectedCompare/></Shell>}
const policyIntents=['هتل کیش برای دو نفر یک اتاق','پرواز تهران استانبول جمعه تا دوشنبه','ارزون‌ترین گزینه رو نشون بده','می‌خوام کنسل کنم','با یک نفر صحبت کنم'];

function formatOfferPrice(entity: AssistantEntity): string {
  const price = entity.best_offer?.final_price ?? entity.price;
  const currency = entity.best_offer?.currency ?? entity.currency ?? '';
  if (price == null) return 'قیمت نامشخص';
  return `${Number(price).toLocaleString('fa-IR')} ${currency === 'IRR' ? 'ریال' : currency}`;
}

function AssistantResultCards({ entities, disabled, onSelect }: { entities: AssistantEntity[]; disabled: boolean; onSelect: (displayIndex: number) => void }) {
  return <div className="assistant-results" role="list">
    {entities.map((entity, i) => {
      const displayIndex = entity.display_index ?? i + 1;
      const phrase = selectResultPhrase(displayIndex);
      return <article className="panel assistant-result-card" role="listitem" key={entity.entity_id || i}>
        <span className="tag">گزینه {displayIndex}</span>
        <h3>{entity.title || 'بدون عنوان'}</h3>
        <p>{formatOfferPrice(entity)}</p>
        {phrase && <button className="button secondary" type="button" disabled={disabled} onClick={() => onSelect(displayIndex)}>انتخاب این گزینه</button>}
      </article>;
    })}
  </div>;
}

function AssistantPanel({ children, tone }: { children: React.ReactNode; tone: 'warn' | 'error' | 'ok' }) {
  return <div className={`panel assistant-panel assistant-panel-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{children}</div>;
}

// Real integration (Phase 6): every message goes through the Assistant
// gateway (/assistant/message -> karenseir-assistant), which is anonymous-
// friendly by design -- Search/Planning/Conversation work with no session.
// Bearer identity, when a session exists, rides the standard Authorization
// header via api.postOptionalAuth; this component never reads or stores a
// token itself. All UI state (approval/auth-required/reservation panels) is
// derived purely from the LAST assistant reply's structured data -- no
// separate client-side state machine to drift from the backend's own.
function Assistant(){
  const router = useRouter();
  const { api, session } = useAuth();
  // Server-rendered HTML has no sessionStorage, so state MUST start from the
  // same SSR-safe default on both server and client (an empty transcript) --
  // reading sessionStorage inside a useState initializer would make the
  // client's first paint differ from the server's and trigger a hydration
  // mismatch (React error #418). Restoring the saved conversation happens
  // only inside this effect, after hydration -- the same pattern this app's
  // own auth-context.tsx already uses for restoring the session.
  const [messages, setMessages] = useState<AssistantChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resumeAvailable, setResumeAvailable] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const requestedPrompt=new URLSearchParams(window.location.search).get("prompt");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate client-only state (URL prompt, localStorage) after mount
    if(requestedPrompt)setDraft(requestedPrompt.slice(0,1000));
    setConversationId(loadConversationId());
    setMessages(loadStoredMessages());
    setHydrated(true);
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot resume flag read from sessionStorage after login
  useEffect(() => { if (session && consumeResumePending()) setResumeAvailable(true); }, [session]);
  useEffect(() => { if (hydrated) saveStoredMessages(messages); }, [hydrated, messages]);

  const lastAssistantData: AssistantReplyData | undefined = [...messages].reverse().find(m => m.role === 'assistant')?.data;

  async function run(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;
    setBusy(true); setError(null); setResumeAvailable(false);
    setMessages(current => [...current, { role: 'user', text }]);
    setDraft('');
    try {
      const resp: AssistantTurnResponse = await sendAssistantMessage(api, conversationId, text);
      setConversationId(resp.conversation_id);
      saveConversationId(resp.conversation_id);
      setMessages(current => [...current, { role: 'assistant', text: resp.message.text, data: resp.message.data }]);
    } catch (err) {
      setError(assistantErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function goToLogin() {
    markResumePending();
    router.push('/login?redirect=/assistant');
  }

  // The same real backend action (CANCEL_CURRENT_FLOW) backs "انصراف" on
  // both the approval and auth-required panels and "لغو رزرو" on a live
  // reservation -- it clears pending state and, when a real hold exists,
  // triggers the genuine rollback (release_reservation_hold), never a
  // frontend-only "pretend cancel".
  function cancelOrRollback() { run('از اول'); }

  const authRequired = lastAssistantData?.type === 'AUTHENTICATION_REQUIRED';
  const reservationResult = lastAssistantData?.reservation_result;
  const releaseResult = lastAssistantData?.release_result;
  const pendingApproval = !authRequired && !reservationResult && !!lastAssistantData?.requires_approval && !!lastAssistantData?.pending_approval_id;
  const readiness = lastAssistantData?.readiness;
  const searchEntities = lastAssistantData?.type === 'SEARCH_RESULT_CARD' ? (lastAssistantData.result?.entities ?? []) : [];

  return <Shell><div className="assistant-page"><section className="assistant-intro">
    <span className="eyebrow">✦ دستیار هوشمند کارن‌سیر</span>
    <h1>از تصمیم سفر تا<br/>مدیریت رزرو همراهت هستم.</h1>
    <p>مقصد و زمان سفرتان را بگویید. نتیجهٔ جست‌وجو به دسترسی خدمات بستگی دارد و گفت‌وگو به معنی تأیید رزرو نیست.</p>
    <ContactOptions/><div className="assistant-steps"><span>جست‌وجو و مقایسه</span><span>انتخاب و تأیید</span><span>رزرو موقت و لغو</span></div>
    <div className="policy-intents" aria-label="نمونه پرسش‌های قابل فهم">{policyIntents.map(intent=><span key={intent} role="button" tabIndex={0} onClick={()=>run(intent)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();run(intent)}}}>{intent}</span>)}</div>
  </section>
  <section className="chat">
    <div className="chat-bar"><button type="button" disabled={busy} onClick={()=>{resetAssistantSession();setConversationId(null);setMessages([]);setError(null);setResumeAvailable(false)}}>گفت‌وگوی تازه</button>دستیار سفر کارن‌سیر <span>{session ? '● وارد شده' : '● مهمان'}</span></div>
    {resumeAvailable && <div className="assistant-resume-banner" role="status">
      <span>وارد حساب شدید؛ برای ادامه‌ی همان رزرو دکمه زیر را بزنید.</span>
      <button className="button primary" type="button" disabled={busy} onClick={()=>run('تایید می‌کنم')}>ادامه رزرو</button>
    </div>}
    <div className="messages">
      {messages.length===0 && <div className="message bot">سلام! بگویید کجا می‌خواهید سفر کنید تا جست‌وجو را شروع کنم.</div>}
      {messages.map((message,index)=><div className={`message ${message.role==='user'?'user':'bot'}`} key={index}>{message.text}</div>)}
      {busy && <div className="message bot" role="status" aria-live="polite">در حال بررسی…</div>}
      {error && <div className="message bot assistant-message-error" role="alert">{error}</div>}
      {searchEntities.length>0 && <AssistantResultCards entities={searchEntities} disabled={busy} onSelect={(idx)=>{const phrase=selectResultPhrase(idx); if(phrase) run(phrase);}} />}
      {readiness?.ready && !pendingApproval && !authRequired && !reservationResult && <div className="assistant-inline-actions">
        <button className="button secondary" type="button" disabled={busy} onClick={()=>run('ادامه بده')}>درخواست تأیید رزرو</button>
      </div>}
      {lastAssistantData?.type==='SELECT_RESULT' && lastAssistantData.selected && !readiness && <div className="assistant-inline-actions">
        <button className="button secondary" type="button" disabled={busy} onClick={()=>run('رزروش کن')}>آماده‌سازی رزرو</button>
      </div>}
      {authRequired && <AssistantPanel tone="warn">
        <strong>برای ادامه رزرو، وارد حساب کاربری شوید.</strong>
        <p>گفت‌وگو و انتخاب شما نگه داشته می‌شود؛ پس از ورود، همین‌جا ادامه می‌دهیم -- نیازی به تأیید دوباره نیست.</p>
        <div className="assistant-panel-actions">
          <button className="button primary" type="button" onClick={goToLogin}>ورود</button>
          <button className="button ghost" type="button" disabled={busy} onClick={cancelOrRollback}>انصراف</button>
        </div>
      </AssistantPanel>}
      {pendingApproval && <AssistantPanel tone="warn">
        <strong>تأیید رزرو موقت</strong>
        <p>با تأیید شما، درخواست «رزرو موقت» (نه رزرو نهایی و نه پرداخت) برای گزینه انتخابی شما ثبت می‌شود.</p>
        <div className="assistant-panel-actions">
          <button className="button primary" type="button" disabled={busy} onClick={()=>run('تایید می‌کنم')}>تأیید و ادامه</button>
          <button className="button ghost" type="button" disabled={busy} onClick={cancelOrRollback}>انصراف</button>
        </div>
      </AssistantPanel>}
      {reservationResult && <AssistantPanel tone={reservationResult.status==='ok'?'ok':'error'}>
        {reservationResult.status==='ok'
          ? <><strong>رزرو موقت با موفقیت ثبت شد.</strong><p>این رزرو نهایی/پرداخت‌شده نیست. شناسه رزرو: {reservationResult.reservation_id ?? '—'}</p></>
          : <><strong>رزرو انجام نشد.</strong><p>قیمت، ظرفیت یا دسترسی به این گزینه تأیید نشد. دوباره جست‌وجو کنید یا از پشتیبانی کمک بگیرید.</p></>}
        {reservationResult.status==='ok' && <div className="assistant-panel-actions">
          {reservationResult.reservation_id&&<><Link className="button primary" href={`/checkout/${reservationResult.reservation_id}`}>تکمیل اطلاعات و ادامهٔ رزرو</Link><Link className="button secondary" href={`/manage-booking/${reservationResult.reservation_id}`}>پیگیری رزرو</Link></>}<button className="button ghost" type="button" disabled={busy} onClick={cancelOrRollback}>درخواست لغو رزرو</button>
        </div>}
      </AssistantPanel>}
      {releaseResult && <AssistantPanel tone={releaseResult.status==='ok'?'ok':'error'}>
        {releaseResult.status==='ok' ? <strong>درخواست لغو رزرو ثبت شد.</strong> : <><strong>لغو رزرو انجام نشد.</strong><p>درخواست لغو تأیید نشد؛ وضعیت رزرو را از حساب یا پشتیبانی پیگیری کنید.</p></>}
      </AssistantPanel>}
    </div>
    <form className="chat-input" onSubmit={event=>{event.preventDefault();run(draft)}}>
      <input value={draft} onChange={event=>setDraft(event.target.value)} placeholder="مثلاً: هتل کیش برای دو نفر یک اتاق" aria-label="پیام به دستیار هوشمند" disabled={busy} style={{flex:1,border:'none',outline:'none',background:'transparent',font:'inherit',color:'inherit'}}/>
      <button type="submit" disabled={busy || !draft.trim()}>ارسال</button>
    </form>
  </section></div></Shell>;
}
function Organization(){return <Shell><div className="page-hero"><span className="eyebrow">داشبورد سازمانی</span><h1>ساختار و گردش تأیید سازمان</h1><p>نمای نقش‌محور با داده سازمان احرازشده.</p></div><div className="container"><ContactOptions/></div><ConnectedOrganization/></Shell>}
function Employee(){return <Shell><EmployeePortal/></Shell>}
function Dashboard({title,subtitle,tenant,employee}:{title:string;subtitle:string;tenant?:string;employee?:boolean}){return <div className="dashboard container"><div className="dashboard-title"><div><span className="eyebrow">{tenant?'داشبورد سازمانی':'داشبورد کارمند'}</span><h1>{title}</h1><p>{subtitle}</p></div><button className="button primary">{employee?'درخواست سفر جدید':'تعریف سیاست جدید'}</button></div><section className="metrics"><div><small>{employee?'اعتبار قابل مصرف':'بودجه تخصیص‌یافته'}</small><strong>{employee?'۴۸٬۰۰۰٬۰۰۰':'۳٬۲۰۰٬۰۰۰٬۰۰۰'} <em>ریال</em></strong><span>Mock · منبع server-side در محصول واقعی</span></div><div><small>{employee?'درخواست‌های من':'درخواست‌های در انتظار'}</small><strong>{employee?'۲':'۱۲'}</strong><span>{employee?'۱ نیازمند تأیید':'۶ مورد نزدیک به SLA'}</span></div><div><small>{employee?'سیاست فعال':'مصرف مطابق policy'}</small><strong>{employee?'سفر داخلی':'۹۴٪'}</strong><span>Mock</span></div></section><section className="dashboard-grid"><article className="panel"><div className="panel-head"><h3>{employee?'فعالیت‌های اخیر':'گردش تأیید'}</h3><span className="tag">Mock</span></div>{['اقامت تهران · در انتظار تأیید','تغییر سقف سفرهای داخلی','هتل زندیه · مطابق policy'].map((x,i)=><div className="activity" key={x}><span className={'status s'+i}></span><div><strong>{x}</strong><small>{i===0?'امروز، ۱۰:۲۵':'امروز، ۰۹:۴۰'}</small></div><button>مشاهده</button></div>)}</article><article className="panel"><div className="panel-head"><h3>{employee?'جزئیات اعتبار':'مصرف اعتبار براساس واحد'}</h3><span>Mock</span></div><div className="bar-list">{['فناوری','فروش','عملیات'].map((x,i)=><div key={x}><span>{x}</span><i><b style={{width:`${72-i*18}%`}}/></i><strong>{72-i*18}%</strong></div>)}</div></article></section></div>}
function WhiteLabel(){return <Shell><ServiceIntro title="سایت اختصاصی خدمات سفر" description="برای بررسی همکاری و شرایط خدمات با نام تجاری سازمان خود با ما تماس بگیرید."/><WhiteLabelConfig/></Shell>}
function Integrations(){return <Shell><ServiceIntro title="همکاری با کارن تراول" description="برای معرفی خدمات اقامتی، حمل‌ونقل یا تجربه‌های مقصد با ما تماس بگیرید. آغاز همکاری و عرضهٔ خدمات به بررسی و توافق جداگانه نیاز دارد."/></Shell>}
export default function Page(){
  const pathname=usePathname();
  if(pathname==='/hotels') return <Hotels/>;
  if(pathname==='/compare') return <Compare/>;
  if(pathname==='/assistant') return <Assistant/>;
  if(pathname==='/organization') return <Organization/>;
  if(pathname==='/employee') return <Employee/>;
  if(pathname==='/white-label') return <WhiteLabel/>;
  if(pathname==='/integrations') return <Integrations/>;
  if(pathname==='/agency') return <Shell><AgencyPortal/></Shell>;
  if(pathname==='/notifications') return <Shell><NotificationCenter/></Shell>;
  return <Home/>;
}
