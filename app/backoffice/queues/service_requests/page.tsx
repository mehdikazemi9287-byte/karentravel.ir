import {PanelShell} from '../../../../components/panel/PanelKit';
import {OpsServiceQueue} from '../../../../components/panel/aftersales/OpsAfterSales';
export const metadata = {title: 'صف لغو، تغییر و استرداد', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="صف لغو، تغییر و استرداد" intro="مرتب بر اساس موعد SLA؛ مورد را بردارید و رسیدگی کنید."><OpsServiceQueue queue="service_requests"/></PanelShell>;}
