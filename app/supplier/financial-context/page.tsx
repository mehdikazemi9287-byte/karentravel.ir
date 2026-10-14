import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierFinancialLinks} from '../../../components/panel/EcosystemSupplierPanel';
export const metadata = {title: 'روابط مالی قرارداد | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="روابط مالی قرارداد" intro="فقط قراردادها و تسویه همین تأمین‌کننده"><SupplierFinancialLinks/></PanelShell>;}
