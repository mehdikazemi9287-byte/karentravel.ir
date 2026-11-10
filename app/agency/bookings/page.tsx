import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyBookings} from '../../../components/panel/AgencyPanel';
import {AgencyCreditBookings} from '../../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'رزروها', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="رزروها" intro="رزروهای پرداخت‌شده از حساب آژانس و رزروهای ثبت‌شده از کانال فروش آژانس."><AgencyCreditBookings/><AgencyBookings/></PanelShell>;}
