import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerWalletPage} from '../../../components/panel/aftersales/CustomerAfterSales';
import {CustomerTreasuryRequests} from '../../../components/panel/CommercePanel';
export const metadata = {title: 'کیف پول و اعتبار', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="کیف پول و اعتبار" intro="موجودی واقعی کیف پول و تاریخچهٔ تراکنش‌ها."><><CustomerWalletPage/><CustomerTreasuryRequests/></></PanelShell>;}
