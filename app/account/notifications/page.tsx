import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerNotifications} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'اعلان‌ها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="اعلان‌ها" intro="تغییرات رزرو و پیام‌های حساب."><CustomerNotifications/></PanelShell>;}
