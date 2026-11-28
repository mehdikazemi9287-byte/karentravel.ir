/* Internal links between related public pages, with descriptive Persian anchors (group SEO baseline item 8).
   Server component: plain links in the HTML, no JS. Not used on the protected homepage or search pages. */
import Link from 'next/link';

const LINKS: Record<string, [string, string][]> = {
  flights: [['رزرو هتل در مقصد سفر', '/hotels'], ['خرید بلیط قطار', '/trains'], ['تور داخلی و خارجی', '/tours'], ['ترانسفر فرودگاهی', '/tourist-transport'], ['اخذ ویزای توریستی', '/visa'], ['سؤالات متداول خرید بلیط', '/faq']],
  trains: [['خرید بلیط هواپیما', '/flights'], ['رزرو هتل مشهد و شهرهای دیگر', '/hotels'], ['تور مشهد و تورهای داخلی', '/tours'], ['اجاره خودرو در مقصد', '/car-rental']],
  hotels: [['اجاره ویلا و اقامتگاه بوم‌گردی', '/villas'], ['خرید بلیط هواپیما', '/flights'], ['تور داخلی و خارجی', '/tours'], ['راهنمای مقصدهای سفر', '/destinations'], ['قوانین کنسلی و استرداد', '/terms']],
  tours: [['تور لحظه آخری', '/tours/last-minute'], ['تور نوروزی', '/tours/nowruz'], ['خرید تور اقساطی', '/tours/installment'], ['جست‌وجوی تور بر اساس مقصد', '/tours/search'], ['راهنمای مقصدهای سفر', '/destinations'], ['اخذ ویزا برای تور خارجی', '/visa']],
  destinations: [['تورهای داخلی به این مقصدها', '/tours'], ['رزرو هتل در مقصد', '/hotels'], ['راهنمای سفر به شهرهای ایران', '/travel-guides'], ['مجله سفر کارن تراول', '/blog'], ['تجربه‌های مقصد و گشت محلی', '/experiences'], ['سوغات شهرهای ایران', '/souvenirs']],
  visa: [['خرید بلیط هواپیمای خارجی', '/flights'], ['تورهای خارجی', '/tours'], ['خدمات سفر؛ بیمه و CIP', '/services'], ['پشتیبانی و پیگیری درخواست', '/support']],
};

export function RelatedLinks({group, title = 'صفحه‌های مرتبط'}: {group: keyof typeof LINKS; title?: string}) {
  return <nav aria-label={title} className="container" style={{margin: '32px auto', padding: '0 20px'}}>
    <h2 style={{fontSize: 18, fontWeight: 800, margin: '0 0 10px'}}>{title}</h2>
    <ul style={{display: 'flex', flexWrap: 'wrap', gap: 10, listStyle: 'none', margin: 0, padding: 0}}>
      {LINKS[group].map(([label, href]) => <li key={href}><Link href={href} className="button secondary">{label}</Link></li>)}
    </ul>
  </nav>;
}
