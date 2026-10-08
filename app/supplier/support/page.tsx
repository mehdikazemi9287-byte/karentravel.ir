import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerSupport} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'پشتیبانی | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="پشتیبانی" intro="پرونده‌های پشتیبانی این حساب."><CustomerSupport/></PanelShell>;}
