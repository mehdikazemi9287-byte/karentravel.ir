import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
import {seoFor} from '../../../lib/seo-pages';
import {serverTourCollection} from '../../../lib/tour-collections-server';
export const metadata = seoFor('/tours/last-minute');
export default async function Page() {const initial = await serverTourCollection('last-minute'); return <JourneyShell><main className="journey-main"><TourCollection collection="last-minute" initial={initial}/></main></JourneyShell>;}
