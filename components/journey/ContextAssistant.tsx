import Link from 'next/link';
import type { TripEvent } from '../../lib/domain/travel';

export function ContextAssistant({stage,events=[]}:{stage:'before'|'during'|'after'|'nearby';events?:TripEvent[]}){
  const copy={before:['برای سفر شیراز چه چیزی مانده؟','اقامت و ترانسفر هنوز قطعی نیستند. این راهنما از اطلاعات نمونه سفر استفاده می‌کند.'],during:['امشب نزدیک محل اقامت کجا برویم؟','پیشنهادها بر اساس فاصله و دسته توضیح داده می‌شوند.'],after:['رسیدهای سفر را کجا ببینم؟','رزروهای تکمیل‌شده و رسیدهای تأییدشده نمایش داده می‌شوند.'],nearby:['یک رستوران خوب نزدیک من پیدا کن.','منبع مکان، فاصله و رابطه با کارن‌سیر شفاف می‌ماند.']}[stage];
  const verifiedEventCount=events.filter(event=>event.status==='verified').length;
  return <section className="context-assistant"><span>✦ دستیار هوشمند</span><h2>{copy[0]}</h2><p>{copy[1]}</p>{verifiedEventCount>0&&<p className="assistant-event-context">{verifiedEventCount} تغییر تأییدشدهٔ سفر برای جمع‌بندی در دسترس است.</p>}<div className="assistant-why"><b>چرا؟</b><span>مرحله سفر</span><span>مقصد</span><span>اقدام باقی‌مانده</span></div><Link href="/assistant">گفت‌وگوی آزمایشی</Link><small>این مسیر جایگزین پشتیبانی انسانی نیست.</small></section>;
}
