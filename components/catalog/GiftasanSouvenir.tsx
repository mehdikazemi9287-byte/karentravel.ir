'use client';
/* Gift Asan (گیفت آسان, sister business) «گیفت سوغات»: the customer names a souvenir from a city and Gift Asan sources,
   packs and delivers it. The request is sent from KarenSeir (WooCommerce order on Gift Asan) and tracked under حساب من;
   the customer never leaves KarenSeir. No price here: Gift Asan answers with price and delivery time. */
import {useState} from 'react';
import {PartnerRequestForm} from './PartnerRequestForm';

export const GIFTASAN_CITIES = ['تبریز', 'ارومیه', 'اردبیل', 'اصفهان', 'کرج', 'ایلام', 'بوشهر', 'تهران', 'شهرکرد', 'بیرجند', 'بجنورد', 'اهواز', 'زنجان', 'سمنان', 'چابهار', 'شیراز', 'قزوین',
  'قم', 'کاشان', 'سنندج', 'کرمان', 'کرمانشاه', 'یاسوج', 'کیش', 'گرگان', 'رشت', 'خرم‌آباد', 'ساری', 'اراک', 'مشهد', 'قشم', 'همدان', 'یزد'];

export function GiftasanSouvenir({city}: {city?: string}) {
  const known = !!city && GIFTASAN_CITIES.includes(city);
  const [pick, setPick] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  if (city && !known) return null;
  const chosen = known ? city! : pick;
  return <section className="gs" aria-labelledby="gs-title">
    <div className="gs-text">
      <h2 id="gs-title">{known ? `سوغات ${city} را بی‌دردسر به خانه بفرست` : 'سوغات هر شهر، تا درِ خانه'}</h2>
      <p>سوغاتی را که می‌خواهی بگو؛ گیفت آسان تهیه، بسته‌بندی و ارسالش را تا درِ خانه یا سازمان هماهنگ می‌کند و قیمت و زمان تحویل را پس از بررسی اعلام می‌کند. پیگیری در حساب کاربری‌ات در کارن‌سیر است.</p>
      {known && <div className="gs-actions"><button type="button" className="gs-btn gs-primary" onClick={() => setOpen(o => !o)}>ثبت درخواست سوغات</button></div>}
    </div>
    {!known && <ul className="gs-cities" aria-label="شهرها">{GIFTASAN_CITIES.map(c => <li key={c}><button type="button" className={pick === c ? 'on' : ''} onClick={() => {setPick(c); setOpen(true);}}>{c}</button></li>)}</ul>}
    {open && chosen && <PartnerRequestForm key={chosen} partner="giftasan" service={`سوغات ${chosen}`} city={chosen} onClose={() => setOpen(false)}/>}
  </section>;
}
