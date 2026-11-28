import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
import {seoFor} from '../../../lib/seo-pages';
import {serverTourCollection} from '../../../lib/tour-collections-server';
export const metadata = seoFor('/tours/installment');
export default async function Page() {const initial = await serverTourCollection('installment'); return <JourneyShell><main className="journey-main"><TourCollection collection="installment" initial={initial}/></main></JourneyShell>;}
