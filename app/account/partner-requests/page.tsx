import {PanelShell} from '../../../components/panel/PanelKit';
import {MyPartnerRequests} from '../../../components/panel/PartnerRequestsPanel';
export const metadata = {title: 'درخواست‌های پادویرا و گیفت آسان | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="درخواست‌های پادویرا و گیفت آسان" intro="درخواست‌هایی که از کارن‌سیر برای برنامه‌های پادویرا و سوغات گیفت آسان فرستاده‌اید؛ وضعیت از سایت همان مجموعه خوانده می‌شود."><MyPartnerRequests/></PanelShell>;}
