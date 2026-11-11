import {PanelShell} from '../../../components/panel/PanelKit';
import {FailedPayments} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'پرداخت‌های ناموفق', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="پرداخت‌های ناموفق" intro="پرداخت‌هایی که درگاه رد کرد یا مشتری رها کرد، با رزرو مربوط."><FailedPayments/></PanelShell>;}
