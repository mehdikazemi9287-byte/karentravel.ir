import { JourneyShell } from '../../../components/journey/JourneyShell';
import { NotificationDeliveries } from '../../../components/operational/PanelViews';
export const metadata = {title: 'وضعیت اعلان‌ها | کارن‌سیر', robots: {index: false}};
export default function Page(){return <JourneyShell><NotificationDeliveries/></JourneyShell>}
