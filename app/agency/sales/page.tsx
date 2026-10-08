import {PanelShell} from '../../../components/panel/PanelKit';
import {AgencySales} from '../../../components/panel/AgencyPanel';
export const metadata = {title: 'فروش و پیشنهاد قیمت | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="agency" title="فروش و پیشنهاد قیمت" intro="ساخت پیشنهاد قیمت برای مشتری روی عرضه‌های فعال."><AgencySales/></PanelShell>;}
