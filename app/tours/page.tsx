import {JourneyShell} from '../../components/journey/JourneyShell';
import {TourList} from '../../components/operational/TravelCommerceViews';
import {Suspense} from 'react';
import {TourCatalog} from '../../components/catalog/CatalogViews';
import {TourCollectionNav} from '../../components/catalog/TourCollections';
import {PadviraServices} from '../../components/catalog/PadviraServices';
import {seoFor} from '../../lib/seo-pages';
import {RelatedLinks} from '../../components/seo/RelatedLinks';
export const metadata = seoFor('/tours');
export default function Page(){return <JourneyShell><main className="journey-main"><TourCollectionNav/><TourList/><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><TourCatalog limit={9} title="برنامهٔ تورها بر اساس مقصد"/></Suspense><PadviraServices group="travel" title="بوت‌کمپ، اردو و سفر تجربه‌محور"/><RelatedLinks group="tours"/></main></JourneyShell>}
