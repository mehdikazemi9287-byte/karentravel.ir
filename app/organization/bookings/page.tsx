import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgBookings} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'رزروهای سازمان | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="رزروهای سازمان" intro="رزروهای متصل به درخواست‌های تأییدشده."><OrgBookings/></PanelShell>;}
