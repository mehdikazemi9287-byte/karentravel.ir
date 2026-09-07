import { Suspense } from 'react';
import { Shell } from '../page';
import { UnifiedSearchView } from '../../components/operational/UnifiedSearchView';
export const metadata={title:'رویداد و تالار | کارن‌سیر'};
export default function EventsVenuesPage(){return <Shell><div className="ref-container" style={{paddingTop:24}}><h1>رویداد و تالار</h1><p>بلیت رویداد و رزرو تالار برای مناسبت‌ها.</p></div><Suspense fallback={null}><UnifiedSearchView defaultVertical="event_hall"/></Suspense></Shell>}
