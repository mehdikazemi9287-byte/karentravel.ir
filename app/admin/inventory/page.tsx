import {PanelShell} from '../../../components/panel/PanelKit';
import {AdminInventory} from '../../../components/panel/InventoryPanel';
export const metadata = {title: 'پرواز و موجودی | کارن‌سیر', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="پرواز و موجودی" intro="تعریف پرواز چارتری و سیستمی، ظرفیت، توقف فروش، مانیفست، تأمین‌کنندگان و مفاد قرارداد."><AdminInventory/></PanelShell>;}
