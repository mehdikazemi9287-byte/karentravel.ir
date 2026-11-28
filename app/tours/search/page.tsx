import {Suspense} from 'react';
import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCatalog} from '../../../components/catalog/CatalogViews';
import {seoFor} from '../../../lib/seo-pages';
export const metadata = seoFor('/tours/search');
export default function Page(){return <JourneyShell><main className="journey-main"><Suspense fallback={<header className="cat-head"><div><h1>جست‌وجوی برنامهٔ تورها</h1><p role="status">در حال دریافت فهرست…</p></div></header>}><TourCatalog mainHeading title="جست‌وجوی برنامهٔ تورها"/></Suspense></main></JourneyShell>}
