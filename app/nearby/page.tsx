import Link from 'next/link';
import { Shell } from '../page';
import { ContactOptions } from '../../components/customer/CustomerHelp';
export default function NearbyPage(){return <Shell><section className="container customer-page"><span className="eyebrow">شناخت مقصد</span><h1>اطراف من</h1><p>نمایش مکان‌های نزدیک بر اساس موقعیت شما هنوز فعال نیست. هیچ فاصله یا مکان فرضی به عنوان نتیجهٔ جست‌وجو نمایش داده نمی‌شود.</p><div className="panel"><h2>برای برنامه‌ریزی مقصد ادامه دهید</h2><p>راهنمای مقصدها را ببینید یا برای بررسی خدمات محل اقامتتان با پشتیبانی تماس بگیرید.</p><Link className="button secondary" href="/destinations">راهنمای مقصدها</Link><ContactOptions/></div></section></Shell>}
