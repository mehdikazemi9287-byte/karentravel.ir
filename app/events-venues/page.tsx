import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {UnifiedSearchView} from '../../components/operational/UnifiedSearchView';
import {LeisureSearch} from '../../components/marketplace/LeisureSearch';
export const metadata={title:'رویداد و تالار | کارن‌سیر'};
export default function EventsVenuesPage(){return <JourneyShell><main className="journey-main dining-marketplace"><span className="eyebrow">برنامه‌ها و گردهمایی‌ها</span><h1>رویداد و تالار</h1><p>برای برنامه‌های دارای بلیت، زمان و شرایط ورود را بررسی کن. برای تالار و برنامهٔ اختصاصی، درخواست بررسی انسانی ثبت کن؛ این درخواست رزرو نیست.</p><Suspense fallback={<p role="status">آماده‌سازی جست‌وجوی رویدادها…</p>}><LeisureSearch service="event_hall"/><UnifiedSearchView embedded defaultVertical="event_hall"/></Suspense></main></JourneyShell>}
