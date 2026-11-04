import {PanelShell} from '../../../components/panel/PanelKit';
import {AdminInventory} from '../../../components/panel/InventoryPanel';
export const metadata = {title: 'پرواز و موجودی', robots: {index: false}};
export default function Page() {return <PanelShell area="admin" title="پرواز و موجودی" intro="پرواز چارتری و سیستمی، قرارداد هتل با ظرفیت و نرخ شبانه، مانیفست، تأمین‌کنندگان و مفاد قرارداد."><AdminInventory/></PanelShell>;}
