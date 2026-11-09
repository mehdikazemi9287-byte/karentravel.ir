import {PanelShell} from '../../../components/panel/PanelKit';
import {FinanceReconciliation} from '../../../components/panel/aftersales/FinanceAfterSales';
export const metadata = {title: 'تطبیق درگاه', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="تطبیق درگاه" intro="مغایرت‌ها را به پرداخت یا رزرو وصل کنید یا با نوع و دلیل حل کنید؛ همه در سوابق ثبت می‌شود."><FinanceReconciliation/></PanelShell>;}
