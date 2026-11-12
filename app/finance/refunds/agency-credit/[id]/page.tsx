import {PanelShell} from '../../../../../components/panel/PanelKit';
import {FinanceAgencyRefundPage} from '../../../../../components/panel/b2b/Settlement';
export const metadata = {title: 'بازگشت به اعتبار آژانس', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="بازگشت به اعتبار آژانس" intro="مبلغ فقط پس از تأیید کارشناس مالی دوم در حساب آژانس ثبت می‌شود."><FinanceAgencyRefundPage/></PanelShell>;}
