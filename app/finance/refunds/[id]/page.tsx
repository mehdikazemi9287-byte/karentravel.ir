import {notFound} from 'next/navigation';
import {PanelShell} from '../../../../components/panel/PanelKit';
import {FinanceRefundExecute} from '../../../../components/panel/aftersales/FinanceAfterSales';
export const metadata = {title: 'اجرای استرداد', robots: {index: false}};
export default async function Page({params}: {params: Promise<{id: string}>}) {
  const {id} = await params; if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) notFound();
  return <PanelShell area="admin" title="اجرای استرداد" intro="هر پرداخت دو نفر از مالی لازم دارد."><FinanceRefundExecute id={id}/></PanelShell>;
}
