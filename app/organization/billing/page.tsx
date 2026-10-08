import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgBilling} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'صورتحساب و تسویه | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="صورتحساب و تسویه" intro="فاکتور رزروهای متصل به درخواست‌های سازمان."><OrgBilling/></PanelShell>;}
