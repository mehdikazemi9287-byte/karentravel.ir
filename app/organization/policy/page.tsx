import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgPolicy} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'سیاست سفر | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="سیاست سفر" intro="قاعده‌هایی که هر درخواست سفر با آن سنجیده می‌شود."><OrgPolicy/></PanelShell>;}
