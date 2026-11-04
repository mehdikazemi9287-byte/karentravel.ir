import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierAdmission} from '../../../components/operational/SupplierAdmission';
export const metadata = {title: 'کنترل بلیت و پذیرش', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="کنترل بلیت و پذیرش" intro=""><SupplierAdmission/></PanelShell>;}
