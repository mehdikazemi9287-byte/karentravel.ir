import {PanelShell} from '../../components/panel/PanelKit';
import {AgencyOverview} from '../../components/panel/AgencyPanel';
import {AgencyTodayB2B} from '../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'پنل همکار', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="امروز" intro="کارهای منتظر، وضعیت حساب و فروش آژانس."><AgencyTodayB2B/><AgencyOverview/></PanelShell>;}
