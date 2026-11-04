import {PanelShell} from '../../../components/panel/PanelKit';
import {ContractFiles} from '../../../components/panel/OpsConsolePanel';
export const metadata = {title: 'پرونده‌ی قرارداد', robots: {index: false}};
export default async function Page({searchParams}: {searchParams: Promise<{id?: string}>}) {
  const {id} = await searchParams;
  return <PanelShell area="admin" title="پرونده‌ی قرارداد" intro="مسیر پرونده، خدمات با خالص و سود و مالیات، پرداخت‌ها، مسافران، کنسلی و وضعیت سامانه‌ی مؤدیان در یک صفحه."><ContractFiles initialId={id ?? null}/></PanelShell>;
}
