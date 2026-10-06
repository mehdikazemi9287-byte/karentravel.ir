import {JourneyShell} from '../../../components/journey/JourneyShell';
import {CatalogAdmin} from '../../../components/catalog/CatalogAdmin';
export const metadata = {title: 'مدیریت هتل‌ها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <JourneyShell><main className="journey-main"><CatalogAdmin/></main></JourneyShell>;}
