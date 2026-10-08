import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerChanges} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'تغییرات سفر | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="تغییرات سفر" intro="هر تغییری که در سفرهای شما ثبت شده است."><CustomerChanges/></PanelShell>;}
