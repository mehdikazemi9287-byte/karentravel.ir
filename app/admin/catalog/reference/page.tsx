import {PanelShell} from '../../../../components/panel/PanelKit';
import {ReferenceAdmin} from '../../../../components/catalog/ReferenceAdmin';
export const metadata = {title: 'داده‌های مرجع | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="داده‌های مرجع"><div className="journey-main"><ReferenceAdmin/></div></PanelShell>;}
