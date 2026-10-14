import {PanelShell} from '../../../components/panel/PanelKit';
import {EcosystemFinancialLinks} from '../../../components/panel/EcosystemFinancePanel';
export const metadata = {title: 'روابط مالی اکوسیستم | کارن‌سیر', robots: {index: false}};
export default function Page() {
  return <PanelShell area="admin" title="روابط مالی اکوسیستم" intro="پیگیری مالکیت و اتصال سفارش، قرارداد و پول"><EcosystemFinancialLinks/></PanelShell>;
}
