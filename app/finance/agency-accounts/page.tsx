import {PanelShell} from '../../../components/panel/PanelKit';
import {FinanceAgencyAccounts} from '../../../components/panel/b2b/StaffB2B';
export const metadata = {title: 'حساب و اعتبار آژانس‌ها', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="حساب و اعتبار آژانس‌ها" intro="شارژ، کاهش و تغییر سقف اعتبار آژانس فقط با تأیید نفر دوم مالی اعمال می‌شود."><FinanceAgencyAccounts/></PanelShell>;}
