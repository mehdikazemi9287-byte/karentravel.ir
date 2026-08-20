import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ContextAssistant } from '../../../components/journey/ContextAssistant';
import { JourneyShell, MockNotice } from '../../../components/journey/JourneyShell';
import { BookingCard, VoucherCard } from '../../../components/journey/TripCards';
import { TripEventFeed } from '../../../components/journey/TripEventFeed';
import { mockTrip, mockTripEvents } from '../../../lib/domain/mock-data';
import type { TripStage } from '../../../lib/domain/travel';

const stageLabels:Record<TripStage,string>={before:'قبل از سفر',during:'حین سفر',after:'بعد از سفر'};

export default async function TripDetailPage({params,searchParams}:{params:Promise<{id:string}>;searchParams:Promise<{stage?:string;support?:string;event?:string}>}){
  const {id}=await params;
  const query=await searchParams;
  if(id!==mockTrip.id)notFound();
  const stage:TripStage=query.stage==='during'||query.stage==='after'?query.stage:'before';
  const items=mockTrip.itinerary.filter(item=>item.stage===stage);

  return <JourneyShell><main className="journey-main">
    <div className="trip-hero"><div><span>تهران <i>←</i> شیراز</span><h1>{mockTrip.title}</h1><p>{mockTrip.startDate} تا {mockTrip.endDate} · {mockTrip.durationLabel} · {mockTrip.travellers.length} مسافر</p></div><MockNotice>رزرو، واچر و مسافران این سفر نمونه و غیرقابل استفاده واقعی‌اند.</MockNotice></div>
    {query.support==='urgent'&&<section className="urgent-panel" role="alert"><div><b>الان کمک می‌خواهم</b><p>اطلاعات سفر و شناسه رزرو آماده است تا همراه درخواست پشتیبانی ارسال شود.</p></div><span>رزرو: KS-MOCK-2841</span><Link href="/assistant?booking=book1">دستیار هوشمند</Link><Link href="/manage-booking/book1">تغییر، کنسلی و استرداد</Link><button type="button">درخواست کارشناس · در نسخه نمایشی غیرفعال</button></section>}
    <TripEventFeed events={mockTripEvents} selectedEventId={query.event}/>
    <nav className="trip-stage-nav" aria-label="مراحل سفر">{(['before','during','after'] as TripStage[]).map(item=><Link className={stage===item?'active':''} href={`/trips/${mockTrip.id}?stage=${item}`} key={item}><span>{item==='before'?'۱':item==='during'?'۲':'۳'}</span>{stageLabels[item]}</Link>)}</nav>
    <div className="trip-context-grid"><section className="trip-timeline"><header><span>{stageLabels[stage]}</span><h2>{stage==='before'?'با خیال راحت آماده شو':stage==='during'?'همه‌چیز در دسترس تو':'سفر را جمع‌بندی کن'}</h2></header>{items.map(item=><article key={item.id} className={`timeline-${item.status}`}><time>{item.dateLabel}</time><div><h3>{item.title}</h3><p>{item.detail.replace('QA','آزمایش').replace('disruption','تغییر').replace('Provider','تأمین‌کننده')}</p></div></article>)}<div className="timeline-actions">{stage==='before'&&<><Link href="/services?destination=shiraz">تکمیل خدمات سفر</Link><Link href="#voucher">مشاهده واچر</Link><Link href="/manage-booking/book1">تغییر، کنسلی و استرداد</Link></>}{stage==='during'&&<><Link href={`/nearby?trip=${mockTrip.id}`}>اطراف من</Link><Link href="#voucher">دسترسی سریع واچر</Link><Link href="/manage-booking/book1">مدیریت رزرو</Link></>}{stage==='after'&&<><button type="button">ثبت بازخورد آزمایشی</button><button type="button">مشاهده رسیدهای نمونه</button></>}</div></section><ContextAssistant stage={stage} events={mockTripEvents}/></div>
    <section className="trip-details-grid"><div><header className="subsection-head"><span>رزروها</span><h2>خلاصه سفارش و اقامت</h2></header><div className="booking-grid">{mockTrip.bookings.map(booking=><BookingCard booking={booking} key={booking.id}/>)}</div><article className="stay-card"><div><span>وضعیت اقامت</span><h3>{mockTrip.accommodation?.name}</h3><p>{mockTrip.accommodation?.address}</p></div><Link href="/services?destination=shiraz">انتخاب اقامت ←</Link></article></div><div><header className="subsection-head"><span>مدارک سفر</span><h2>واچر و مسافران</h2></header><VoucherCard voucher={mockTrip.vouchers[0]}/><div className="traveller-list">{mockTrip.travellers.map(traveller=><div key={traveller.id}><i aria-hidden="true">●</i><span><b>{traveller.fullName}</b><small>{traveller.documentHint.replace('Mock','نمونه')}</small></span></div>)}</div></div></section>
  </main></JourneyShell>;
}
