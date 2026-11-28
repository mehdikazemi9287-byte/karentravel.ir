import { JourneyShell } from '../../components/journey/JourneyShell';
import { ItineraryView } from '../../components/operational/EcosystemViews';
import {seoFor} from '../../lib/seo-pages';
export const metadata = seoFor('/itineraries');
export default function ItinerariesPage(){return <JourneyShell><main className="journey-main"><h1>برنامه‌ریز سفر</h1><ItineraryView/></main></JourneyShell>}
