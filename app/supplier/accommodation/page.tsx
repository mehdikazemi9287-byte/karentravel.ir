import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierAccommodation} from '../../../components/operational/SupplierAccommodation';
export const metadata = {title: 'اقامتگاه و تقویم | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="اقامتگاه و تقویم" intro=""><SupplierAccommodation/></PanelShell>;}
