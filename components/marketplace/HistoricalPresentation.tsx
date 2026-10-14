'use client';
import Link from 'next/link';
import Image from 'next/image';
import {useEffect,useState} from 'react';
import {supportPhone} from '../../lib/site-contact';

/* Figma Ei8MUR9VN2yCX6BLOpvTXm — "KarenSeir Homepage / Desktop 1440" (44:3) and refinement (75:435).
   Layout, palette and photography follow the file; prices, ratings and app badges from the mock are not
   rendered because they are not backed by live data. */

const assistant=(prompt:string)=>'/assistant?prompt='+encodeURIComponent(prompt);
const compareOptions=[['هزینهٔ نهایی','مبلغ کل و خدمات شامل','M4 7h16M4 12h16M4 17h10'],['شرایط تغییر','مهلت کنسلی و هزینهٔ جریمه','M4 12a8 8 0 1 0 3-6.2M4 4v5h5'],['تناسب با سفر','موقعیت و امکانات موردنیاز','M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z']];
const trips=[
 {title:'مسیر سبز شمال',copy:'قدم‌زدن در ماسوله و جنگل‌های گیلان',image:'/images/figma/trip-north.jpeg',slug:'masuleh'},
 {title:'آرامش در جزیره قشم',copy:'سواحل و طبیعت جزیره',image:'/images/figma/trip-qeshm.jpeg',slug:'qeshm'},
 {title:'سه روز در شیراز',copy:'باغ‌ها و معماری شیراز',image:'/images/figma/trip-shiraz.jpeg',slug:'shiraz'},
];
const tiles={
 masuleh:{name:'ماسوله',image:'/images/figma/tile-masuleh.jpeg',alt:'خانه‌های پلکانی ماسوله در دامنهٔ کوه'},
 isfahan:{name:'اصفهان',image:'/images/figma/tile-isfahan.jpeg',alt:'سی‌وسه‌پل اصفهان در شب'},
 shiraz:{name:'شیراز',image:'/images/figma/tile-shiraz.jpeg',alt:'شیشه‌های رنگی مسجد نصیرالملک شیراز'},
 qeshm:{name:'قشم',image:'/images/figma/tile-qeshm.jpeg',alt:'درهٔ ستارگان قشم'},
} as const;
type TileKey=keyof typeof tiles;

function Icon({d,size=20}:{d:string;size?:number}){return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d}/></svg>}
const arrowLeft='M19 12H5M11 6l-6 6 6 6';
function LogoMark(){return <svg className="fh-logo-mark" width="34" height="34" viewBox="0 0 34 34" aria-hidden="true"><path d="M3 27 13 11l6 9 4-5 8 12z" fill="#2a1530"/><circle cx="24" cy="9" r="4" fill="#ef5b3d"/></svg>}
function Brand(){return <Link className="fh-brand" href="/" aria-label="کارن‌سیر، صفحه اصلی"><b>کارن سیر</b><LogoMark/></Link>}

function Tile({k,sizes}:{k:TileKey;sizes:string}){const t=tiles[k];return <Link href={`/destinations/${k}`} className={`fh-tile fh-tile-${k}`}><Image src={t.image} fill sizes={sizes} alt={t.alt}/><b>{t.name}</b></Link>}
function DestinationMosaic(){return <section className="fh-section fh-bento" id="destinations"><div className="fh-wrap"><div className="fh-head"><h2>کجای ایران<br/>صدایت می‌زند؟</h2><Link href="/destinations">همه مقصدها <Icon d={arrowLeft} size={16}/></Link></div><div className="fh-bento-row"><div className="fh-bento-col"><Tile k="masuleh" sizes="(max-width:760px) 100vw, 35vw"/><Tile k="isfahan" sizes="(max-width:760px) 100vw, 35vw"/></div><Tile k="shiraz" sizes="(max-width:760px) 100vw, 31vw"/><Tile k="qeshm" sizes="(max-width:760px) 100vw, 31vw"/></div></div></section>}

