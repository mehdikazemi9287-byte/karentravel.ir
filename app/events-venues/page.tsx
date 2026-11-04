import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {UnifiedSearchView} from '../../components/operational/UnifiedSearchView';
import {LeisureSearch} from '../../components/marketplace/LeisureSearch';
import {PartnerVenues} from '../../components/catalog/PartnerVenues';
import {PadviraServices} from '../../components/catalog/PadviraServices';
export const metadata={title:'رویداد و تالار | کارن‌سیر'};
export default function EventsVenuesPage(){return <JourneyShell><main className="journey-main dining-marketplace"><h1>رویداد و تالار</h1><p>بلیت رویدادها را بگیر، یا برای تالار و مراسم اختصاصی درخواست بده تا کارشناس با تو تماس بگیرد.</p><Suspense fallback={<p role="status">آماده‌سازی جست‌وجوی رویدادها…</p>}><LeisureSearch service="event_hall"/><UnifiedSearchView embedded defaultVertical="event_hall"/></Suspense><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><PartnerVenues section="events-venues" title="رویدادها و تالارها"/></Suspense><PadviraServices group="events" title="مراسم، همایش و رویداد اختصاصی"/></main></JourneyShell>}
