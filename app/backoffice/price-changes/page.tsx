import {PanelShell} from '../../../components/panel/PanelKit';
import {OpsPriceChanges} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'پیشنهاد تغییر قیمت', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="پیشنهاد تغییر قیمت" intro="پیشنهاد عملیات، تأیید مالی و پذیرش مشتری؛ بدون کسر خودکار."><div className="as"><OpsPriceChanges/></div></PanelShell>;}
