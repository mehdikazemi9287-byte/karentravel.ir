import {Suspense} from 'react';
import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCatalog} from '../../../components/catalog/CatalogViews';
import {seoFor} from '../../../lib/seo-pages';
export const metadata = seoFor('/tours/search');
export default function Page(){return <JourneyShell><main className="journey-main"><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><TourCatalog title="جست‌وجوی برنامهٔ تورها"/></Suspense></main></JourneyShell>}
