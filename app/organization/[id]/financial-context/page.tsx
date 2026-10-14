import {PanelShell} from '../../../../components/panel/PanelKit';
import {EcosystemFinancialLinks} from '../../../../components/panel/EcosystemFinancePanel';
export const metadata = {title: 'تعهد مالی سفر | کارن‌سیر', robots: {index: false}};
export default async function Page({params}: {params: Promise<{id: string}>}) {
  const {id} = await params;
  return <PanelShell area="organization" title="تعهد مالی سفر" intro="درخواست، رزرو و پرداخت سازمان جدا بررسی می‌شوند."><EcosystemFinancialLinks organizationId={id}/></PanelShell>;
}
