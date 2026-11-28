import {JourneyShell} from '../../components/journey/JourneyShell';
import {TourCollection} from '../../components/catalog/TourCollections';
import {seoFor} from '../../lib/seo-pages';
import {serverTourCollection} from '../../lib/tour-collections-server';
export const metadata = seoFor('/festival');
export default async function Page() {const initial = await serverTourCollection('festival'); return <JourneyShell><main className="journey-main"><TourCollection collection="festival" initial={initial}/></main></JourneyShell>;}
