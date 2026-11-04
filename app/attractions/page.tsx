import {Suspense} from 'react';
import {JourneyShell} from '../../components/journey/JourneyShell';
import {UnifiedSearchView} from '../../components/operational/UnifiedSearchView';
import {LeisureSearch} from '../../components/marketplace/LeisureSearch';
import {PartnerVenues} from '../../components/catalog/PartnerVenues';
export const metadata={title:'جاذبه‌ها و تفریح'};
export default function AttractionsPage(){return <JourneyShell><main className="journey-main dining-marketplace"><h1>جاذبه‌ها و مراکز تفریحی</h1><p>شهر و تاریخ بازدید را انتخاب کن تا جاذبه‌ها و بلیت‌هایشان را ببینی.</p><Suspense fallback={<p role="status">آماده‌سازی جست‌وجوی جاذبه‌ها…</p>}><LeisureSearch service="attraction"/><UnifiedSearchView embedded defaultVertical="attraction"/></Suspense><Suspense fallback={<p role="status">در حال دریافت فهرست…</p>}><PartnerVenues section="attractions" title="جاذبه‌ها، موزه‌ها و مراکز تفریحی"/></Suspense></main></JourneyShell>}
