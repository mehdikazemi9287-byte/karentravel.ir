import {PanelShell} from '../../../../components/panel/PanelKit';
import {AgencyCharterNoticesPage} from '../../../../components/panel/b2b/Settlement';
export const metadata = {title: 'اطلاعیه‌های تغییر پرواز', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="اطلاعیه‌های تغییر پرواز" intro="تغییر زمان یا لغو پروازهای چارتری که از آن خرید یا سهمیه دارید؛ برای هر رزرو بپذیرید یا استرداد بخواهید."><AgencyCharterNoticesPage/></PanelShell>;}
