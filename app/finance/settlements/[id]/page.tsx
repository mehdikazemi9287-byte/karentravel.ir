import {PanelShell} from '../../../../components/panel/PanelKit';
import {FinanceSettlementDetailPage} from '../../../../components/panel/b2b/Settlement';
export const metadata = {title: 'صورت تسویهٔ آژانس', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="صورت تسویهٔ آژانس" intro="ردیف‌ها پس از صدور تغییر نمی‌کنند؛ اصلاح فقط با ردیف اصلاحیهٔ تازه و تأیید نفر دوم."><FinanceSettlementDetailPage/></PanelShell>;}
