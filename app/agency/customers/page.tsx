import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyCustomers} from '../../../components/panel/AgencyPanel';
export const metadata = {title: 'مشتریان | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="مشتریان" intro="مشتریانی که از طریق آژانس رزرو کرده‌اند."><AgencyCustomers/></PanelShell>;}
