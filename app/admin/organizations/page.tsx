import {PanelShell} from '../../../components/panel/PanelKit';
import {AdminOrganizations} from '../../../components/panel/AdminPanel';
export const metadata = {title: 'سازمان‌ها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="سازمان‌ها" intro="سازمان‌های مشتری، اعضا و حساب اعتباری."><AdminOrganizations/></PanelShell>;}
