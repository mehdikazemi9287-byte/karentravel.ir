import { JourneyShell } from '../../components/journey/JourneyShell';
import { MapListView } from '../../components/operational/EcosystemViews';
export const metadata={title:'نقشه خدمات سفر',description:'فهرست و محدوده خدمات مقصد در کارن تراول'};
export default function MapPage(){return <JourneyShell><main className="journey-main"><MapListView/></main></JourneyShell>}
