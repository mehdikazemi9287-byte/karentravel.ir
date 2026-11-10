import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyCreditPage} from '../../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'حساب و اعتبار', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="حساب و اعتبار" intro="مانده و حرکات از دفتر کل داخلی خوانده می‌شود. شارژ فقط پس از تأیید دومرحله‌ای مالی ثبت می‌شود."><AgencyCreditPage/></PanelShell>;}
