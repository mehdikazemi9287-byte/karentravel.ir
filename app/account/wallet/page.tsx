import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerWallet} from '../../../components/panel/CustomerPanel';
export const metadata = {title: 'کیف پول و اعتبار | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="کیف پول و اعتبار" intro="موجودی واقعی کیف پول و اعتبار سازمانی."><CustomerWallet/></PanelShell>;}
