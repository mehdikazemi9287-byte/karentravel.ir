import {PanelShell} from '../../../components/panel/PanelKit';
import {FinanceRefundQueue} from '../../../components/panel/aftersales/FinanceAfterSales';
import {AgencyCreditRefundQueue} from '../../../components/panel/b2b/Settlement';
export const metadata = {title: 'صف استرداد', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="صف استرداد" intro="استردادهای تأییدشدهٔ عملیات؛ هر پرداخت را یک نفر آماده و نفر دیگری تأیید می‌کند."><FinanceRefundQueue/><AgencyCreditRefundQueue/></PanelShell>;}
