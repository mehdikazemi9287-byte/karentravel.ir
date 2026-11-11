import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencySellPage} from '../../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'فروش با اعتبار آژانس', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="فروش با اعتبار آژانس" intro="استعلام قیمت، تفکیک مبلغ و رزرو با پرداخت از حساب آژانس."><AgencySellPage/></PanelShell>;}
