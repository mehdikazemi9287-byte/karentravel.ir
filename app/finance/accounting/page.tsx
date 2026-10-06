import { JourneyShell } from '../../../components/journey/JourneyShell';
import { FinanceAccounting } from '../../../components/operational/PartnerViews';
export const metadata = {title: 'حسابداری | کارن‌سیر', robots: {index: false}};
export default function Page(){return <JourneyShell><FinanceAccounting/></JourneyShell>}
