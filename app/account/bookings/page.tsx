import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerBookings} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'رزروها و سفرها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="رزروها و سفرها" intro="پرواز، هتل، تور و سایر خدمات رزروشده."><CustomerBookings/></PanelShell>;}