function ReferenceTrips(){return <section className="fh-section fh-trips" id="selected-trips"><div className="fh-wrap"><div className="fh-head"><h2 className="fh-h2-sm">سفرهای انتخاب‌شده برای تو</h2></div><div className="fh-trip-row">{trips.map(t=><article className="fh-trip" key={t.slug}><div className="fh-trip-img"><Image src={t.image} fill sizes="(max-width:760px) 88vw, 32vw" alt={t.title}/></div><div className="fh-trip-body"><h3>{t.title}</h3><p>{t.copy}</p><small>راهنمای مقصد؛ قیمت و ظرفیت پس از جست‌وجو و استعلام تأیید می‌شود.</small><footer><span>ایدهٔ سفر</span><Link href={`/destinations/${t.slug}`} aria-label={`مشاهده راهنمای ${t.title}`}><Icon d={arrowLeft} size={16}/></Link></footer></div></article>)}</div></div></section>}

const aiChips:[string,string][]=[
 ['برنامه‌ریزی سفر',assistant('برای سفرم برنامه‌ریزی کنیم')],
 ['مقایسه پرواز، هتل، پرواز + هتل و سایر خدمات','/compare'],
 ['پیشنهاد گزینه‌های مناسب',assistant('برای پیدا کردن گزینه‌های سفر کمک می‌خواهم')],
 ['راهنمایی قبل، حین و بعد از سفر','/trips'],
 ['پیشنهاد مقصد متناسب با بودجه',assistant('با توجه به بودجه‌ام یک مقصد پیشنهاد بده')],
 ['ساخت برنامهٔ سفر','/itineraries'],
];
const prompts=['برای آخر هفته شمال کجا بریم؟','برای ۴ نفر ویلا با استخر پیدا کن','پرواز صبح تهران مشهد و هتل نزدیک حرم می‌خواهم'];
function AssistantSection(){return <section className="fh-ai-wrap" aria-labelledby="fh-ai-title"><div className="fh-wrap"><div className="fh-ai"><div className="fh-ai-content"><span className="fh-eyebrow">دستیار هوشمند سفر</span><h2 id="fh-ai-title">دستیار هوشمند سفر کارن‌سیر</h2><p>مقصد، بودجه و شرایطت را بگو؛ سفرت را هوشمندانه طراحی و مقایسه می‌کنم. قیمت، موجودی و تأیید رزرو فقط از اطلاعات معتبر خدمت اعلام می‌شوند.</p><div className="fh-chips">{aiChips.map(([label,href])=><Link href={href} key={label}><i aria-hidden="true"/>{label}</Link>)}</div><div className="fh-prompts"><span>یا گفت‌وگو را با یکی از این ایده‌ها شروع کن:</span>{prompts.map(p=><Link href={assistant(p)} key={p}>{p}</Link>)}</div><Link className="fh-btn fh-btn-coral" href="/assistant">شروع گفتگو با AI</Link></div><div className="fh-ai-id" aria-hidden="true"><span>AI</span><b>AI</b><p>هوشمندی برای تصمیم بهتر؛<br/>نه جایگزین انتخاب شما</p></div></div></div></section>}

function CompareBand(){return <section className="fh-compare"><div className="fh-wrap"><div className="fh-compare-top"><h2>دو انتخاب داری؟ کنار هم ببین</h2><Link className="fh-btn fh-btn-coral" href="/compare"><Icon d="M7 7h13l-3-3M17 17H4l3 3" size={16}/>مقایسه کن</Link></div><div className="fh-compare-row">{compareOptions.map(x=><div key={x[0]}><i><Icon d={x[2]} size={22}/></i><span><b>{x[0]}</b><small>{x[1]}</small></span></div>)}</div></div></section>}

