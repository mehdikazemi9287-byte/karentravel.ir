import {PanelShell} from '../../../components/panel/PanelKit';
import {BankBatches} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'پرداخت گروهی بانکی', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="پرداخت گروهی بانکی" intro="ساخت فایل واریز گروهی برای استردادهای بانکی، با تأیید نفر دوم مالی."><div className="as"><BankBatches/></div></PanelShell>;}
