import {PanelShell} from '../../../components/panel/PanelKit';
import {OpsDashboard} from '../../../components/panel/OpsConsolePanel';
export const metadata = {title: 'پیشخوان عملیات', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="پیشخوان عملیات" intro="آمار امروز، کارهای در انتظار، ۳۰ روز اخیر، پروازهای امروز و هشدارهای داده؛ همه از رکوردهای واقعی همین مجموعه."><OpsDashboard/></PanelShell>;}
