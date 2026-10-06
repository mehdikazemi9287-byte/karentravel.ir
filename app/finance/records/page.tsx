import { JourneyShell } from '../../../components/journey/JourneyShell';
import { FinanceRecords } from '../../../components/operational/PanelViews';
export const metadata = {title: 'رکوردهای مالی | کارن‌سیر', robots: {index: false}};
export default function Page(){return <JourneyShell><FinanceRecords/></JourneyShell>}
