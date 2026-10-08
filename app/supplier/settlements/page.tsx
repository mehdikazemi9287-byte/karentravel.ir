import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierSettlements} from '../../../components/operational/PanelViews';
export const metadata = {title: 'تسویه و قرارداد | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="تسویه و قرارداد" intro=""><SupplierSettlements/></PanelShell>;}
