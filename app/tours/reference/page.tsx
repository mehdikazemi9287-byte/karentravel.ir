import {Suspense} from 'react';
import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCatalog} from '../../../components/catalog/CatalogViews';
export const metadata={title:'برنامهٔ تورهای برگزارشده | کارن‌سیر',description:'برنامه، مقصد، مدت و خدمات تورهای برگزارشده. قیمت و تاریخ جدید با استعلام.'};
export default function Page(){return <JourneyShell><main className="journey-main"><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><TourCatalog/></Suspense></main></JourneyShell>}
