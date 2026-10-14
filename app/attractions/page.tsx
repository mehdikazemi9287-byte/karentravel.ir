import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {UnifiedSearchView} from '../../components/operational/UnifiedSearchView';
import {LeisureSearch} from '../../components/marketplace/LeisureSearch';
import {VenueDirectory} from '../../components/catalog/CatalogViews';
export const metadata={title:'جاذبه‌ها و تفریح | کارن‌سیر'};
export default function AttractionsPage(){return <JourneyShell><main className="journey-main dining-marketplace"><span className="eyebrow">دیدنی‌ها و تجربه‌های مقصد</span><h1>جاذبه‌ها و مراکز تفریحی</h1><p>زمان بازدید و بلیت‌های ثبت‌شده را بررسی کن. شرایط ورود و هزینهٔ انتخابت پیش از رزرو مشخص می‌شود.</p><Suspense fallback={<p role="status">آماده‌سازی جست‌وجوی جاذبه‌ها…</p>}><LeisureSearch service="attraction"/><UnifiedSearchView embedded defaultVertical="attraction"/></Suspense><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><VenueDirectory kinds={['attraction','museum','historic']} title="جاذبه‌ها، موزه‌ها و بناهای تاریخی"/></Suspense></main></JourneyShell>}
