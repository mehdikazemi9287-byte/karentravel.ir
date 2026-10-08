import {PanelShell} from '../../../components/panel/PanelKit';
import {PartnersAdmin} from '../../../components/operational/PartnerViews';
export const metadata = {title: 'تأمین‌کنندگان و آژانس‌ها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="تأمین‌کنندگان و آژانس‌ها" intro="عضویت، کانال فروش و حساب اعتباری همکاران."><PartnersAdmin/></PanelShell>;}
