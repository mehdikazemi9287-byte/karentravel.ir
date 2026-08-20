import { JourneyShell } from '../../components/journey/JourneyShell';
import { MapListView } from '../../components/operational/EcosystemViews';
export const metadata={title:'نقشه خدمات سفر | کارن‌سیر',description:'فهرست و محدوده خدمات مقصد در کارن‌سیر'};
export default function MapPage(){return <JourneyShell><main className="journey-main"><MapListView/></main></JourneyShell>}
