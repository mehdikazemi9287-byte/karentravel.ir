import {PanelShell} from '../../../components/panel/PanelKit';
import {Loyalty} from '../../../components/panel/LoyaltyPanel';
export const metadata = {title: 'حلقه‌ی همسفران | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="حلقه‌ی همسفران" intro="سطح‌ها، امتیاز سفرهای انجام‌شده و کد معرف مشتریان."><Loyalty/></PanelShell>;}
