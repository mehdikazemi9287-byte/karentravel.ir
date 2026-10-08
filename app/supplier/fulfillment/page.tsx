import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierFulfillment} from '../../../components/operational/SupplierFulfillment';
export const metadata = {title: 'سفارش‌ها و تأیید | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="سفارش‌ها و تأیید" intro=""><SupplierFulfillment/></PanelShell>;}
