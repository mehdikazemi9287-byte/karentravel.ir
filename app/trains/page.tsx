import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {HomeSearchExperience} from '../../components/search/HomeSearchExperience';
import {RailDirectory} from '../../components/catalog/CatalogViews';
export const metadata={title:'قطار | کارن‌سیر',description:'جست‌وجوی قطار و اطلاعات مرجع شرکت‌ها و ایستگاه‌های راه‌آهن.',alternates:{canonical:'/trains'}};
export default function Page(){return <JourneyShell><main className="journey-main flight-entry"><h1>خرید بلیط قطار</h1><p>مبدأ، مقصد و تاریخ سفر را انتخاب کن تا قطارهای موجود را ببینی.</p><Suspense fallback={<p role="status">در حال آماده‌سازی جست‌وجوی قطار…</p>}><HomeSearchExperience defaultVertical="train"/></Suspense><RailDirectory/></main></JourneyShell>}
