import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {HomeSearchExperience} from '../../components/search/HomeSearchExperience';
import {RailDirectory} from '../../components/catalog/CatalogViews';
export const metadata={title:'قطار | کارن‌سیر',description:'جست‌وجوی قطار و اطلاعات مرجع شرکت‌ها و ایستگاه‌های راه‌آهن.',alternates:{canonical:'/trains'}};
export default function Page(){return <JourneyShell><main className="journey-main flight-entry"><span className="eyebrow">سفر ریلی</span><h1>قطار و ایستگاه‌های راه‌آهن</h1><p>مبدأ، مقصد و تاریخ را مشخص کن. ساعت حرکت، نوع واگن و قیمت بلیت فقط از نتیجهٔ جست‌وجو اعلام می‌شود.</p><Suspense fallback={<p role="status">در حال آماده‌سازی جست‌وجوی قطار…</p>}><HomeSearchExperience defaultVertical="train"/></Suspense><RailDirectory/></main></JourneyShell>}
