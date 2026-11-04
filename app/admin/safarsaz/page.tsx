import {PanelShell} from '../../../components/panel/PanelKit';
import {Safarsaz} from '../../../components/panel/SafarsazPanel';
export const metadata = {title: 'سفرساز', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="سفرساز" intro="ساخت تور از منابع مجاز، نرخ هر نوع اتاق و مسافر، حرکت‌ها و ظرفیت، چک‌لیست و انتشار در فهرست تورها."><Safarsaz/></PanelShell>;}
