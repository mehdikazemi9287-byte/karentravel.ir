import {PanelShell} from '../../../components/panel/PanelKit';
import {OrgPassengers} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'مسافران سازمان', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="مسافران سازمان" intro="مسافران ذخیره‌شدهٔ سازمان برای رزرو سریع؛ شماره‌های هویتی در فهرست ماسک می‌شوند."><div className="as"><OrgPassengers/></div></PanelShell>;}
