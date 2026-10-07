import {PanelShell} from '../../components/panel/PanelKit';
import {CustomerOverview} from '../../components/panel/CustomerPanel';
export const metadata = {title: 'حساب من | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="حساب من" intro="رزروها، پرداخت‌ها و پیام‌های شما در یک جا."><CustomerOverview/></PanelShell>;}
