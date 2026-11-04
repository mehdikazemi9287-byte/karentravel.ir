import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerWallet} from '../../../components/panel/CustomerPanel';
import {CustomerTreasuryRequests} from '../../../components/panel/CommercePanel';
export const metadata = {title: 'کیف پول و اعتبار', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="کیف پول و اعتبار" intro="موجودی واقعی کیف پول و اعتبار سازمانی."><><CustomerWallet/><CustomerTreasuryRequests/></></PanelShell>;}
