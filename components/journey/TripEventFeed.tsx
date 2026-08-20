import Link from 'next/link';
import type { TripEvent } from '../../lib/domain/travel';

const sourceLabels:Record<TripEvent['source'],string>={
  system:'به‌روزرسانی سفر',
  provider:'اطلاع تأمین‌کننده',
  ai:'جمع‌بندی دستیار هوشمند',
  human_support:'پیام کارشناس',
};

export function TripEventFeed({events,selectedEventId}:{events:TripEvent[];selectedEventId?:string}){
  if(events.length===0)return null;
  return <section className="trip-events" aria-labelledby="trip-events-title">
    <header><div><span>رویدادهای نمونه</span><h2 id="trip-events-title">چه چیزی در سفر من تغییر کرده؟</h2></div><small>تغییرهای مهم در یک مسیر قابل پیگیری</small></header>
    <div>{events.map(event=><article id={event.id} className={`${event.severity==='important'?'important ':''}${event.source==='human_support'?'human-source ':''}${selectedEventId===event.id?'selected':''}`} key={event.id}>
      <i aria-hidden="true">{event.severity==='important'?'!':'✓'}</i>
      <div><span>{sourceLabels[event.source]} · {event.occurredAt}</span><h3>{event.title}</h3><p>{event.message}</p>{event.status==='pending-verification'&&<small>نیازمند بررسی</small>}</div>
      <Link href={event.deepLink??`/trips/${event.tripId}?event=${event.id}`}>{event.requiresAction?'بررسی تغییر':'مشاهده'} ←</Link>
    </article>)}</div>
  </section>;
}
