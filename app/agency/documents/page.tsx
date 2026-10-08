import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyDocuments} from '../../../components/panel/AgencyPanel';
export const metadata = {title: 'تسویه و اسناد | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="تسویه و اسناد" intro="تسویه‌های ثبت‌شده برای آژانس."><AgencyDocuments/></PanelShell>;}
