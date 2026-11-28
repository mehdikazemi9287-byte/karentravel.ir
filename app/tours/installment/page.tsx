import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
import {seoFor} from '../../../lib/seo-pages';
export const metadata = seoFor('/tours/installment');
export default function Page() {return <JourneyShell><main className="journey-main"><TourCollection collection="installment"/></main></JourneyShell>;}
