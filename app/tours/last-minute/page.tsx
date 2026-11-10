import {JourneyShell} from '../../../components/journey/JourneyShell';
import {TourCollection} from '../../../components/catalog/TourCollections';
export const metadata = {title: 'تورهای لحظه‌آخری', description: 'تورهایی که در دو هفته‌ی آینده حرکت می‌کنند و هنوز ظرفیت دارند.'};
export default function Page() {return <JourneyShell><main className="journey-main"><TourCollection collection="last-minute"/></main></JourneyShell>;}
