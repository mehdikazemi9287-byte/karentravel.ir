import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerVisa} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'ویزا | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="ویزا" intro="درخواست‌های ویزا و راهنمای کشورها."><CustomerVisa/></PanelShell>;}
