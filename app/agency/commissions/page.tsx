import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyCommissions} from '../../../components/panel/AgencyPanel';
export const metadata = {title: 'کمیسیون | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="کمیسیون" intro="دفتر کمیسیون و صورت رزروهای تأییدشده."><AgencyCommissions/></PanelShell>;}
