import {notFound} from 'next/navigation';
import {PanelShell} from '../../../../components/panel/PanelKit';
import {OpsRequestHandling} from '../../../../components/panel/aftersales/OpsAfterSales';
export const metadata = {title: 'رسیدگی به درخواست', robots: {index: false}};
export default async function Page({params}: {params: Promise<{id: string}>}) {
  const {id} = await params; if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) notFound();
  return <PanelShell area="admin" title="رسیدگی به درخواست"><OpsRequestHandling id={id}/></PanelShell>;
}
