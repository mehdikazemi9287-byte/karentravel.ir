import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyBookings} from '../../../components/panel/AgencyPanel';
export const metadata = {title: 'رزروها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="رزروها" intro="رزروهای ثبت‌شده از کانال فروش آژانس."><AgencyBookings/></PanelShell>;}
