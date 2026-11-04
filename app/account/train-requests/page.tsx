import {PanelShell} from '../../../components/panel/PanelKit';
import {MyTrainRequests} from '../../../components/panel/TrainRequestsPanel';
export const metadata = {title: 'درخواست‌های قطار', robots: {index: false}};
export default function Page() {return <PanelShell area="customer" title="درخواست‌های قطار" intro="پیشنهادهای کارشناس را ببینید، قطار را انتخاب و پرداخت کنید؛ شماره‌ی بلیت بعد از صدور همین‌جا و در سفرهای من نمایش داده می‌شود."><MyTrainRequests/></PanelShell>;}
