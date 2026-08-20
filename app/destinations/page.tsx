import { JourneyShell } from '../../components/journey/JourneyShell';
import { DestinationListView } from '../../components/operational/EcosystemViews';
export const metadata={title:'مقصدهای سفر | کارن‌سیر',description:'کاتالوگ مقصدها و خدمات تازه سفر در کارن‌سیر'};
export default function DestinationsPage(){return <JourneyShell><main className="journey-main"><DestinationListView/></main></JourneyShell>}
