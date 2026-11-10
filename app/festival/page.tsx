import {JourneyShell} from '../../components/journey/JourneyShell';
import {TourCollection} from '../../components/catalog/TourCollections';
export const metadata = {title: 'جشنواره‌ی سفر', description: 'تورهای منتخب جشنواره‌ی سفر کارن تراول در بازه‌ی برگزاری جشنواره.'};
export default function Page() {return <JourneyShell><main className="journey-main"><TourCollection collection="festival"/></main></JourneyShell>;}
