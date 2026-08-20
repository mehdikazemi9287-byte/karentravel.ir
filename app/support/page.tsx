import Link from 'next/link';
import { JourneyShell, MockNotice } from '../../components/journey/JourneyShell';
import { SupportComposer } from '../../components/operational/CustomerAccount';

const supportPaths=[
  {icon:'✦',title:'دستیار هوشمند',description:'راهنمایی سریع و هوشمند بر اساس سفر شما',cta:'گفت‌وگو با دستیار',href:'/assistant?booking=book1',family:'ai'},
  {icon:'◎',title:'صحبت با کارشناس',description:'برای موارد پیچیده یا نیاز به بررسی',cta:'ارسال درخواست',href:'/support?channel=expert&booking=book1',family:'human'},
  {icon:'▤',title:'پیگیری رزرو',description:'وضعیت رزرو، بلیت و واچر را یک‌جا ببین',cta:'مشاهده سفر من',href:'/trips/mock-shiraz-1405',family:'track'},
  {icon:'↺',title:'تغییر، کنسلی و استرداد',description:'هزینه و نتیجه را پیش از ثبت درخواست ببین',cta:'مدیریت رزرو',href:'/manage-booking/book1',family:'manage'},
  {icon:'!',title:'مشکل در سفر',description:'برای اختلال سفر، واچر یا یک مسئله فوری',cta:'دریافت راهنمایی',href:'/trips/mock-shiraz-1405?support=urgent',family:'urgent'},
];

export default async function SupportPage({searchParams}:{searchParams:Promise<{booking?:string}>}){const {booking}=await searchParams;if(booking&&/^[0-9a-f-]{36}$/i.test(booking))return <JourneyShell><main className="journey-main support-page"><SupportComposer reservationId={booking}/></main></JourneyShell>;return <JourneyShell><main className="journey-main support-page"><div className="journey-title"><div><span>مرکز همراهی کارن‌سیر</span><h1>چطور می‌توانیم کمک کنیم؟</h1><p>متناسب با نوع مسئله، راهنمایی هوشمند یا بررسی کارشناس را انتخاب کن.</p></div><MockNotice/></div><section className="support-disruption" role="status"><div><span>نیازمند توجه</span><h2>تغییری در سفرت پیش آمده؟</h2><p>جزئیات رزرو را ببین و پیش از هر اقدامی، گزینه‌هایت را بررسی کن.</p></div><Link href="/manage-booking/book1">بررسی رزرو</Link></section><section className="support-paths" aria-label="راه‌های دریافت کمک">{supportPaths.map(path=><article className={`support-path support-path-${path.family}`} key={path.title}><i aria-hidden="true">{path.icon}</i><div><h2>{path.title}</h2><p>{path.description}</p></div><Link href={path.href}>{path.cta} ←</Link></article>)}</section></main></JourneyShell>}
