import {PanelShell} from '../../../components/panel/PanelKit';
import {SalesDesk} from '../../../components/panel/SalesDeskPanel';

export const metadata = {title: 'میز گفتگو و فروش', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="میز گفتگو و فروش" intro="هر درخواست مشتری یک پرونده: ارجاع نوبتی، مهلت پاسخ، پیش‌فاکتور، اتصال به رزرو و پیگیری تا بعد از سفر."><SalesDesk/></PanelShell>;}
