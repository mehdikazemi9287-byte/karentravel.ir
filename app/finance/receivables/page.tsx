import {PanelShell} from '../../../components/panel/PanelKit';
import {Receivables} from '../../../components/panel/ReceivablesPanel';
export const metadata = {title: 'مطالبات سازمان‌ها', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="مطالبات سازمان‌ها" intro="مانده و سن مطالبات هر سازمان بر اساس فاکتورهای واقعی و مهلت پرداخت، با ثبت وصول در دفتر صندوق."><Receivables/></PanelShell>;}
