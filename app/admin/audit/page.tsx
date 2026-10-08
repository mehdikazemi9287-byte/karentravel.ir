import {PanelShell} from '../../../components/panel/PanelKit';
import {AdminAudit} from '../../../components/panel/AdminPanel';
export const metadata = {title: 'سوابق ممیزی | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="سوابق ممیزی" intro="رویدادهای ثبت‌شدهٔ همین مجموعه."><AdminAudit/></PanelShell>;}
