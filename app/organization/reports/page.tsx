import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgReports} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'گزارش | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="گزارش" intro="آمار درخواست‌های سفر سازمان."><OrgReports/></PanelShell>;}
