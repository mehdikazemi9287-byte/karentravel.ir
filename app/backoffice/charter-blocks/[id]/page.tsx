import {PanelShell} from '../../../../components/panel/PanelKit';
import {OpsCharterChangePage} from '../../../../components/panel/b2b/Settlement';
export const metadata = {title: 'تغییر برنامهٔ پرواز', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="تغییر برنامهٔ پرواز" intro="تغییر زمان یا لغو پرواز چارتر با پیش‌نمایش اثر؛ اعمال پس از تأیید نفر دوم."><OpsCharterChangePage/></PanelShell>;}
