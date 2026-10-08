import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierRfqs} from '../../../components/panel/SupplierPanel';
export const metadata = {title: 'درخواست‌های سازمانی | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="درخواست‌های سازمانی" intro="درخواست پیشنهاد قیمت از سوی سازمان‌ها."><SupplierRfqs/></PanelShell>;}
