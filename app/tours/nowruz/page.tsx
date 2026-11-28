import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
import {seoFor} from '../../../lib/seo-pages';
import {serverTourCollection} from '../../../lib/tour-collections-server';
export const metadata = seoFor('/tours/nowruz');
export default async function Page() {const initial = await serverTourCollection('nowruz'); return <JourneyShell><main className="journey-main"><TourCollection collection="nowruz" initial={initial}/></main></JourneyShell>;}
