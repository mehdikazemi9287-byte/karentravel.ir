import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerWalletPage} from '../../../components/panel/aftersales/CustomerAfterSales';
import {CustomerTreasuryRequests} from '../../../components/panel/CommercePanel';
import '../../../components/operational/stitch-account-2026-11.css';
export const metadata = {title: 'کیف پول و اعتبار', robots: {index: false}};
/* Stitch _45 (light) / _1 (dark). */
export default function Page() {return <PanelShell area="customer" title="کیف پول و اعتبار" intro="موجودی واقعی کیف پول و تاریخچهٔ تراکنش‌ها."><><CustomerWalletPage/><div id="wallet-treasury" className="sa-anchor"><CustomerTreasuryRequests/></div></></PanelShell>;}