const orgItems:[string,string,string][]=[
 ['اعتبار کارکنان','/employee','M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.6-6 8-6s8 2 8 6'],
 ['تأیید مرحله‌ای','/organization/requests','M5 12.5l4.5 4.5L19 7.5'],
 ['پیگیری سفرها','/trips','M5 20V10M10 20V5M15 20v-8M20 20V8'],
];
function OrganizationSection(){return <section className="fh-org"><div className="fh-wrap fh-org-grid"><div className="fh-org-text"><h2>سفر سازمانی، بدون پیچیدگی</h2><p>درخواست سفر، سیاست سازمان، گردش تأیید و استعلام گروهی را در یک مسیر پیگیری کنید. اعتبار یا اقساط فقط با احراز شرایط و سیاست مصوب فعال می‌شود.</p><div className="fh-org-items">{orgItems.map(([label,href,d])=><Link href={href} key={label}><i><Icon d={d} size={20}/></i>{label}</Link>)}</div><Link className="fh-btn fh-btn-plum" href="/organization">راهکارهای سازمانی <Icon d="M15 6l-6 6 6 6" size={16}/></Link></div><div className="fh-org-art" aria-hidden="true"><div className="fh-art-screen"><i/><i/><div><span/><span/><span/><span/></div></div><div className="fh-art-tablet"><span/></div><div className="fh-art-plant"/></div></div></section>}

const iconNav:[string,string,string][]=[
 ['خدمات سفر','/services','M4 13a8 8 0 0 1 16 0M4 13v4h3v-5H4M20 13v4h-3v-5h3'],
 ['تور','/tours','M3 20h18M5 20l4-9 3 5 3-8 4 12M9 6h6'],
 ['قطار','/trains','M7 4h10a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM5 11h14M9 14h.01M15 14h.01M8 21l2-4M16 21l-2-4'],
 ['اقامت','/hotels','M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 10h3a1 1 0 0 1 1 1v10M3 21h18M8 7h4M8 11h4M8 15h4'],
 ['پرواز','/flights','M3 13l18-8-6 16-3-7-9-1z'],
];
function ReferenceFooter(){return <footer className="fh-footer"><div className="fh-wrap"><nav className="fh-icon-nav" aria-label="دسترسی سریع خدمات">{iconNav.map(([label,href,d])=><Link href={href} key={label}><Icon d={d} size={22}/>{label}</Link>)}</nav><div className="fh-footer-top"><div><Link className="fh-footer-brand" href="/" aria-label="کارن‌سیر، صفحه اصلی"><b>کارن سیر</b><i aria-hidden="true"/></Link><p>سفر، قصه‌ی ماست. کارن سیر، همراه هر سفر توست.</p><a className="fh-footer-phone" href={supportPhone.href}>پشتیبانی سفر <span dir="ltr">{supportPhone.display}</span></a></div><div className="fh-footer-cta"><b>راهنمایی و استعلام خدمات سفر</b><div><Link href="/contact">تماس با ما</Link><Link href="/support">پشتیبانی</Link></div></div></div><hr/><div className="fh-footer-cols"><div><b>قوانین</b><Link href="/terms">قوانین و مقررات</Link><Link href="/privacy">حریم خصوصی</Link></div><div><b>پشتیبانی</b><Link href="/support">پشتیبانی سفر</Link><Link href="/trips">سفرهای من</Link><Link href="/contact">تماس با ما</Link></div><div><b>کارن سیر</b><Link href="/hotels">هتل و اقامتگاه</Link><Link href="/compare">مقایسه</Link><Link href="/assistant">همراه هوشمند</Link></div><div><b>راهکارها</b><Link href="/organization">سازمانی و رفاهی</Link><Link href="/white-label">وایت‌لیبل</Link><Link href="/integrations">همکاری با تأمین‌کنندگان</Link></div></div><div className="fh-footer-bottom"><span>© ۱۴۰۵ کارن سیر. کلیه حقوق محفوظ است.</span></div></div></footer>}

function FloatingAssistant(){
  const [visible,setVisible]=useState(false);
  useEffect(()=>{
    function check(){const shell=document.querySelector('.fh-search');const clearY=shell?shell.getBoundingClientRect().bottom+window.scrollY:600;setVisible(window.scrollY+window.innerHeight>clearY+40)}
    check();
    window.addEventListener('scroll',check,{passive:true});
    window.addEventListener('resize',check);
    return()=>{window.removeEventListener('scroll',check);window.removeEventListener('resize',check)};
  },[]);
  if(!visible)return null;
  return <Link className="fh-float-ai" href="/assistant" aria-label="بازکردن دستیار هوشمند سفر"><span>AI</span>دستیار AI</Link>;
}

