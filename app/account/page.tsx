import {PanelShell} from '../../components/panel/PanelKit';
import {CustomerToday} from '../../components/panel/aftersales/CustomerAfterSales';
export const metadata = {title: 'حساب من', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="امروز" intro="سفر بعدی، کارهای منتظر و موجودی کیف پول."><CustomerToday/></PanelShell>;}
