import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgMembers} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'کارکنان | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="کارکنان" intro="اعضای سازمان و دسترسی آن‌ها."><OrgMembers/></PanelShell>;}