function ReferenceHero(){return <div className="fh-hero-row"><div className="fh-hero-text"><h1>سفر را<br/>زندگی کن</h1><p>از اولین جست‌وجو تا آخرین خاطره،<br/>همه‌چیز در کارن سیر کنار هم است.</p><ul><li><i><Icon d="M5 12.5l4.5 4.5L19 7.5" size={18}/></i><span><b>رزرو</b><small>قابل پیگیری</small></span></li><li><i><Icon d="M4 13a8 8 0 0 1 16 0M4 13v4h3v-5H4M20 13v4h-3v-5h3" size={18}/></i><span><b>پشتیبانی</b><small>کارشناس انسانی</small></span></li></ul></div><div className="fh-hero-img"><Image src="/images/figma/hero-yazd.jpeg" fill priority sizes="(max-width:1100px) 100vw, 46vw" alt="بادگیرهای خشتی یزد زیر آسمان آبی"/><div className="fh-mini"><Link href="/destinations/shiraz"><Icon d={arrowLeft} size={14}/><Image src="/images/figma/mini-shiraz.jpeg" width={48} height={48} alt=""/><b>شیراز</b></Link><Link href="/destinations/kish"><Icon d={arrowLeft} size={14}/><Image src="/images/figma/mini-kish.jpeg" width={48} height={48} alt=""/><b>کیش</b></Link></div></div></div>}

const ecosystem:[string,string,string,string,string][]=[
 ['پرواز، قطار و حمل‌ونقل','جست‌وجوی مسیرهای پرواز، قطار و اتوبوس','/flights','coral','M3 13l18-8-6 16-3-7-9-1z'],
 ['هتل و اقامتگاه','هتل، بوم‌گردی و اقامت متناسب با سفر','/hotels','sky','M3 11l9-8 9 8M5 10v11h14V10M10 21v-7h4v7'],
 ['تور و تجربه','تورها، گشت‌ها و تجربه‌های مقصد','/tours','gold','M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M16 8l-3 6-5 2 2-5z'],
 ['خودرو و ترانسفر','اجاره خودرو و حمل‌ونقل گردشگری','/car-rental','plum','M3 12l3-7h12l3 7v7H3zM3 12h18M6 16h2M16 16h2'],
 ['رستوران و تفریح','رستوران، استخر و تجربه‌های شهری','/restaurants','coral','M5 3v7M9 3v7M5 7h4M7 10v11M18 3c-4 3-4 8 0 9v9M18 3v9'],
 ['راهنمای سفر هوشمند','برنامه‌ریزی سفر با دستیار هوشمند','/assistant','sky','M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z'],
 ['مقایسه قیمت و کیفیت','مقایسهٔ هم‌زمان چند گزینه پیش از خرید','/compare','gold','M7 7h13l-3-3M17 17H4l3 3'],
 ['سفر و رفاه سازمانی','درخواست، سیاست و اعتبار سفر سازمان','/organization','plum','M4 21V7l8-4 8 4v14M9 21v-6h6v6M9 10h.01M15 10h.01'],
];
function HomeServicesHub(){return <section className="fh-section fh-eco" id="home-services"><div className="fh-wrap"><div className="fh-head fh-head-stack"><h2 className="fh-h2-sm">همهٔ سفر، در یک اکوسیستم</h2><p>از برنامه‌ریزی و مقایسه تا رزرو و پشتیبانی؛ وضعیت دسترسی هر خدمت در صفحهٔ خودش روشن است.</p><Link href="/services">مشاهده همه خدمات <Icon d={arrowLeft} size={16}/></Link></div><div className="fh-eco-grid">{ecosystem.map(([title,copy,href,tone,d])=><Link href={href} key={title}><i className={`fh-tone-${tone}`}><Icon d={d} size={22}/></i><b>{title}</b><span>{copy}</span></Link>)}</div></div></section>}

export {Brand, ReferenceHero, HomeServicesHub, DestinationMosaic, ReferenceTrips, AssistantSection, CompareBand, OrganizationSection, ReferenceFooter, FloatingAssistant};
