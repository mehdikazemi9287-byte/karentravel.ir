import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierInsights} from '../../../components/panel/SupplierInsightsPanel';
export const metadata = {title: 'عملکرد و تطبیق تأمین‌کنندگان | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="عملکرد و تطبیق تأمین‌کنندگان" intro="نرخ کنسلی و خرید هر تأمین‌کننده از رزروهای واقعی، و تطبیق صورت‌حساب آن‌ها با دفتر ما."><SupplierInsights/></PanelShell>;}
