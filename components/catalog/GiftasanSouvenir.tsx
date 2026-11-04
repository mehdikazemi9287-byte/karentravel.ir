/* Gift Asan (گیفت آسان, sister business) «گیفت سوغات»: the customer names a souvenir from a city and Gift Asan sources,
   packs and delivers it. Requests go to Gift Asan's own WhatsApp line with the same text its site uses; no price here. */
export const GIFTASAN_CITIES = ['تبریز', 'ارومیه', 'اردبیل', 'اصفهان', 'کرج', 'ایلام', 'بوشهر', 'تهران', 'شهرکرد', 'بیرجند', 'بجنورد', 'اهواز', 'زنجان', 'سمنان', 'چابهار', 'شیراز', 'قزوین',
  'قم', 'کاشان', 'سنندج', 'کرمان', 'کرمانشاه', 'یاسوج', 'کیش', 'گرگان', 'رشت', 'خرم‌آباد', 'ساری', 'اراک', 'مشهد', 'قشم', 'همدان', 'یزد'];
const PAGE = 'https://giftasan.com/travel-souvenirs/';
const wa = (city?: string) => `https://wa.me/989939889013?text=${encodeURIComponent(city ? `سلام، برای سوغات ${city} از گیفت‌آسان راهنمایی می‌خواهم.` : 'سلام، برای خرید یا ارسال سوغات از گیفت‌آسان راهنمایی می‌خواهم.\nنام کالا: \nتعداد: \nشهر مقصد: ')}`;

export function GiftasanSouvenir({city}: {city?: string}) {
  const known = city && GIFTASAN_CITIES.includes(city);
  if (city && !known) return null;
  return <section className="gs" aria-labelledby="gs-title">
    <div className="gs-text">
      <h2 id="gs-title">{known ? `سوغات ${city} را بی‌دردسر به خانه بفرست` : 'سوغات هر شهر، تا درِ خانه'}</h2>
      <p>سوغاتی را که می‌خواهی بگو؛ گیفت آسان تهیه، بسته‌بندی و ارسالش را تا درِ خانه یا سازمان هماهنگ می‌کند. قیمت و زمان تحویل را پس از بررسی اعلام می‌کند.</p>
      <div className="gs-actions"><a className="gs-btn" href={wa(known ? city : undefined)} target="_blank" rel="noreferrer">درخواست در واتساپ</a><a className="gs-link" href={PAGE} target="_blank" rel="noreferrer">گیفت سوغات در گیفت آسان ←</a></div>
    </div>
    {!known && <ul className="gs-cities" aria-label="شهرها">{GIFTASAN_CITIES.map(c => <li key={c}><a href={wa(c)} target="_blank" rel="noreferrer">{c}</a></li>)}</ul>}
  </section>;
}
