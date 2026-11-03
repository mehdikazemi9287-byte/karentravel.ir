import {PanelShell} from '../../../components/panel/PanelKit';
import {TrainDesk} from '../../../components/panel/TrainRequestsPanel';
export const metadata = {title: 'میز بلیت قطار | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="میز بلیت قطار" intro="درخواست‌ها را بردارید، ظرفیت را در پنل فروش ریلی بررسی کنید و قطارهای موجود را با قیمت بفرستید؛ بعد از پرداخت مشتری، بلیت را در پنل صادر و شماره‌اش را اینجا ثبت کنید."><TrainDesk/></PanelShell>;}
