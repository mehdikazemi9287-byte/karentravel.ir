import {PanelShell} from '../../../components/panel/PanelKit';
import {MarkupRevenue} from '../../../components/panel/MarkupRevenuePanel';
export const metadata = {title: 'سود و کمیسیون فروش', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="سود و کمیسیون فروش" intro="سود و تخفیفی که قوانین فروش روی هر رزرو اعمال کرده‌اند، به تفکیک خدمت و با سند درآمد در دفتر."><MarkupRevenue/></PanelShell>;}
