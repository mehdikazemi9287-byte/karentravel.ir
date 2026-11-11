import {PanelShell} from '../../../components/panel/PanelKit';
import {TaxRates} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'نرخ مالیات تاریخ‌دار', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="نرخ مالیات تاریخ‌دار" intro="نرخ ارزش افزوده بر اساس تاریخ، با مرجع قانونی."><div className="as"><TaxRates/></div></PanelShell>;}
