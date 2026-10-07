import {PanelShell} from '../../components/panel/PanelKit';
import {EmployeePortal} from '../../components/operational/EmployeePortal';
export const metadata = {title: 'میز کار کارمند | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="میز کار کارمند" intro="درخواست‌ها و مزایای سازمانی شما."><EmployeePortal/></PanelShell>;}
