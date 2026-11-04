import {PanelShell} from '../../../components/panel/PanelKit';
import {JournalExport} from '../../../components/panel/DataExchangePanel';
export const metadata = {title: 'خروجی فرانگر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="خروجی حسابداری (فرانگر)" intro="سند دفتر صندوق با کدینگ حساب‌های خودتان، به‌صورت اکسل یا CSV."><JournalExport/></PanelShell>;}
