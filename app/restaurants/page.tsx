import { Suspense } from 'react';
import { Shell } from '../page';
import { UnifiedSearchView } from '../../components/operational/UnifiedSearchView';
export const metadata={title:'رستوران و کافه | کارن‌سیر'};
export default function RestaurantsPage(){return <Shell><div className="ref-container" style={{paddingTop:24}}><h1>رستوران و کافه</h1><p>رزرو میز و مشاهده رستوران و کافه‌های معتبر هر مقصد.</p></div><Suspense fallback={null}><UnifiedSearchView defaultVertical="restaurant"/></Suspense></Shell>}
