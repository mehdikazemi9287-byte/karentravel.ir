import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierHotels} from '../../../components/operational/PartnerViews';
export const metadata = {title: 'هتل‌های من | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="هتل‌های من" intro=""><SupplierHotels/></PanelShell>;}
