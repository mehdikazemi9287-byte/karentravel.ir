import {PanelShell} from '../../../components/panel/PanelKit';
import {CustomerPriceChanges} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'تغییر قیمت رزرو', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="تغییر قیمت رزرو" intro="اگر مبلغ رزروی تغییر کند، تا تأیید شما هیچ مبلغی کسر یا پرداخت نمی‌شود."><div className="as"><CustomerPriceChanges/></div></PanelShell>;}
