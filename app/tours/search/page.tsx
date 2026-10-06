import {Suspense} from 'react';
import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCatalog} from '../../../components/catalog/CatalogViews';
export const metadata={title:'جست‌وجوی تور | کارن‌سیر',description:'برنامهٔ تورها بر اساس مقصد، دسته‌بندی، مدت و سال برگزاری. قیمت و تاریخ جدید با استعلام.'};
export default function Page(){return <JourneyShell><main className="journey-main"><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><TourCatalog title="جست‌وجوی برنامهٔ تورها"/></Suspense></main></JourneyShell>}
