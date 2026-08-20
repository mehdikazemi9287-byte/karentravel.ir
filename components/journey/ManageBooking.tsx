'use client';

import Link from 'next/link';
import { useState } from 'react';
import type { AfterSalesCaseType, Booking, CancellationQuote, PolicySnapshot, Trip } from '../../lib/domain/travel';
import { StatusBadge } from './Badges';

type MainAction='change'|'cancel'|'problem'|'track';

const requestReasons:Array<[AfterSalesCaseType,string]>=[
  ['voluntary','تغییر به درخواست من'],
  ['provider-disruption','تغییر یا لغو سفر'],
  ['exceptional','شرایط ویژه'],
  ['platform-error','اشکال در فرایند رزرو'],
];

const requestSteps=['درخواست ثبت شد','در حال بررسی','در انتظار پاسخ','نیازمند اقدام شما','تأیید شد','رد شد','در حال بازپرداخت','بازپرداخت انجام شد','بسته شد'];

export function ManageBooking({booking,trip,policyAtBooking}:{booking:Booking;trip:Trip;policyAtBooking:PolicySnapshot;currentPolicy:PolicySnapshot;quote:CancellationQuote}){
  const isStay=booking.type==='accommodation';
  const [action,setAction]=useState<MainAction>('cancel');
  const [caseType,setCaseType]=useState<AfterSalesCaseType>('voluntary');
  const [confirmed,setConfirmed]=useState(false);
  const [submitted,setSubmitted]=useState(false);
  const actionCards:Array<[MainAction,string,string,string]>=[
    ['change','تغییر رزرو',isStay?'تاریخ، اتاق، مهمان یا سایر موارد مجاز':'تاریخ یا سایر موارد مجاز','↻'],
    ['cancel','کنسلی و استرداد','قوانین، جریمه و مبلغ قابل بازگشت را ببین','×'],
    ['problem','مشکل در رزرو','برای واچر، تغییر برنامه یا مشکل سفر','!'],
    ['track','پیگیری درخواست','وضعیت درخواست‌های قبلی','✓'],
  ];
  const actionTitle=action==='cancel'?'اگر الان درخواست کنسلی بدهی':action==='change'?'اگر درخواست تغییر بدهی':action==='problem'?'بررسی مشکل رزرو':'وضعیت درخواست تو';
  const bookingType=isStay?'هتل و اقامت':booking.serviceType==='train'?'قطار':booking.serviceType==='tour'?'تور':'پرواز';
  const confirmationCode=booking.reference.replace('-MOCK','');
  const supplierText=booking.supplierLabel.includes('Mock')||booking.supplierLabel.includes('Provider')?'اطلاعات تأمین‌کننده هنوز تأیید نشده است':booking.supplierLabel;
  const dateLabel=isStay?`${trip.startDate} تا ${trip.endDate}`:trip.startDate;
  const travellerLabel=isStay?`${trip.travellers.length} مهمان`:`${trip.travellers.length} مسافر`;

  function selectAction(next:MainAction){setAction(next);setConfirmed(false);setSubmitted(false);}

  return <>
    <section className="booking-overview" aria-labelledby="manage-booking-title">
      <div className="booking-overview-heading"><span>{bookingType}</span><h1 id="manage-booking-title">مدیریت رزرو سفر</h1><p>رزروت را ببین، نتیجهٔ هر اقدام را بررسی کن و بعد تصمیم بگیر.</p></div>
      <div className="booking-overview-route"><small>{isStay?'اقامت':'مسیر سفر'}</small><h2>{booking.title}</h2><p>{supplierText}</p></div>
      <dl><div><dt>تاریخ</dt><dd>{dateLabel}</dd></div><div><dt>{isStay?'مهمانان':'مسافران'}</dt><dd>{travellerLabel}</dd></div><div><dt>کد تأیید</dt><dd dir="ltr">{confirmationCode}</dd></div><div><dt>وضعیت</dt><dd><StatusBadge status={booking.status}/></dd></div></dl>
      <Link className="voucher-access" href={`/trips/${trip.id}#voucher`}>{isStay?'مشاهده واچر':'مشاهده بلیت / واچر'} ←</Link>
    </section>

    {booking.disruptionStatus&&booking.disruptionStatus!=='none'&&<section className="booking-disruption" role="status"><div><span>نیازمند توجه</span><h2>تغییری در سفرت پیش آمده؟</h2><p>جزئیات این تغییر هنوز باید بررسی شود؛ تا آن زمان رزرو فعلی حفظ می‌شود.</p></div><button type="button" onClick={()=>selectAction('problem')}>بررسی گزینه‌ها</button></section>}

    <section className="manage-action-section" aria-labelledby="manage-actions-title"><header><span>انتخاب اقدام</span><h2 id="manage-actions-title">چه کاری می‌خواهی انجام دهی؟</h2></header><div className="manage-actions">{actionCards.map(item=><button type="button" className={`${action===item[0]?'active ':''}action-${item[0]}`} onClick={()=>selectAction(item[0])} key={item[0]}><i aria-hidden="true">{item[3]}</i><span><b>{item[1]}</b><small>{item[2]}</small></span><em aria-hidden="true">←</em></button>)}</div></section>

    <div className="manage-content-grid"><main>
      {action!=='track'&&<section className="request-reason"><header><span>دلیل درخواست</span><h2>کدام وضعیت به درخواست تو نزدیک‌تر است؟</h2></header><div className="case-types">{requestReasons.map(item=><button type="button" className={caseType===item[0]?'active':''} onClick={()=>setCaseType(item[0])} key={item[0]}>{item[1]}</button>)}</div></section>}

      {action!=='track'&&<section className="consequence-preview" aria-labelledby="consequence-title"><header><span>پیش‌نمایش نتیجه</span><h2 id="consequence-title">{actionTitle}</h2><p>قبل از ثبت درخواست، هزینه و نتیجه را شفاف می‌بینی.</p></header><div className="policy-alert">نیاز به بررسی قوانین تأمین‌کننده</div><div className="consequence-values"><div><small>مبلغ پرداختی</small><b>پس از دریافت اطلاعات معتبر نمایش داده می‌شود</b></div><div><small>جریمه احتمالی</small><b>مبلغ دقیق پس از بررسی نمایش داده می‌شود</b></div><div><small>مبلغ تقریبی قابل بازگشت</small><b>هنوز مشخص نیست</b></div><div><small>روش بازگشت وجه</small><b>پس از بررسی مشخص می‌شود</b></div><div><small>زمان تقریبی بررسی</small><b>پس از ثبت درخواست اعلام می‌شود</b></div></div><div className="booking-rules-note"><b>قوانین زمان ثبت رزرو محفوظ است.</b><span>{policyAtBooking.capturedAt} · تغییرات بعدی بدون اطلاع تو جایگزین نمی‌شود.</span></div><p className="no-change-note">تا قبل از تأیید نهایی، رزرو شما تغییری نمی‌کند.</p><label className="confirmation-check"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/><span>اطلاعات بالا را خواندم و می‌خواهم درخواست برای بررسی ارسال شود.</span></label><button className="confirm-request" type="button" disabled={!confirmed||submitted} onClick={()=>setSubmitted(true)}>{submitted?'درخواست ثبت شد':'تأیید درخواست'}</button>{submitted&&<div className="submitted-note" role="status">✓ درخواست ثبت شد و رزرو فعلی بدون تغییر باقی ماند.</div>}</section>}

      <section className="request-pipeline" id="request-status"><header><span>پیگیری درخواست</span><h2>درخواستت در چه مرحله‌ای است؟</h2><p>هر زمان وضعیت تغییر کند، مرحلهٔ جاری اینجا نمایش داده می‌شود.</p></header><div>{requestSteps.map((step,index)=><article className={index===1?'current':''} key={step}><i>{index===1?'●':index+1}</i><span>{step}</span></article>)}</div></section>
    </main>

    <aside className="manage-guidance">
      <section className="booking-capabilities"><span>{isStay?'راهنمای اقامت':'راهنمای حمل‌ونقل'}</span><h2>{isStay?'امکان‌های این رزرو':'برای این رزرو چه می‌توانی درخواست کنی؟'}</h2>{isStay?<><div className="cancellation-rules"><h3>قوانین کنسلی</h3><article><i>✓</i><span><b>تا مهلت درج‌شده در رزرو</b><small>نیازمند بررسی</small></span></article><article><i>○</i><span><b>نزدیک به زمان ورود</b><small>میزان جریمه پس از بررسی نمایش داده می‌شود</small></span></article><article><i>○</i><span><b>عدم مراجعه</b><small>مطابق قوانین ثبت‌شدهٔ رزرو</small></span></article><p>مبلغ دقیق پس از بررسی تأمین‌کننده نمایش داده می‌شود.</p></div><CapabilityRows items={['تغییر تاریخ','تغییر تعداد شب','تغییر اتاق','تغییر تعداد مهمان','ورود دیرهنگام','خروج زودهنگام']}/></>:<CapabilityRows items={['تغییر تاریخ','کنسلی','تغییر و صدور مجدد','تأخیر یا لغو','عدم حضور در زمان حرکت']}/>}<small className="capability-footnote">امکان نهایی هر مورد براساس قوانین همین رزرو مشخص می‌شود.</small></section>
      <section className="support-choice support-ai-card"><span>✦ دستیار هوشمند</span><h2>{isStay?'هتلم را کنسل کنم چقدر جریمه می‌شود؟':'چقدر پولم برمی‌گردد؟'}</h2><p>راهنمایی سریع و هوشمند بر اساس سفر شما؛ بدون حدس‌زدن مبلغ یا قانون.</p><Link href={`/assistant?intent=refund&booking=${booking.id}`}>پرسیدن از دستیار</Link></section>
      <section className="support-choice support-human-card"><span>صحبت با کارشناس</span><h2>نیاز به بررسی دقیق‌تر داری؟</h2><p>برای موارد پیچیده یا نیاز به بررسی، اطلاعات رزرو همراه درخواست ارسال می‌شود.</p><Link href={`/support?channel=expert&booking=${booking.id}`}>ارسال برای بررسی کارشناس</Link></section>
    </aside></div>

    <nav className="manage-links" aria-label="مسیرهای مرتبط"><Link href={`/trips/${trip.id}`}>بازگشت به سفر من</Link><Link href={`/support?issue=urgent&trip=${trip.id}`}>مشکل در سفر</Link><Link href={`/assistant?intent=rules&booking=${booking.id}`}>قوانین این رزرو چیست؟</Link></nav>
  </>;
}

function CapabilityRows({items}:{items:string[]}){return <div className="capability-rows">{items.map(item=><div key={item}><span>{item}</span><b>نیازمند بررسی</b></div>)}</div>}
