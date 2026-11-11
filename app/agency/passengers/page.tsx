import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencyPassengers} from '../../../components/panel/phase1/Phase1Rest';
export const metadata = {title: 'مسافران آژانس', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="مسافران آژانس" intro="مسافران ذخیره‌شدهٔ آژانس برای رزرو سریع؛ شماره‌های هویتی در فهرست ماسک می‌شوند."><AgencyPassengers/></PanelShell>;}
