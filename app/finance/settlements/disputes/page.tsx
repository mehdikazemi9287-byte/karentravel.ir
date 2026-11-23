import {PanelShell} from '../../../../components/panel/PanelKit';
import {FinanceDisputesPage} from '../../../../components/panel/b2b/Settlement';
export const metadata = {title: 'اعتراض‌های تسویهٔ آژانس', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="اعتراض‌های تسویهٔ آژانس" intro="پذیرش با اصلاحیه (تأیید نفر دوم) یا رد با دلیل."><FinanceDisputesPage/></PanelShell>;}
