import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
import {seoFor} from '../../../lib/seo-pages';
export const metadata = seoFor('/tours/last-minute');
export default function Page() {return <JourneyShell><main className="journey-main"><TourCollection collection="last-minute"/></main></JourneyShell>;}
