import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgAudit} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'سوابق و گردش تأیید | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="سوابق و گردش تأیید" intro="چه کسی چه چیزی را چه زمانی تغییر داده است."><OrgAudit/></PanelShell>;}
