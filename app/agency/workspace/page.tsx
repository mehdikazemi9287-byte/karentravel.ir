import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyWorkspace} from '../../../components/operational/PanelViews';
export const metadata = {title: 'میز کار کامل آژانس | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="میز کار کامل آژانس" intro="همهٔ ابزارهای آژانس در یک صفحه."><AgencyWorkspace/></PanelShell>;}
