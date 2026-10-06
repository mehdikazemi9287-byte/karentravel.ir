import { JourneyShell } from '../../../components/journey/JourneyShell';
import { SupplierSettlements } from '../../../components/operational/PanelViews';
export const metadata = {title: 'تسویه و قراردادها | کارن‌سیر', robots: {index: false}};
export default function Page(){return <JourneyShell><SupplierSettlements/></JourneyShell>}
