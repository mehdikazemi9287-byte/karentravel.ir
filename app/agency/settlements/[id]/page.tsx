import {PanelShell} from '../../../../components/panel/PanelKit';
import {AgencySettlementDetailPage} from '../../../../components/panel/b2b/Settlement';
export const metadata = {title: 'صورت تسویه', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="صورت تسویه" intro="مبالغ سمت سرور محاسبه شده‌اند؛ ارزش افزوده فقط روی کمیسیون است."><AgencySettlementDetailPage/></PanelShell>;}
