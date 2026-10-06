import {JourneyShell} from '../../components/journey/JourneyShell';
import {VacationRentalList} from '../../components/operational/TravelCommerceViews';
import {Suspense} from 'react';
import {HotelCatalog} from '../../components/catalog/CatalogViews';
export default function Page(){return <JourneyShell><main className="journey-main stay-marketplace"><VacationRentalList/><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><HotelCatalog presetTypes={['chalet','apartment','guest_house','hostel','resort']} title="ویلا، سوئیت و اقامتگاه‌های ثبت‌شده"/></Suspense></main></JourneyShell>}
