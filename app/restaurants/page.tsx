import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {UnifiedSearchView} from '../../components/operational/UnifiedSearchView';
import {DiningSearch} from '../../components/marketplace/DiningSearch';
import {VenueDirectory} from '../../components/catalog/CatalogViews';
export const metadata={title:'رستوران و کافه | کارن‌سیر'};
export default function Page(){return <JourneyShell><main className="journey-main dining-marketplace"><span className="eyebrow">غذا و همراهی در مقصد</span><h1>رستوران و برنامه‌های پذیرایی</h1><p>خدمات ثبت‌شده و زمان‌های پذیرش مقصد را بررسی کن. جزئیات برنامه، شرایط ورود و مبلغ هر انتخاب پیش از رزرو نمایش داده می‌شوند.</p><Suspense fallback={<p role="status">آماده‌سازی جست‌وجو…</p>}><DiningSearch/><UnifiedSearchView embedded defaultVertical="restaurant"/></Suspense><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><VenueDirectory kinds={['restaurant','cafe']} title="رستوران‌ها و کافه‌های ثبت‌شده"/></Suspense></main></JourneyShell>}
