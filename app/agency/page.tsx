import {PanelShell} from '../../components/panel/PanelKit';
import {AgencyOverview} from '../../components/panel/AgencyPanel';
export const metadata = {title: 'پنل همکار | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="پنل همکار" intro="فروش، رزروها و حساب آژانس."><AgencyOverview/></PanelShell>;}
