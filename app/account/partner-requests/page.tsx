import {PanelShell} from '../../../components/panel/PanelKit';
import {MyPartnerRequests} from '../../../components/panel/PartnerRequestsPanel';
export const metadata = {title: 'درخواست‌های خدمات همکار', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="شهرشاد، پادویرا و سوغات" intro="درخواست‌های رزرو مجموعه‌های تفریحی، برنامه‌های پادویرا و سوغات؛ وضعیت و پاسخ هر درخواست همین‌جا نمایش داده می‌شود."><MyPartnerRequests/></PanelShell>;}
