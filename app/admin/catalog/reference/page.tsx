import {JourneyShell} from '../../../../components/journey/JourneyShell';
import {ReferenceAdmin} from '../../../../components/catalog/ReferenceAdmin';
export const metadata = {title: 'داده‌های مرجع | کارن‌سیر', robots: {index: false}};
export default function Page() {return <JourneyShell><main className="journey-main"><ReferenceAdmin/></main></JourneyShell>;}
