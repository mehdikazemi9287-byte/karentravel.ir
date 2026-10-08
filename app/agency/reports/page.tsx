import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyReports} from '../../../components/panel/AgencyPanel';
export const metadata = {title: 'گزارش | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="گزارش" intro="آمار رزرو و فروش آژانس."><AgencyReports/></PanelShell>;}
