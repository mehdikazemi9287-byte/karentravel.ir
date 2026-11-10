import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyInvoicesPage} from '../../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'صورتحساب‌ها', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="صورتحساب‌ها" intro="صورتحساب کمیسیون آژانس با ارزش افزودهٔ کمیسیون."><AgencyInvoicesPage/></PanelShell>;}
