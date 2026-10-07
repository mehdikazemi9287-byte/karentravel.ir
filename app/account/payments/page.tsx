import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerPayments} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'پرداخت و فاکتور | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="پرداخت و فاکتور" intro="پرداخت‌ها، فاکتورها و اقساط."><CustomerPayments/></PanelShell>;}
