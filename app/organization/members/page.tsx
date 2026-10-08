import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgMembers} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'کارکنان و دسترسی‌ها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="کارکنان و دسترسی‌ها" intro="اعضای سازمان و دسترسی مدیریتی هر عضو."><OrgMembers/></PanelShell>;}
