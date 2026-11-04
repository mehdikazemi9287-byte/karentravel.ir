import { JourneyShell } from '../../components/journey/JourneyShell';
import { MyQuotes } from '../../components/operational/PartnerViews';
export const metadata = {title: 'پیشنهادهای قیمت', robots: {index: false}};
export default function Page(){return <JourneyShell><MyQuotes/></JourneyShell>}
