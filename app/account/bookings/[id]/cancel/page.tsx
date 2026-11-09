import {notFound} from 'next/navigation';
import {PanelShell} from '../../../../../components/panel/PanelKit';
import {CancelWizard} from '../../../../../components/panel/aftersales/CustomerAfterSales';
export const metadata = {title: 'درخواست لغو یا تغییر', robots: {index: false}};
export default async function Page({params, searchParams}: {params: Promise<{id: string}>; searchParams: Promise<{type?: string}>}) {
  const {id} = await params; const {type} = await searchParams; if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) notFound();
  return <PanelShell area="customer" title="درخواست لغو یا تغییر" intro="سه گام: نوع درخواست، پیش‌نمایش جریمه از سرور، مقصد وجه و تأیید."><CancelWizard id={id} initialType={type}/></PanelShell>;
}
