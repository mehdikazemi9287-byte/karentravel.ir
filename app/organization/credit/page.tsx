import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgCredit} from '../../../components/panel/OrganizationPanel';
export const metadata = {title: 'اعتبار و اقساط | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="اعتبار و اقساط" intro="اعتبار سازمانی و طرح‌های پرداخت."><OrgCredit/></PanelShell>;}
