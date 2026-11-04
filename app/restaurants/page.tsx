import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {UnifiedSearchView} from '../../components/operational/UnifiedSearchView';
import {DiningSearch} from '../../components/marketplace/DiningSearch';
import {VenueDirectory} from '../../components/catalog/CatalogViews';
export const metadata={title:'رستوران و کافه | کارن‌سیر'};
export default function Page(){return <JourneyShell><main className="journey-main dining-marketplace"><h1>رستوران و کافه</h1><p>شهر و تاریخ را انتخاب کن تا رستوران‌ها و برنامه‌های پذیرایی مقصد را ببینی.</p><Suspense fallback={<p role="status">آماده‌سازی جست‌وجو…</p>}><DiningSearch/><UnifiedSearchView embedded defaultVertical="restaurant"/></Suspense><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><VenueDirectory kinds={['restaurant','cafe']} title="رستوران‌ها و کافه‌های ثبت‌شده"/></Suspense></main></JourneyShell>}
