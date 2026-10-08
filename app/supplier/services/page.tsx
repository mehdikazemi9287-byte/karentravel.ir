import {PanelShell} from '../../../components/panel/PanelKit';
import {SupplierServices} from '../../../components/panel/SupplierPanel';
export const metadata = {title: 'خدمات، نرخ و ظرفیت | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="supplier" title="خدمات، نرخ و ظرفیت" intro="عرضه‌های ثبت‌شده و ابزار ثبت خدمت."><SupplierServices/></PanelShell>;}
