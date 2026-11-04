import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {HomeSearchExperience} from '../../components/search/HomeSearchExperience';
import {TrainLanding} from '../../components/catalog/CatalogViews';
export const metadata={title:'قطار',description:'خرید بلیط قطار مشهد، اصفهان، تبریز و دیگر شهرها؛ مقایسه‌ی قطارها و پشتیبانی تا پایان سفر.',alternates:{canonical:'/trains'}};
export default function Page(){return <JourneyShell><main className="journey-main flight-entry"><h1>خرید بلیط قطار</h1><p>مبدأ، مقصد و تاریخ سفر را انتخاب کن تا قطارهای موجود را ببینی.</p><Suspense fallback={<p role="status">در حال آماده‌سازی جست‌وجوی قطار…</p>}><HomeSearchExperience defaultVertical="train"/></Suspense><TrainLanding/></main></JourneyShell>}
