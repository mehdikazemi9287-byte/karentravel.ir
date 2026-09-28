import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {UnifiedSearchView} from '../../components/operational/UnifiedSearchView';
import {PoolSearch} from '../../components/marketplace/PoolSearch';
export const metadata={title:'استخر و ورزش | کارن‌سیر'};
export default function PoolsSportsPage(){return <JourneyShell><main className="journey-main dining-marketplace"><span className="eyebrow">تفریح و تندرستی در مقصد</span><h1>استخر و مراکز ورزشی</h1><p>سانس‌های ثبت‌شدهٔ مقصد را پیدا کن؛ زمان، شرایط ورود و هزینهٔ واقعی هر انتخاب در جزئیات نمایش داده می‌شود.</p><Suspense fallback={<p role="status">آماده‌سازی جست‌وجوی سانس‌ها…</p>}><PoolSearch/><UnifiedSearchView embedded defaultVertical="pool_sport"/></Suspense></main></JourneyShell>}
