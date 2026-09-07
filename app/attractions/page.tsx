import { Suspense } from 'react';
import { Shell } from '../page';
import { UnifiedSearchView } from '../../components/operational/UnifiedSearchView';
export const metadata={title:'اماکن گردشگری و تفریحی | کارن‌سیر'};
export default function AttractionsPage(){return <Shell><div className="ref-container" style={{paddingTop:24}}><h1>اماکن گردشگری و تفریحی</h1><p>بلیت جاذبه‌ها و مراکز تفریحی هر مقصد.</p></div><Suspense fallback={null}><UnifiedSearchView defaultVertical="attraction"/></Suspense></Shell>}
