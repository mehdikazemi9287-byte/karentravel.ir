import {notFound} from 'next/navigation';
import {PanelShell} from '../../../../components/panel/PanelKit';
import {CustomerBookingDetail} from '../../../../components/panel/aftersales/CustomerAfterSales';
export const metadata = {title: 'جزئیات رزرو', robots: {index: false}};
export default async function Page({params}: {params: Promise<{id: string}>}) {
  const {id} = await params; if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) notFound();
  return <PanelShell area="customer" title="جزئیات رزرو" intro="روند رزرو، تفکیک مبلغ و درخواست لغو یا تغییر."><CustomerBookingDetail id={id}/></PanelShell>;
}
