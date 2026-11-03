import {JourneyShell} from '../../components/journey/JourneyShell';
import {TourList} from '../../components/operational/TravelCommerceViews';
import {Suspense} from 'react';
import {TourCatalog} from '../../components/catalog/CatalogViews';
export default function Page(){return <JourneyShell><main className="journey-main"><TourList/><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><TourCatalog limit={9} title="برنامهٔ تورها بر اساس مقصد"/></Suspense></main></JourneyShell>}
