import {notFound} from 'next/navigation';
import {PanelShell} from '../../../../components/panel/PanelKit';
import {OpsServiceQueue} from '../../../../components/panel/aftersales/OpsAfterSales';
export const metadata = {title: 'صف درخواست‌ها', robots: {index: false}};
const QUEUES = ['service_requests', 'failed_issuance', 'supplier_confirmation', 'schedule_changes', 'documents', 'inventory_review', 'failed_payments'];
export default async function Page({params}: {params: Promise<{queue: string}>}) {
  const {queue} = await params; if (!QUEUES.includes(queue)) notFound();
  return <PanelShell area="admin" title="صف‌های عملیات"><OpsServiceQueue queue={queue}/></PanelShell>;
}
