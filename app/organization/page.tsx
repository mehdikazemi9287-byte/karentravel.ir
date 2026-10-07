import {PanelShell} from '../../components/panel/PanelKit';
import {OrgOverview} from '../../components/panel/OrganizationPanel';
export const metadata = {title: 'پنل سازمان | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="پنل سازمان" intro="کارکنان، درخواست‌های سفر و وضعیت سازمان."><OrgOverview/></PanelShell>;}
