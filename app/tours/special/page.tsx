import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
export const metadata = {title: 'تورهای ویژه', description: 'تورهای منتخب کارشناسان کارن تراول.'};
export default function Page() {return <JourneyShell><main className="journey-main"><TourCollection collection="special"/></main></JourneyShell>;}
