import {PanelShell} from '../../../components/panel/PanelKit';
import {SlaSettings} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'SLA صف عملیات', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="SLA صف عملیات" intro="زمان هدف هر گام صف لغو، تغییر و استرداد."><div className="as"><SlaSettings/></div></PanelShell>;}
