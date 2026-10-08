import {PanelShell} from '../../components/panel/PanelKit';
import {SupplierOverview} from '../../components/panel/SupplierPanel';
export const metadata = {title: 'پنل تأمین‌کننده | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="پنل تأمین‌کننده" intro="عرضه‌ها، سفارش‌ها و تسویه."><SupplierOverview/></PanelShell>;}
