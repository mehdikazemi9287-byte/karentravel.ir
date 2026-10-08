import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierReports} from '../../../components/panel/SupplierPanel';
export const metadata = {title: 'گزارش | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="گزارش" intro="آمار عرضه، تسویه و اتصال."><SupplierReports/></PanelShell>;}
