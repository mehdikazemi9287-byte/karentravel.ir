import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyCredit} from '../../../components/panel/AgencyPanel';
export const metadata = {title: 'اعتبار و حساب | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="اعتبار و حساب" intro="حساب اعتباری آژانس و گردش آن."><AgencyCredit/></PanelShell>;}
