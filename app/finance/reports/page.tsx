import {PanelShell} from '../../../components/panel/PanelKit';
import {SalesReport} from '../../../components/panel/InventoryPanel';
export const metadata = {title: 'گزارش فروش | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="گزارش فروش" intro="فروش به تفکیک خدمت، خریدار و وضعیت."><SalesReport/></PanelShell>;}
