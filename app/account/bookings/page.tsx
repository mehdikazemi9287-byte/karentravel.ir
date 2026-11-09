import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerBookingList} from '../../../components/panel/aftersales/CustomerAfterSales';
export const metadata = {title: 'رزروها و سفرها', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="رزروها و سفرها" intro="پرواز، هتل، تور و سایر خدمات رزروشده."><CustomerBookingList/></PanelShell>;}
