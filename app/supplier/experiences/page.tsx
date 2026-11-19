import {PanelShell} from '../../../components/panel/PanelKit';
import {HostExperiencePortal} from '../../../components/supplier/HostExperiencePortal';
export const metadata = {title: 'پورتال تجربه‌ها و کارگاه‌ها', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="تجربه‌ها و کارگاه‌ها" intro="کارگاه‌ها، مسترکلاس‌ها و تجربه‌های بومی خود را مدیریت کنید: سانس‌ها، ظرفیت، ورود مسافران و تسویه."><HostExperiencePortal/></PanelShell>;}
