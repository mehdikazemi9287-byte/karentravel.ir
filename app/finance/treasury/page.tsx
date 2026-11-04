import {PanelShell} from '../../../components/panel/PanelKit';
import {FinanceTreasury} from '../../../components/panel/CommercePanel';
export const metadata = {title: 'صندوق و حساب‌ها', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="صندوق و حساب‌ها" intro="دفتر صندوق، بدهکار و بستانکار، درخواست‌های واریز و حساب کاربران."><FinanceTreasury/></PanelShell>;}
