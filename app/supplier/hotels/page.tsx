import { JourneyShell } from '../../../components/journey/JourneyShell';
import { SupplierHotels } from '../../../components/operational/PartnerViews';
export const metadata = {title: 'هتل‌های من | کارن‌سیر', robots: {index: false}};
export default function Page(){return <JourneyShell><SupplierHotels/></JourneyShell>}
