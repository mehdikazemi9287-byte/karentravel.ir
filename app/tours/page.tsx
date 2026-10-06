import {JourneyShell} from '../../components/journey/JourneyShell';
import {TourList} from '../../components/operational/TravelCommerceViews';
import {Suspense} from 'react';
import {TourCatalog, VenueDirectory} from '../../components/catalog/CatalogViews';
export default function Page(){return <JourneyShell><main className="journey-main"><TourList/><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><TourCatalog limit={6}/><VenueDirectory kinds={['travel_agency']} title="آژانس‌ها و برگزارکنندگان تور ثبت‌شده" intro="فهرست مرجع دفاتر خدمات مسافرتی. برنامه، تاریخ حرکت و قیمت هر تور فقط از برگزارکننده استعلام می‌شود."/></Suspense></main></JourneyShell>}
