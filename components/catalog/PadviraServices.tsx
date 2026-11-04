'use client';
import {useState} from 'react';
import {PartnerRequestForm} from './PartnerRequestForm';
/* Services from Padvira (پادویرا دنیا, sister business): request-based programs; time, capacity and cost are set by
   Padvira after reviewing the request, so no price is shown here. Each card opens the request page on padviradonia.com. */
const P = 'https://padviradonia.com';
type S = {title: string; text: string; href: string; tag: string};
export const PADVIRA: Record<'travel' | 'events' | 'organizations' | 'family', S[]> = {
  travel: [
    {title: 'بوت‌کمپ حرکت، طبیعت و خودشناسی', text: 'تجربه‌ی چندروزه برای فاصله از روزمرگی، حرکت آگاهانه و شروعی تازه.', href: `${P}/bootcamps`, tag: 'بوت‌کمپ'},
    {title: 'سفر فرهنگی و تجربه‌ی محلی', text: 'سفر فرهنگی، تجربه‌ی محلی و برنامه‌ی هنری با اجرای شریک دارای مجوز.', href: `${P}/discover/leisure-tourism`, tag: 'گردشگری'},
    {title: 'اردو و اقامت تجربه‌محور', text: 'کمپ ورزشی، اردوی فرهنگی و برنامه‌ی تندرستی برای گروه‌ها.', href: `${P}/services/camps`, tag: 'اردو'},
    {title: 'طبیعت و ورزش', text: 'فعالیت‌های بیرونی، کمپ و گردشگری ورزشی.', href: `${P}/discover/sport`, tag: 'ورزش'},
  ],
  events: [
    {title: 'ازدواج آسان و خدمات مراسم', text: 'تالار، پذیرایی، سفره و دکور، صدا و نور، عکاسی و جهیزیه با ریزهزینه و قرارداد روشن.', href: `${P}/easy-marriage`, tag: 'مراسم'},
    {title: 'همایش، نمایشگاه و کارگروه', text: 'برگزاری کنگره، نمایشگاه و رویداد سازمانی از برنامه تا گزارش نهایی.', href: `${P}/services/camps`, tag: 'همایش'},
    {title: 'مسابقه و رویداد ورزشی', text: 'ثبت‌نام، داوری، جدول، بلیت و رسانه‌ی رویداد ورزشی.', href: `${P}/services/camps`, tag: 'رویداد'},
    {title: 'پیدا کردن تالار و سالن', text: 'شهر، زمان و نیاز رویداد را ثبت کن تا مکان مناسب پیشنهاد شود.', href: `${P}/venues`, tag: 'تالار'},
  ],
  organizations: [
    {title: 'اعزام و میزبانی تیم‌ها', text: 'سفر داخلی و خارجی تیم، دعوت‌نامه، برنامه‌ی بازی و پشتیبانی.', href: `${P}/services/camps`, tag: 'ورزش سازمانی'},
    {title: 'برنامه‌های فرهنگی و ورزشی کارکنان', text: 'طراحی و اجرای برنامه‌های فرهنگی، ورزشی، هنری و آموزشی برای سازمان‌ها.', href: `${P}/services/corporate`, tag: 'سازمانی'},
    {title: 'سلامت و سنجش', text: 'سبک زندگی فعال و ارتباط با متخصصان واجد صلاحیت برای فرد، تیم و سازمان.', href: `${P}/services/health`, tag: 'سلامت'},
  ],
  family: [
    {title: 'برنامه‌های خانواده', text: 'تفریح، تجربه‌ی مشترک و سفر آموزشی برای خانواده.', href: `${P}/for-family`, tag: 'خانواده'},
    {title: 'برنامه‌های کودک و نوجوان', text: 'ورزش، خلاقیت و یادگیری متناسب با سن.', href: `${P}/for-children`, tag: 'کودک'},
    {title: 'صبح حرکت و همراهی', text: 'یک صبح فعال با حرکت گروهی، گفت‌وگو و زمان آزاد.', href: `${P}/programs/morning-movement`, tag: 'برنامه'},
  ],
};

export function PadviraServices({group, title}: {group: keyof typeof PADVIRA; title: string}) {
  const [open, setOpen] = useState<string | null>(null);
  return <section className="pdv" aria-labelledby={`pdv-${group}`}>
    <header className="pv-head"><h2 id={`pdv-${group}`}>{title}</h2><small>با همکاری پادویرا</small></header>
    <div className="pdv-grid">{PADVIRA[group].map(s => <article key={s.title} className="pdv-card">
      <em>{s.tag}</em><b>{s.title}</b><p>{s.text}</p>
      <span className="pdv-actions"><button type="button" onClick={() => setOpen(open === s.title ? null : s.title)}>ثبت درخواست</button><a href={s.href} target="_blank" rel="noreferrer">جزئیات در پادویرا ←</a></span></article>)}</div>
    {PADVIRA[group].filter(s => s.title === open).map(s => <PartnerRequestForm key={s.title} partner="padvira" service={s.title} onClose={() => setOpen(null)}/>)}
    <p className="pv-muted">زمان، ظرفیت و هزینه را پادویرا پس از بررسی درخواست اعلام می‌کند.</p>
  </section>;
}
