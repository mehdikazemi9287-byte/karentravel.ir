import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyUsersPage} from '../../../components/panel/b2b/AgencyB2B';
export const metadata = {title: 'کاربران آژانس', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="کاربران آژانس" intro="نقش هر کاربر در آژانس."><AgencyUsersPage/></PanelShell>;}
