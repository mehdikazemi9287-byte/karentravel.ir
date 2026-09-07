import { Suspense } from 'react';
import { Shell } from '../page';
import { UnifiedSearchView } from '../../components/operational/UnifiedSearchView';
export const metadata={title:'استخر و ورزش | کارن‌سیر'};
export default function PoolsSportsPage(){return <Shell><div className="ref-container" style={{paddingTop:24}}><h1>استخر و ورزش</h1><p>رزرو سانس استخر و مراکز ورزشی با بلیت بزرگ‌سال و کودک مجزا.</p></div><Suspense fallback={null}><UnifiedSearchView defaultVertical="pool_sport"/></Suspense></Shell>}
