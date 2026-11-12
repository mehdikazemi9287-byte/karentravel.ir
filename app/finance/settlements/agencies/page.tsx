import {PanelShell} from '../../../../components/panel/PanelKit';
import {FinanceSettlementsPage} from '../../../../components/panel/b2b/Settlement';
export const metadata = {title: 'تسویهٔ دوره‌ای آژانس‌ها', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="تسویهٔ دوره‌ای آژانس‌ها" intro="پیش‌نویس، صدور، اعتراض و تسویه؛ هر اقدام پولی با تأیید کارشناس مالی دوم اعمال می‌شود."><FinanceSettlementsPage/></PanelShell>;}
