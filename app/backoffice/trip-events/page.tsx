import { JourneyShell } from '../../../components/journey/JourneyShell';
import { TripOpsCenter } from '../../../components/operational/TripChangeViews';
export const metadata = {title: 'مرکز عملیات سفر | کارن‌سیر', robots: {index: false}};
export default function Page(){return <JourneyShell><TripOpsCenter/></JourneyShell>}
