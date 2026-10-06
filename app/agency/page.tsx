import { JourneyShell } from '../../components/journey/JourneyShell';
import { AgencyWorkspace } from '../../components/operational/PanelViews';
export const metadata = {title: 'پنل آژانس | کارن‌سیر', robots: {index: false}};
export default function Page(){return <JourneyShell><AgencyWorkspace/></JourneyShell>}
