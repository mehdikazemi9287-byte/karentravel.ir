import {PanelShell} from '../../../components/panel/PanelKit';
import {OrganizationFinancialLinks} from '../../../components/panel/EcosystemFinancePanel';
export const metadata = {title: 'تعهد مالی سفر | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="organization" title="تعهد مالی سفر" intro="درخواست، رزرو و پرداخت سازمان جدا بررسی می‌شوند."><OrganizationFinancialLinks/></PanelShell>;}
