import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencySettlementsPage} from '../../../components/panel/b2b/Settlement';
export const metadata = {title: 'صورت تسویهٔ دوره‌ای', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="صورت تسویهٔ دوره‌ای" intro="صورت‌های صادرشدهٔ مالی؛ تأیید کنید یا روی ردیف اعتراض ثبت کنید. پیش‌نویس‌ها دیده نمی‌شوند."><AgencySettlementsPage/></PanelShell>;}
