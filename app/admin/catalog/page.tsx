import {PanelShell} from '../../../components/panel/PanelKit';
import {CatalogAdmin} from '../../../components/catalog/CatalogAdmin';
export const metadata = {title: 'مدیریت هتل‌ها | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="هتل‌ها"><div className="journey-main"><CatalogAdmin/></div></PanelShell>;}
