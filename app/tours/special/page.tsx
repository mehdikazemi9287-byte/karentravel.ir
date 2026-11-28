import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
import {seoFor} from '../../../lib/seo-pages';
import {serverTourCollection} from '../../../lib/tour-collections-server';
export const metadata = seoFor('/tours/special');
export default async function Page() {const initial = await serverTourCollection('special'); return <JourneyShell><main className="journey-main"><TourCollection collection="special" initial={initial}/></main></JourneyShell>;}
